"""Client for the PlanIt planning-application API.

PlanIt rate limits aggressively and signals it either with a 429 or by
returning a non-JSON body, so every response is parsed defensively.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx

from . import config


class PlanitError(RuntimeError):
    pass


@dataclass
class Page:
    records: list[dict]
    total: int
    frm: int


def _parse(response: httpx.Response) -> Page:
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        # PlanIt serves an HTML error page rather than JSON when throttled.
        raise PlanitError(
            f"PlanIt returned a non-JSON body (HTTP {response.status_code}); "
            "this usually means the rate limit was hit"
        ) from exc
    return Page(
        records=payload.get("records") or [],
        total=payload.get("total") or 0,
        frm=payload.get("from") or 0,
    )


def _get(client: httpx.Client, params: dict) -> Page:
    for attempt in range(1, config.MAX_RETRIES + 1):
        response = client.get(config.PLANIT_URL, params=params)

        if response.status_code == 429:
            wait = float(response.headers.get("Retry-After", config.PAGE_DELAY_SECONDS * 4))
            if attempt == config.MAX_RETRIES:
                raise PlanitError(f"PlanIt rate limit persisted after {attempt} attempts")
            print(f"  rate limited, waiting {wait:.0f}s (attempt {attempt})")
            time.sleep(wait)
            continue

        response.raise_for_status()

        try:
            return _parse(response)
        except PlanitError:
            if attempt == config.MAX_RETRIES:
                raise
            time.sleep(config.PAGE_DELAY_SECONDS * 4)

    raise PlanitError("unreachable")


def fetch_permitted(decided_from: str, decided_to: str) -> list[dict]:
    """Fetch every Permitted Bromley application decided in the window.

    Dates are YYYY-MM-DD. Note PlanIt's `decided_start`/`decided_end` filter on
    the decision date, whereas `start_date`/`end_date` filter on the date the
    application was made -- they are not interchangeable.
    """
    base = {
        "auth": config.AUTHORITY,
        "app_state": "Permitted",
        "decided_start": decided_from,
        "decided_end": decided_to,
        "pg_sz": config.PAGE_SIZE,
        "sort": "-decided_date",
        "select": config.PLANIT_SELECT,
    }

    records: list[dict] = []
    page_no = 1

    with httpx.Client(timeout=60.0, headers={"User-Agent": "bromley-planning/1.0"}) as client:
        while True:
            page = _get(client, {**base, "page": page_no})
            records.extend(page.records)

            print(f"  page {page_no}: {len(page.records)} records ({len(records)}/{page.total})")

            if not page.records or len(records) >= page.total:
                break

            page_no += 1
            time.sleep(config.PAGE_DELAY_SECONDS)

    return records
