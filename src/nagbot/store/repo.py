"""The single storage module: every SQL statement in the app lives here.

One Store instance is shared by the scheduler thread and the web thread; a lock
serializes writes (SQLite WAL handles concurrent reads fine).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from nagbot.store.db import connect, migrate


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class RunRow:
    id: int
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    dry_run: bool
    status: str
    tickets_seen: int | None
    digests_built: int | None
    sends_attempted: int | None
    error: str | None
    warnings: list[str]


@dataclass(frozen=True)
class SnapshotRow:
    run_id: int
    ticket_id: int
    title: str
    status: int
    date_opened: datetime | None
    date_mod: datetime | None
    sla_due: datetime | None
    owner_key: str
    owner_name: str
    tier: str
    age_bd: float
    stale_bd: float
    sla_status: str
    snoozed: bool = False


@dataclass(frozen=True)
class SendRow:
    id: int
    run_id: int | None
    kind: str
    channel: str
    recipient: str
    cc: str | None
    owner_key: str | None
    ticket_ids: list[int]
    status: str
    detail: str
    sent_at: datetime


@dataclass(frozen=True)
class SnoozeRow:
    ticket_id: int
    until: date
    reason: str | None
    created_by: str | None
    created_at: datetime


@dataclass(frozen=True)
class EscalationRow:
    ticket_id: int
    consecutive_red_days: int
    first_red_at: datetime | None
    last_red_date: date | None
    escalated_at: datetime | None


@dataclass(frozen=True)
class P0EscalationRow:
    """E7-S3 per-ticket P0 escalation state (single-writer: the escalation engine)."""

    ticket_id: int
    p0_detected_at: datetime
    current_rung: int = 0
    last_notified_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    stopped_reason: str | None = None
    stopped_at: datetime | None = None


def _row_to_p0(d: dict[str, Any]) -> P0EscalationRow:
    def s(key: str) -> str | None:
        v = d.get(key)
        return str(v) if v is not None else None

    return P0EscalationRow(
        ticket_id=int(d["ticket_id"]),
        p0_detected_at=_parse_dt(s("p0_detected_at")) or datetime.now(UTC),
        current_rung=int(d["current_rung"]),
        last_notified_at=_parse_dt(s("last_notified_at")),
        acknowledged_at=_parse_dt(s("acknowledged_at")),
        acknowledged_by=s("acknowledged_by"),
        stopped_reason=s("stopped_reason"),
        stopped_at=_parse_dt(s("stopped_at")),
    )


class Store:
    def __init__(self, path: Path | str) -> None:
        self._conn = connect(path)
        self._lock = threading.Lock()
        migrate(self._conn)

    def close(self) -> None:
        self._conn.close()

    # -- runs ------------------------------------------------------------------

    def start_run(self, *, trigger: str, dry_run: bool, now: datetime) -> int:
        with self._lock, self._conn as conn:
            cur = conn.execute(
                "INSERT INTO runs (started_at, trigger, dry_run) VALUES (?, ?, ?)",
                (_iso(now), trigger, int(dry_run)),
            )
        return int(cur.lastrowid or 0)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        now: datetime,
        tickets_seen: int | None = None,
        digests_built: int | None = None,
        sends_attempted: int | None = None,
        error: str | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        with self._lock, self._conn as conn:
            conn.execute(
                """UPDATE runs SET finished_at=?, status=?, tickets_seen=?,
                   digests_built=?, sends_attempted=?, error=?, warnings=? WHERE id=?""",
                (
                    _iso(now),
                    status,
                    tickets_seen,
                    digests_built,
                    sends_attempted,
                    error,
                    json.dumps(warnings or []),
                    run_id,
                ),
            )

    def recent_runs(self, limit: int = 50) -> list[RunRow]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._run_row(r) for r in rows]

    def last_run(self) -> RunRow | None:
        row = self._conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        return self._run_row(row) if row else None

    @staticmethod
    def _run_row(r: object) -> RunRow:
        d = dict(r)  # type: ignore[call-overload]
        return RunRow(
            id=d["id"],
            started_at=_parse_dt(d["started_at"]) or datetime.now(UTC),
            finished_at=_parse_dt(d["finished_at"]),
            trigger=d["trigger"],
            dry_run=bool(d["dry_run"]),
            status=d["status"],
            tickets_seen=d["tickets_seen"],
            digests_built=d["digests_built"],
            sends_attempted=d["sends_attempted"],
            error=d["error"],
            warnings=json.loads(d.get("warnings") or "[]"),
        )

    # -- snapshots ---------------------------------------------------------------

    def save_snapshots(self, rows: list[SnapshotRow]) -> None:
        with self._lock, self._conn as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO ticket_snapshots
                   (run_id, ticket_id, title, status, date_opened, date_mod, sla_due,
                    owner_key, owner_name, tier, age_bd, stale_bd, sla_status, snoozed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        s.run_id,
                        s.ticket_id,
                        s.title,
                        s.status,
                        _iso(s.date_opened),
                        _iso(s.date_mod),
                        _iso(s.sla_due),
                        s.owner_key,
                        s.owner_name,
                        s.tier,
                        s.age_bd,
                        s.stale_bd,
                        s.sla_status,
                        int(s.snoozed),
                    )
                    for s in rows
                ],
            )

    def latest_snapshot(self) -> tuple[RunRow | None, list[SnapshotRow]]:
        """Snapshots of the most recent run that produced any."""
        row = self._conn.execute(
            """SELECT r.* FROM runs r
               WHERE EXISTS (SELECT 1 FROM ticket_snapshots s WHERE s.run_id = r.id)
               ORDER BY r.id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None, []
        run = self._run_row(row)
        snaps = self._conn.execute(
            "SELECT * FROM ticket_snapshots WHERE run_id=?", (run.id,)
        ).fetchall()
        return run, [self._snapshot_row(s) for s in snaps]

    def ticket_history(self, ticket_id: int, limit: int = 50) -> list[SnapshotRow]:
        rows = self._conn.execute(
            "SELECT * FROM ticket_snapshots WHERE ticket_id=? ORDER BY run_id DESC LIMIT ?",
            (ticket_id, limit),
        ).fetchall()
        return [self._snapshot_row(r) for r in rows]

    @staticmethod
    def _snapshot_row(r: object) -> SnapshotRow:
        d = dict(r)  # type: ignore[call-overload]
        return SnapshotRow(
            run_id=d["run_id"],
            ticket_id=d["ticket_id"],
            title=d["title"] or "",
            status=d["status"] or 0,
            date_opened=_parse_dt(d["date_opened"]),
            date_mod=_parse_dt(d["date_mod"]),
            sla_due=_parse_dt(d["sla_due"]),
            owner_key=d["owner_key"],
            owner_name=d["owner_name"] or "",
            tier=d["tier"],
            age_bd=d["age_bd"] or 0.0,
            stale_bd=d["stale_bd"] or 0.0,
            sla_status=d["sla_status"] or "no_sla",
            snoozed=bool(d["snoozed"]),
        )

    # -- send log ------------------------------------------------------------------

    def log_send(
        self,
        *,
        run_id: int | None,
        kind: str,
        channel: str,
        recipient: str,
        status: str,
        now: datetime,
        cc: str | None = None,
        owner_key: str | None = None,
        ticket_ids: list[int] | None = None,
        detail: str = "",
    ) -> None:
        with self._lock, self._conn as conn:
            conn.execute(
                """INSERT INTO send_log
                   (run_id, kind, channel, recipient, cc, owner_key, ticket_ids,
                    status, detail, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    kind,
                    channel,
                    recipient,
                    cc,
                    owner_key,
                    json.dumps(ticket_ids or []),
                    status,
                    detail,
                    _iso(now),
                ),
            )

    def recent_sends(
        self,
        limit: int = 200,
        *,
        channel: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ) -> list[SendRow]:
        query = "SELECT * FROM send_log"
        clauses, params = [], []
        if channel:
            clauses.append("channel=?")
            params.append(channel)
        if status:
            clauses.append("status=?")
            params.append(status)
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        rows = self._conn.execute(query, (*params, limit)).fetchall()
        return [self._send_row(r) for r in rows]

    def sends_for_ticket(self, ticket_id: int, limit: int = 50) -> list[SendRow]:
        rows = self._conn.execute(
            """SELECT * FROM send_log
               WHERE EXISTS (SELECT 1 FROM json_each(send_log.ticket_ids) WHERE value = ?)
               ORDER BY id DESC LIMIT ?""",
            (ticket_id, limit),
        ).fetchall()
        return [self._send_row(r) for r in rows]

    @staticmethod
    def _send_row(r: object) -> SendRow:
        d = dict(r)  # type: ignore[call-overload]
        return SendRow(
            id=d["id"],
            run_id=d["run_id"],
            kind=d["kind"],
            channel=d["channel"],
            recipient=d["recipient"],
            cc=d["cc"],
            owner_key=d["owner_key"],
            ticket_ids=json.loads(d["ticket_ids"] or "[]"),
            status=d["status"],
            detail=d["detail"] or "",
            sent_at=_parse_dt(d["sent_at"]) or datetime.now(UTC),
        )

    # -- snoozes -----------------------------------------------------------------

    def snooze(
        self,
        ticket_id: int,
        *,
        until: date,
        now: datetime,
        reason: str | None = None,
        created_by: str | None = None,
    ) -> None:
        with self._lock, self._conn as conn:
            conn.execute(
                """INSERT OR REPLACE INTO snoozes
                   (ticket_id, until, reason, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (ticket_id, until.isoformat(), reason, created_by, _iso(now)),
            )

    def unsnooze(self, ticket_id: int) -> None:
        with self._lock, self._conn as conn:
            conn.execute("DELETE FROM snoozes WHERE ticket_id=?", (ticket_id,))

    def active_snoozes(self, now: datetime) -> dict[int, SnoozeRow]:
        """Snoozes still in effect (until >= today in UTC terms; caller passes tz-aware now)."""
        today = now.date().isoformat()
        rows = self._conn.execute(
            "SELECT * FROM snoozes WHERE until >= ?", (today,)
        ).fetchall()
        result: dict[int, SnoozeRow] = {}
        for r in rows:
            d = dict(r)
            result[d["ticket_id"]] = SnoozeRow(
                ticket_id=d["ticket_id"],
                until=date.fromisoformat(d["until"]),
                reason=d["reason"],
                created_by=d["created_by"],
                created_at=_parse_dt(d["created_at"]) or now,
            )
        return result

    def snooze_for(self, ticket_id: int) -> SnoozeRow | None:
        row = self._conn.execute(
            "SELECT * FROM snoozes WHERE ticket_id=?", (ticket_id,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        return SnoozeRow(
            ticket_id=d["ticket_id"],
            until=date.fromisoformat(d["until"]),
            reason=d["reason"],
            created_by=d["created_by"],
            created_at=_parse_dt(d["created_at"]) or datetime.now(UTC),
        )

    # -- escalation streaks ---------------------------------------------------------

    def bump_red_streaks(
        self, red_ids: set[int], *, run_date: date, threshold: int, now: datetime
    ) -> list[int]:
        """Advance 🔴 streaks for this run-day; return ids newly crossing the threshold.

        - one bump per distinct run_date (a same-day manual run never double-counts)
        - tickets no longer red are cleared entirely (streak and escalated_at reset)
        - a ticket already stamped escalated_at is not returned again
        """
        newly_escalated: list[int] = []
        day = run_date.isoformat()
        with self._lock, self._conn as conn:
            if red_ids:
                placeholders = ",".join("?" * len(red_ids))
                conn.execute(
                    f"DELETE FROM escalations WHERE ticket_id NOT IN ({placeholders})",
                    tuple(red_ids),
                )
            else:
                conn.execute("DELETE FROM escalations")
            for tid in sorted(red_ids):
                row = conn.execute(
                    "SELECT consecutive_red_days, last_red_date, escalated_at "
                    "FROM escalations WHERE ticket_id=?",
                    (tid,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """INSERT INTO escalations
                           (ticket_id, consecutive_red_days, first_red_at, last_red_date)
                           VALUES (?, 1, ?, ?)""",
                        (tid, _iso(now), day),
                    )
                    streak, stamped = 1, None
                elif row["last_red_date"] == day:
                    streak, stamped = row["consecutive_red_days"], row["escalated_at"]
                else:
                    streak = row["consecutive_red_days"] + 1
                    stamped = row["escalated_at"]
                    conn.execute(
                        "UPDATE escalations SET consecutive_red_days=?, last_red_date=? "
                        "WHERE ticket_id=?",
                        (streak, day, tid),
                    )
                if streak >= threshold and stamped is None:
                    conn.execute(
                        "UPDATE escalations SET escalated_at=? WHERE ticket_id=?",
                        (_iso(now), tid),
                    )
                    newly_escalated.append(tid)
        return newly_escalated

    def escalations(self) -> list[EscalationRow]:
        rows = self._conn.execute(
            "SELECT * FROM escalations ORDER BY consecutive_red_days DESC"
        ).fetchall()
        return [
            EscalationRow(
                ticket_id=d["ticket_id"],
                consecutive_red_days=d["consecutive_red_days"],
                first_red_at=_parse_dt(d["first_red_at"]),
                last_red_date=date.fromisoformat(d["last_red_date"])
                if d["last_red_date"]
                else None,
                escalated_at=_parse_dt(d["escalated_at"]),
            )
            for d in (dict(r) for r in rows)
        ]

    # -- P0 escalations (E7-S3; single-writer = escalation engine) -------------------

    def active_p0_escalations(self) -> list[P0EscalationRow]:
        # Locked read: this runs on the escalation thread against the connection shared
        # with the digest writer; the lock closes the concurrent-use window.
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM p0_escalations WHERE stopped_at IS NULL ORDER BY p0_detected_at"
            ).fetchall()
        return [_row_to_p0(dict(r)) for r in rows]

    def upsert_p0_escalation(self, row: P0EscalationRow) -> None:
        with self._lock, self._conn as conn:
            conn.execute(
                """INSERT OR REPLACE INTO p0_escalations
                   (ticket_id, p0_detected_at, current_rung, last_notified_at,
                    acknowledged_at, acknowledged_by, stopped_reason, stopped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.ticket_id,
                    _iso(row.p0_detected_at),
                    row.current_rung,
                    _iso(row.last_notified_at),
                    _iso(row.acknowledged_at),
                    row.acknowledged_by,
                    row.stopped_reason,
                    _iso(row.stopped_at),
                ),
            )

    def advance_p0_rung(self, ticket_id: int, *, rung: int, now: datetime) -> None:
        """Targeted rung bump — never touches ack/stop columns (avoids lost updates)."""
        with self._lock, self._conn as conn:
            conn.execute(
                "UPDATE p0_escalations SET current_rung=?, last_notified_at=? WHERE ticket_id=?",
                (rung, _iso(now), ticket_id),
            )

    def stop_p0_escalation(self, ticket_id: int, *, reason: str, now: datetime) -> None:
        with self._lock, self._conn as conn:
            conn.execute(
                "UPDATE p0_escalations SET stopped_reason=?, stopped_at=? WHERE ticket_id=?",
                (reason, _iso(now), ticket_id),
            )

    # -- field cache (implements glpi.fields.CacheBackend) ---------------------------

    def get(self, key: str) -> tuple[str, datetime] | None:
        row = self._conn.execute(
            "SELECT payload, fetched_at FROM field_cache WHERE itemtype=?", (key,)
        ).fetchone()
        if row is None:
            return None
        fetched = _parse_dt(row["fetched_at"])
        return (row["payload"], fetched) if fetched else None

    def put(self, key: str, payload: str, fetched_at: datetime) -> None:
        with self._lock, self._conn as conn:
            conn.execute(
                "INSERT OR REPLACE INTO field_cache (itemtype, payload, fetched_at) "
                "VALUES (?, ?, ?)",
                (key, payload, _iso(fetched_at)),
            )
