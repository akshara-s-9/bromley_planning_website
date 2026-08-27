"""FastAPI app serving the cached Bromley new-dwelling approvals."""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, store

app = FastAPI(title="Bromley new-dwelling approvals")


@app.on_event("startup")
def _ensure_schema() -> None:
    conn = store.connect()
    try:
        store.init(conn)
    finally:
        conn.close()


@app.get("/api/applications")
def applications(
    decided_from: str | None = Query(None, description="decision date from, YYYY-MM-DD"),
    decided_to: str | None = Query(None, description="decision date to, YYYY-MM-DD"),
    include_all: bool = Query(False, description="include non new-build permissions"),
) -> list[dict]:
    conn = store.connect()
    try:
        return store.query(conn, decided_from, decided_to, include_all)
    finally:
        conn.close()


@app.get("/api/status")
def status() -> dict:
    conn = store.connect()
    try:
        return store.status(conn)
    finally:
        conn.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
