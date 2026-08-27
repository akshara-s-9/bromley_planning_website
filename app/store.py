"""SQLite cache. The web app reads only from here -- never from PlanIt."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    uid                   TEXT PRIMARY KEY,
    app_type              TEXT,
    app_size              TEXT,
    address               TEXT,
    postcode              TEXT,
    description           TEXT,
    decided_date          TEXT,
    start_date            TEXT,
    latitude              REAL,
    longitude             REAL,
    bromley_url           TEXT,
    planit_url            TEXT,
    is_new_build          INTEGER NOT NULL DEFAULT 0,
    classification_reason TEXT,
    fetched_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_decided ON applications(decided_date);
CREATE INDEX IF NOT EXISTS idx_applications_new_build ON applications(is_new_build);

CREATE TABLE IF NOT EXISTS refresh_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at         TEXT NOT NULL,
    decided_from   TEXT NOT NULL,
    decided_to     TEXT NOT NULL,
    fetched        INTEGER NOT NULL,
    new_build      INTEGER NOT NULL
);
"""

UPSERT = """
INSERT INTO applications (
    uid, app_type, app_size, address, postcode, description,
    decided_date, start_date, latitude, longitude,
    bromley_url, planit_url, is_new_build, classification_reason, fetched_at
) VALUES (
    :uid, :app_type, :app_size, :address, :postcode, :description,
    :decided_date, :start_date, :latitude, :longitude,
    :bromley_url, :planit_url, :is_new_build, :classification_reason, :fetched_at
)
ON CONFLICT(uid) DO UPDATE SET
    app_type              = excluded.app_type,
    app_size              = excluded.app_size,
    address               = excluded.address,
    postcode              = excluded.postcode,
    description           = excluded.description,
    decided_date          = excluded.decided_date,
    start_date            = excluded.start_date,
    latitude              = excluded.latitude,
    longitude             = excluded.longitude,
    bromley_url           = excluded.bromley_url,
    planit_url            = excluded.planit_url,
    is_new_build          = excluded.is_new_build,
    classification_reason = excluded.classification_reason,
    fetched_at            = excluded.fetched_at
"""


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_many(conn: sqlite3.Connection, rows: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany(UPSERT, [{**row, "fetched_at": now} for row in rows])
    conn.commit()


def log_refresh(
    conn: sqlite3.Connection, decided_from: str, decided_to: str, fetched: int, new_build: int
) -> None:
    conn.execute(
        "INSERT INTO refresh_log (ran_at, decided_from, decided_to, fetched, new_build)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            decided_from,
            decided_to,
            fetched,
            new_build,
        ),
    )
    conn.commit()


def query(
    conn: sqlite3.Connection,
    decided_from: str | None = None,
    decided_to: str | None = None,
    include_all: bool = False,
) -> list[dict]:
    sql = "SELECT * FROM applications WHERE 1=1"
    params: list = []

    if not include_all:
        sql += " AND is_new_build = 1"
    if decided_from:
        sql += " AND decided_date >= ?"
        params.append(decided_from)
    if decided_to:
        sql += " AND decided_date <= ?"
        params.append(decided_to)

    sql += " ORDER BY decided_date DESC, uid DESC"
    return [dict(row) for row in conn.execute(sql, params)]


def status(conn: sqlite3.Connection) -> dict:
    totals = conn.execute(
        "SELECT COUNT(*) AS total,"
        " COALESCE(SUM(is_new_build), 0) AS new_build,"
        " MIN(decided_date) AS earliest,"
        " MAX(decided_date) AS latest"
        " FROM applications"
    ).fetchone()

    last = conn.execute(
        "SELECT ran_at, decided_from, decided_to, fetched, new_build"
        " FROM refresh_log ORDER BY id DESC LIMIT 1"
    ).fetchone()

    return {
        "total_permitted": totals["total"],
        "new_build": totals["new_build"],
        "earliest_decision": totals["earliest"],
        "latest_decision": totals["latest"],
        "last_refresh": dict(last) if last else None,
    }
