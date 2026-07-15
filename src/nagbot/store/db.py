"""SQLite connection + tiny numbered-migration runner (no ORM, no Alembic)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS: list[str] = [
    # 001 — initial schema
    """
    CREATE TABLE runs (
        id INTEGER PRIMARY KEY,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        trigger TEXT NOT NULL,
        dry_run INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        tickets_seen INTEGER,
        digests_built INTEGER,
        sends_attempted INTEGER,
        error TEXT
    );

    CREATE TABLE ticket_snapshots (
        run_id INTEGER NOT NULL REFERENCES runs(id),
        ticket_id INTEGER NOT NULL,
        title TEXT,
        status INTEGER,
        date_opened TEXT,
        date_mod TEXT,
        sla_due TEXT,
        owner_key TEXT NOT NULL,
        owner_name TEXT,
        tier TEXT NOT NULL,
        age_bd REAL,
        stale_bd REAL,
        sla_status TEXT,
        snoozed INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (run_id, ticket_id)
    );
    CREATE INDEX idx_snap_ticket ON ticket_snapshots(ticket_id);

    CREATE TABLE send_log (
        id INTEGER PRIMARY KEY,
        run_id INTEGER REFERENCES runs(id),
        kind TEXT NOT NULL,
        channel TEXT NOT NULL,
        recipient TEXT NOT NULL,
        cc TEXT,
        owner_key TEXT,
        ticket_ids TEXT,
        status TEXT NOT NULL,
        detail TEXT,
        sent_at TEXT NOT NULL
    );

    CREATE TABLE snoozes (
        ticket_id INTEGER PRIMARY KEY,
        until TEXT NOT NULL,
        reason TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE escalations (
        ticket_id INTEGER PRIMARY KEY,
        consecutive_red_days INTEGER NOT NULL DEFAULT 0,
        first_red_at TEXT,
        last_red_date TEXT,
        escalated_at TEXT
    );

    CREATE TABLE field_cache (
        itemtype TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        fetched_at TEXT NOT NULL
    );
    """,
    # 002 — ownership warnings recorded per run (ops dashboard callout)
    """
    ALTER TABLE runs ADD COLUMN warnings TEXT;
    """,
    # 003 — E7: per-ticket P0 escalation state (single-writer: the escalation engine)
    """
    CREATE TABLE p0_escalations (
        ticket_id INTEGER PRIMARY KEY,
        p0_detected_at TEXT NOT NULL,
        current_rung INTEGER NOT NULL DEFAULT 0,
        last_notified_at TEXT,
        acknowledged_at TEXT,
        acknowledged_by TEXT,
        stopped_reason TEXT,
        stopped_at TEXT
    );
    """,
    # 004 — E7-S4: append-only inbound-ack inbox (webhook writes; engine drains)
    """
    CREATE TABLE p0_ack_inbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        text TEXT NOT NULL DEFAULT '',
        received_at TEXT NOT NULL,
        processed_at TEXT
    );
    """,
]


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    for version, sql in enumerate(MIGRATIONS, start=1):
        if version in applied:
            continue
        with conn:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
