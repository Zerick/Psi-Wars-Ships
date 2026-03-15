"""
Maneuver catalog and validation for M1 Psi-Core.

Defines all 15 chase maneuvers with their properties, validates
maneuver choices against ship state, and determines attack permissions
based on maneuver, Ace Pilot, and Gunslinger abilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ManeuverDef:
    """Definition of a chase maneuver and its properties."""
    name: str
    facing: str              # "front", "rear", "any", "any_opponent_choice"
    chase_modifier: int
    allows_attack: str       # "none", "no_accuracy", "half_accuracy", "full_accuracy"
    dodge_bonus: int
    is_static: bool
    requires_collision: bool
    stall_restricted: bool   # True if stall-speed ships have restrictions


# ---------------------------------------------------------------------------
# Maneuver Catalog
# ---------------------------------------------------------------------------

MANEUVER_CATALOG = {
    "attack": ManeuverDef(
        name="Attack", facing="front", chase_modifier=0,
        allows_attack="full_accuracy", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=True,
    ),
    "move": ManeuverDef(
        name="Move", facing="front",  # Depends on intent, but default front
        chase_modifier=0, allows_attack="none", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
    "move_and_attack": ManeuverDef(
        name="Move and Attack", facing="front", chase_modifier=0,
        allows_attack="half_accuracy", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
    "evade": ManeuverDef(
        name="Evade", facing="rear", chase_modifier=-2,
        allows_attack="none", dodge_bonus=2,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
    "mobility_pursuit": ManeuverDef(
        name="Mobility Pursuit", facing="front", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
    "mobility_escape": ManeuverDef(
        name="Mobility Escape", facing="rear", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
    "stunt": ManeuverDef(
        name="Stunt", facing="any", chase_modifier=0,  # Variable in practice
        allows_attack="none", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=True,
    ),
    "stunt_escape": ManeuverDef(
        name="Stunt Escape", facing="any", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
    "force": ManeuverDef(
        name="Force", facing="any", chase_modifier=0,
        allows_attack="half_accuracy", dodge_bonus=0,
        is_static=False, requires_collision=True, stall_restricted=False,
    ),
    "ram": ManeuverDef(
        name="Ram", facing="front", chase_modifier=0,
        allows_attack="half_accuracy", dodge_bonus=0,
        is_static=False, requires_collision=True, stall_restricted=False,
    ),
    "hide": ManeuverDef(
        name="Hide", facing="any", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=True, requires_collision=False, stall_restricted=True,
    ),
    "stop": ManeuverDef(
        name="Stop", facing="any", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=True, requires_collision=False, stall_restricted=False,
    ),
    "precision_aiming": ManeuverDef(
        name="Precision Aiming", facing="front", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=True, requires_collision=False, stall_restricted=True,
    ),
    "embark_disembark": ManeuverDef(
        name="Embark/Disembark", facing="any", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,  # Special: Ace=none, Gunslinger=half
        is_static=False, requires_collision=True, stall_restricted=False,
    ),
    "emergency_action": ManeuverDef(
        name="Emergency Action", facing="any_opponent_choice", chase_modifier=0,
        allows_attack="none", dodge_bonus=0,
        is_static=False, requires_collision=False, stall_restricted=False,
    ),
}


# ---------------------------------------------------------------------------
# Ace Pilot / Gunslinger attack permission tables
# ---------------------------------------------------------------------------

# Maneuvers where NO ONE can attack (not even Ace/Gunslinger)
_NO_ATTACK_EVER = {"emergency_action", "hide"}

# Ace Pilot: no attack on embark_disembark; Gunslinger: half accuracy
_ACE_NO_ATTACK = {"embark_disembark"}

# Ace/Gunslinger: attack without accuracy
_ACE_NO_ACCURACY = {"mobility_escape", "mobility_pursuit", "move", "stunt", "stunt_escape"}

# Ace/Gunslinger: attack with halved accuracy
_ACE_HALF_ACCURACY = {"force", "move_and_attack", "ram"}
# Gunslinger additionally gets half accuracy on embark_disembark

# Full accuracy maneuvers
_FULL_ACCURACY = {"attack"}


def get_attack_permission(
    maneuver: str,
    is_ace_pilot: bool = False,
    is_gunslinger: bool = False,
) -> str:
    """
    Determine the attack permission level for a given maneuver.

    Returns: "none", "no_accuracy", "half_accuracy", or "full_accuracy".
    """
    if maneuver in _NO_ATTACK_EVER:
        return "none"

    if maneuver in _FULL_ACCURACY:
        return "full_accuracy"

    # Check Ace Pilot / Gunslinger overrides
    if is_ace_pilot or is_gunslinger:
        # Embark/disembark: Ace = none, Gunslinger = half accuracy
        if maneuver == "embark_disembark":
            if is_gunslinger:
                return "half_accuracy"
            return "none"

        if maneuver in _ACE_NO_ACCURACY:
            return "no_accuracy"

        if maneuver in _ACE_HALF_ACCURACY:
            return "half_accuracy"

    # Default: use the maneuver's built-in permission
    m = MANEUVER_CATALOG.get(maneuver)
    if m:
        return m.allows_attack

    return "none"


# ---------------------------------------------------------------------------
# Maneuver validation
# ---------------------------------------------------------------------------

def validate_maneuver(
    maneuver: str,
    stall_speed: int = 0,
    opponent_has_advantage: bool = False,
    at_collision_range: bool = False,
    is_stopped: bool = False,
    soar_like_leaf: bool = False,
) -> list[str]:
    """
    Validate a maneuver choice against ship state.

    Returns a list of violation messages. Empty list = valid.
    """
    errors = []
    m = MANEUVER_CATALOG.get(maneuver)
    if m is None:
        return [f"Unknown maneuver: '{maneuver}'"]

    # Effective stall for validation (Soar Like a Leaf imposes stall restrictions)
    has_stall = stall_speed > 0 or soar_like_leaf

    # Stall speed restrictions
    if has_stall and m.stall_restricted:
        if maneuver == "attack":
            errors.append(
                "Ships with stall speed (or Soar Like a Leaf) "
                "cannot use the Attack maneuver."
            )
        elif maneuver == "stunt" and opponent_has_advantage:
            errors.append(
                "Ships with stall speed cannot Stunt against "
                "an opponent that has advantage."
            )
        elif maneuver in ("hide", "precision_aiming"):
            if not is_stopped:
                errors.append(
                    f"Ships with stall speed cannot use static maneuver "
                    f"'{maneuver}' unless stopped first."
                )

    # Collision range requirements
    if m.requires_collision and not at_collision_range:
        errors.append(
            f"Maneuver '{maneuver}' requires collision range."
        )

    return errors
