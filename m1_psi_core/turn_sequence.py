"""
Turn sequence subsystem for M1 Psi-Core.

Manages the five-phase turn structure, declaration validation,
force screen regeneration timing, turn ordering, and turn counting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Turn phases
# ---------------------------------------------------------------------------

TURN_PHASES = [
    "declaration",
    "chase_resolution",
    "attack",
    "damage",
    "cleanup",
]


# ---------------------------------------------------------------------------
# Declaration validation
# ---------------------------------------------------------------------------

@dataclass
class DeclarationValidation:
    """Result of validating a turn declaration."""
    is_valid: bool
    errors: list[str]


def validate_declaration(
    maneuver: Optional[str],
    intent: Optional[str],
    configuration: Optional[dict] = None,
) -> DeclarationValidation:
    """
    Validate a turn declaration.

    A valid declaration must include:
    - A maneuver choice
    - An intent (pursue or evade)
    - Configuration is locked with the declaration
    """
    errors = []

    if maneuver is None:
        errors.append("Declaration must include a maneuver choice.")

    if intent is None:
        errors.append("Declaration must include an intent (pursue or evade).")
    elif intent not in ("pursue", "evade"):
        errors.append(f"Intent must be 'pursue' or 'evade', got '{intent}'.")

    return DeclarationValidation(
        is_valid=len(errors) == 0,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Force screen regeneration
# ---------------------------------------------------------------------------

def should_regen_force_screens(phase: str) -> bool:
    """Force screens regenerate during the cleanup phase."""
    return phase == "cleanup"


def can_regen_force_screen(no_power: bool = False) -> bool:
    """Force screens cannot regenerate if the power system is destroyed."""
    return not no_power


# ---------------------------------------------------------------------------
# Turn order
# ---------------------------------------------------------------------------

@dataclass
class TurnOrder:
    """Resolved turn order for a round."""
    declares_first: str
    declares_second: str
    resolves_first: str
    resolves_second: str


def determine_turn_order(ships: list[dict]) -> TurnOrder:
    """
    Determine turn order based on Basic Speed and advantage.

    Higher Basic Speed (or advantaged) declares second and resolves first.
    Advantage overrides speed.
    """
    if len(ships) < 2:
        raise ValueError("Need at least 2 ships to determine turn order")

    a, b = ships[0], ships[1]

    # Advantage overrides speed
    a_advantage = a.get("has_advantage", False)
    b_advantage = b.get("has_advantage", False)

    if a_advantage and not b_advantage:
        # A has advantage: declares second, resolves first
        return TurnOrder(
            declares_first=b["id"], declares_second=a["id"],
            resolves_first=a["id"], resolves_second=b["id"],
        )
    elif b_advantage and not a_advantage:
        return TurnOrder(
            declares_first=a["id"], declares_second=b["id"],
            resolves_first=b["id"], resolves_second=a["id"],
        )

    # No advantage difference: use Basic Speed
    a_speed = a.get("basic_speed", 0)
    b_speed = b.get("basic_speed", 0)

    if a_speed >= b_speed:
        # A is faster or tied: A declares second, resolves first
        return TurnOrder(
            declares_first=b["id"], declares_second=a["id"],
            resolves_first=a["id"], resolves_second=b["id"],
        )
    else:
        return TurnOrder(
            declares_first=a["id"], declares_second=b["id"],
            resolves_first=b["id"], resolves_second=a["id"],
        )


# ---------------------------------------------------------------------------
# Turn tracker
# ---------------------------------------------------------------------------

class TurnTracker:
    """Simple turn counter."""

    def __init__(self):
        self.current_turn = 1

    def advance(self):
        """Advance to the next turn."""
        self.current_turn += 1
