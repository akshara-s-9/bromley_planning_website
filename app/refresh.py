"""Pull Bromley permissions from PlanIt, classify them, and cache them.

    python -m app.refresh                              # last 30 days of decisions
    python -m app.refresh --from 2025-08-26 --to 2026-08-26
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from . import classify, config, planit, store


def to_row(record: dict) -> dict:
    is_new_build, reason = classify.classify(record)
    return {
        "uid": record.get("uid"),
        "app_type": record.get("app_type"),
        "app_size": record.get("app_size"),
        "address": record.get("address"),
        "postcode": classify.extract_postcode(record),
        "description": record.get("description"),
        "decided_date": record.get("decided_date"),
        "start_date": record.get("start_date"),
        "latitude": record.get("location_y"),
        "longitude": record.get("location_x"),
        "bromley_url": record.get("url"),
        "planit_url": record.get("link"),
        "is_new_build": int(is_new_build),
        "classification_reason": reason,
    }


def run(decided_from: str, decided_to: str) -> dict:
    print(f"Fetching Bromley permissions decided {decided_from} .. {decided_to}")
    records = planit.fetch_permitted(decided_from, decided_to)

    rows = [to_row(r) for r in records if r.get("uid")]
    new_build = sum(r["is_new_build"] for r in rows)

    conn = store.connect()
    try:
        store.init(conn)
        store.upsert_many(conn, rows)
        store.log_refresh(conn, decided_from, decided_to, len(rows), new_build)
        totals = store.status(conn)
    finally:
        conn.close()

    print(f"\nStored {len(rows)} permitted applications, {new_build} flagged as new-build.")
    print(f"Cache now holds {totals['total_permitted']} applications "
          f"({totals['new_build']} new-build).")
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="decided_from", help="decision date from (YYYY-MM-DD)")
    parser.add_argument("--to", dest="decided_to", help="decision date to (YYYY-MM-DD)")
    args = parser.parse_args()

    decided_to = args.decided_to or date.today().isoformat()
    decided_from = args.decided_from or (
        date.fromisoformat(decided_to) - timedelta(days=config.DEFAULT_REFRESH_DAYS)
    ).isoformat()

    run(decided_from, decided_to)


if __name__ == "__main__":
    main()
