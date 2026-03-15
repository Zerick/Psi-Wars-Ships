"""
Subsystem damage tracking and gameplay effects for M1 Psi-Core.

When a ship takes a major+ wound, a subsystem is hit (via the 3d6
subsystem table in damage.py). This module tracks which systems are
disabled/destroyed and computes the gameplay effects.

GAMEPLAY EFFECTS BY SYSTEM (Rules as Written):
    propulsion (disabled): Move and Accel halved
    propulsion (destroyed): ship adrift, Move 0, Accel 0
    weaponry (disabled): effective ROF halved (round down)
    weaponry (destroyed): cannot fire at all
    power (disabled): force screen regens to half max fDR
    power (destroyed): no fDR regen, no sensors, no weapons
    controls (disabled): -4 to all pilot/dodge rolls
    controls (destroyed): ship uncontrollable, no maneuvers, no dodge
    equipment (disabled/destroyed): narrative only (sensors degraded, flavor)
    habitat (disabled/destroyed): narrative only (life support issues)
    cargo_hangar (disabled/destroyed): narrative only
    fuel (disabled/destroyed): narrative only (range reduced, leak)
    armor (disabled/destroyed): narrative only (could reduce DR in future)

TRACKING MECHANISM:
    Each ship object gets two sets: 'disabled_systems' and 'destroyed_systems'.
    These are stored as Python sets on the ship stats object. If the object
    doesn't have them, we create them on first access (duck typing compatible
    with both MockShipStats and future EffectiveStatBlock).

Modification guide:
    - To add a new system effect: add a new function and call it from engine.py
    - To change severity of effects: modify the relevant get_effective_* function
    - To make cosmetic systems have effects: add functions for them
"""
from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# System status tracking
# ---------------------------------------------------------------------------

def _ensure_tracking(ship) -> None:
    """
    Ensure the ship object has disabled_systems and destroyed_systems sets.
    Creates them if they don't exist (duck-typing safe).
    """
    if not hasattr(ship, "disabled_systems"):
        ship.disabled_systems = set()
    if not hasattr(ship, "destroyed_systems"):
        ship.destroyed_systems = set()


def disable_system(ship, system: str) -> None:
    """
    Mark a system as disabled (major wound hit).

    If the system is already destroyed, this is a no-op.
    """
    _ensure_tracking(ship)
    if system not in ship.destroyed_systems:
        ship.disabled_systems.add(system)


def destroy_system(ship, system: str) -> None:
    """
    Mark a system as destroyed (crippling+ wound hit).

    Promotes from disabled to destroyed if already disabled.
    """
    _ensure_tracking(ship)
    ship.disabled_systems.discard(system)
    ship.destroyed_systems.add(system)


def get_disabled(ship) -> set[str]:
    """Get the set of disabled (but not destroyed) systems."""
    _ensure_tracking(ship)
    return set(ship.disabled_systems)


def get_destroyed(ship) -> set[str]:
    """Get the set of destroyed systems."""
    _ensure_tracking(ship)
    return set(ship.destroyed_systems)


def is_system_disabled(ship, system: str) -> bool:
    """Check if a specific system is disabled."""
    _ensure_tracking(ship)
    return system in ship.disabled_systems


def is_system_destroyed(ship, system: str) -> bool:
    """Check if a specific system is destroyed."""
    _ensure_tracking(ship)
    return system in ship.destroyed_systems


def is_system_damaged(ship, system: str) -> bool:
    """Check if a system is either disabled or destroyed."""
    return is_system_disabled(ship, system) or is_system_destroyed(ship, system)


# ---------------------------------------------------------------------------
# Propulsion effects
# ---------------------------------------------------------------------------

def get_effective_move(ship) -> dict[str, int]:
    """
    Get effective Move and Accel after propulsion damage.

    Disabled: halved. Destroyed: zero.
    Returns dict with 'accel' and 'top_speed' keys.
    """
    base_accel = getattr(ship, "accel", 0)
    base_speed = getattr(ship, "top_speed", 0)

    if is_system_destroyed(ship, "propulsion"):
        return {"accel": 0, "top_speed": 0}
    elif is_system_disabled(ship, "propulsion"):
        return {"accel": base_accel // 2, "top_speed": base_speed // 2}
    else:
        return {"accel": base_accel, "top_speed": base_speed}


# ---------------------------------------------------------------------------
# Weaponry effects
# ---------------------------------------------------------------------------

def get_effective_rof(ship, base_rof: int) -> int:
    """
    Get effective ROF after weaponry damage.

    Disabled: halved (round down, minimum 1).
    Destroyed: 0 (cannot fire handled by can_fire_weapons).
    """
    if is_system_destroyed(ship, "weaponry"):
        return 0
    elif is_system_disabled(ship, "weaponry"):
        return max(1, base_rof // 2)
    else:
        return base_rof


def can_fire_weapons(ship) -> bool:
    """
    Check if a ship can fire weapons at all.

    Cannot fire if: weaponry destroyed, OR power destroyed.
    """
    if is_system_destroyed(ship, "weaponry"):
        return False
    if is_system_destroyed(ship, "power"):
        return False
    return True


# ---------------------------------------------------------------------------
# Power effects
# ---------------------------------------------------------------------------

def get_effective_fdr_max(ship) -> int:
    """
    Get effective maximum fDR for force screen regeneration.

    Disabled power: half max. Destroyed power: zero.
    """
    base_fdr = getattr(ship, "fdr_max", 0)

    if is_system_destroyed(ship, "power"):
        return 0
    elif is_system_disabled(ship, "power"):
        return base_fdr // 2
    else:
        return base_fdr


# ---------------------------------------------------------------------------
# Controls effects
# ---------------------------------------------------------------------------

def get_controls_penalty(ship) -> int:
    """
    Get the piloting/dodge penalty from controls damage.

    Disabled: -4 to all pilot rolls.
    Destroyed: handled by is_controllable() — ship cannot act.
    """
    if is_system_disabled(ship, "controls"):
        return -4
    return 0


def is_controllable(ship) -> bool:
    """
    Check if the ship can be controlled at all.

    Destroyed controls: ship is uncontrollable.
    """
    return not is_system_destroyed(ship, "controls")
