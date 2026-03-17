"""
WebSocket Handler — Psi-Wars Web UI
====================================

Manages WebSocket connections for real-time multiplayer sessions.
Routes incoming client messages to the SessionManager, and broadcasts
state updates to all connected clients.

Architecture:
  - Each session has a "room" of connected WebSocket clients.
  - Incoming messages are dispatched to handler functions by type.
  - Handler functions call SessionManager methods, then broadcast
    the resulting state changes to the appropriate clients.
  - The handler never modifies session state directly — all mutations
    go through SessionManager.

Connection lifecycle:
  1. Client connects to /ws/{keyword}
  2. Client sends AUTH message
  3. Server authenticates via SessionManager, sends AUTH_OK or AUTH_FAIL
  4. On AUTH_OK, client is added to the session room
  5. Messages are dispatched to type-specific handlers
  6. On disconnect, client is removed from room, user marked disconnected

Modification guide:
  - To add a new message handler: add a method named _handle_{type}(),
    and add it to the _HANDLERS dict in __init__.
  - To change broadcast behavior: modify _broadcast() or _broadcast_except()
  - To add rate limiting: add checks in handle_message()
  - To add message validation: add schemas to ws_protocol.py and validate here

Dependencies: FastAPI WebSocket, SessionManager, psi_dice
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from session_manager import SessionManager, UserRole, ConnectedUser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection tracking
# ---------------------------------------------------------------------------

class ClientConnection:
    """
    Represents a single authenticated WebSocket connection.

    Tracks the WebSocket object, the user it belongs to, and the
    session it's connected to.
    """

    def __init__(
        self,
        websocket: WebSocket,
        keyword: str,
        user_name: str,
        role: str,
    ):
        self.websocket = websocket
        self.keyword = keyword
        self.user_name = user_name
        self.role = role

    async def send(self, message: dict) -> bool:
        """
        Send a JSON message to this client.

        Returns False if the send fails (client disconnected).
        """
        try:
            await self.websocket.send_json(message)
            return True
        except Exception:
            logger.debug("Failed to send to %s", self.user_name)
            return False


# ---------------------------------------------------------------------------
# WebSocket Handler
# ---------------------------------------------------------------------------

class WebSocketHandler:
    """
    Manages all WebSocket connections and message routing.

    One instance per server. Holds references to all active connections
    organized by session keyword.

    Usage (in FastAPI route):
        handler = WebSocketHandler(session_manager, dice_roller)

        @app.websocket("/ws/{keyword}")
        async def ws_endpoint(websocket, keyword):
            await handler.handle_connection(websocket, keyword)
    """

    def __init__(
        self,
        session_manager: SessionManager,
        dice_roller=None,
    ):
        """
        Args:
            session_manager: The SessionManager instance.
            dice_roller:     The dice rolling function (from psi_dice.py).
                             Signature: roll(expression) -> dict
        """
        self.sm = session_manager
        self.dice_roller = dice_roller

        # Active connections: keyword -> list of ClientConnection
        self._rooms: dict[str, list[ClientConnection]] = {}

        # Message type -> handler method mapping
        # Each handler receives (connection, payload, request_id)
        self._HANDLERS: dict[str, callable] = {
            "CHAT": self._handle_chat,
            "DICE_ROLL": self._handle_dice_roll,
            "ADD_SHIP": self._handle_add_ship,
            "REMOVE_SHIP": self._handle_remove_ship,
            "UPDATE_SHIP": self._handle_update_ship,
            "ASSIGN_SHIP": self._handle_assign_ship,
            "SELECT_SHIP": self._handle_select_ship,
            "UNASSIGN_SHIP": self._handle_unassign_ship,
            "ADD_ENGAGEMENT": self._handle_add_engagement,
            "REMOVE_ENGAGEMENT": self._handle_remove_engagement,
            "UPDATE_ENGAGEMENT": self._handle_update_engagement,
            "UPDATE_ACTIVE_STATE": self._handle_update_active_state,
            "SET_SESSION_STATUS": self._handle_set_session_status,
            "UPDATE_SETTINGS": self._handle_update_settings,
            "UNDO": self._handle_undo,
            "REDO": self._handle_redo,
            "TOGGLE_SEE_STATS": self._handle_toggle_see_stats,
        }

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def handle_connection(self, websocket: WebSocket, keyword: str) -> None:
        """
        Handle a WebSocket connection from connect to disconnect.

        This is the main entry point called by the FastAPI route. It:
        1. Accepts the WebSocket
        2. Waits for AUTH message
        3. Authenticates the user
        4. Enters the message loop
        5. Cleans up on disconnect

        Args:
            websocket: The FastAPI WebSocket object.
            keyword:   The session keyword from the URL.
        """
        await websocket.accept()

        # Verify session exists
        session = self.sm.get_session(keyword)
        if not session:
            await websocket.send_json({
                "type": "AUTH_FAIL",
                "payload": {"error": f"Session '{keyword}' not found."},
            })
            await websocket.close()
            return

        # Wait for AUTH message (with timeout handled by client)
        connection = await self._authenticate(websocket, keyword)
        if not connection:
            return  # Auth failed, connection already closed

        # Add to room
        self._add_to_room(connection)

        # Notify other users
        await self._broadcast_except(keyword, connection.user_name, {
            "type": "USER_JOINED",
            "payload": {
                "name": connection.user_name,
                "role": connection.role,
            },
        })

        # Message loop
        try:
            await self._message_loop(connection)
        except WebSocketDisconnect:
            logger.info("User '%s' disconnected from '%s'", connection.user_name, keyword)
        except Exception:
            logger.exception(
                "Error in WebSocket for user '%s' in '%s'",
                connection.user_name, keyword,
            )
        finally:
            # Cleanup
            self._remove_from_room(connection)
            self.sm.disconnect_user(keyword, connection.user_name)

            # Notify remaining users
            await self._broadcast(keyword, {
                "type": "USER_LEFT",
                "payload": {"name": connection.user_name},
            })

    async def _authenticate(
        self,
        websocket: WebSocket,
        keyword: str,
    ) -> Optional[ClientConnection]:
        """
        Wait for and process the AUTH message.

        Tries token-based reconnection first, then falls back to
        name + optional GM password.

        Returns a ClientConnection on success, None on failure.
        """
        try:
            raw = await websocket.receive_json()
        except Exception:
            await websocket.close()
            return None

        if raw.get("type") != "AUTH":
            await websocket.send_json({
                "type": "AUTH_FAIL",
                "payload": {"error": "First message must be AUTH."},
            })
            await websocket.close()
            return None

        payload = raw.get("payload", {})
        name = payload.get("name", "").strip()
        token = payload.get("token", "").strip()
        gm_password = payload.get("gm_password", "").strip()

        # Try token-based reconnection first
        if token:
            user = self.sm.reconnect(keyword, token)
            if user:
                connection = ClientConnection(
                    websocket=websocket,
                    keyword=keyword,
                    user_name=user.name,
                    role=user.role,
                )
                # Send auth success with full state
                state = self.sm.get_state_for_user(keyword, user.name)
                await websocket.send_json({
                    "type": "AUTH_OK",
                    "payload": {
                        "user": {
                            "name": user.name,
                            "role": user.role,
                            "ship_ids": user.ship_ids,
                            "token": user.token,
                        },
                        "state": state,
                    },
                })
                return connection

        # Token failed or not provided — try name + password
        if not name:
            await websocket.send_json({
                "type": "AUTH_FAIL",
                "payload": {"error": "Display name is required."},
            })
            await websocket.close()
            return None

        try:
            user = self.sm.join_session(
                keyword=keyword,
                name=name,
                gm_password=gm_password,
            )
        except (KeyError, ValueError) as e:
            await websocket.send_json({
                "type": "AUTH_FAIL",
                "payload": {"error": str(e)},
            })
            await websocket.close()
            return None

        connection = ClientConnection(
            websocket=websocket,
            keyword=keyword,
            user_name=user.name,
            role=user.role,
        )

        # Send auth success with full state
        state = self.sm.get_state_for_user(keyword, user.name)
        await websocket.send_json({
            "type": "AUTH_OK",
            "payload": {
                "user": {
                    "name": user.name,
                    "role": user.role,
                    "ship_ids": user.ship_ids,
                    "token": user.token,
                },
                "state": state,
            },
        })
        return connection

    async def _message_loop(self, connection: ClientConnection) -> None:
        """
        Main message processing loop for an authenticated connection.

        Reads messages, dispatches to handlers, catches and reports errors.
        """
        while True:
            raw = await connection.websocket.receive_json()

            msg_type = raw.get("type", "")
            payload = raw.get("payload", {})
            request_id = raw.get("request_id", "")

            handler = self._HANDLERS.get(msg_type)
            if not handler:
                await connection.send({
                    "type": "ERROR",
                    "payload": {
                        "error": f"Unknown message type: {msg_type}",
                        "request_id": request_id,
                    },
                })
                continue

            try:
                await handler(connection, payload, request_id)
            except PermissionError as e:
                await connection.send({
                    "type": "ERROR",
                    "payload": {
                        "error": str(e),
                        "request_id": request_id,
                    },
                })
            except (KeyError, ValueError) as e:
                await connection.send({
                    "type": "ERROR",
                    "payload": {
                        "error": str(e),
                        "request_id": request_id,
                    },
                })
            except Exception:
                logger.exception(
                    "Error handling %s from %s",
                    msg_type, connection.user_name,
                )
                await connection.send({
                    "type": "ERROR",
                    "payload": {
                        "error": "Internal server error.",
                        "request_id": request_id,
                    },
                })

    # ------------------------------------------------------------------
    # Room management
    # ------------------------------------------------------------------

    def _add_to_room(self, connection: ClientConnection) -> None:
        """Add a connection to its session's room."""
        keyword = connection.keyword
        if keyword not in self._rooms:
            self._rooms[keyword] = []
        self._rooms[keyword].append(connection)
        logger.debug(
            "Added %s to room %s (%d connections)",
            connection.user_name, keyword, len(self._rooms[keyword]),
        )

    def _remove_from_room(self, connection: ClientConnection) -> None:
        """Remove a connection from its session's room."""
        keyword = connection.keyword
        if keyword in self._rooms:
            self._rooms[keyword] = [
                c for c in self._rooms[keyword]
                if c is not connection
            ]
            if not self._rooms[keyword]:
                del self._rooms[keyword]

    async def _broadcast(self, keyword: str, message: dict) -> None:
        """Send a message to all connections in a session room."""
        connections = self._rooms.get(keyword, [])
        failed = []
        for conn in connections:
            success = await conn.send(message)
            if not success:
                failed.append(conn)
        # Clean up failed connections
        for conn in failed:
            self._remove_from_room(conn)

    async def _broadcast_except(
        self,
        keyword: str,
        exclude_name: str,
        message: dict,
    ) -> None:
        """Send a message to all connections except the named user."""
        connections = self._rooms.get(keyword, [])
        for conn in connections:
            if conn.user_name != exclude_name:
                await conn.send(message)

    async def _broadcast_role_filtered(self, keyword: str, message_factory) -> None:
        """
        Broadcast a message with per-user role filtering.

        Args:
            keyword: Session keyword.
            message_factory: Callable that takes (role: str) and returns
                             the message dict to send, or None to skip.
        """
        connections = self._rooms.get(keyword, [])
        for conn in connections:
            message = message_factory(conn.role)
            if message:
                await conn.send(message)

    async def _send_full_state_to_all(self, keyword: str) -> None:
        """
        Send a role-filtered full state update to every connected client.

        Used after major state changes where incremental updates would
        be more complex than just resending everything.
        """
        connections = self._rooms.get(keyword, [])
        for conn in connections:
            state = self.sm.get_state_for_user(keyword, conn.user_name)
            if state:
                await conn.send({
                    "type": "FULL_STATE",
                    "payload": {"state": state},
                })

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    def _require_setup_powers(self, connection: ClientConnection) -> None:
        """
        Raise PermissionError if user cannot perform setup actions
        (add/remove ships, create engagements, manage factions, etc.).

        GM: always allowed.
        GM-less session: ALL players (HOST and PLAYER) are allowed.
        GM session (non-GM): not allowed.
        """
        if not self.sm.can_edit_ships(connection.keyword, connection.user_name):
            raise PermissionError(
                "You don't have permission for this action. "
                "In GM sessions, only the GM can manage ships and engagements."
            )

    def _require_gm(self, connection: ClientConnection) -> None:
        """Raise PermissionError if user is not GM."""
        if connection.role != UserRole.GM.value:
            raise PermissionError("Only the GM can perform this action.")

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _handle_chat(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle a CHAT message — broadcast to all users."""
        message_text = payload.get("message", "").strip()
        if not message_text:
            return

        timestamp = datetime.now(timezone.utc).isoformat()

        chat_entry = {
            "sender": conn.user_name,
            "message": message_text,
            "timestamp": timestamp,
            "role": conn.role,
        }

        self.sm.add_chat_message(conn.keyword, chat_entry)

        room_size = len(self._rooms.get(conn.keyword, []))
        logger.info(
            "CHAT from '%s' in '%s' — broadcasting to %d connection(s): %s",
            conn.user_name, conn.keyword, room_size, message_text[:50],
        )

        await self._broadcast(conn.keyword, {
            "type": "CHAT_MESSAGE",
            "payload": chat_entry,
        })

    async def _handle_dice_roll(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """
        Handle a DICE_ROLL message — roll via server engine, broadcast result.

        The psi_dice.roll_dice() function may return different formats
        depending on the command (roll, stats, help, about). We normalize
        the result into a consistent dict with 'result' and 'breakdown' keys.
        """
        expression = payload.get("expression", "").strip()
        context = payload.get("context", "").strip()

        if not expression:
            return

        # Roll the dice
        result = None
        if self.dice_roller:
            try:
                raw_result = self.dice_roller(expression)

                # Normalize: psi_dice returns different formats depending on version.
                # Known formats:
                #   - tuple: (total, breakdown_str, is_verbose_bool)
                #   - dict:  {"total": int, "breakdown": str, ...}
                #   - d20 Result object: has .total and __str__
                #   - str: raw text (help, about, stats commands)
                if isinstance(raw_result, tuple):
                    # psi_dice.roll_dice() returns (total, breakdown, verbose_flag)
                    total = raw_result[0] if len(raw_result) > 0 else 0
                    breakdown = raw_result[1] if len(raw_result) > 1 else str(total)
                    result = {
                        "result": str(total),
                        "breakdown": str(breakdown),
                        "total": total,
                    }
                elif isinstance(raw_result, dict):
                    result = {
                        "result": str(raw_result.get("total", raw_result.get("result", "?"))),
                        "breakdown": raw_result.get("breakdown", str(raw_result)),
                        "total": raw_result.get("total", 0),
                    }
                elif isinstance(raw_result, str):
                    result = {
                        "result": raw_result,
                        "breakdown": raw_result,
                        "total": raw_result,
                    }
                else:
                    # d20 library Result object — has .total and str() representation
                    result = {
                        "result": str(getattr(raw_result, 'total', raw_result)),
                        "breakdown": str(raw_result),
                        "total": getattr(raw_result, 'total', 0),
                    }

            except Exception as e:
                logger.warning("Dice roll failed: %s — %s", expression, e)
                await conn.send({
                    "type": "ERROR",
                    "payload": {
                        "error": f"Dice error: {expression} — {e}",
                        "request_id": req_id,
                    },
                })
                return

        if result is None:
            await conn.send({
                "type": "ERROR",
                "payload": {
                    "error": "Dice engine not available.",
                    "request_id": req_id,
                },
            })
            return

        # Determine if verbose
        is_verbose = expression.rstrip().endswith("v")

        # Build dice log entry
        dice_entry = {
            "ship": conn.user_name,
            "context": context or "Roll",
            "expression": expression,
            "result": result.get("result", ""),
            "breakdown": result.get("breakdown", ""),
            "total": result.get("total", 0),
            "is_npc": False,
            "roller": conn.user_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.sm.add_dice_entry(conn.keyword, dice_entry)

        # Broadcast to all (including the roller)
        await self._broadcast(conn.keyword, {
            "type": "DICE_RESULT",
            "payload": {
                "roller": conn.user_name,
                "expression": expression,
                "result": result.get("result", ""),
                "breakdown": result.get("breakdown", ""),
                "is_verbose": is_verbose,
                "context": context,
                "dice_entry": dice_entry,
            },
        })

    async def _handle_add_ship(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle ADD_SHIP — GM/HOST adds a ship to the session."""
        self._require_setup_powers(conn)

        ship_data = payload.get("ship_data", {})
        if not ship_data:
            raise ValueError("Ship data is required.")

        ship_id = self.sm.add_ship(conn.keyword, ship_data)

        # Broadcast the new ship (role-filtered for player visibility)
        await self._send_full_state_to_all(conn.keyword)

    async def _handle_remove_ship(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle REMOVE_SHIP — GM/HOST removes a ship."""
        self._require_setup_powers(conn)

        ship_id = payload.get("ship_id", "")
        if not ship_id:
            raise ValueError("Ship ID is required.")

        removed = self.sm.remove_ship(conn.keyword, ship_id)
        if not removed:
            raise ValueError(f"Ship '{ship_id}' not found.")

        await self._broadcast(conn.keyword, {
            "type": "SHIP_REMOVED",
            "payload": {"ship_id": ship_id},
        })

    async def _handle_update_ship(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """
        Handle UPDATE_SHIP — update ship stats.

        GM can update any ship silently.
        HOST can update any ship (not silently).
        Players can only update their own ships (limited fields).
        """
        ship_id = payload.get("ship_id", "")
        updates = payload.get("updates", {})
        silent = payload.get("silent", False)

        if not ship_id or not updates:
            raise ValueError("Ship ID and updates are required.")

        # Permission check
        if conn.role == UserRole.PLAYER.value:
            # Players can only edit their own ships
            session = self.sm.get_session(conn.keyword)
            user = session.users.get(conn.user_name) if session else None
            if not user or ship_id not in user.ship_ids:
                raise PermissionError("You can only edit your own ships.")
            # Players can't do silent edits
            silent = False

        success = self.sm.update_ship(conn.keyword, ship_id, updates)
        if not success:
            raise ValueError(f"Ship '{ship_id}' not found.")

        # Broadcast: GM silent edits only go to GM, all others go to everyone
        if silent and conn.role == UserRole.GM.value:
            # Only send to GM connections
            connections = self._rooms.get(conn.keyword, [])
            for c in connections:
                if c.role == UserRole.GM.value:
                    await c.send({
                        "type": "SHIP_UPDATED",
                        "payload": {
                            "ship_id": ship_id,
                            "updates": updates,
                            "silent": True,
                        },
                    })
            # But also send full state to non-GM users (so they see
            # the result without knowing it was a silent edit)
            for c in connections:
                if c.role != UserRole.GM.value:
                    state = self.sm.get_state_for_user(conn.keyword, c.user_name)
                    if state:
                        await c.send({
                            "type": "FULL_STATE",
                            "payload": {"state": state},
                        })
        else:
            # Normal update — broadcast to all
            await self._send_full_state_to_all(conn.keyword)

    async def _handle_assign_ship(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle ASSIGN_SHIP — GM/HOST assigns a ship to a player."""
        self._require_setup_powers(conn)

        ship_id = payload.get("ship_id", "")
        player_name = payload.get("player_name", "")

        self.sm.assign_ship(conn.keyword, ship_id, player_name)

        await self._broadcast(conn.keyword, {
            "type": "SHIP_ASSIGNED",
            "payload": {
                "ship_id": ship_id,
                "player_name": player_name,
            },
        })

        # Send full state since visibility may have changed for the assigned player
        await self._send_full_state_to_all(conn.keyword)

    async def _handle_select_ship(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle SELECT_SHIP — player selects a ship in player-select mode."""
        ship_id = payload.get("ship_id", "")

        session = self.sm.get_session(conn.keyword)
        if not session:
            raise KeyError("Session not found.")

        if session.ship_assign_mode != "player_select":
            raise PermissionError("Ship selection is not enabled in this session.")

        self.sm.assign_ship(conn.keyword, ship_id, conn.user_name)

        await self._broadcast(conn.keyword, {
            "type": "SHIP_ASSIGNED",
            "payload": {
                "ship_id": ship_id,
                "player_name": conn.user_name,
            },
        })

        await self._send_full_state_to_all(conn.keyword)

    async def _handle_unassign_ship(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle UNASSIGN_SHIP — GM/HOST removes a ship assignment."""
        self._require_setup_powers(conn)

        ship_id = payload.get("ship_id", "")
        player_name = payload.get("player_name", "")

        self.sm.unassign_ship(conn.keyword, ship_id, player_name)

        await self._broadcast(conn.keyword, {
            "type": "SHIP_UNASSIGNED",
            "payload": {
                "ship_id": ship_id,
                "player_name": player_name,
            },
        })

        await self._send_full_state_to_all(conn.keyword)

    async def _handle_add_engagement(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle ADD_ENGAGEMENT — GM/HOST creates an engagement."""
        self._require_setup_powers(conn)

        engagement = {
            "ship_a_id": payload.get("ship_a_id", ""),
            "ship_b_id": payload.get("ship_b_id", ""),
            "range_band": payload.get("range_band", "long"),
            "advantage": None,
            "matched_speed": False,
            "hugging": None,
        }

        self.sm.add_engagement(conn.keyword, engagement)

        await self._broadcast(conn.keyword, {
            "type": "ENGAGEMENT_ADDED",
            "payload": {"engagement": engagement},
        })

    async def _handle_remove_engagement(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle REMOVE_ENGAGEMENT — GM/HOST removes an engagement."""
        self._require_setup_powers(conn)

        ship_a_id = payload.get("ship_a_id", "")
        ship_b_id = payload.get("ship_b_id", "")

        removed = self.sm.remove_engagement(conn.keyword, ship_a_id, ship_b_id)
        if not removed:
            raise ValueError("Engagement not found.")

        await self._broadcast(conn.keyword, {
            "type": "ENGAGEMENT_REMOVED",
            "payload": {
                "ship_a_id": ship_a_id,
                "ship_b_id": ship_b_id,
            },
        })

    async def _handle_update_engagement(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle UPDATE_ENGAGEMENT — update engagement state."""
        self._require_setup_powers(conn)

        ship_a_id = payload.get("ship_a_id", "")
        ship_b_id = payload.get("ship_b_id", "")
        updates = payload.get("updates", {})

        success = self.sm.update_engagement(conn.keyword, ship_a_id, ship_b_id, updates)
        if not success:
            raise ValueError("Engagement not found.")

        await self._broadcast(conn.keyword, {
            "type": "ENGAGEMENT_UPDATED",
            "payload": {
                "ship_a_id": ship_a_id,
                "ship_b_id": ship_b_id,
                "updates": updates,
            },
        })

    async def _handle_update_active_state(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle UPDATE_ACTIVE_STATE — update turn counter, active ship, etc."""
        self._require_setup_powers(conn)

        updates = payload.get("updates", {})
        self.sm.update_active_state(conn.keyword, updates)

        await self._broadcast(conn.keyword, {
            "type": "ACTIVE_STATE_UPDATED",
            "payload": {"active_state": updates},
        })

    async def _handle_set_session_status(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle SET_SESSION_STATUS — change session lifecycle state."""
        self._require_setup_powers(conn)

        status = payload.get("status", "")
        self.sm.set_session_status(conn.keyword, status)

        await self._broadcast(conn.keyword, {
            "type": "SESSION_STATUS_CHANGED",
            "payload": {"status": status},
        })

    async def _handle_update_settings(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle UPDATE_SETTINGS — change session settings."""
        self._require_setup_powers(conn)

        settings = payload.get("settings", {})
        session = self.sm.get_session(conn.keyword)
        if session:
            session.settings.update(settings)
            self.sm._save_session(session)

        await self._broadcast(conn.keyword, {
            "type": "SETTINGS_UPDATED",
            "payload": {"settings": settings},
        })

    async def _handle_undo(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle UNDO — GM only. Placeholder for future engine integration."""
        self._require_gm(conn)
        # TODO: Implement undo when engine is wired in
        await conn.send({
            "type": "ERROR",
            "payload": {
                "error": "Undo is not yet implemented.",
                "request_id": req_id,
            },
        })

    async def _handle_redo(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """Handle REDO — GM only. Placeholder for future engine integration."""
        self._require_gm(conn)
        # TODO: Implement redo when engine is wired in
        await conn.send({
            "type": "ERROR",
            "payload": {
                "error": "Redo is not yet implemented.",
                "request_id": req_id,
            },
        })

    async def _handle_toggle_see_stats(self, conn: ClientConnection, payload: dict, req_id: str) -> None:
        """
        Handle TOGGLE_SEE_STATS — player toggles their "see all stats" preference.

        When ALL connected non-GM players have see_stats=True, the server
        sends a full state update to everyone with complete ship data.
        When any player turns it off, everyone reverts to filtered views.

        This is a consensus mechanism: one holdout blocks visibility for all.
        The UI shows each player's toggle state so there's social pressure
        to opt in (or a clear reason why someone hasn't).
        """
        value = payload.get("value", False)

        consensus = self.sm.set_see_stats(conn.keyword, conn.user_name, value)
        if consensus is None:
            return

        # Broadcast the updated toggle state to all clients
        # Every client gets: who toggled, their new value, and the consensus
        await self._broadcast(conn.keyword, {
            "type": "SEE_STATS_CHANGED",
            "payload": {
                "user_name": conn.user_name,
                "value": value,
                "consensus": consensus,
            },
        })

        # If consensus changed, push full state to everyone (visibility changed)
        await self._send_full_state_to_all(conn.keyword)
