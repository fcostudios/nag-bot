"""READ-ONLY GLPI probe v2: fetch open tickets with priority/urgency/impact/category
and aggregate the real value distributions, to design the P0 rule (E7-S2)."""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line and line.split("=", 1)[0].strip().startswith("GLPI_"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

import httpx  # noqa: E402

BASE = os.environ["GLPI_BASE_URL"].rstrip("/")
H0 = {"App-Token": os.environ["GLPI_APP_TOKEN"], "Authorization": f"user_token {os.environ['GLPI_USER_TOKEN']}"}
FIELDS = {1: "name", 3: "priority", 10: "urgency", 11: "impact", 7: "category", 14: "type"}

with httpx.Client(timeout=60) as c:
    tok = c.post(f"{BASE}/initSession", headers=H0).json()["session_token"]
    h = {"App-Token": os.environ["GLPI_APP_TOKEN"], "Session-Token": tok}
    try:
        params = {
            "is_deleted": 0,
            "criteria[0][field]": 12, "criteria[0][searchtype]": "equals", "criteria[0][value]": "notold",
            "range": "0-499",
        }
        for i, fid in enumerate(FIELDS):
            params[f"forcedisplay[{i}]"] = fid
        data = c.get(f"{BASE}/search/Ticket", headers=h, params=params).json()
        rows = data.get("data", [])
        print(f"open tickets fetched: {len(rows)}\n")

        pri, urg, imp, cat = Counter(), Counter(), Counter(), Counter()
        for row in rows:
            pri[row.get("3")] += 1
            urg[row.get("10")] += 1
            imp[row.get("11")] += 1
            cat[str(row.get("7"))] += 1
        print("priority dist:", dict(pri.most_common()))
        print("urgency  dist:", dict(urg.most_common()))
        print("impact   dist:", dict(imp.most_common()))
        print("\ntop 15 categories by open-ticket count:")
        for name, n in cat.most_common(15):
            print(f"  {n:4d}  {name[:70]}")
    finally:
        c.get(f"{BASE}/killSession", headers=h)
print("\nDONE.")
