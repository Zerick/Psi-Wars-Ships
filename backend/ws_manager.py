# =============================================================================
# Psi-Wars Space Combat Simulator — ws_manager.py
# =============================================================================
# Manages active WebSocket connections per session.
# Handles broadcast-to-all and send-to-specific-user operations.
# =============================================================================
import json
import logging
from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # session_id -> list of (WebSocket, user_id, role)
        self._sessions: dict[str, list[tuple[WebSocket, str, str]]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, user_id: str, role: str):
        await websocket.accept()
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append((websocket, user_id, role))
        log.info(f"WS connected: session={session_id} user={user_id} role={role}")

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id] = [
                entry for entry in self._sessions[session_id]
                if entry[0] is not websocket
            ]
            log.info(f"WS disconnected: session={session_id}")

    async def broadcast(self, session_id: str, message: dict):
        """Send a message to ALL connected participants in a session."""
        payload = json.dumps(message)
        dead = []
        for entry in self._sessions.get(session_id, []):
            ws, uid, role = entry
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(entry)
        # Clean up dead connections
        if dead:
            self._sessions[session_id] = [
                e for e in self._sessions[session_id] if e not in dead
            ]

    async def send_to_role(self, session_id: str, role: str, message: dict):
        """Send a message only to participants with a specific role (e.g. 'gm')."""
        payload = json.dumps(message)
        dead = []
        for entry in self._sessions.get(session_id, []):
            ws, uid, r = entry
            if r == role:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(entry)
        if dead:
            self._sessions[session_id] = [
                e for e in self._sessions[session_id] if e not in dead
            ]

    async def send_to_user(self, session_id: str, user_id: str, message: dict):
        """Send a message to a specific user by user_id."""
        payload = json.dumps(message)
        for entry in self._sessions.get(session_id, []):
            ws, uid, role = entry
            if uid == user_id:
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass

    def get_connected_user_ids(self, session_id: str) -> list[str]:
        return [uid for _, uid, _ in self._sessions.get(session_id, [])]


# Singleton instance used across the app
manager = ConnectionManager()
