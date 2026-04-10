import logging
from typing import Any
import aiosqlite
from config import settings

logger = logging.getLogger(__name__)

CREATE_CONTACTS_TABLE = """
CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number    TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    total_calls     INTEGER DEFAULT 0,
    last_call_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CALLS_TABLE = """
CREATE TABLE IF NOT EXISTS calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id      INTEGER NOT NULL REFERENCES contacts(id),
    phone_number    TEXT NOT NULL,
    direction       TEXT CHECK(direction IN ('incoming','outgoing','unknown')),
    duration_sec    INTEGER,
    recorded_at     TIMESTAMP NOT NULL,
    audio_path      TEXT,
    status          TEXT DEFAULT 'uploaded'
                    CHECK(status IN ('uploaded','transcribing','transcribed',
                                      'summarizing','done','failed')),
    transcript      TEXT,
    summary         TEXT,
    key_points      TEXT,
    action_items    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TRANSCRIPT_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS transcript_chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id         INTEGER NOT NULL REFERENCES calls(id),
    chunk_index     INTEGER NOT NULL,
    chunk_text      TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    """Create all tables if they don't exist and apply performance settings."""
    async with aiosqlite.connect(settings.DATABASE_PATH) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute(CREATE_CONTACTS_TABLE)
        await conn.execute(CREATE_CALLS_TABLE)
        await conn.execute(CREATE_TRANSCRIPT_CHUNKS_TABLE)
        await conn.commit()
    logger.info(f"Database initialized at {settings.DATABASE_PATH}")


async def execute_query(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a SELECT query and return list of row dicts."""
    async with aiosqlite.connect(settings.DATABASE_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def execute_write(query: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return lastrowid."""
    async with aiosqlite.connect(settings.DATABASE_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys=ON")
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.lastrowid
