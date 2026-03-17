"""
Faction Manager — Psi-Wars Web UI
===================================

Manages factions within a game session:
  - Create and remove factions with colors
  - Asymmetric faction relationships (hostile/neutral/friendly)
  - Auto-escalation when NPC factions are attacked
  - Targeting warning checks and acknowledgment tracking

This module operates on session state dicts passed in by the
SessionManager. It does not access sessions directly and has
no dependency on SessionManager, WebSocket, or any other module.

Design notes:
  - Factions are stored as a list of dicts in session state.
  - Relationships are stored as a dict keyed by "FactionA→FactionB".
  - This asymmetric key format means Empire→Alliance and
    Alliance→Empire are separate entries with potentially
    different values.
  - Auto-escalation only applies to NPC-controlled factions.
  - Targeting warnings are tracked per attacker-faction → target-faction
    pair, acknowledged once per session.

Usage (called by SessionManager):
    from faction_manager import FactionManager
    fm = FactionManager()

    fm.create_faction(session_state, "Empire", "#60a5fa")
    fm.set_relationship(session_state, "Empire", "Alliance", "hostile")
    rel = fm.get_relationship(session_state, "Empire", "Alliance")

Modification guide:
    - To add new relationship types: add to VALID_RELATIONSHIPS
    - To change default relationship: edit DEFAULT_RELATIONSHIP
    - To change escalation rules: edit escalate_relationship()
    - To change warning behavior: edit check_targeting_warning()
    - To change the default faction: edit DEFAULT_FACTION_*
    - To change color palette: edit FACTION_COLOR_PALETTE
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_RELATIONSHIPS = {"hostile", "neutral", "friendly"}
DEFAULT_RELATIONSHIP = "neutral"

# Escalation order: friendly → neutral → hostile
ESCALATION_ORDER = ["friendly", "neutral", "hostile"]

# Default faction created automatically when the first ship is added
DEFAULT_FACTION_NAME = "NPC Hostiles"
DEFAULT_FACTION_COLOR = "#f87171"

# Color palette for new factions. Assigned round-robin when the user
# doesn't specify a color. These are chosen for high contrast on a
# dark background.
FACTION_COLOR_PALETTE = [
    "#f87171",  # red
    "#60a5fa",  # blue
    "#4ade80",  # green
    "#facc15",  # yellow
    "#c084fc",  # purple
    "#fb923c",  # orange
    "#2dd4bf",  # teal
    "#f472b6",  # pink
    "#a78bfa",  # violet
    "#38bdf8",  # sky
]


# ---------------------------------------------------------------------------
# Data structure helpers
# ---------------------------------------------------------------------------

def _relationship_key(from_faction: str, to_faction: str) -> str:
    """
    Build the asymmetric relationship key.

    Format: "FactionA→FactionB"
    This means "how FactionA views FactionB."
    """
    return f"{from_faction}→{to_faction}"


def _ensure_faction_fields(state_dict: dict) -> None:
    """
    Ensure the session state dict has the required faction fields.

    Called at the start of every public method to handle sessions
    created before faction support was added (backward compatibility).
    Mutates the dict in place.
    """
    if "factions" not in state_dict:
        state_dict["factions"] = []
    if "faction_relationships" not in state_dict:
        state_dict["faction_relationships"] = {}
    if "targeting_warnings_acknowledged" not in state_dict:
        state_dict["targeting_warnings_acknowledged"] = []


# ---------------------------------------------------------------------------
# Faction Manager
# ---------------------------------------------------------------------------

class FactionManager:
    """
    Stateless manager for faction operations.

    All methods take a session state dict (or the relevant sub-fields)
    and mutate it in place. The SessionManager is responsible for
    persisting changes after calling these methods.

    This class is intentionally stateless so it can be shared across
    sessions and tested without SessionManager.
    """

    # ------------------------------------------------------------------
    # Faction CRUD
    # ------------------------------------------------------------------

    def create_faction(
        self,
        state: dict,
        name: str,
        color: str = "",
    ) -> dict:
        """
        Create a new faction in the session.

        Args:
            state: Session state dict (mutated in place).
            name:  Faction name. Must be unique within the session.
            color: CSS color string (e.g. "#60a5fa"). If empty, one
                   is assigned from the palette.

        Returns:
            The new faction dict.

        Raises:
            ValueError: If a faction with this name already exists.
        """
        _ensure_faction_fields(state)

        # Check for duplicates
        existing_names = {f["name"] for f in state["factions"]}
        if name in existing_names:
            raise ValueError(f"Faction '{name}' already exists.")

        # Assign a color if not provided
        if not color:
            used_colors = {f.get("color", "") for f in state["factions"]}
            for palette_color in FACTION_COLOR_PALETTE:
                if palette_color not in used_colors:
                    color = palette_color
                    break
            else:
                # All palette colors used — cycle back to first
                color = FACTION_COLOR_PALETTE[len(state["factions"]) % len(FACTION_COLOR_PALETTE)]

        faction = {
            "name": name,
            "color": color,
            "is_default": (name == DEFAULT_FACTION_NAME),
        }
        state["factions"].append(faction)

        # Set default relationships with all existing factions
        for existing in state["factions"]:
            if existing["name"] == name:
                continue
            # Both directions default to neutral
            key_forward = _relationship_key(name, existing["name"])
            key_reverse = _relationship_key(existing["name"], name)
            state["faction_relationships"].setdefault(key_forward, DEFAULT_RELATIONSHIP)
            state["faction_relationships"].setdefault(key_reverse, DEFAULT_RELATIONSHIP)

        logger.info("Created faction: %s (%s)", name, color)
        return faction

    def get_factions(self, state: dict) -> list[dict]:
        """
        Get all factions in the session.

        Returns a list of faction dicts. Each has: name, color, is_default.
        """
        _ensure_faction_fields(state)
        return state["factions"]

    def get_faction(self, state: dict, name: str) -> Optional[dict]:
        """Get a single faction by name, or None if not found."""
        _ensure_faction_fields(state)
        for f in state["factions"]:
            if f["name"] == name:
                return f
        return None

    def remove_faction(self, state: dict, name: str) -> dict:
        """
        Remove a faction from the session.

        Ships assigned to the removed faction KEEP their faction tag
        but are flagged as orphaned. The caller should alert users.

        Args:
            state: Session state dict (mutated in place).
            name:  Faction name to remove.

        Returns:
            A result dict with:
                "removed": name of removed faction
                "orphaned_ships": list of ship_ids that still reference it

        Raises:
            KeyError: Faction not found.
        """
        _ensure_faction_fields(state)

        # Find and remove the faction
        original_count = len(state["factions"])
        state["factions"] = [f for f in state["factions"] if f["name"] != name]

        if len(state["factions"]) == original_count:
            raise KeyError(f"Faction '{name}' not found.")

        # Clean up relationships involving this faction
        keys_to_remove = [
            k for k in state["faction_relationships"]
            if name in k.split("→")
        ]
        for k in keys_to_remove:
            del state["faction_relationships"][k]

        # Find orphaned ships
        orphaned = []
        ships = state.get("ships", [])
        for ship in ships:
            if ship.get("faction") == name:
                ship["faction_orphaned"] = True
                orphaned.append(ship.get("ship_id", "unknown"))

        logger.info(
            "Removed faction '%s'. %d orphaned ship(s).",
            name, len(orphaned),
        )
        return {
            "removed": name,
            "orphaned_ships": orphaned,
        }

    def update_faction(
        self,
        state: dict,
        name: str,
        new_name: str = "",
        new_color: str = "",
    ) -> None:
        """
        Update a faction's name or color.

        If the name changes, all references (ships, relationships,
        warnings) are updated to match.

        Args:
            state:     Session state dict.
            name:      Current faction name.
            new_name:  New name (empty to keep current).
            new_color: New color (empty to keep current).

        Raises:
            KeyError:   Faction not found.
            ValueError: New name conflicts with an existing faction.
        """
        _ensure_faction_fields(state)

        faction = self.get_faction(state, name)
        if not faction:
            raise KeyError(f"Faction '{name}' not found.")

        if new_color:
            faction["color"] = new_color

        if new_name and new_name != name:
            # Check for conflicts
            if any(f["name"] == new_name for f in state["factions"]):
                raise ValueError(f"Faction '{new_name}' already exists.")

            # Update faction name
            faction["name"] = new_name

            # Update ship references
            for ship in state.get("ships", []):
                if ship.get("faction") == name:
                    ship["faction"] = new_name

            # Update relationship keys
            new_rels = {}
            for key, value in state["faction_relationships"].items():
                new_key = key.replace(f"{name}→", f"{new_name}→").replace(f"→{name}", f"→{new_name}")
                new_rels[new_key] = value
            state["faction_relationships"] = new_rels

            # Update warning acknowledgments
            state["targeting_warnings_acknowledged"] = [
                w.replace(f"{name}→", f"{new_name}→").replace(f"→{name}", f"→{new_name}")
                for w in state["targeting_warnings_acknowledged"]
            ]

    def ensure_default_faction(self, state: dict) -> None:
        """
        Ensure the default "NPC Hostiles" faction exists.

        Called automatically when the first ship is added to a session.
        Safe to call multiple times — does nothing if the faction
        already exists.
        """
        _ensure_faction_fields(state)
        existing_names = {f["name"] for f in state["factions"]}
        if DEFAULT_FACTION_NAME not in existing_names:
            self.create_faction(state, DEFAULT_FACTION_NAME, DEFAULT_FACTION_COLOR)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def set_relationship(
        self,
        state: dict,
        from_faction: str,
        to_faction: str,
        relationship: str,
    ) -> None:
        """
        Set the relationship from one faction toward another.

        This is directional: setting Empire→Alliance to "hostile"
        does NOT change Alliance→Empire.

        Args:
            state:        Session state dict.
            from_faction: The faction whose stance is being set.
            to_faction:   The faction being viewed.
            relationship: One of "hostile", "neutral", "friendly".

        Raises:
            ValueError: Invalid relationship value.
            KeyError:   Either faction not found.
        """
        _ensure_faction_fields(state)

        if relationship not in VALID_RELATIONSHIPS:
            raise ValueError(
                f"Invalid relationship '{relationship}'. "
                f"Must be one of: {', '.join(sorted(VALID_RELATIONSHIPS))}"
            )

        # Verify both factions exist
        faction_names = {f["name"] for f in state["factions"]}
        if from_faction not in faction_names:
            raise KeyError(f"Faction '{from_faction}' not found.")
        if to_faction not in faction_names:
            raise KeyError(f"Faction '{to_faction}' not found.")
        if from_faction == to_faction:
            raise ValueError("Cannot set a faction's relationship with itself.")

        key = _relationship_key(from_faction, to_faction)
        state["faction_relationships"][key] = relationship

        logger.debug("Set relationship %s = %s", key, relationship)

    def get_relationship(
        self,
        state: dict,
        from_faction: str,
        to_faction: str,
    ) -> str:
        """
        Get the relationship from one faction toward another.

        Returns "neutral" if no explicit relationship is set.
        """
        _ensure_faction_fields(state)
        key = _relationship_key(from_faction, to_faction)
        return state["faction_relationships"].get(key, DEFAULT_RELATIONSHIP)

    def get_all_relationships(self, state: dict) -> dict[str, str]:
        """Get the full relationship map (key → relationship)."""
        _ensure_faction_fields(state)
        return dict(state["faction_relationships"])

    # ------------------------------------------------------------------
    # Auto-escalation
    # ------------------------------------------------------------------

    def escalate_relationship(
        self,
        state: dict,
        attacker_faction: str,
        defender_faction: str,
    ) -> Optional[str]:
        """
        Escalate an NPC faction's relationship when attacked.

        When a ship of attacker_faction attacks a ship of
        defender_faction, and defender_faction is NPC-controlled,
        the defender's outgoing relationship toward the attacker
        escalates: friendly → neutral → hostile.

        This simulates NPCs becoming hostile when provoked.

        Args:
            state:            Session state dict.
            attacker_faction: Faction that initiated the attack.
            defender_faction: Faction being attacked (must be NPC-controlled).

        Returns:
            The new relationship value, or None if no change occurred
            (already hostile, or defender is not NPC-controlled).
        """
        _ensure_faction_fields(state)

        # Get current relationship: how defender views attacker
        current = self.get_relationship(state, defender_faction, attacker_faction)

        if current == "hostile":
            return None  # Already hostile, no change

        # Escalate one step
        try:
            current_idx = ESCALATION_ORDER.index(current)
        except ValueError:
            return None

        if current_idx >= len(ESCALATION_ORDER) - 1:
            return None  # Already at maximum hostility

        new_rel = ESCALATION_ORDER[current_idx + 1]

        key = _relationship_key(defender_faction, attacker_faction)
        state["faction_relationships"][key] = new_rel

        logger.info(
            "Auto-escalation: %s→%s changed from %s to %s",
            defender_faction, attacker_faction, current, new_rel,
        )
        return new_rel

    # ------------------------------------------------------------------
    # Targeting warnings
    # ------------------------------------------------------------------

    def check_targeting_warning(
        self,
        state: dict,
        attacker_ship: dict,
        target_ship: dict,
    ) -> Optional[str]:
        """
        Check if a targeting warning should be shown.

        A warning is shown when the attacker's faction considers
        the target's faction neutral or friendly, AND the warning
        hasn't been acknowledged yet for this faction pair.

        Args:
            state:          Session state dict.
            attacker_ship:  The ship that wants to target (dict with "faction").
            target_ship:    The ship being targeted (dict with "faction").

        Returns:
            A warning message string, or None if no warning needed.
        """
        _ensure_faction_fields(state)

        attacker_faction = attacker_ship.get("faction", "")
        target_faction = target_ship.get("faction", "")

        if not attacker_faction or not target_faction:
            return None
        if attacker_faction == target_faction:
            return None  # Same faction — no warning

        # Get the attacker's view of the target's faction
        relationship = self.get_relationship(state, attacker_faction, target_faction)

        if relationship == "hostile":
            return None  # Expected behavior, no warning

        # Check if already acknowledged
        ack_key = _relationship_key(attacker_faction, target_faction)
        if ack_key in state["targeting_warnings_acknowledged"]:
            return None  # Already acknowledged

        # Generate warning
        if relationship == "neutral":
            return (
                f"{attacker_faction} considers {target_faction} neutral. "
                f"Continue targeting?"
            )
        elif relationship == "friendly":
            return (
                f"{attacker_faction} considers {target_faction} friendly. "
                f"Continue targeting?"
            )

        return None

    def acknowledge_targeting_warning(
        self,
        state: dict,
        attacker_faction: str,
        target_faction: str,
    ) -> None:
        """
        Acknowledge a targeting warning so it doesn't repeat.

        Args:
            state:            Session state dict.
            attacker_faction: The faction that initiated targeting.
            target_faction:   The faction being targeted.
        """
        _ensure_faction_fields(state)
        ack_key = _relationship_key(attacker_faction, target_faction)
        if ack_key not in state["targeting_warnings_acknowledged"]:
            state["targeting_warnings_acknowledged"].append(ack_key)
