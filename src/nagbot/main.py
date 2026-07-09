"""Command-line entrypoint: serve (scheduler + web), run-once, fetch."""

from __future__ import annotations

import argparse
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


def _cmd_fetch(as_json: bool) -> int:
    from nagbot.config import load_config
    from nagbot.glpi.client import GlpiClient
    from nagbot.glpi.fields import FieldMap

    cfg = load_config()
    field_map = FieldMap(cfg.app.glpi.field_ids)
    with GlpiClient(
        cfg.env.glpi_base_url,
        cfg.env.glpi_app_token.get_secret_value(),
        cfg.env.glpi_user_token.get_secret_value(),
        page_size=cfg.app.glpi.page_size,
        server_timezone=cfg.glpi_server_tz,
        web_base=cfg.glpi_web_base,
    ) as client:
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    if command == "fetch":
        return _cmd_fetch(as_json=args.json)
    # Remaining subcommands land in later stories (E2-S6, E3-S1).
    print(f"nagbot {__version__}: '{command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
