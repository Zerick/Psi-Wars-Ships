"""
Missile attack subsystem for M1 Psi-Core.

Missiles use a completely different modifier pipeline from beam weapons.
Torpedoes are NOT missiles and use normal attack rules.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class NearMissResult:
    """Result of a near-miss check."""
    is_near_miss: bool
    damage_multiplier: float = 1.0
    ignore_armor_divisor: bool = False
    full_miss: bool = False


# ---------------------------------------------------------------------------
# Missile hit calculation
# ---------------------------------------------------------------------------

def calculate_missile_hit(
    gunner_skill: int,
    weapon_acc: int,
    target_sm: int,
    target_ecm: int,
    target_speed_penalty: int,
) -> int:
    """
    Calculate effective skill for a missile attack.

    Missile modifiers: Acc + SM + ECM + half speed penalty.
    Ignores: range, sensor lock, targeting computer, deceptive attacks.
    Ace pilots never add extra accuracy to missiles.
    """
    speed_penalty = calculate_missile_speed_penalty(target_speed_penalty)
    return gunner_skill + weapon_acc + target_sm + target_ecm + speed_penalty


def calculate_missile_speed_penalty(target_speed_penalty: int) -> int:
    """
    Calculate the speed penalty for missile attacks.

    Uses half of target speed penalty, rounded toward more negative
    (i.e., rounded up in absolute value): -7 -> -4, -8 -> -4.
    """
    if target_speed_penalty >= 0:
        return 0
    # Round toward more negative: take abs, divide, round up, re-negate
    return -(math.ceil(abs(target_speed_penalty) / 2))


# ---------------------------------------------------------------------------
# Air burst
# ---------------------------------------------------------------------------

def get_air_burst_bonus(
    explosive: bool,
    armor_divisor: Optional[float],
) -> int:
    """
    Get the air burst bonus for explosive weapons.

    +4 to hit, but only for explosive weapons WITHOUT armor divisors.
    """
    if explosive and armor_divisor is None:
        return 4
    return 0


# ---------------------------------------------------------------------------
# Near miss
# ---------------------------------------------------------------------------

def check_near_miss(
    margin: int,
    explosive: bool,
    armor_divisor: Optional[float],
) -> NearMissResult:
    """
    Check if a miss qualifies as a "near miss."

    Miss by 1 on an explosive weapon = near miss: 1/3 damage, no AD.
    Only applies to explosive weapons without armor divisors.
    """
    if margin == -1 and explosive:
        return NearMissResult(
            is_near_miss=True,
            damage_multiplier=1 / 3,
            ignore_armor_divisor=True,
        )
    return NearMissResult(is_near_miss=False)


def check_defense_near_miss(
    defense_margin: int,
    explosive: bool,
    armor_divisor: Optional[float],
    already_near_miss: bool = False,
) -> NearMissResult:
    """
    Check for near miss when defending against explosive missiles.

    If defense margin = 0 against explosive (no AD): near miss (1/3 damage).
    If the attack was already a near miss and defense margin = 0: full miss.
    """
    if defense_margin == 0 and explosive:
        if already_near_miss:
            return NearMissResult(is_near_miss=False, full_miss=True)
        return NearMissResult(
            is_near_miss=True,
            damage_multiplier=1 / 3,
            ignore_armor_divisor=True,
        )
    return NearMissResult(is_near_miss=False)


# ---------------------------------------------------------------------------
# Free missile
# ---------------------------------------------------------------------------

def is_free_missile_eligible(attack_permission: str) -> bool:
    """
    Check if a free missile can be fired.

    Under circumstances where you would gain accuracy, you may
    fire a free missile instead.
    """
    return attack_permission == "full_accuracy"


# ---------------------------------------------------------------------------
# Torpedo rules
# ---------------------------------------------------------------------------

def get_torpedo_dodge_bonus(range_band: str) -> int:
    """
    Get the dodge bonus that torpedoes grant to their target.

    +1 at extreme, +2 at distant.
    """
    if range_band == "extreme":
        return 1
    elif range_band == "distant":
        return 2
    return 0


def can_torpedo_attack_at_range(range_band: str) -> bool:
    """
    Check if a torpedo can attack at the given range.

    Torpedoes cannot attack beyond distant range.
    """
    from m1_psi_core.combat_state import RANGE_BAND_ORDER
    band_idx = RANGE_BAND_ORDER.index(range_band)
    distant_idx = RANGE_BAND_ORDER.index("distant")
    return band_idx <= distant_idx


def is_guided_weapon(weapon_type: str) -> bool:
    """
    Check if a weapon is guided (uses missile rules).

    Missiles are guided. Torpedoes are NOT guided — they use
    normal attack rules.
    """
    return weapon_type == "missile"
