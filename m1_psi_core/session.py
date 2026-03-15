"""
Game Session Manager for M1 Psi-Core.

Orchestrates a complete combat game session: faction relationships,
ship registration, engagement tracking, turn ordering, NPC AI
integration, combat end detection, and force screen regeneration.

This module sits between the rules engine (M1) and the terminal UI.
It manages all game state that isn't persisted to the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from m1_psi_core.combat_state import EngagementState
from m1_psi_core.npc_ai import (
    assess_situation, StandardAI, AIDecision,
)


# ---------------------------------------------------------------------------
# Faction
# ---------------------------------------------------------------------------

@dataclass
class Faction:
    """A faction in the combat session."""
    name: str
    color: str = "white"


# Valid relationship types
VALID_RELATIONSHIPS = {"allied", "enemy", "neutral"}


# ---------------------------------------------------------------------------
# Ship Registration
# ---------------------------------------------------------------------------

@dataclass
class RegisteredShip:
    """A ship registered in the session with its pilot and metadata."""
    ship_id: str
    ship_stats: object      # MockShipStats or EffectiveStatBlock
    pilot: object            # MockPilot or real pilot data
    faction: str
    control: str             # "human", "npc", "gm"


# ---------------------------------------------------------------------------
# Game Session
# ---------------------------------------------------------------------------

class GameSession:
    """
    Manages a complete combat session.

    Tracks factions, ships, engagements, turn state, and provides
    the interface that the terminal UI calls into.
    """

    def __init__(self):
        self._factions: dict[str, Faction] = {}
        self._relationships: dict[tuple[str, str], str] = {}
        self._ships: dict[str, RegisteredShip] = {}
        self._engagements: dict[tuple[str, str], EngagementState] = {}
        self.current_turn: int = 1
        self._ai = StandardAI()

    # -------------------------------------------------------------------
    # Faction Management
    # -------------------------------------------------------------------

    def add_faction(self, name: str, color: str = "white") -> None:
        """Add a faction to the session."""
        self._factions[name] = Faction(name=name, color=color)

    @property
    def factions(self) -> dict[str, Faction]:
        """All factions in the session."""
        return dict(self._factions)

    def get_faction_color(self, faction_name: str) -> str:
        """Get the display color for a faction."""
        f = self._factions.get(faction_name)
        return f.color if f else "white"

    def set_relationship(self, faction_a: str, faction_b: str, relationship: str) -> None:
        """
        Set the relationship between two factions. Symmetric.

        Valid relationships: "allied", "enemy", "neutral".
        """
        if relationship not in VALID_RELATIONSHIPS:
            raise ValueError(
                f"Invalid relationship '{relationship}'. "
                f"Must be one of: {sorted(VALID_RELATIONSHIPS)}"
            )
        # Store both directions for easy lookup
        self._relationships[(faction_a, faction_b)] = relationship
        self._relationships[(faction_b, faction_a)] = relationship

    def get_relationship(self, faction_a: str, faction_b: str) -> str:
        """
        Get the relationship between two factions.

        Returns "neutral" if no relationship has been set.
        """
        if faction_a == faction_b:
            return "allied"
        return self._relationships.get((faction_a, faction_b), "neutral")

    def register_hostile_action(self, aggressor_faction: str, target_faction: str) -> None:
        """
        Register that one faction attacked another.

        Neutral or allied factions become enemies on hostile action.
        """
        current = self.get_relationship(aggressor_faction, target_faction)
        if current in ("neutral", "allied"):
            self.set_relationship(aggressor_faction, target_faction, "enemy")

    def is_valid_target(self, attacker_faction: str, target_faction: str) -> bool:
        """
        Check if a faction can target another.

        Only enemies are valid targets. Allies and neutrals are not.
        """
        return self.get_relationship(attacker_faction, target_faction) == "enemy"

    # -------------------------------------------------------------------
    # Ship Registration
    # -------------------------------------------------------------------

    def register_ship(
        self,
        ship_id: str,
        ship_stats: object,
        pilot: object,
        faction: str,
        control: str,
    ) -> None:
        """
        Register a ship in the session.

        Args:
            ship_id: Unique identifier for this ship instance.
            ship_stats: Ship stat block (MockShipStats or EffectiveStatBlock).
            pilot: Pilot stat block (MockPilot or real pilot data).
            faction: Which faction this ship belongs to.
            control: Control mode — "human", "npc", or "gm".
        """
        self._ships[ship_id] = RegisteredShip(
            ship_id=ship_id,
            ship_stats=ship_stats,
            pilot=pilot,
            faction=faction,
            control=control,
        )

    def get_ship(self, ship_id: str) -> Optional[object]:
        """Get a ship's stat block by ID."""
        reg = self._ships.get(ship_id)
        return reg.ship_stats if reg else None

    def get_pilot(self, ship_id: str) -> Optional[object]:
        """Get a ship's pilot by ship ID."""
        reg = self._ships.get(ship_id)
        return reg.pilot if reg else None

    def get_control_mode(self, ship_id: str) -> Optional[str]:
        """Get a ship's control mode."""
        reg = self._ships.get(ship_id)
        return reg.control if reg else None

    def get_faction_for_ship(self, ship_id: str) -> Optional[str]:
        """Get the faction a ship belongs to."""
        reg = self._ships.get(ship_id)
        return reg.faction if reg else None

    def get_ships_in_faction(self, faction: str) -> list[str]:
        """Get all ship IDs belonging to a faction."""
        return [
            sid for sid, reg in self._ships.items()
            if reg.faction == faction
        ]

    def get_all_ship_ids(self) -> list[str]:
        """Get all registered ship IDs."""
        return list(self._ships.keys())

    # -------------------------------------------------------------------
    # Engagement Management
    # -------------------------------------------------------------------

    def create_engagement(
        self,
        ship_a_id: str,
        ship_b_id: str,
        range_band: str = "long",
    ) -> EngagementState:
        """
        Create an engagement between two ships.

        The engagement key is always stored with the lower ID first
        so lookups are order-independent.
        """
        key = self._engagement_key(ship_a_id, ship_b_id)
        eng = EngagementState(
            ship_a_id=key[0],
            ship_b_id=key[1],
            range_band=range_band,
        )
        self._engagements[key] = eng
        return eng

    def get_engagement(self, ship_a_id: str, ship_b_id: str) -> Optional[EngagementState]:
        """Get the engagement state between two ships."""
        key = self._engagement_key(ship_a_id, ship_b_id)
        return self._engagements.get(key)

    def get_engagements_for_ship(self, ship_id: str) -> list[EngagementState]:
        """Get all engagements involving a specific ship."""
        result = []
        for key, eng in self._engagements.items():
            if ship_id in key:
                result.append(eng)
        return result

    @staticmethod
    def _engagement_key(a: str, b: str) -> tuple[str, str]:
        """Normalize engagement key so order doesn't matter."""
        return (min(a, b), max(a, b))

    # -------------------------------------------------------------------
    # Turn Ordering
    # -------------------------------------------------------------------

    def get_declaration_order(self) -> list[str]:
        """
        Determine the order in which ships declare maneuvers.

        Slower / non-advantaged ships declare first.
        Faster / advantaged ships declare second (and resolve first).

        Returns list of ship IDs in declaration order.
        """
        ship_ids = self.get_all_ship_ids()

        # Build sort key: (has_advantage, basic_speed)
        # Lower values declare first
        def sort_key(sid: str):
            pilot = self.get_pilot(sid)
            speed = getattr(pilot, "basic_speed", 5.0) if pilot else 5.0

            # Check if this ship has advantage in any engagement
            has_adv = False
            for eng in self.get_engagements_for_ship(sid):
                if eng.advantage == sid:
                    has_adv = True
                    break

            # Advantaged ships declare last (higher sort value)
            # Faster ships declare later (higher sort value)
            return (has_adv, speed)

        ship_ids.sort(key=sort_key)
        return ship_ids

    # -------------------------------------------------------------------
    # NPC AI Integration
    # -------------------------------------------------------------------

    def get_npc_declaration(self, ship_id: str) -> dict:
        """
        Get the AI's maneuver declaration for an NPC ship.

        Returns a dict with 'maneuver' and 'intent' keys.
        """
        reg = self._ships.get(ship_id)
        if reg is None:
            raise ValueError(f"Ship '{ship_id}' not registered")

        ship_stats = reg.ship_stats

        # Find the engagement for this ship
        engagements = self.get_engagements_for_ship(ship_id)
        if not engagements:
            # No engagement — default to moving
            return {"maneuver": "move", "intent": "pursue"}

        eng = engagements[0]  # Use first engagement for 1v1

        # Find opponent
        opponent_id = (eng.ship_b_id
                       if eng.ship_a_id == ship_id
                       else eng.ship_a_id)
        opponent_reg = self._ships.get(opponent_id)
        opponent_stats = opponent_reg.ship_stats if opponent_reg else None

        # Assess situation and get AI decision
        situation = assess_situation(ship_id, ship_stats, eng, opponent_stats)
        decision = self._ai.decide(situation)

        return {
            "maneuver": decision.maneuver,
            "intent": decision.intent,
            "reasoning": decision.reasoning,
        }

    # -------------------------------------------------------------------
    # Combat End Detection
    # -------------------------------------------------------------------

    def check_combat_end(self) -> bool:
        """
        Check if combat should end.

        Combat ends when no active enemy relationships exist between
        factions with surviving (non-destroyed) ships.
        """
        # Group surviving ships by faction
        active_factions = set()
        for sid, reg in self._ships.items():
            ship = reg.ship_stats
            if not getattr(ship, "is_destroyed", False):
                active_factions.add(reg.faction)

        # Check if any pair of active factions are enemies
        active_list = list(active_factions)
        for i in range(len(active_list)):
            for j in range(i + 1, len(active_list)):
                if self.get_relationship(active_list[i], active_list[j]) == "enemy":
                    return False  # Still have active enemies

        return True  # No active enemy pairs

    # -------------------------------------------------------------------
    # Force Screen Regeneration
    # -------------------------------------------------------------------

    def regen_all_force_screens(self) -> None:
        """
        Regenerate force screens for all ships (end-of-turn cleanup).

        Ships with destroyed power systems do NOT regenerate.
        """
        for sid, reg in self._ships.items():
            ship = reg.ship_stats
            if getattr(ship, "no_power", False):
                continue  # No power = no regen
            if getattr(ship, "fdr_max", 0) > 0:
                ship.current_fdr = ship.fdr_max

    # -------------------------------------------------------------------
    # Turn Management
    # -------------------------------------------------------------------

    def advance_turn(self) -> None:
        """Advance to the next turn."""
        self.current_turn += 1
