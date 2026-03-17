"""
WebSocket Protocol — Psi-Wars Web UI
=====================================

Defines all message types exchanged between client and server over
WebSocket. This module is a reference — both the server (ws_handler.py)
and the frontend (ws-client.js) implement this protocol.

Protocol overview:
  - All messages are JSON objects with a required "type" field.
  - Client → Server messages are "actions" (requests to mutate state).
  - Server → Client messages are "events" (state updates to render).
  - The server is the source of truth. Clients never mutate local state
    directly; they send an action and wait for the server event.

Connection flow:
  1. Client opens WebSocket to /ws/{keyword}
  2. Client sends AUTH message (name + token or name + gm_password)
  3. Server responds with AUTH_OK (full state) or AUTH_FAIL (error)
  4. Bidirectional message exchange begins
  5. On disconnect, server marks user as disconnected
  6. On reconnect, client sends AUTH with stored token

Message format:
  {
    "type": "MESSAGE_TYPE",
    "payload": { ... }     # Type-specific data
    "request_id": "abc"    # Optional, for client-side request tracking
  }

Modification guide:
  - To add a new client action: add to CLIENT_MESSAGES, implement in ws_handler.py
  - To add a new server event: add to SERVER_MESSAGES, handle in ws-client.js
  - To change auth flow: modify AUTH/AUTH_OK/AUTH_FAIL messages
"""

# ---------------------------------------------------------------------------
# Client → Server message types
# ---------------------------------------------------------------------------

CLIENT_MESSAGES = {
    # --- Authentication ---
    "AUTH": {
        "description": "Authenticate with the session. Sent first after connect.",
        "payload": {
            "name": "str — Display name",
            "token": "str — Reconnection token (from localStorage), or empty",
            "gm_password": "str — GM password (for initial GM join), or empty",
        },
    },

    # --- Chat ---
    "CHAT": {
        "description": "Send a chat message to all connected users.",
        "payload": {
            "message": "str — Chat message text",
        },
    },

    # --- Dice ---
    "DICE_ROLL": {
        "description": "Request a dice roll through the server-side engine.",
        "payload": {
            "expression": "str — Dice expression (e.g. '3d6', '3d6+4v')",
            "context": "str — Optional context text around the roll",
        },
    },

    # --- Ship management (GM/HOST only) ---
    "ADD_SHIP": {
        "description": "Add a ship to the session.",
        "payload": {
            "ship_data": "dict — Full ship data (API contract format)",
        },
    },
    "REMOVE_SHIP": {
        "description": "Remove a ship from the session.",
        "payload": {
            "ship_id": "str — ID of the ship to remove",
        },
    },
    "UPDATE_SHIP": {
        "description": "Update ship stats (GM click-to-edit, subsystem cycling).",
        "payload": {
            "ship_id": "str — ID of the ship to update",
            "updates": "dict — Partial ship data to merge",
            "silent": "bool — If true, don't add to combat log (GM edits)",
        },
    },
    "ASSIGN_SHIP": {
        "description": "Assign a ship to a player (GM/HOST only).",
        "payload": {
            "ship_id": "str — ID of the ship",
            "player_name": "str — Name of the player",
        },
    },
    "SELECT_SHIP": {
        "description": "Player selects a ship (player-select mode only).",
        "payload": {
            "ship_id": "str — ID of the ship to claim",
        },
    },
    "UNASSIGN_SHIP": {
        "description": "Remove a ship assignment (GM/HOST only).",
        "payload": {
            "ship_id": "str — ID of the ship",
            "player_name": "str — Name of the player",
        },
    },

    # --- Engagement management (GM/HOST only) ---
    "ADD_ENGAGEMENT": {
        "description": "Create an engagement between two ships.",
        "payload": {
            "ship_a_id": "str",
            "ship_b_id": "str",
            "range_band": "str — close/medium/long/extreme",
        },
    },
    "REMOVE_ENGAGEMENT": {
        "description": "Remove an engagement between two ships.",
        "payload": {
            "ship_a_id": "str",
            "ship_b_id": "str",
        },
    },
    "UPDATE_ENGAGEMENT": {
        "description": "Update engagement state (range, advantage, etc.).",
        "payload": {
            "ship_a_id": "str",
            "ship_b_id": "str",
            "updates": "dict — Partial engagement data to merge",
        },
    },

    # --- Combat controls (GM only) ---
    "UNDO": {
        "description": "Undo the last action. GM only.",
        "payload": {},
    },
    "REDO": {
        "description": "Redo the last undone action. GM only.",
        "payload": {},
    },
    "PAUSE_COMBAT": {
        "description": "Pause or unpause combat. GM only.",
        "payload": {},
    },
    "END_COMBAT": {
        "description": "End the combat session. GM only.",
        "payload": {},
    },
    "SET_SESSION_STATUS": {
        "description": "Change session status (setup/active/paused/complete).",
        "payload": {
            "status": "str — New status value",
        },
    },

    # --- Session settings (GM/HOST only) ---
    "UPDATE_SETTINGS": {
        "description": "Update session settings (e.g. hide_npc_rolls).",
        "payload": {
            "settings": "dict — Settings to merge",
        },
    },

    # --- See Stats toggle (any player) ---
    "TOGGLE_SEE_STATS": {
        "description": "Toggle this player's 'see all stats' preference. "
                       "When ALL connected non-GM players have it on, everyone "
                       "sees full stats for all ships.",
        "payload": {
            "value": "bool — True to opt in, False to opt out",
        },
    },

    # --- Active state ---
    "UPDATE_ACTIVE_STATE": {
        "description": "Update combat active state (turn, active ship, targets).",
        "payload": {
            "updates": "dict — Partial active state to merge",
        },
    },
}


