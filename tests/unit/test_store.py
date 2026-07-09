from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from nagbot.store.db import connect, migrate
from nagbot.store.repo import SnapshotRow, Store

NOW = datetime(2026, 7, 9, 13, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "test.db")


def snap(run_id: int, ticket_id: int, tier: str = "fresh", **kw: object) -> SnapshotRow:
    defaults: dict[str, object] = {
        "title": f"T{ticket_id}",
        "status": 2,
        "date_opened": NOW - timedelta(days=3),
        "date_mod": NOW - timedelta(days=1),
        "sla_due": None,
        "owner_key": "tech:jdoe",
        "owner_name": "Juan Doe",
        "age_bd": 3.0,
        "stale_bd": 1.0,
        "sla_status": "no_sla",
    }
    defaults.update(kw)
    return SnapshotRow(run_id=run_id, ticket_id=ticket_id, tier=tier, **defaults)  # type: ignore[arg-type]


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "m.db")
    migrate(conn)
    migrate(conn)  # second call must be a no-op
    versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert versions == [1]


def test_run_lifecycle(store: Store) -> None:
    run_id = store.start_run(trigger="cron", dry_run=True, now=NOW)
    store.finish_run(
        run_id, status="ok", now=NOW + timedelta(minutes=1), tickets_seen=5,
        digests_built=2, sends_attempted=2,
    )
    run = store.last_run()
    assert run is not None
    assert (run.status, run.dry_run, run.tickets_seen) == ("ok", True, 5)
    assert run.finished_at is not None


def test_snapshots_and_latest(store: Store) -> None:
    r1 = store.start_run(trigger="cron", dry_run=True, now=NOW)
    store.save_snapshots([snap(r1, 1), snap(r1, 2, tier="on_fire")])
    r2 = store.start_run(trigger="manual", dry_run=True, now=NOW + timedelta(hours=1))
    store.save_snapshots([snap(r2, 1, tier="hot")])
    run, snaps = store.latest_snapshot()
    assert run is not None and run.id == r2
    assert [s.tier for s in snaps] == ["hot"]
    # runs without snapshots don't win latest_snapshot
    store.start_run(trigger="manual", dry_run=True, now=NOW + timedelta(hours=2))
    run2, _ = store.latest_snapshot()
    assert run2 is not None and run2.id == r2
    assert [s.run_id for s in store.ticket_history(1)] == [r2, r1]


def test_send_log_filters_and_ticket_lookup(store: Store) -> None:
    rid = store.start_run(trigger="cron", dry_run=False, now=NOW)
    store.log_send(
        run_id=rid, kind="digest", channel="email", recipient="a@x.com",
        status="sent", now=NOW, ticket_ids=[1, 2],
    )
    store.log_send(
        run_id=rid, kind="digest", channel="teams", recipient="a@x.com",
        status="skipped", now=NOW, ticket_ids=[2, 3],
    )
    assert len(store.recent_sends()) == 2
    assert [s.channel for s in store.recent_sends(channel="email")] == ["email"]
    assert [s.status for s in store.recent_sends(status="skipped")] == ["skipped"]
    hits = store.sends_for_ticket(2)
    assert len(hits) == 2
    assert store.sends_for_ticket(1)[0].ticket_ids == [1, 2]
    assert store.sends_for_ticket(99) == []


def test_snooze_roundtrip_and_expiry(store: Store) -> None:
    store.snooze(7, until=date(2026, 7, 10), now=NOW, reason="waiting on vendor")
    assert 7 in store.active_snoozes(NOW)
    # replace: snoozing again overwrites
    store.snooze(7, until=date(2026, 7, 20), now=NOW)
    row = store.snooze_for(7)
    assert row is not None and row.until == date(2026, 7, 20)
    # expired: until < today
    assert 7 not in store.active_snoozes(datetime(2026, 7, 21, tzinfo=UTC))
    store.unsnooze(7)
    assert store.snooze_for(7) is None


def test_red_streaks_escalate_once_and_reset(store: Store) -> None:
    d1, d2, d3, d4 = (date(2026, 7, 6 + i) for i in range(4))
    assert store.bump_red_streaks({1}, run_date=d1, threshold=3, now=NOW) == []
    # same-day second run must not double-bump
    assert store.bump_red_streaks({1}, run_date=d1, threshold=3, now=NOW) == []
    assert store.bump_red_streaks({1}, run_date=d2, threshold=3, now=NOW) == []
    # third distinct run-day crosses threshold -> escalate exactly once
    assert store.bump_red_streaks({1}, run_date=d3, threshold=3, now=NOW) == [1]
    assert store.bump_red_streaks({1}, run_date=d4, threshold=3, now=NOW) == []
    # leaving red clears the row; re-streaking can escalate again
    store.bump_red_streaks(set(), run_date=d4, threshold=3, now=NOW)
    assert store.escalations() == []
    for i, d in enumerate((d1, d2, d3)):
        expected = [1] if i == 2 else []
        assert store.bump_red_streaks({1}, run_date=d, threshold=3, now=NOW) == expected


def test_field_cache_backend(store: Store) -> None:
    assert store.get("Ticket") is None
    store.put("Ticket", '{"1": {}}', NOW)
    hit = store.get("Ticket")
    assert hit is not None
    assert hit[0] == '{"1": {}}'
    assert hit[1] == NOW
