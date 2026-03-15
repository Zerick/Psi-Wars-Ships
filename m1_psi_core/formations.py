"""
Formation subsystem for M1 Psi-Core.

Handles multi-ship formation rules: intercept, area jammer sharing,
and three modes of tactical coordination.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Formation rules
# ---------------------------------------------------------------------------

def can_intercept(attacker_has_advantage: bool) -> bool:
    """
    Check if a formation member can intercept an attack on another member.

    Only possible if the attacker is NOT advantaged against the formation.
    """
    return not attacker_has_advantage


def formation_has_area_jammer(ships: list[dict]) -> bool:
    """
    Check if any ship in the formation has an area jammer.

    If any member has one, the entire formation benefits.
    """
    return any(s.get("has_area_jammer", False) for s in ships)


def validate_formation_size(size: int) -> bool:
    """
    Validate formation size. Minimum 2, no maximum cap.
    """
    return size >= 2


# ---------------------------------------------------------------------------
# Tactical coordination
# ---------------------------------------------------------------------------

@dataclass
class TacticalCoordinationEffect:
    """Effect of a tactical coordination mode."""
    chase_bonus: int = 0
    hit_bonus: int = 0
    dodge_bonus: int = 0
    enemy_hit_penalty: int = 0
    enemy_dodge_penalty: int = 0


def get_tactical_coordination_effect(mode: str) -> TacticalCoordinationEffect:
    """
    Get the effect of a tactical coordination mode.

    Pursuit: +2 to formation chase rolls.
    Defensive: target at -2 to hit formation OR formation at +1 dodge.
    Offensive: formation at +2 to hit target OR target at -1 dodge.
    """
    if mode == "pursuit":
        return TacticalCoordinationEffect(chase_bonus=2)
    elif mode == "defensive":
        # Default to the hit penalty variant; GM can choose dodge variant
        return TacticalCoordinationEffect(enemy_hit_penalty=-2, dodge_bonus=1)
    elif mode == "offensive":
        # Default to the hit bonus variant; GM can choose dodge variant
        return TacticalCoordinationEffect(hit_bonus=2, enemy_dodge_penalty=-1)
    else:
        raise ValueError(f"Unknown tactical coordination mode: '{mode}'")
