# =============================================================================
# Psi-Wars Space Combat Simulator — models.py
# =============================================================================
# SQLite schema and database initialisation.
# Uses raw sqlite3 — no ORM dependency, easy to inspect and debug.
# =============================================================================
import sqlite3
import logging
from config import DB_PATH

log = logging.getLogger(__name__)

def get_connection() -> sqlite3.Connection:
    """Return a database connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    log.info(f"Initialising database at {DB_PATH}")
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                invite_code  TEXT UNIQUE NOT NULL,
                gm_user_id   TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS participants (
                participant_id  TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES sessions(session_id),
                user_id         TEXT NOT NULL,
                display_name    TEXT NOT NULL,
                role            TEXT NOT NULL CHECK(role IN ('gm','player','spectator')),
                joined_at       DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS log_entries (
                entry_id        TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES sessions(session_id),
                entry_type      TEXT NOT NULL CHECK(entry_type IN ('chat','roll','system')),
                author_id       TEXT,
                author_name     TEXT,
                content         TEXT,
                expression      TEXT,
                dice_results    TEXT,
                total           INTEGER,
                original_total  INTEGER,
                gm_overridden   INTEGER DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pending_rolls (
                pending_id      TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL,
                entry_id        TEXT NOT NULL,
                status          TEXT DEFAULT 'pending'
                                     CHECK(status IN ('pending','approved','overridden','rerolled')),
                override_value  INTEGER,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        log.info("Database ready.")
    finally:
        conn.close()