# ---------------------------------------------------------------------------
# Server → Client message types
# ---------------------------------------------------------------------------

SERVER_MESSAGES = {
    # --- Authentication ---
    "AUTH_OK": {
        "description": "Authentication succeeded. Includes full session state.",
        "payload": {
            "user": "dict — {name, role, ship_ids, token}",
            "state": "dict — Full session state (role-filtered)",
        },
    },
    "AUTH_FAIL": {
        "description": "Authentication failed.",
        "payload": {
            "error": "str — Human-readable error message",
        },
    },

    # --- State sync ---
    "FULL_STATE": {
        "description": "Complete session state push (after major changes).",
        "payload": {
            "state": "dict — Full session state (role-filtered)",
        },
    },
    "SHIP_UPDATED": {
        "description": "A ship's data changed. Partial update.",
        "payload": {
            "ship_id": "str",
            "updates": "dict — Changed fields only",
            "silent": "bool — If true, this was a GM silent edit",
        },
    },
    "SHIP_ADDED": {
        "description": "A new ship was added to the session.",
        "payload": {
            "ship": "dict — Full ship data (role-filtered)",
        },
    },
    "SHIP_REMOVED": {
        "description": "A ship was removed from the session.",
        "payload": {
            "ship_id": "str",
        },
    },
    "SHIP_ASSIGNED": {
        "description": "A ship was assigned to a player.",
        "payload": {
            "ship_id": "str",
            "player_name": "str",
        },
    },
    "SHIP_UNASSIGNED": {
        "description": "A ship assignment was removed.",
        "payload": {
            "ship_id": "str",
            "player_name": "str",
        },
    },

    # --- Engagement sync ---
    "ENGAGEMENT_ADDED": {
        "description": "A new engagement was created.",
        "payload": {
            "engagement": "dict — Full engagement data",
        },
    },
    "ENGAGEMENT_REMOVED": {
        "description": "An engagement was removed.",
        "payload": {
            "ship_a_id": "str",
            "ship_b_id": "str",
        },
    },
    "ENGAGEMENT_UPDATED": {
        "description": "An engagement was updated.",
        "payload": {
            "ship_a_id": "str",
            "ship_b_id": "str",
            "updates": "dict",
        },
    },

    # --- Log events ---
    "COMBAT_LOG_ENTRY": {
        "description": "New entry in the combat log.",
        "payload": {
            "entry": "dict — {message, event_type, turn}",
        },
    },
    "CHAT_MESSAGE": {
        "description": "New chat message from a user.",
        "payload": {
            "sender": "str — Display name of sender",
            "message": "str — Message text",
            "timestamp": "str — ISO timestamp",
            "role": "str — Sender's role (for styling)",
        },
    },
    "DICE_RESULT": {
        "description": "Result of a dice roll.",
        "payload": {
            "roller": "str — Who rolled",
            "expression": "str — Original expression",
            "result": "str — Formatted result string",
            "breakdown": "str — Full breakdown (for hover)",
            "is_verbose": "bool — Whether breakdown should show inline",
            "dice_entry": "dict — Full dice log entry for GM panel",
        },
    },

    # --- User events ---
    "USER_JOINED": {
        "description": "A user connected to the session.",
        "payload": {
            "name": "str",
            "role": "str",
        },
    },
    "USER_LEFT": {
        "description": "A user disconnected.",
        "payload": {
            "name": "str",
        },
    },

    # --- Active state ---
    "ACTIVE_STATE_UPDATED": {
        "description": "Combat active state changed (turn, active ship, etc.).",
        "payload": {
            "active_state": "dict",
        },
    },

    # --- Session status ---
    "SESSION_STATUS_CHANGED": {
        "description": "Session status changed.",
        "payload": {
            "status": "str",
        },
    },

    # --- Settings ---
    "SETTINGS_UPDATED": {
        "description": "Session settings changed.",
        "payload": {
            "settings": "dict",
        },
    },

    # --- See Stats consensus ---
    "SEE_STATS_CHANGED": {
        "description": "A player toggled their 'see all stats' preference, "
                       "or the consensus state changed.",
        "payload": {
            "user_name": "str — Who toggled",
            "value": "bool — Their new value",
            "consensus": "bool — Whether ALL players now have it on",
        },
    },

    # --- Error ---
    "ERROR": {
        "description": "Server-side error in response to a client action.",
        "payload": {
            "error": "str — Human-readable error message",
            "request_id": "str — Echoed from client request, if provided",
        },
    },
}
