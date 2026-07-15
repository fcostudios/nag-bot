"""READ-ONLY GLPI probe for E7-S2: discover the P0-relevant fields (priority /
urgency / impact / category) and sample their real values on open tickets.

Reads GLPI creds from .env (never printed). Makes only GET calls (listSearchOptions
+ search). No writes, no session side effects beyond init/kill.

Run:  python scripts/probe_glpi_p0_fields.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# load env file: argv[1] if given, else the repo-root .env
env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import httpx  # noqa: E402

BASE = os.environ["GLPI_BASE_URL"].rstrip("/")
APP = os.environ["GLPI_APP_TOKEN"]
USER = os.environ["GLPI_USER_TOKEN"]

INTERESTING = ("priority", "urgency", "impact", "category", "itilcategor", "type", "status")

with httpx.Client(timeout=30, verify=True) as c:
    r = c.post(f"{BASE}/initSession", headers={"App-Token": APP, "Authorization": f"user_token {USER}"})
    r.raise_for_status()
    session = r.json()["session_token"]
    h = {"App-Token": APP, "Session-Token": session}
    try:
        # 1) field map — which search-option IDs are priority/urgency/impact/category
        opts = c.get(f"{BASE}/listSearchOptions/Ticket", headers=h).json()
        print("=== Ticket fields relevant to P0 detection (id: name [table.field]) ===")
        for sid, meta in opts.items():
            if not isinstance(meta, dict):
                continue
            name = str(meta.get("name", "")).lower()
            field = str(meta.get("field", "")).lower()
            table = str(meta.get("table", "")).lower()
            if any(k in name or k in field or k in table for k in INTERESTING):
                print(f"  {sid}: {meta.get('name')!r}  [{meta.get('table')}.{meta.get('field')}]")

        # 2) sample: how many OPEN tickets at each priority (GLPI priority field id = 3 by convention)
        print("\n=== open-ticket count by priority (searchoption 3 = priority) ===")
        for pri in range(1, 7):  # GLPI priority 1..6 (6 = Major)
            params = {
                "is_deleted": 0,
                "criteria[0][field]": 12, "criteria[0][searchtype]": "equals", "criteria[0][value]": "notold",
                "criteria[1][link]": "AND", "criteria[1][field]": 3,
                "criteria[1][searchtype]": "equals", "criteria[1][value]": pri,
                "range": "0-0",
            }
            resp = c.get(f"{BASE}/search/Ticket", headers=h, params=params)
            total = resp.headers.get("Content-Range", "0-0/0").split("/")[-1]
            print(f"  priority={pri}: {total} open tickets")
    finally:
        c.get(f"{BASE}/killSession", headers=h)
print("\nDONE — read-only probe complete.")
