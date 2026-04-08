"""
SQLite persistence for lead generation sessions.
All blocking sqlite3 calls are wrapped in asyncio.to_thread so they
don't stall the FastAPI event loop.
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent / ".runtime" / "data" / "sessions.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_sync() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                created_at   TEXT NOT NULL,
                industry     TEXT,
                location     TEXT,
                target_role  TEXT,
                company_size TEXT,
                lead_type    TEXT,
                keywords     TEXT,
                num_leads    INTEGER,
                status       TEXT NOT NULL DEFAULT 'running',
                total_leads  INTEGER DEFAULT 0,
                verified     INTEGER DEFAULT 0,
                missing_email INTEGER DEFAULT 0,
                preview      TEXT,
                excel_data   BLOB
            )
        """)
        conn.commit()


def _save_session_sync(
    session_id: str,
    criteria: dict,
    *,
    status: str,
    total_leads: int = 0,
    verified: int = 0,
    missing_email: int = 0,
    preview: list | None = None,
    excel_data: bytes | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions
                (session_id, created_at, industry, location, target_role,
                 company_size, lead_type, keywords, num_leads,
                 status, total_leads, verified, missing_email, preview, excel_data)
            VALUES
                (?,?,?,?,?, ?,?,?,?, ?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                status        = excluded.status,
                total_leads   = excluded.total_leads,
                verified      = excluded.verified,
                missing_email = excluded.missing_email,
                preview       = excluded.preview,
                excel_data    = COALESCE(excluded.excel_data, excel_data)
            """,
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                criteria.get("industry"),
                criteria.get("location"),
                criteria.get("target_role"),
                criteria.get("company_size"),
                criteria.get("lead_type"),
                criteria.get("keywords"),
                criteria.get("num_leads"),
                status,
                total_leads,
                verified,
                missing_email,
                json.dumps(preview or []),
                excel_data,
            ),
        )
        conn.commit()


def _get_excel_sync(session_id: str) -> bytes | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT excel_data FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return bytes(row["excel_data"]) if row and row["excel_data"] else None


def _list_sessions_sync(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT session_id, created_at, industry, location, target_role,
                   company_size, lead_type, keywords, num_leads,
                   status, total_leads, verified, missing_email, preview
            FROM sessions
            WHERE status = 'ready'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["preview"] = json.loads(d["preview"] or "[]")
            except Exception:
                d["preview"] = []
            result.append(d)
        return result


# ── Async public API ──────────────────────────────────────────────────────────

async def init_db() -> None:
    await asyncio.to_thread(_init_sync)


async def save_session(session_id: str, criteria: dict, **kwargs) -> None:
    await asyncio.to_thread(_save_session_sync, session_id, criteria, **kwargs)


async def get_excel(session_id: str) -> bytes | None:
    return await asyncio.to_thread(_get_excel_sync, session_id)


async def list_sessions(limit: int = 100) -> list[dict]:
    return await asyncio.to_thread(_list_sessions_sync, limit)
