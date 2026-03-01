# =============================================================================
# Psi-Wars Space Combat Simulator — session_manager.py
# =============================================================================
# Session creation, joining, and participant management.
# Tokens are stored in memory (dict) for PoC simplicity.
# =============================================================================
import uuid
import random
import string
import logging
from models import get_connection

log = logging.getLogger(__name__)

# In-memory token store: token -> {user_id, session_id, role, display_name}
# Lives for the lifetime of the process. Proper auth is a later slice.
_token_store: dict[str, dict] = {}

# --- Token helpers -----------------------------------------------------------

def issue_token(user_id: str, session_id: str, role: str, display_name: str) -> str:
    token = str(uuid.uuid4())
    _token_store[token] = {
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "display_name": display_name,
    }
    return token


def resolve_token(token: str) -> dict | None:
    """Return token data or None if invalid."""
    return _token_store.get(token)


# --- Invite code generation --------------------------------------------------

_WORDS = [
    "WOLF", "NOVA", "HAWK", "IRON", "STAR", "VOID", "GRIM", "BOLT",
    "APEX", "VEGA", "DUSK", "ECHO", "FLUX", "GRID", "HELM", "JADE",
    "KILO", "LYNX", "MARS", "NEON", "ONYX", "PIKE", "ROOK", "SAGE",
    "TUSK", "URAL", "WASP", "XRAY", "ZERO", "ARCH", "BANE", "CROW",
]

def _generate_invite_code() -> str:
    word = random.choice(_WORDS)
    num = random.randint(1, 99)
    return f"{word}-{num}"


def _unique_invite_code(conn) -> str:
    for _ in range(20):
        code = _generate_invite_code()
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE invite_code = ?", (code,)
        ).fetchone()
        if not row:
            return code
    # Fallback to random suffix
    return "PSIWARS-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))


# --- Session CRUD ------------------------------------------------------------

def create_session(gm_display_name: str) -> dict:
    """
    Create a new session. Returns session info and the GM's auth token.
    """
    session_id = str(uuid.uuid4())
    gm_user_id = str(uuid.uuid4())
    participant_id = str(uuid.uuid4())

    conn = get_connection()
    try:
        invite_code = _unique_invite_code(conn)

        conn.execute(
            "INSERT INTO sessions (session_id, invite_code, gm_user_id) VALUES (?,?,?)",
            (session_id, invite_code, gm_user_id)
        )
        conn.execute(
            """INSERT INTO participants
               (participant_id, session_id, user_id, display_name, role)
               VALUES (?,?,?,?,?)""",
            (participant_id, session_id, gm_user_id, gm_display_name, "gm")
        )

        # System log entry
        _insert_system_entry(conn, session_id, f"Session created by {gm_display_name}.")

        conn.commit()

        token = issue_token(gm_user_id, session_id, "gm", gm_display_name)

        log.info(f"Session created: {session_id} invite={invite_code} gm={gm_display_name}")
        return {
            "session_id": session_id,
            "invite_code": invite_code,
            "token": token,
            "user_id": gm_user_id,
            "role": "gm",
            "display_name": gm_display_name,
        }
    finally:
        conn.close()


def join_session(invite_code: str, display_name: str, role: str) -> dict | None:
    """
    Join an existing session by invite code.
    Role must be 'player' or 'spectator'.
    Returns participant info and token, or None if code not found.
    """
    conn = get_connection()
    try:
        session_row = conn.execute(
            "SELECT session_id FROM sessions WHERE invite_code = ?",
            (invite_code.upper(),)
        ).fetchone()

        if not session_row:
            return None

        session_id = session_row["session_id"]
        user_id = str(uuid.uuid4())
        participant_id = str(uuid.uuid4())

        conn.execute(
            """INSERT INTO participants
               (participant_id, session_id, user_id, display_name, role)
               VALUES (?,?,?,?,?)""",
            (participant_id, session_id, user_id, display_name, role)
        )

        _insert_system_entry(conn, session_id, f"{display_name} joined as {role}.")

        conn.commit()

        token = issue_token(user_id, session_id, role, display_name)

        log.info(f"Participant joined: session={session_id} name={display_name} role={role}")
        return {
            "session_id": session_id,
            "invite_code": invite_code.upper(),
            "token": token,
            "user_id": user_id,
            "role": role,
            "display_name": display_name,
        }
    finally:
        conn.close()


def get_participants(session_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT user_id, display_name, role, joined_at
               FROM participants WHERE session_id = ?
               ORDER BY joined_at ASC""",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT session_id, invite_code, gm_user_id, created_at FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- Internal helpers --------------------------------------------------------

def _insert_system_entry(conn, session_id: str, message: str):
    import uuid as _uuid
    entry_id = str(_uuid.uuid4())
    conn.execute(
        """INSERT INTO log_entries
           (entry_id, session_id, entry_type, content)
           VALUES (?,?,?,?)""",
        (entry_id, session_id, "system", message)
    )
