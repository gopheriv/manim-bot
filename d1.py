"""Cloudflare D1 cache integration — async-safe with graceful degradation.

All Cloudflare SDK calls run inside asyncio.to_thread to avoid blocking
the event loop. If D1 is unreachable, every method silently no-ops.
"""

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any

from config import (
    CF_API_TOKEN,
    CF_ACCOUNT_ID,
    CF_DATABASE_ID,
    D1_ENABLED,
)

logger = logging.getLogger(__name__)

# In-memory fallback when D1 is disabled (local SQLite for session-only cache)
_local_cache: dict[str, dict] = {}
_local_cache_path = Path(__file__).parent / ".local_cache.db"
_cf_available = False


def _init_local_db() -> sqlite3.Connection:
    """Create a local SQLite fallback cache."""
    conn = sqlite3.connect(str(_local_cache_path), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS render_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            generated_code TEXT,
            telegram_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_prompt ON render_history(chat_id, prompt)")
    conn.commit()
    return conn


_local_db: sqlite3.Connection | None = None


async def init() -> bool:
    """Initialize D1 connection. Returns True if D1 is reachable."""
    global _cf_available, _local_db

    if not D1_ENABLED:
        logger.info("D1 disabled — credentials not configured, using local cache")
        _local_db = _init_local_db()
        return False

    try:
        # Test connection with a lightweight query
        result = await asyncio.to_thread(_cf_query, "SELECT 1")
        if result:
            _cf_available = True
            logger.info("D1 connected successfully")

            # Ensure schema exists
            await asyncio.to_thread(_cf_query, """
                CREATE TABLE IF NOT EXISTS render_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    generated_code TEXT,
                    telegram_file_id TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            return True
        else:
            raise RuntimeError("D1 returned empty result for health check")

    except Exception as e:
        logger.warning(f"D1 unreachable ({e}) — falling back to local cache")
        _cf_available = False
        _local_db = _init_local_db()
        return False


async def health_check() -> dict:
    """Quick D1 health check. Returns status dict for diagnostics."""
    result = {
        "d1_enabled": D1_ENABLED,
        "cf_available": _cf_available,
        "local_db": _local_db is not None,
    }

    if _cf_available:
        try:
            await asyncio.to_thread(_cf_query, "SELECT 1")
            result["status"] = "healthy"
        except Exception as e:
            result["status"] = "degraded"
            result["error"] = str(e)
            # Switch to local if D1 became unreachable
            _cf_available = False
            _local_db = _init_local_db()
            result["fallback"] = "local sqlite"
    else:
        result["status"] = "local_fallback"

    return result


def _cf_query(sql: str, params: list | None = None) -> Any:
    """Synchronous Cloudflare D1 query — must be called from to_thread."""
    import httpx

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{CF_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    body: dict = {"sql": sql}
    if params:
        body["params"] = params

    resp = httpx.post(url, json=body, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success"):
        errors = data.get("errors", [])
        raise RuntimeError(f"D1 query failed: {errors}")

    return data.get("result", [])


async def check_cache(chat_id: int, prompt: str) -> str | None:
    """Check if we have a cached telegram_file_id for this exact prompt."""
    try:
        if _cf_available:
            result = await asyncio.to_thread(
                _cf_query,
                "SELECT telegram_file_id FROM render_history WHERE chat_id = ? AND prompt = ? ORDER BY created_at DESC LIMIT 1",
                [chat_id, prompt],
            )
            if result and len(result) > 0:
                rows = result[0].get("results", [])
                if rows and rows[0].get("telegram_file_id"):
                    logger.info(f"Cache HIT for chat_id={chat_id}")
                    return rows[0]["telegram_file_id"]
        else:
            # Local SQLite fallback
            await asyncio.to_thread(
                _local_query,
                "SELECT telegram_file_id FROM render_history WHERE chat_id = ? AND prompt = ? ORDER BY created_at DESC LIMIT 1",
                (chat_id, prompt),
            )
            if _local_db:
                cur = _local_db.execute(
                    "SELECT telegram_file_id FROM render_history WHERE chat_id = ? AND prompt = ? ORDER BY created_at DESC LIMIT 1",
                    (chat_id, prompt),
                )
                row = cur.fetchone()
                if row and row[0]:
                    logger.info(f"Local cache HIT for chat_id={chat_id}")
                    return row[0]
    except Exception as e:
        logger.warning(f"Cache check error: {e}")
    return None


async def save_render(
    chat_id: int,
    prompt: str,
    generated_code: str,
    telegram_file_id: str,
) -> None:
    """Save a successful render's metadata to cache."""
    try:
        if _cf_available:
            await asyncio.to_thread(
                _cf_query,
                "INSERT INTO render_history (chat_id, prompt, generated_code, telegram_file_id) VALUES (?, ?, ?, ?)",
                [chat_id, prompt, generated_code, telegram_file_id],
            )
            logger.info(f"Saved render to D1 for chat_id={chat_id}")
        elif _local_db:
            await asyncio.to_thread(
                _local_db.execute,
                "INSERT INTO render_history (chat_id, prompt, generated_code, telegram_file_id) VALUES (?, ?, ?, ?)",
                (chat_id, prompt, generated_code, telegram_file_id),
            )
            await asyncio.to_thread(_local_db.commit)
            logger.info(f"Saved render to local cache for chat_id={chat_id}")
    except Exception as e:
        logger.warning(f"Cache save error: {e}")


async def get_history(chat_id: int, limit: int = 10) -> list[dict]:
    """Get last N renders for a chat_id."""
    try:
        if _cf_available:
            result = await asyncio.to_thread(
                _cf_query,
                "SELECT prompt, created_at FROM render_history WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
                [chat_id, limit],
            )
            if result and len(result) > 0:
                return result[0].get("results", [])
        elif _local_db:
            cur = _local_db.execute(
                "SELECT prompt, created_at FROM render_history WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
                (chat_id, limit),
            )
            rows = cur.fetchall()
            return [{"prompt": r[0], "created_at": r[1]} for r in rows]
    except Exception as e:
        logger.warning(f"History fetch error: {e}")
    return []


async def get_last_code(chat_id: int) -> str | None:
    """Get the generated code from the user's latest render."""
    try:
        if _cf_available:
            result = await asyncio.to_thread(
                _cf_query,
                "SELECT generated_code FROM render_history WHERE chat_id = ? ORDER BY created_at DESC LIMIT 1",
                [chat_id],
            )
            if result and len(result) > 0:
                rows = result[0].get("results", [])
                if rows and rows[0].get("generated_code"):
                    return rows[0]["generated_code"]
        elif _local_db:
            cur = _local_db.execute(
                "SELECT generated_code FROM render_history WHERE chat_id = ? ORDER BY created_at DESC LIMIT 1",
                (chat_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logger.warning(f"Last code fetch error: {e}")
    return None


def _local_query(sql: str, params: tuple | None = None):
    """Synchronous local SQLite query helper."""
    if _local_db:
        if params:
            return _local_db.execute(sql, params)
        return _local_db.execute(sql)
    return None
