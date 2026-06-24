"""
fetch_test_fixture.py — Fetch real DHIS2 event analytics and save as local JSON fixture.

Usage:
    python fetch_test_fixture.py --url https://hmis.gov.la/hmis --user admin --password secret
                                 --program pUID --stage sUID --de deUID
                                 --ou USER_ORGUNIT --pe LAST_12_MONTHS
                                 --out C:/Temp/test_fixture_bar_dim.json

The saved JSON is the raw DHIS2 analytics/events/aggregate response.
Used by test_bar_real.py to mock dhis2Get() in a real-data checklist test.
"""
import argparse
import json
import sys
from pathlib import Path

import requests


def fetch(url, user, password, program, stage, de_uid, ou, pe, out_path):
    base = url.rstrip("/")
    endpoint = (
        f"{base}/api/analytics/events/aggregate/{program}"
        f"?stage={stage}"
        f"&dimension={stage}.{de_uid}"
        f"&dimension=pe:{pe}"
        f"&dimension=ou:{ou}"
        f"&displayProperty=NAME"
        f"&outputType=EVENT"
        f"&paging=false"
    )
    print(f"Fetching: {endpoint}")
    resp = requests.get(endpoint, auth=(user, password), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("rows", [])
    print(f"Rows returned: {len(rows)}")
    print("Headers:", [h["name"] for h in data.get("headers", [])])
    if rows:
        print("Sample row:", rows[0])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved -> {out_path}")
    return data


def main():
    p = argparse.ArgumentParser(description="Fetch DHIS2 event analytics fixture")
    p.add_argument("--url",      required=True)
    p.add_argument("--user",     required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--program",  required=True, help="Program UID")
    p.add_argument("--stage",    required=True, help="Program stage UID")
    p.add_argument("--de",       required=True, help="Dimension DE UID (tracker_option)")
    p.add_argument("--ou",       default="USER_ORGUNIT")
    p.add_argument("--pe",       default="LAST_12_MONTHS")
    p.add_argument("--out",      default="C:/Temp/test_fixture_bar_dim.json")
    args = p.parse_args()
    fetch(args.url, args.user, args.password,
          args.program, args.stage, args.de,
          args.ou, args.pe, args.out)


if __name__ == "__main__":
    main()
