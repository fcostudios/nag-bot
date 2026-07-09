"""Command-line entrypoint: serve (scheduler + web), run-once, fetch."""

from __future__ import annotations

import argparse
import logging
import sys

from nagbot import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nagbot", description=__doc__)
    parser.add_argument("--version", action="version", version=f"nagbot {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the scheduler and web dashboard (default)")
    run_once = sub.add_parser("run-once", help="execute a single nag run and exit")
    run_once.add_argument(
        "--live",
        action="store_true",
        help="attempt a live run (config must also have dry-run disabled)",
    )
    fetch = sub.add_parser("fetch", help="fetch open tickets from GLPI and print them")
    fetch.add_argument("--json", action="store_true", help="print tickets as JSON")
    return parser


def _setup_logging() -> None:
    from nagbot.config import EnvSettings

    level = EnvSettings().nagbot_log_level.upper()
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )


def _cmd_fetch(as_json: bool) -> int:
    from nagbot.config import load_config
    from nagbot.glpi.client import GlpiClient
    from nagbot.glpi.fields import FieldMap

    cfg = load_config()
    with GlpiClient(
        cfg.env.glpi_base_url,
        cfg.env.glpi_app_token.get_secret_value(),
        cfg.env.glpi_user_token.get_secret_value(),
        page_size=cfg.app.glpi.page_size,
        server_timezone=cfg.glpi_server_tz,
        web_base=cfg.glpi_web_base,
    ) as client:
        field_map = FieldMap.discover(client, overrides=cfg.app.glpi.field_ids)
        tickets = client.search_open_tickets(field_map)
    if as_json:
        import json

        print(json.dumps([t.model_dump(mode="json") for t in tickets], indent=2))
    else:
        for t in tickets:
            techs = ",".join(t.tech_names) or "-"
            print(f"#{t.id}\t{t.status_label}\t{techs}\t{t.title}")
    print(f"({len(tickets)} open tickets)", file=sys.stderr)
    return 0


def _cmd_run_once(live: bool) -> int:
    from nagbot.run import execute_nag_run
    from nagbot.runtime import build_runtime

    rt = build_runtime()
    # --live is necessary but not sufficient: config (env AND yaml) must also allow it
    dry_run = not live or rt.cfg.dry_run
    if live and rt.cfg.dry_run:
        print(
            "note: --live requested but config forces dry-run "
            "(set NAGBOT_DRY_RUN=false and channels.dry_run: false)",
            file=sys.stderr,
        )
    report = execute_nag_run(
        rt.cfg, rt.store, rt.adapters, rt.glpi_factory, dry_run=dry_run, trigger="manual"
    )
    print(report.summary())
    for send in report.sends:
        print(f"  [{send.status}] {send.channel} -> {send.recipient}  {send.detail}")
    for warning in report.warnings:
        print(f"  warning: {warning}", file=sys.stderr)
    return 0 if report.status == "ok" else 1


def _cmd_serve() -> int:
    from nagbot.web.app import serve

    return serve()


def main(argv: list[str] | None = None) -> int:
    from nagbot.config import ConfigError

    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    _setup_logging()
    try:
        if command == "fetch":
            return _cmd_fetch(as_json=args.json)
        if command == "run-once":
            return _cmd_run_once(live=args.live)
        return _cmd_serve()
    except ConfigError as exc:
        print(f"nagbot: configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
