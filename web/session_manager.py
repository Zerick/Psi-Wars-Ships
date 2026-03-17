"""
Session Manager — Psi-Wars Web UI Multiplayer Backend
=====================================================

Manages the full lifecycle of game sessions:
  - Create sessions with keyword identifiers
  - Join sessions as GM, host-player, or player
  - Assign ships to players (GM-assign or player-select modes)
  - Persist session state to JSON files
  - List, load, and purge sessions
  - Issue and validate reconnection tokens

Architecture notes:
  - Each session is stored as a single JSON file: sessions/{keyword}.json
  - The SessionManager is a singleton that holds active sessions in memory
  - On every state change, the session is auto-saved to disk
  - Tokens are stored per-session so they survive server restarts
  - The WebSocket layer (ws_handler.py) calls into this module for all
    state mutations; this module never touches WebSocket directly.

Modification guide:
  - To change keyword format: edit _generate_keyword()
  - To add new roles: add to UserRole enum and update join_session()
  - To change persistence format: edit _save_session() / _load_session()
  - To add session settings: add fields to SessionState dataclass
  - To change auth: edit _hash_password() / _verify_password()
  - To add co-GM support later: change role validation in join_session()

Dependencies: hashlib (stdlib), secrets (stdlib), json (stdlib), pathlib (stdlib)
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from ship_catalog import ShipCatalog
from faction_manager import FactionManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Word lists for keyword generation (adjective-noun-number)
# Kept short and memorable; all space/military themed for flavor.
ADJECTIVES = [
    "iron", "shadow", "crimson", "void", "stellar", "ghost", "plasma",
    "dark", "frozen", "burning", "silent", "wild", "broken", "golden",
    "fallen", "savage", "azure", "silver", "rogue", "black", "amber",
    "crystal", "storm", "lunar", "solar", "dread", "swift", "grim",
    "bright", "ancient", "neon", "cobalt", "scarlet", "violet", "jade",
]

NOUNS = [
    "hawk", "wolf", "serpent", "lance", "blade", "star", "comet",
    "viper", "falcon", "phoenix", "tiger", "dragon", "raven", "storm",
    "hunter", "shadow", "shield", "arrow", "bolt", "flame", "talon",
    "fang", "wraith", "specter", "fury", "dagger", "hammer", "anvil",
    "crown", "throne", "pyre", "nova", "nebula", "pulse", "drift",
]

# Token length in bytes (produces 32-char hex string)
TOKEN_BYTES = 16

# Default sessions directory (relative to web root)
DEFAULT_SESSIONS_DIR = "sessions"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    """
    Roles a connected user can have within a session.

    GM:     Full control. Sees everything. Can edit all stats silently.
            Can undo/redo. Manages session settings. Only one per session.
    HOST:   The player who created a GM-less session. Functionally
            identical to PLAYER in terms of setup powers — in GM-less
            sessions ALL players can add/remove ships, set factions,
            create engagements, and manage assignments. The HOST
            distinction exists only for housekeeping (e.g. showing who
            created the session). NO GM visibility, no silent edits,
            no undo/redo.
    PLAYER: Controls their assigned ship(s). In GM sessions, limited
            setup powers (only the GM manages ships/engagements). In
            GM-less sessions, full setup powers (same as HOST).
            Visibility: sees full stats only for ships they control.
            Other ships show limited info (name, class, rough condition).
            A consensus "see all stats" toggle overrides this when ALL
            players have it enabled.
    """
    GM = "gm"
    HOST = "host"
    PLAYER = "player"


class ShipAssignMode(str, Enum):
    """
    How ships get assigned to players in a session.

    GM_ASSIGN:      GM (or host) manually assigns ships to players.
    PLAYER_SELECT:  Players choose their own ship from the available pool.
    """
    GM_ASSIGN = "gm_assign"
    PLAYER_SELECT = "player_select"


class SessionStatus(str, Enum):
    """
    High-level session lifecycle state.

    SETUP:    Ships being added, players joining, not yet in combat.
    ACTIVE:   Combat is underway.
    PAUSED:   Combat paused (GM action).
    COMPLETE: Combat finished or session ended.
    """
    SETUP = "setup"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConnectedUser:
    """
    A user connected to a session (or previously connected).

    Fields:
        name:       Display name chosen at join time.
        role:       GM, HOST, or PLAYER.
        ship_ids:   List of ship IDs this user controls.
        token:      Reconnection token (hex string). Stored in the user's
                    browser localStorage and validated on reconnect.
        connected:  Whether the user currently has an active WebSocket.
        last_seen:  ISO timestamp of last activity (for stale detection).
        see_stats:  Whether this user has toggled "see all stats" on.
                    When ALL connected players have see_stats=True, every
                    player sees full stats for every ship. If any one
                    player has it False, everyone sees limited info for
                    ships they don't control.
    """
    name: str
    role: str  # Stored as string for JSON serialization; use UserRole enum in code
    ship_ids: list[str] = field(default_factory=list)
    token: str = ""
    connected: bool = False
    last_seen: str = ""
    see_stats: bool = False

    def to_dict(self) -> dict:
        """Serialize for JSON persistence."""
        return {
            "name": self.name,
            "role": self.role,
            "ship_ids": self.ship_ids,
            "token": self.token,
            "connected": False,  # Always save as disconnected
            "last_seen": self.last_seen,
            "see_stats": self.see_stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConnectedUser:
        """Deserialize from JSON."""
        return cls(
            name=data["name"],
            role=data["role"],
            ship_ids=data.get("ship_ids", []),
            token=data.get("token", ""),
            connected=False,  # Always start disconnected on load
            last_seen=data.get("last_seen", ""),
            see_stats=data.get("see_stats", False),
        )


@dataclass
class SessionState:
    """
    Complete state of a game session.

    This is the single source of truth. The WebSocket layer reads from
    this and writes to this via SessionManager methods. The entire state
    is serialized to JSON for persistence.

    Fields:
        keyword:            Unique session identifier (e.g. "iron-hawk-7").
        created:            ISO timestamp of creation.
        updated:            ISO timestamp of last modification.
        status:             Session lifecycle state.
        has_gm:             Whether this session has a GM role.
        gm_password_hash:   Hashed GM password (empty string = no GM).
        ship_assign_mode:   How ships get assigned to players.
        ships:              List of ship data dicts (API contract format).
        engagements:        List of engagement dicts.
        combat_log:         List of combat log entry dicts.
        dice_log:           List of dice roll dicts.
        chat_log:           List of chat message dicts (separate from combat log).
        active_state:       Current combat state (active ship, targets, turn).
        users:              Dict of connected/known users, keyed by name.
        available_ship_ids: Ship IDs not yet assigned to any player (for
                            player-select mode).
        settings:           Arbitrary session settings dict for future use.
        version:            Schema version for forward compatibility.
    """
    keyword: str
    created: str = ""
    updated: str = ""
    status: str = SessionStatus.SETUP.value
    has_gm: bool = True
    gm_password_hash: str = ""
    ship_assign_mode: str = ShipAssignMode.GM_ASSIGN.value
    ships: list[dict] = field(default_factory=list)
    engagements: list[dict] = field(default_factory=list)
    factions: list[dict] = field(default_factory=list)
    faction_relationships: dict[str, str] = field(default_factory=dict)
    targeting_warnings_acknowledged: list[str] = field(default_factory=list)
    combat_log: list[dict] = field(default_factory=list)
    dice_log: list[dict] = field(default_factory=list)
    chat_log: list[dict] = field(default_factory=list)
    active_state: dict = field(default_factory=lambda: {
        "active_ship_id": None,
        "targets": [],
        "targeting": [],
        "current_turn": 0,
    })
    users: dict[str, ConnectedUser] = field(default_factory=dict)
    available_ship_ids: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        """Serialize the full session state for JSON persistence."""
        return {
            "keyword": self.keyword,
            "created": self.created,
            "updated": self.updated,
            "status": self.status,
            "has_gm": self.has_gm,
            "gm_password_hash": self.gm_password_hash,
            "ship_assign_mode": self.ship_assign_mode,
            "ships": self.ships,
            "engagements": self.engagements,
            "factions": self.factions,
            "faction_relationships": self.faction_relationships,
            "targeting_warnings_acknowledged": self.targeting_warnings_acknowledged,
            "combat_log": self.combat_log,
            "dice_log": self.dice_log,
            "chat_log": self.chat_log,
            "active_state": self.active_state,
            "users": {
                name: user.to_dict()
                for name, user in self.users.items()
            },
            "available_ship_ids": self.available_ship_ids,
            "settings": self.settings,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionState:
        """Deserialize from a JSON dict."""
        users = {}
        for name, udata in data.get("users", {}).items():
            users[name] = ConnectedUser.from_dict(udata)

        return cls(
            keyword=data["keyword"],
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            status=data.get("status", SessionStatus.SETUP.value),
            has_gm=data.get("has_gm", True),
            gm_password_hash=data.get("gm_password_hash", ""),
            ship_assign_mode=data.get("ship_assign_mode", ShipAssignMode.GM_ASSIGN.value),
            ships=data.get("ships", []),
            engagements=data.get("engagements", []),
            factions=data.get("factions", []),
            faction_relationships=data.get("faction_relationships", {}),
            targeting_warnings_acknowledged=data.get("targeting_warnings_acknowledged", []),
            combat_log=data.get("combat_log", []),
            dice_log=data.get("dice_log", []),
            chat_log=data.get("chat_log", []),
            active_state=data.get("active_state", {
                "active_ship_id": None,
                "targets": [],
                "targeting": [],
                "current_turn": 0,
            }),
            users=users,
            available_ship_ids=data.get("available_ship_ids", []),
            settings=data.get("settings", {}),
            version=data.get("version", "1.0.0"),
        )


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_keyword(existing_keywords: set[str]) -> str:
    """
    Generate a unique session keyword in the format: adjective-noun-number.

    Examples: iron-hawk-7, shadow-viper-42, crimson-phoenix-3

    Retries if the generated keyword already exists (astronomically unlikely
    with the current word list sizes, but defensive coding is good coding).

    Args:
        existing_keywords: Set of keywords already in use.

    Returns:
        A unique keyword string.
    """
    for _ in range(100):  # Safety valve
        adj = secrets.choice(ADJECTIVES)
        noun = secrets.choice(NOUNS)
        num = secrets.randbelow(99) + 1  # 1-99
        keyword = f"{adj}-{noun}-{num}"
        if keyword not in existing_keywords:
            return keyword

    # Fallback: append timestamp to guarantee uniqueness
    return f"session-{int(time.time())}"


def _generate_token() -> str:
    """Generate a cryptographically random reconnection token."""
    return secrets.token_hex(TOKEN_BYTES)


def _hash_password(password: str) -> str:
    """
    Hash a password for storage.

    Uses SHA-256 with a random salt. Not bcrypt-level security, but
    appropriate for a game session password on a local network.

    Args:
        password: Plaintext password.

    Returns:
        "salt:hash" string for storage.
    """
    salt = secrets.token_hex(16)
    hash_val = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{hash_val}"


def _verify_password(password: str, stored: str) -> bool:
    """
    Verify a password against a stored salt:hash string.

    Args:
        password: Plaintext password to check.
        stored:   "salt:hash" string from _hash_password().

    Returns:
        True if the password matches.
    """
    if not stored or ":" not in stored:
        return False
    salt, expected_hash = stored.split(":", 1)
    actual_hash = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return secrets.compare_digest(actual_hash, expected_hash)


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages all game sessions — creation, joining, persistence, cleanup.

    This is the central authority for session state. The WebSocket handler
    and HTTP routes call into this; it never initiates network communication.

    Usage:
        manager = SessionManager(sessions_dir=Path("sessions"))
        manager.load_all()  # Load persisted sessions on startup

        # Create a new session
        session, user = manager.create_session(
            creator_name="GM Dave",
            has_gm=True,
            gm_password="secret123",
        )

        # Player joins
        user = manager.join_session(
            keyword="iron-hawk-7",
            name="Alice",
        )

        # Reconnect with token
        user = manager.reconnect(
            keyword="iron-hawk-7",
            token="abc123...",
        )

    Thread safety:
        Not thread-safe. FastAPI's async model means we process one
        request at a time per session (no concurrent mutations). If this
        changes, add asyncio.Lock per session.
    """

    def __init__(
        self,
        sessions_dir: Path | str = DEFAULT_SESSIONS_DIR,
        templates_dir: Path | str | None = None,
    ):
        """
        Initialize the session manager.

        Args:
            sessions_dir:  Directory for session JSON files. Created if needed.
            templates_dir: Directory for ship template JSON files. If None,
                           the catalog will be empty (templates can be loaded
                           later via ship_catalog.load_from_list()).
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Active sessions indexed by keyword
        self._sessions: dict[str, SessionState] = {}

        # Ship template catalog
        self.ship_catalog = ShipCatalog(templates_dir=templates_dir)
        if templates_dir:
            self.ship_catalog.load()

        # Faction manager (stateless — shared across all sessions)
        self.faction_mgr = FactionManager()

        logger.info("SessionManager initialized. Sessions dir: %s", self.sessions_dir)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_session(self, session: SessionState) -> None:
        """
        Save a session to its JSON file.

        Called automatically after every state mutation. The file is written
        atomically (write to temp file, then rename) to prevent corruption
        if the server crashes mid-write.

        Args:
            session: The session state to persist.
        """
        session.updated = _now_iso()
        filepath = self.sessions_dir / f"{session.keyword}.json"

        # Atomic write: write to temp file, then rename
        tmp_path = filepath.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(session.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
            tmp_path.replace(filepath)
            logger.debug("Saved session: %s", session.keyword)
        except Exception:
            logger.exception("Failed to save session: %s", session.keyword)
            # Clean up temp file if rename failed
            tmp_path.unlink(missing_ok=True)
            raise

    def _load_session(self, filepath: Path) -> Optional[SessionState]:
        """
        Load a single session from a JSON file.

        Args:
            filepath: Path to the session JSON file.

        Returns:
            SessionState if successful, None if the file is corrupt/invalid.
        """
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            session = SessionState.from_dict(data)
            logger.debug("Loaded session: %s", session.keyword)
            return session
        except Exception:
            logger.exception("Failed to load session: %s", filepath)
            return None

    def load_all(self) -> int:
        """
        Load all persisted sessions from the sessions directory.

        Called once on server startup. Sessions that fail to load are
        skipped with a warning (not deleted — could be manually repaired).

        Returns:
            Number of sessions successfully loaded.
        """
        loaded = 0
        for filepath in sorted(self.sessions_dir.glob("*.json")):
            session = self._load_session(filepath)
            if session:
                self._sessions[session.keyword] = session
                loaded += 1

        logger.info("Loaded %d sessions from disk.", loaded)
        return loaded

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        creator_name: str,
        has_gm: bool = True,
        gm_password: str = "",
        ship_assign_mode: str = ShipAssignMode.GM_ASSIGN.value,
    ) -> tuple[SessionState, ConnectedUser]:
        """
        Create a new game session.

        The creator becomes GM (if has_gm=True and password provided) or
        HOST (if has_gm=False). The session starts in SETUP status.

        Args:
            creator_name:     Display name of the session creator.
            has_gm:           Whether the session has a GM role.
            gm_password:      Password for GM access (required if has_gm).
            ship_assign_mode: How ships get assigned to players.

        Returns:
            Tuple of (SessionState, ConnectedUser for the creator).

        Raises:
            ValueError: If has_gm is True but no password is provided.
        """
        if has_gm and not gm_password:
            raise ValueError("GM password is required when creating a session with a GM.")

        keyword = _generate_keyword(set(self._sessions.keys()))

        # Determine creator's role
        if has_gm:
            creator_role = UserRole.GM.value
        else:
            creator_role = UserRole.HOST.value

        # Create the creator's user record
        token = _generate_token()
        creator = ConnectedUser(
            name=creator_name,
            role=creator_role,
            token=token,
            connected=True,
            last_seen=_now_iso(),
        )

        # Create the session
        session = SessionState(
            keyword=keyword,
            created=_now_iso(),
            has_gm=has_gm,
            gm_password_hash=_hash_password(gm_password) if gm_password else "",
            ship_assign_mode=ship_assign_mode,
            users={creator_name: creator},
        )

        self._sessions[keyword] = session
        self._save_session(session)

        logger.info(
            "Created session '%s' by '%s' (role=%s, has_gm=%s)",
            keyword, creator_name, creator_role, has_gm,
        )
        return session, creator

    def join_session(
        self,
        keyword: str,
        name: str,
        gm_password: str = "",
    ) -> ConnectedUser:
        """
        Join an existing session as a player (or GM if password matches).

        Rules:
          - If gm_password is provided and correct, join as GM (if no GM
            is currently connected — only one GM at a time for now).
          - Otherwise, join as PLAYER.
          - Name must be unique within the session.
          - Generates a reconnection token for the new user.

        Args:
            keyword:      Session keyword to join.
            name:         Display name.
            gm_password:  Optional GM password.

        Returns:
            ConnectedUser for the newly joined user.

        Raises:
            KeyError:    Session not found.
            ValueError:  Name already taken, or GM slot occupied, or
                         wrong GM password.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        # Check if name is already taken by a different user
        if name in session.users:
            existing = session.users[name]
            if existing.connected:
                raise ValueError(
                    f"Name '{name}' is already in use in this session. "
                    "Choose a different name or reconnect with your token."
                )
            # Name exists but user is disconnected — they should use reconnect
            raise ValueError(
                f"Name '{name}' is already registered. Use the reconnect "
                "feature (refresh the page) to rejoin."
            )

        # Determine role
        role = UserRole.PLAYER.value
        if gm_password and session.has_gm:
            if _verify_password(gm_password, session.gm_password_hash):
                # Check if there's already a connected GM
                for user in session.users.values():
                    if user.role == UserRole.GM.value and user.connected:
                        raise ValueError(
                            "A GM is already connected to this session. "
                            "Only one GM is allowed at a time."
                        )
                role = UserRole.GM.value
            else:
                raise ValueError("Incorrect GM password.")
        elif gm_password and not session.has_gm:
            raise ValueError("This is a GM-less session. No GM password needed.")

        # Create user
        token = _generate_token()
        user = ConnectedUser(
            name=name,
            role=role,
            token=token,
            connected=True,
            last_seen=_now_iso(),
        )

        session.users[name] = user
        self._save_session(session)

        logger.info(
            "User '%s' joined session '%s' as %s",
            name, keyword, role,
        )
        return user

    def reconnect(
        self,
        keyword: str,
        token: str,
    ) -> Optional[ConnectedUser]:
        """
        Reconnect a user to a session using their stored token.

        Called when a client has a token in localStorage and attempts
        silent reconnection on page load.

        Args:
            keyword: Session keyword.
            token:   Reconnection token from localStorage.

        Returns:
            ConnectedUser if token is valid, None if not.
        """
        session = self._sessions.get(keyword)
        if not session:
            return None

        for user in session.users.values():
            if user.token and secrets.compare_digest(user.token, token):
                user.connected = True
                user.last_seen = _now_iso()
                self._save_session(session)
                logger.info(
                    "User '%s' reconnected to session '%s'",
                    user.name, keyword,
                )
                return user

        return None

    def disconnect_user(self, keyword: str, name: str) -> None:
        """
        Mark a user as disconnected (WebSocket closed).

        Does NOT remove them from the session — they can reconnect later.

        Args:
            keyword: Session keyword.
            name:    User's display name.
        """
        session = self._sessions.get(keyword)
        if not session:
            return

        user = session.users.get(name)
        if user:
            user.connected = False
            user.last_seen = _now_iso()
            self._save_session(session)
            logger.debug("User '%s' disconnected from '%s'", name, keyword)

    # ------------------------------------------------------------------
    # Session queries
    # ------------------------------------------------------------------

    def get_session(self, keyword: str) -> Optional[SessionState]:
        """Get a session by keyword, or None if not found."""
        return self._sessions.get(keyword)

    def list_sessions(self) -> list[dict]:
        """
        List all sessions with summary info (for the GM session browser).

        Returns a list of dicts with: keyword, created, updated, status,
        has_gm, player_count, ship_count.
        """
        result = []
        for session in self._sessions.values():
            result.append({
                "keyword": session.keyword,
                "created": session.created,
                "updated": session.updated,
                "status": session.status,
                "has_gm": session.has_gm,
                "player_count": sum(
                    1 for u in session.users.values()
                    if u.role in (UserRole.PLAYER.value, UserRole.HOST.value)
                ),
                "gm_connected": any(
                    u.connected for u in session.users.values()
                    if u.role == UserRole.GM.value
                ),
                "ship_count": len(session.ships),
            })
        return result

    def purge_session(self, keyword: str) -> bool:
        """
        Permanently delete a session (memory + disk).

        Args:
            keyword: Session keyword to purge.

        Returns:
            True if the session was found and deleted, False if not found.
        """
        if keyword not in self._sessions:
            return False

        del self._sessions[keyword]

        filepath = self.sessions_dir / f"{keyword}.json"
        filepath.unlink(missing_ok=True)

        logger.info("Purged session: %s", keyword)
        return True

    # ------------------------------------------------------------------
    # Ship management
    # ------------------------------------------------------------------

    def add_ship(self, keyword: str, ship_data: dict) -> str:
        """
        Add a ship to a session.

        The ship_data dict should follow the API contract's serialized
        ship schema. A unique ship_id is generated if not present.

        Args:
            keyword:   Session keyword.
            ship_data: Ship data dict.

        Returns:
            The ship_id of the added ship.

        Raises:
            KeyError: Session not found.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        # Generate ship_id if not provided
        if "ship_id" not in ship_data or not ship_data["ship_id"]:
            ship_data["ship_id"] = f"ship_{len(session.ships) + 1}"

        # Ensure default faction exists if the ship references it
        ship_faction = ship_data.get("faction", "")
        if ship_faction:
            state_dict = session.to_dict()
            faction_names = {f["name"] for f in state_dict.get("factions", [])}
            if ship_faction not in faction_names:
                # Auto-create the faction (handles "NPC Hostiles" and any other)
                from faction_manager import DEFAULT_FACTION_NAME, DEFAULT_FACTION_COLOR
                if ship_faction == DEFAULT_FACTION_NAME:
                    self.faction_mgr.ensure_default_faction(state_dict)
                else:
                    self.faction_mgr.create_faction(state_dict, ship_faction)
                session.factions = state_dict["factions"]
                session.faction_relationships = state_dict["faction_relationships"]

        session.ships.append(ship_data)

        # In player-select mode, new ships start as available
        if session.ship_assign_mode == ShipAssignMode.PLAYER_SELECT.value:
            session.available_ship_ids.append(ship_data["ship_id"])

        self._save_session(session)
        logger.info("Added ship '%s' to session '%s'", ship_data["ship_id"], keyword)
        return ship_data["ship_id"]

    def remove_ship(self, keyword: str, ship_id: str) -> bool:
        """
        Remove a ship from a session.

        Also:
          - Removes the ship from any user's ship_ids list
          - Removes from available_ship_ids
          - Clears target_id on any ship that was targeting the removed ship
          - Removes all engagements involving the removed ship

        Args:
            keyword: Session keyword.
            ship_id: ID of the ship to remove.

        Returns:
            True if the ship was found and removed, False otherwise.
        """
        session = self._sessions.get(keyword)
        if not session:
            return False

        original_count = len(session.ships)
        session.ships = [s for s in session.ships if s.get("ship_id") != ship_id]

        if len(session.ships) == original_count:
            return False

        # Clean up user assignments
        for user in session.users.values():
            if ship_id in user.ship_ids:
                user.ship_ids.remove(ship_id)
        if ship_id in session.available_ship_ids:
            session.available_ship_ids.remove(ship_id)

        # Clear target_id on ships that were targeting the removed ship
        for ship in session.ships:
            if ship.get("target_id") == ship_id:
                ship["target_id"] = None

        # Remove engagements involving this ship (as pursuer or target)
        session.engagements = [
            e for e in session.engagements
            if ship_id not in (
                e.get("ship_a_id"), e.get("ship_b_id"),
                # Also check the directional key format
                e.get("pursuer_id"), e.get("target_id"),
            )
        ]

        self._save_session(session)
        logger.info("Removed ship '%s' from session '%s'", ship_id, keyword)
        return True

    def assign_ship(self, keyword: str, ship_id: str, player_name: str) -> None:
        """
        Assign a ship to a player.

        In GM_ASSIGN mode, this is called by the GM/host.
        In PLAYER_SELECT mode, this is called when a player picks a ship.

        Args:
            keyword:     Session keyword.
            ship_id:     ID of the ship to assign.
            player_name: Name of the player to assign to.

        Raises:
            KeyError:   Session not found, or player not in session.
            ValueError: Ship not found, or already assigned (in select mode).
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        if player_name not in session.users:
            raise KeyError(f"Player '{player_name}' not found in session.")

        # Verify the ship exists
        ship_exists = any(s.get("ship_id") == ship_id for s in session.ships)
        if not ship_exists:
            raise ValueError(f"Ship '{ship_id}' not found in session.")

        # In player-select mode, check availability
        if session.ship_assign_mode == ShipAssignMode.PLAYER_SELECT.value:
            if ship_id not in session.available_ship_ids:
                raise ValueError(f"Ship '{ship_id}' is already assigned.")
            session.available_ship_ids.remove(ship_id)

        # Assign
        user = session.users[player_name]
        if ship_id not in user.ship_ids:
            user.ship_ids.append(ship_id)

        self._save_session(session)
        logger.info(
            "Assigned ship '%s' to player '%s' in session '%s'",
            ship_id, player_name, keyword,
        )

    def unassign_ship(self, keyword: str, ship_id: str, player_name: str) -> None:
        """
        Remove a ship assignment from a player.

        In player-select mode, the ship returns to the available pool.

        Args:
            keyword:     Session keyword.
            ship_id:     ID of the ship.
            player_name: Name of the player.
        """
        session = self._sessions.get(keyword)
        if not session:
            return

        user = session.users.get(player_name)
        if user and ship_id in user.ship_ids:
            user.ship_ids.remove(ship_id)

            if session.ship_assign_mode == ShipAssignMode.PLAYER_SELECT.value:
                session.available_ship_ids.append(ship_id)

            self._save_session(session)

    # ------------------------------------------------------------------
    # Engagement management
    # ------------------------------------------------------------------

    def add_engagement(self, keyword: str, engagement: dict) -> None:
        """
        Add an engagement between two ships.

        Args:
            keyword:    Session keyword.
            engagement: Engagement dict (API contract format).

        Raises:
            KeyError: Session not found.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        session.engagements.append(engagement)
        self._save_session(session)

    def remove_engagement(self, keyword: str, ship_a_id: str, ship_b_id: str) -> bool:
        """
        Remove an engagement between two ships (order-independent).

        Returns True if found and removed.
        """
        session = self._sessions.get(keyword)
        if not session:
            return False

        original_count = len(session.engagements)
        session.engagements = [
            e for e in session.engagements
            if not (
                {e.get("ship_a_id"), e.get("ship_b_id")} == {ship_a_id, ship_b_id}
            )
        ]

        if len(session.engagements) < original_count:
            self._save_session(session)
            return True
        return False

    # ------------------------------------------------------------------
    # Log management
    # ------------------------------------------------------------------

    def add_combat_log_entry(self, keyword: str, entry: dict) -> None:
        """Append an entry to the combat log."""
        session = self._sessions.get(keyword)
        if not session:
            return
        session.combat_log.append(entry)
        self._save_session(session)

    def add_chat_message(self, keyword: str, message: dict) -> None:
        """Append a chat message to the chat log."""
        session = self._sessions.get(keyword)
        if not session:
            return
        session.chat_log.append(message)
        self._save_session(session)

    def add_dice_entry(self, keyword: str, entry: dict) -> None:
        """Append a dice roll to the dice log."""
        session = self._sessions.get(keyword)
        if not session:
            return
        session.dice_log.append(entry)
        self._save_session(session)

    # ------------------------------------------------------------------
    # State mutations
    # ------------------------------------------------------------------

    def update_ship(self, keyword: str, ship_id: str, updates: dict) -> bool:
        """
        Apply partial updates to a ship's data.

        Args:
            keyword: Session keyword.
            ship_id: Ship to update.
            updates: Dict of fields to update (merged into ship data).

        Returns:
            True if the ship was found and updated.
        """
        session = self._sessions.get(keyword)
        if not session:
            return False

        for ship in session.ships:
            if ship.get("ship_id") == ship_id:
                ship.update(updates)
                self._save_session(session)
                return True
        return False

    def update_engagement(self, keyword: str, ship_a_id: str, ship_b_id: str, updates: dict) -> bool:
        """
        Apply partial updates to an engagement.

        Finds the engagement by ship pair (order-independent) and merges updates.

        Returns True if found and updated.
        """
        session = self._sessions.get(keyword)
        if not session:
            return False

        for eng in session.engagements:
            if {eng.get("ship_a_id"), eng.get("ship_b_id")} == {ship_a_id, ship_b_id}:
                eng.update(updates)
                self._save_session(session)
                return True
        return False

    def update_active_state(self, keyword: str, updates: dict) -> None:
        """Update the active combat state (turn counter, active ship, etc.)."""
        session = self._sessions.get(keyword)
        if not session:
            return
        session.active_state.update(updates)
        self._save_session(session)

    def set_session_status(self, keyword: str, status: str) -> None:
        """Change session lifecycle status (setup → active → paused → complete)."""
        session = self._sessions.get(keyword)
        if not session:
            return
        session.status = status
        self._save_session(session)

    # ------------------------------------------------------------------
    # Role-based state views
    # ------------------------------------------------------------------

    def _all_players_see_stats(self, session: SessionState) -> bool:
        """
        Check if the consensus "see all stats" condition is met.

        Returns True only when EVERY connected non-GM user has
        see_stats=True. If there are no connected non-GM users,
        returns False (no one to consent).
        """
        non_gm_users = [
            u for u in session.users.values()
            if u.role != UserRole.GM.value and u.connected
        ]
        if not non_gm_users:
            return False
        return all(u.see_stats for u in non_gm_users)

    def set_see_stats(self, keyword: str, user_name: str, value: bool) -> Optional[bool]:
        """
        Toggle a player's "see all stats" preference.

        Args:
            keyword:   Session keyword.
            user_name: The user toggling the setting.
            value:     True to opt in, False to opt out.

        Returns:
            The new consensus state (True if ALL players now have it on),
            or None if session/user not found.
        """
        session = self._sessions.get(keyword)
        if not session:
            return None

        user = session.users.get(user_name)
        if not user:
            return None

        user.see_stats = value
        self._save_session(session)

        return self._all_players_see_stats(session)

    def get_state_for_user(self, keyword: str, user_name: str) -> Optional[dict]:
        """
        Get session state filtered for a specific user's role.

        Visibility rules:
          - GM: Gets everything. Full stats for all ships. All logs.
          - HOST/PLAYER (with GM present): Players see full stats only
            for their own ships. Other ships get limited view (name,
            class, rough condition). UNLESS the consensus "see all stats"
            toggle is active, in which case everyone sees everything.
          - HOST/PLAYER (no GM, i.e. GM-less session): Same visibility
            as above — own ships full, others limited, consensus override.

        Args:
            keyword:   Session keyword.
            user_name: The requesting user's name.

        Returns:
            Filtered state dict, or None if session/user not found.
        """
        session = self._sessions.get(keyword)
        if not session:
            return None

        user = session.users.get(user_name)
        if not user:
            return None

        role = UserRole(user.role)

        # Compute consensus see-stats for the UI to display toggle state
        consensus_see_stats = self._all_players_see_stats(session)

        # Build per-user see_stats map for UI (who has it on/off)
        see_stats_status = {
            u.name: u.see_stats
            for u in session.users.values()
            if u.role != UserRole.GM.value
        }

        # Base state that everyone gets
        state = {
            "keyword": session.keyword,
            "status": session.status,
            "has_gm": session.has_gm,
            "ship_assign_mode": session.ship_assign_mode,
            "active_state": session.active_state,
            "engagements": session.engagements,
            "current_user": {
                "name": user.name,
                "role": user.role,
                "ship_ids": user.ship_ids,
                "see_stats": user.see_stats,
            },
            "connected_users": [
                {
                    "name": u.name,
                    "role": u.role,
                    "connected": u.connected,
                    "see_stats": u.see_stats,
                }
                for u in session.users.values()
            ],
            "consensus_see_stats": consensus_see_stats,
            "see_stats_status": see_stats_status,
            "settings": session.settings,
            "available_ship_ids": session.available_ship_ids,
            "version": session.version,
        }

        # GM gets full everything
        if role == UserRole.GM:
            state["ships"] = session.ships
            state["combat_log"] = session.combat_log
            state["dice_log"] = session.dice_log
            state["chat_log"] = session.chat_log

        # HOST and PLAYER get filtered ship views
        else:
            if consensus_see_stats:
                # All players agreed — everyone sees full stats
                state["ships"] = session.ships
            else:
                # Normal player visibility: own ships full, others limited
                state["ships"] = self._filter_ships_for_player(session, user)

            # No NPC reasoning for non-GM users
            state["combat_log"] = [
                e for e in session.combat_log
                if e.get("event_type") != "npc_reasoning"
            ]

            # Filter NPC dice rolls if GM has hidden them
            if session.settings.get("hide_npc_rolls", False):
                state["dice_log"] = [
                    d for d in session.dice_log
                    if not d.get("is_npc", False)
                ]
            else:
                state["dice_log"] = session.dice_log

            state["chat_log"] = session.chat_log

        return state

    def _filter_ships_for_player(
        self,
        session: SessionState,
        player: ConnectedUser,
    ) -> list[dict]:
        """
        Filter ship data for a player's view.

        - Player's own ships (in their ship_ids): full detail.
        - ALL other ships (regardless of faction): limited detail.
          Shows name, class, faction, SM, rough condition descriptor.
          Hides exact HP, systems, weapons, stats, pilot details.

        Players never see full stats for ships they don't control,
        unless the consensus "see all stats" toggle is active (handled
        by the caller — this method is only called when consensus is off).
        """
        player_ship_ids = set(player.ship_ids)

        filtered = []
        for ship in session.ships:
            ship_id = ship.get("ship_id", "")

            # Player's own ships — full detail
            if ship_id in player_ship_ids:
                filtered.append(ship)
            else:
                # All other ships — limited detail
                filtered.append(self._limited_ship_view(ship))

        return filtered

    @staticmethod
    def _limited_ship_view(ship: dict) -> dict:
        """
        Limited detail view of a ship the player does not control.

        Shows: name, class, faction, SM, rough condition descriptor.
        Hides: exact HP, systems, weapons, stats, pilot details.

        The rough condition uses a descriptor instead of exact HP numbers:
        fine / damaged / heavily damaged / crippled / destroyed.
        """
        st_hp = ship.get("st_hp", 1)
        current_hp = ship.get("current_hp", st_hp)
        hp_pct = (current_hp / st_hp * 100) if st_hp > 0 else 0

        if ship.get("is_destroyed", False):
            condition = "destroyed"
        elif hp_pct >= 90:
            condition = "fine"
        elif hp_pct >= 60:
            condition = "damaged"
        elif hp_pct >= 30:
            condition = "heavily damaged"
        else:
            condition = "crippled"

        return {
            "ship_id": ship.get("ship_id"),
            "template_id": ship.get("template_id"),
            "display_name": ship.get("display_name"),
            "faction": ship.get("faction"),
            "sm": ship.get("sm"),
            "ship_class": ship.get("ship_class"),
            "condition": condition,
            "is_destroyed": ship.get("is_destroyed", False),
            "visibility": "limited",
        }

    # ------------------------------------------------------------------
    # Permission checks
    # ------------------------------------------------------------------

    def can_edit_ships(self, keyword: str, user_name: str) -> bool:
        """
        Check if a user has permission to add/remove/edit ships.

        GM: always.
        GM-less session: ALL players (HOST and PLAYER) have setup powers.
        GM session (non-GM user): no.
        """
        session = self._sessions.get(keyword)
        if not session:
            return False
        user = session.users.get(user_name)
        if not user:
            return False

        # GM always can
        if user.role == UserRole.GM.value:
            return True

        # In GM-less sessions, everyone can
        if not session.has_gm:
            return True

        # In GM sessions, only the GM can edit ships
        return False

    def can_manage_session(self, keyword: str, user_name: str) -> bool:
        """
        Check if a user has permission to manage session settings.

        Same logic as can_edit_ships: GM always, all players in GM-less.
        """
        session = self._sessions.get(keyword)
        if not session:
            return False
        user = session.users.get(user_name)
        if not user:
            return False

        if user.role == UserRole.GM.value:
            return True
        if not session.has_gm:
            return True
        return False

    def can_undo_redo(self, keyword: str, user_name: str) -> bool:
        """Check if a user has permission to undo/redo. GM only."""
        session = self._sessions.get(keyword)
        if not session:
            return False
        user = session.users.get(user_name)
        if not user:
            return False
        return user.role == UserRole.GM.value

    # ------------------------------------------------------------------
    # Ship template catalog
    # ------------------------------------------------------------------

    def get_ship_catalog(self) -> dict:
        """
        Get the categorized ship template catalog for the UI picker.

        Returns a dict with "categories" list, each containing "label",
        "description", and "ships" list with summary stats.
        """
        return self.ship_catalog.get_catalog()

    def add_ship_from_template(
        self,
        keyword: str,
        template_id: str,
        ship_id: str = "",
    ) -> Optional[str]:
        """
        Add a ship to a session by instantiating a template.

        Creates a new ship with all template stats, default NPC pilot
        (all skills at 12), default "NPC Hostiles" faction, and NPC
        control mode. The default faction is auto-created if it doesn't
        exist yet.

        Args:
            keyword:     Session keyword.
            template_id: Template to instantiate (e.g. "wildcat_v1").
            ship_id:     Optional ship_id. Auto-generated if empty.

        Returns:
            The ship_id of the new ship, or None if template not found.

        Raises:
            KeyError: Session not found.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        # Generate a ship_id if not provided
        if not ship_id:
            existing_ids = {s.get("ship_id", "") for s in session.ships}
            counter = len(session.ships) + 1
            while f"ship_{counter}" in existing_ids:
                counter += 1
            ship_id = f"ship_{counter}"

        # Create ship instance from template
        ship = self.ship_catalog.create_ship_from_template(template_id, ship_id)
        if not ship:
            return None

        # Ensure default faction exists
        state_dict = session.to_dict()
        self.faction_mgr.ensure_default_faction(state_dict)
        session.factions = state_dict["factions"]
        session.faction_relationships = state_dict["faction_relationships"]

        # Add the ship
        session.ships.append(ship)

        # In player-select mode, new ships start as available
        if session.ship_assign_mode == ShipAssignMode.PLAYER_SELECT.value:
            session.available_ship_ids.append(ship_id)

        self._save_session(session)
        logger.info(
            "Added ship '%s' (template=%s) to session '%s'",
            ship_id, template_id, keyword,
        )
        return ship_id

    # ------------------------------------------------------------------
    # Faction management (delegates to FactionManager)
    # ------------------------------------------------------------------

    def create_faction(self, keyword: str, name: str, color: str = "") -> dict:
        """
        Create a new faction in a session.

        See FactionManager.create_faction() for details.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        state_dict = session.to_dict()
        result = self.faction_mgr.create_faction(state_dict, name, color)
        session.factions = state_dict["factions"]
        session.faction_relationships = state_dict["faction_relationships"]
        self._save_session(session)
        return result

    def get_factions(self, keyword: str) -> list[dict]:
        """Get all factions in a session."""
        session = self._sessions.get(keyword)
        if not session:
            return []
        state_dict = session.to_dict()
        return self.faction_mgr.get_factions(state_dict)

    def remove_faction(self, keyword: str, name: str) -> dict:
        """
        Remove a faction from a session.

        Ships referencing the removed faction are flagged as orphaned.
        Returns a dict with "removed" and "orphaned_ships".
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        state_dict = session.to_dict()
        result = self.faction_mgr.remove_faction(state_dict, name)
        session.factions = state_dict["factions"]
        session.faction_relationships = state_dict["faction_relationships"]
        session.ships = state_dict["ships"]
        self._save_session(session)
        return result

    def set_faction_relationship(
        self,
        keyword: str,
        from_faction: str,
        to_faction: str,
        relationship: str,
    ) -> None:
        """
        Set the directional relationship from one faction to another.

        See FactionManager.set_relationship() for details.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        state_dict = session.to_dict()
        self.faction_mgr.set_relationship(
            state_dict, from_faction, to_faction, relationship,
        )
        session.faction_relationships = state_dict["faction_relationships"]
        self._save_session(session)

    def get_faction_relationship(
        self,
        keyword: str,
        from_faction: str,
        to_faction: str,
    ) -> str:
        """
        Get the directional relationship from one faction to another.

        Returns "neutral" if no relationship is set.
        """
        session = self._sessions.get(keyword)
        if not session:
            return "neutral"

        state_dict = session.to_dict()
        return self.faction_mgr.get_relationship(
            state_dict, from_faction, to_faction,
        )

    def escalate_faction_relationship(
        self,
        keyword: str,
        attacker_faction: str,
        defender_faction: str,
    ) -> Optional[str]:
        """
        Escalate an NPC faction's relationship when attacked.

        friendly → neutral → hostile. Only applies to NPC factions.
        Returns the new relationship, or None if no change.
        """
        session = self._sessions.get(keyword)
        if not session:
            return None

        state_dict = session.to_dict()
        result = self.faction_mgr.escalate_relationship(
            state_dict, attacker_faction, defender_faction,
        )
        session.faction_relationships = state_dict["faction_relationships"]
        self._save_session(session)
        return result

    # ------------------------------------------------------------------
    # Targeting warnings
    # ------------------------------------------------------------------

    def check_targeting_warning(
        self,
        keyword: str,
        attacker_ship_id: str,
        target_ship_id: str,
    ) -> Optional[str]:
        """
        Check if a targeting warning should be shown.

        Returns a warning message string, or None if no warning needed.
        """
        session = self._sessions.get(keyword)
        if not session:
            return None

        attacker = next(
            (s for s in session.ships if s.get("ship_id") == attacker_ship_id),
            None,
        )
        target = next(
            (s for s in session.ships if s.get("ship_id") == target_ship_id),
            None,
        )
        if not attacker or not target:
            return None

        state_dict = session.to_dict()
        return self.faction_mgr.check_targeting_warning(
            state_dict, attacker, target,
        )

    def acknowledge_targeting_warning(
        self,
        keyword: str,
        attacker_faction: str,
        target_faction: str,
    ) -> None:
        """
        Acknowledge a targeting warning so it doesn't repeat.
        """
        session = self._sessions.get(keyword)
        if not session:
            return

        state_dict = session.to_dict()
        self.faction_mgr.acknowledge_targeting_warning(
            state_dict, attacker_faction, target_faction,
        )
        session.targeting_warnings_acknowledged = state_dict["targeting_warnings_acknowledged"]
        self._save_session(session)

    # ------------------------------------------------------------------
    # Target assignment and engagements
    # ------------------------------------------------------------------

    def set_ship_target(
        self,
        keyword: str,
        ship_id: str,
        target_id: Optional[str],
        range_band: str = "long",
        advantage: Optional[str] = None,
        matched_speed: bool = False,
    ) -> None:
        """
        Set a ship's target, creating or updating an engagement.

        Setting a target creates a directional engagement (pursuer →
        target). Changing a target removes the old engagement and
        creates a new one. Setting target_id to None clears the target
        and removes the engagement.

        Args:
            keyword:      Session keyword.
            ship_id:      The pursuing ship's ID.
            target_id:    The target ship's ID, or None to clear.
            range_band:   Starting range band (default "long").
            advantage:    Ship ID that has advantage, or None.
            matched_speed: Whether speed is matched (default False).

        Raises:
            KeyError:   Session or ship not found.
            ValueError: Ship targeting itself.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        # Find the pursuing ship
        ship = next(
            (s for s in session.ships if s.get("ship_id") == ship_id),
            None,
        )
        if not ship:
            raise KeyError(f"Ship '{ship_id}' not found.")

        if target_id == ship_id:
            raise ValueError("A ship cannot target itself.")

        # If target_id is provided, verify the target exists
        if target_id is not None:
            target_exists = any(
                s.get("ship_id") == target_id for s in session.ships
            )
            if not target_exists:
                raise KeyError(f"Target ship '{target_id}' not found.")

        # Remove old engagement if the ship had a previous target
        old_target = ship.get("target_id")
        if old_target:
            old_key = f"{ship_id}→{old_target}"
            session.engagements = [
                e for e in session.engagements
                if e.get("key") != old_key
            ]

        # Set the new target
        ship["target_id"] = target_id

        # Create new engagement if target is set
        if target_id is not None:
            eng_key = f"{ship_id}→{target_id}"
            engagement = {
                "key": eng_key,
                "pursuer_id": ship_id,
                "target_id": target_id,
                # Legacy fields for backward compatibility with display code
                "ship_a_id": ship_id,
                "ship_b_id": target_id,
                "range_band": range_band,
                "advantage": advantage,
                "matched_speed": matched_speed,
                "hugging": False,
            }
            session.engagements.append(engagement)

        self._save_session(session)
        logger.info(
            "Ship '%s' target set to '%s' in session '%s'",
            ship_id, target_id, keyword,
        )

    def get_engagements(self, keyword: str) -> dict:
        """
        Get all engagements as a dict keyed by "pursuer→target".

        Returns a dict like:
            {
                "ship_1→ship_2": {
                    "range_band": "long",
                    "advantage": null,
                    "matched_speed": false,
                    "hugging": false
                }
            }
        """
        session = self._sessions.get(keyword)
        if not session:
            return {}

        result = {}
        for eng in session.engagements:
            key = eng.get("key", f"{eng.get('ship_a_id', '')}→{eng.get('ship_b_id', '')}")
            result[key] = {
                "range_band": eng.get("range_band", "long"),
                "advantage": eng.get("advantage"),
                "matched_speed": eng.get("matched_speed", False),
                "hugging": eng.get("hugging", False),
                "pursuer_id": eng.get("pursuer_id", eng.get("ship_a_id")),
                "target_id": eng.get("target_id", eng.get("ship_b_id")),
            }
        return result

    # ------------------------------------------------------------------
    # Combat transition
    # ------------------------------------------------------------------

    def start_combat(self, keyword: str) -> dict:
        """
        Transition a session from SETUP to ACTIVE.

        Performs non-blocking validation and returns warnings about
        incomplete setup (ships without targets, default pilots, etc.).
        The transition proceeds regardless of warnings.

        Args:
            keyword: Session keyword.

        Returns:
            A dict with:
                "status": "active"
                "warnings": list of warning strings (advisory only)

        Raises:
            KeyError: Session not found.
        """
        session = self._sessions.get(keyword)
        if not session:
            raise KeyError(f"Session '{keyword}' not found.")

        # Collect validation warnings (non-blocking)
        warnings = []

        for ship in session.ships:
            sid = ship.get("ship_id", "?")
            name = ship.get("display_name", sid)

            # No target assigned
            if not ship.get("target_id"):
                warnings.append(f"Ship '{name}' has no target assigned.")

            # Default pilot (all skills still at 12, or no pilot configured)
            pilot = ship.get("pilot", {})
            if not pilot:
                warnings.append(f"Ship '{name}' has no pilot configured.")
            elif (pilot.get("piloting_skill") == 12
                    and pilot.get("gunnery_skill") == 12
                    and pilot.get("basic_speed") == 6.0):
                warnings.append(f"Ship '{name}' still has default pilot stats.")

            # No player assigned (in multiplayer with human control)
            if (ship.get("control") == "human"
                    and not ship.get("assigned_player")):
                warnings.append(f"Ship '{name}' is human-controlled but not assigned to a player.")

        # Check for factions with no relationships
        faction_names = {f["name"] for f in session.factions}
        for fname in faction_names:
            has_any_rel = any(
                k.startswith(f"{fname}→") or k.endswith(f"→{fname}")
                for k in session.faction_relationships
            )
            if not has_any_rel and len(faction_names) > 1:
                warnings.append(f"Faction '{fname}' has no relationships defined.")

        # Transition to active
        session.status = SessionStatus.ACTIVE.value
        session.active_state["current_turn"] = 1

        # Add combat log entry
        session.combat_log.append({
            "message": "═══ COMBAT BEGINS ═══",
            "event_type": "turn",
            "turn": 1,
        })

        self._save_session(session)
        logger.info("Combat started in session '%s' with %d warning(s)", keyword, len(warnings))

        return {
            "status": "active",
            "warnings": warnings,
        }

