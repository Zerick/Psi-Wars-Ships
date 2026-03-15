"""
Passenger actions subsystem for M1 Psi-Core.

Handles crew skill defaults, emergency repairs, hyperspace navigation,
tactical coordination (delegated to formations.py), and internal movement.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Crew skill constants
# ---------------------------------------------------------------------------

DEFAULT_CREW_SKILL = 12
CREW_SKILL_MIN = 10
CREW_SKILL_MAX = 15


# ---------------------------------------------------------------------------
# Emergency repairs
# ---------------------------------------------------------------------------

EMERGENCY_REPAIR_PENALTY = -10


def get_repair_penalty(has_quick_gadgeteer: bool = False) -> int:
    """
    Get the emergency repair skill penalty.

    Base: -10. Quick Gadgeteer halves it to -5.
    """
    if has_quick_gadgeteer:
        return EMERGENCY_REPAIR_PENALTY // 2
    return EMERGENCY_REPAIR_PENALTY


def is_jury_rigged_check_needed(
    jury_rigged: bool,
    checked_this_battle: bool,
) -> bool:
    """
    Check if a jury-rigged component needs an HT check.

    Jury-rigged components must roll HT the first time used in battle.
    One check per battle is sufficient.
    """
    return jury_rigged and not checked_this_battle


# ---------------------------------------------------------------------------
# Hyperspace navigation
# ---------------------------------------------------------------------------

HYPERSPACE_BASE_TURNS = 5


def calculate_navigation_penalty(
    turns_reduced: int,
    has_quick_shunt: bool = False,
) -> int:
    """
    Calculate the Navigation (Hyperspace) penalty for time reduction.

    Each turn reduced imposes -2.
    Quick Shunt perk: ignore up to -2 in time penalties.
    """
    base_penalty = -2 * turns_reduced

    if has_quick_shunt:
        # Remove up to -2 (i.e., add 2 toward zero)
        base_penalty = min(0, base_penalty + 2)

    return base_penalty


# ---------------------------------------------------------------------------
# Internal movement
# ---------------------------------------------------------------------------

_MOVEMENT_TURNS = {
    "fighter": 0,
    "shuttle": 0,
    "corvette": 1,
    "capital": 2,
}


def get_internal_movement_turns(ship_class: str) -> int:
    """
    Get the number of turns required to move between stations.

    Fighters/shuttles: 0 (free movement).
    Corvettes: 1 turn.
    Capital ships: 2 turns.
    """
    return _MOVEMENT_TURNS.get(ship_class, 2)
