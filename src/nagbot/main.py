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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    # Subcommand implementations land in later stories (E1-S3, E2-S6, E3-S1).
    print(f"nagbot {__version__}: '{command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
