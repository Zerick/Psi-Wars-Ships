# =============================================================================
# Psi-Wars Space Combat Simulator — log_manager.py
# =============================================================================
# Append to and retrieve the shared combat/chat log.
# Handles both chat entries and roll entries (post-GM-review).
# =============================================================================
import uuid
import json
import logging
from models import get_connection

log = logging.getLogger(__name__)


def get_log(session_id: str, limit: int = 200) -> list[dict]:
    """
    Return the most recent `limit` log entries for a session, oldest first.
    Excludes pending rolls (those have gm_overridden = NULL and total = NULL
    and are still in the pending_rolls table with status='pending').
    
    We display an entry only once it has been broadcast (i.e. not sitting in
    pending state). The pending_rolls join handles this.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT le.*
            FROM log_entries le
            LEFT JOIN pending_rolls pr ON pr.entry_id = le.entry_id
            WHERE le.session_id = ?
              AND (pr.pending_id IS NULL OR pr.status != 'pending')
            ORDER BY le.created_at ASC
            LIMIT ?
            """,
            (session_id, limit)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def append_chat(session_id: str, author_id: str, author_name: str, content: str) -> dict:
    """Insert a plain chat entry. Returns the entry dict."""
    entry_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO log_entries
               (entry_id, session_id, entry_type, author_id, author_name, content)
               VALUES (?,?,?,?,?,?)""",
            (entry_id, session_id, "chat", author_id, author_name, content)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM log_entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def create_pending_roll(
    session_id: str,
    author_id: str,
    author_name: str,
    expression: str,
    dice_results: str,   # JSON string
    total: int,
    content: str,        # label text (message surrounding the [[roll]])
) -> tuple[dict, dict]:
    """
    Insert a log_entry for the roll (not yet visible) and a pending_rolls record.
    Returns (log_entry_dict, pending_roll_dict).
    """
    entry_id = str(uuid.uuid4())
    pending_id = str(uuid.uuid4())

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO log_entries
               (entry_id, session_id, entry_type, author_id, author_name,
                content, expression, dice_results, total)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (entry_id, session_id, "roll", author_id, author_name,
             content, expression, dice_results, total)
        )
        conn.execute(
            """INSERT INTO pending_rolls
               (pending_id, session_id, entry_id, status)
               VALUES (?,?,?,?)""",
            (pending_id, session_id, entry_id, "pending")
        )
        conn.commit()

        entry_row = conn.execute(
            "SELECT * FROM log_entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        pending_row = conn.execute(
            "SELECT * FROM pending_rolls WHERE pending_id = ?", (pending_id,)
        ).fetchone()

        return _row_to_dict(entry_row), dict(pending_row)
    finally:
        conn.close()


def approve_pending_roll(pending_id: str) -> dict | None:
    """Mark pending roll as approved. Returns the log_entry dict for broadcast."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE pending_rolls SET status='approved' WHERE pending_id=?",
            (pending_id,)
        )
        conn.commit()
        row = conn.execute(
            """SELECT le.* FROM log_entries le
               JOIN pending_rolls pr ON pr.entry_id = le.entry_id
               WHERE pr.pending_id = ?""",
            (pending_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def override_pending_roll(pending_id: str, override_value: int) -> dict | None:
    """
    GM overrides the roll total. Updates log_entry and marks pending as overridden.
    Returns updated log_entry dict for broadcast.
    """
    conn = get_connection()
    try:
        # Get the entry_id
        pr = conn.execute(
            "SELECT entry_id FROM pending_rolls WHERE pending_id=?", (pending_id,)
        ).fetchone()
        if not pr:
            return None

        entry_id = pr["entry_id"]

        # Save original total, set new total, mark overridden
        conn.execute(
            """UPDATE log_entries
               SET original_total = total,
                   total = ?,
                   gm_overridden = 1
               WHERE entry_id = ?""",
            (override_value, entry_id)
        )
        conn.execute(
            """UPDATE pending_rolls
               SET status='overridden', override_value=?
               WHERE pending_id=?""",
            (override_value, pending_id)
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM log_entries WHERE entry_id=?", (entry_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def reroll_pending(pending_id: str, new_dice_results: str, new_total: int) -> dict | None:
    """
    GM requested a re-roll. Updates the pending_roll with new results.
    The log_entry is NOT yet broadcast — GM must approve/override again.
    Returns the updated pending info dict for the GM's review panel.
    """
    conn = get_connection()
    try:
        pr = conn.execute(
            "SELECT entry_id FROM pending_rolls WHERE pending_id=?", (pending_id,)
        ).fetchone()
        if not pr:
            return None

        entry_id = pr["entry_id"]

        conn.execute(
            """UPDATE log_entries
               SET dice_results=?, total=?
               WHERE entry_id=?""",
            (new_dice_results, new_total, entry_id)
        )
        conn.execute(
            "UPDATE pending_rolls SET status='pending' WHERE pending_id=?",
            (pending_id,)
        )
        conn.commit()

        entry_row = conn.execute(
            "SELECT * FROM log_entries WHERE entry_id=?", (entry_id,)
        ).fetchone()
        pr_row = conn.execute(
            "SELECT * FROM pending_rolls WHERE pending_id=?", (pending_id,)
        ).fetchone()

        entry = _row_to_dict(entry_row)
        return {**dict(pr_row), "entry": entry}
    finally:
        conn.close()


def get_pending_rolls(session_id: str) -> list[dict]:
    """Return all pending rolls for a session (for GM reconnect)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT pr.*, le.author_name, le.expression, le.dice_results,
                      le.total, le.content, le.entry_id as log_entry_id
               FROM pending_rolls pr
               JOIN log_entries le ON le.entry_id = pr.entry_id
               WHERE pr.session_id = ? AND pr.status = 'pending'
               ORDER BY pr.created_at ASC""",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    # Parse dice_results JSON if present
    if d.get("dice_results") and isinstance(d["dice_results"], str):
        try:
            d["dice_results"] = json.loads(d["dice_results"])
        except Exception:
            pass
    # Normalise booleans
    if "gm_overridden" in d:
        d["gm_overridden"] = bool(d["gm_overridden"])
    return d
