"""
Attack subsystem for M1 Psi-Core.

Implements the complete hit roll modifier pipeline for direct-fire
(beam) weapons. Missile attacks use a separate pipeline in missile.py.
"""
from __future__ import annotations

import math
from typing import Optional


# ---------------------------------------------------------------------------
# Range / Speed penalty
# ---------------------------------------------------------------------------

def calculate_range_speed_penalty(
    range_penalty: int,
    own_speed_penalty: int,
    target_speed_penalty: int,
    matched_speed: bool = False,
    stall_speed: int = 0,
) -> int:
    """
    Determine the effective range/speed penalty.

    Use the HIGHEST (most severe) of:
    - Absolute value of range penalty
    - Own speed penalty (absolute value)
    - Target speed penalty (absolute value)

    With matched speed: use higher of |range penalty| or stall speed
    derived penalty.
    """
    if matched_speed:
        # Matched speed: use higher of |range| or stall speed penalty
        # Stall speed maps to a speed penalty via the same table
        stall_penalty = _speed_to_penalty(stall_speed) if stall_speed > 0 else 0
        return -max(abs(range_penalty), stall_penalty)

    return -max(abs(range_penalty), abs(own_speed_penalty), abs(target_speed_penalty))


def _speed_to_penalty(speed: int) -> int:
    """Convert a speed value to a GURPS speed/range penalty magnitude."""
    if speed <= 0:
        return 0
    elif speed <= 3:
        return 1
    elif speed <= 7:
        return 3
    elif speed <= 15:
        return 5
    elif speed <= 30:
        return 7
    elif speed <= 70:
        return 9
    elif speed <= 150:
        return 11
    elif speed <= 300:
        return 13
    elif speed <= 700:
        return 15
    elif speed <= 1500:
        return 17
    else:
        return 19


# ---------------------------------------------------------------------------
# Size modifier
# ---------------------------------------------------------------------------

def get_sm_bonus(target_sm: int) -> int:
    """Target's Size Modifier applied as a bonus to hit."""
    return target_sm


# ---------------------------------------------------------------------------
# Relative size penalty
# ---------------------------------------------------------------------------

def get_relative_size_penalty(
    attacker_class: str,
    target_class: str,
    is_light_turret: bool = False,
) -> int:
    """
    Calculate the relative size penalty between ship classes.

    Corvette -> fighter: -5
    Capital -> corvette: -5
    Capital -> fighter: -10
    Same class or smaller firing at larger: 0

    Light turrets halve the penalty (rounded down).
    """
    class_rank = {"fighter": 0, "corvette": 1, "capital": 2}
    a_rank = class_rank.get(attacker_class, 0)
    t_rank = class_rank.get(target_class, 0)

    if a_rank <= t_rank:
        return 0

    difference = a_rank - t_rank
    penalty = -5 * difference  # -5 per class difference

    if is_light_turret:
        penalty = -(abs(penalty) // 2)

    return penalty


# ---------------------------------------------------------------------------
# Sensor lock
# ---------------------------------------------------------------------------

def get_sensor_lock_bonus(has_lock: bool, targeting_bonus: int = 0) -> int:
    """
    Get the sensor lock bonus.

    RAW: +3 with basic sensor lock. With targeting computer, use
    the ship's targeting_bonus value (typically +4 for obsolete
    computers, +5 for standard).

    If no targeting computer (targeting_bonus=0), base +3 applies.
    """
    if not has_lock:
        return 0
    if targeting_bonus > 0:
        return targeting_bonus
    return 3  # Base sensor lock without targeting computer


# ---------------------------------------------------------------------------
# Accuracy
# ---------------------------------------------------------------------------

def apply_accuracy(weapon_acc: int, permission: str) -> int:
    """
    Apply weapon accuracy based on attack permission level.

    full_accuracy: add full Acc
    half_accuracy: add Acc // 2 (rounded down)
    no_accuracy / none: add 0
    """
    if permission == "full_accuracy":
        return weapon_acc
    elif permission == "half_accuracy":
        return weapon_acc // 2
    else:
        return 0


# ---------------------------------------------------------------------------
# Precision aiming
# ---------------------------------------------------------------------------

def get_precision_aim_bonus(
    aimed_last_turn: bool,
    current_maneuver: str = "attack",
) -> int:
    """
    Get precision aiming bonus.

    +4 to attacks next turn, but only with the Attack maneuver
    (not Move and Attack or others).
    """
    if not aimed_last_turn:
        return 0
    if current_maneuver == "attack":
        return 4
    return 0


# ---------------------------------------------------------------------------
# Deceptive attack
# ---------------------------------------------------------------------------

def calculate_deceptive_attack(deceptive_levels: int) -> tuple[int, int]:
    """
    Calculate deceptive attack trade-off.

    Each level: -2 to attacker's skill, -1 to target's defense.

    Returns: (skill_penalty, defense_penalty)
    """
    return (-2 * deceptive_levels, -deceptive_levels)


def max_deceptive_levels(effective_skill: int) -> int:
    """
    Maximum deceptive attack levels.

    Cannot reduce effective skill below 10.
    """
    if effective_skill <= 10:
        return 0
    return (effective_skill - 10) // 2


# ---------------------------------------------------------------------------
# ROF bonus (GURPS rapid fire table)
# ---------------------------------------------------------------------------

_ROF_BONUS_TABLE = [
    (50, 6),
    (25, 5),
    (17, 4),
    (13, 3),
    (9, 2),
    (5, 1),
]


def get_rof_bonus(rof: int) -> int:
    """
    Look up the rapid fire bonus from the GURPS table.

    ROF 1-4: +0, 5-8: +1, 9-12: +2, 13-16: +3, 17-24: +4,
    25-49: +5, 50-99: +6, then +1 per doubling.
    """
    if rof < 5:
        return 0
    for threshold, bonus in _ROF_BONUS_TABLE:
        if rof >= threshold:
            return bonus
    return 0


# ---------------------------------------------------------------------------
# Weapon facing restrictions
# ---------------------------------------------------------------------------

def can_weapon_fire(
    mount: str,
    arc: str,
    current_facing: str,
    is_advantaged: bool = False,
) -> bool:
    """
    Check if a weapon can fire given current facing.

    Turret (arc "all"): always fires.
    Fixed mount: must match facing direction.
    Advantaged attacker: may choose facing, so fixed weapons can fire.
    """
    if arc == "all" or mount == "turret":
        return True
    if is_advantaged:
        return True
    # Fixed mount must match facing
    if mount == "fixed_front" and current_facing == "front":
        return True
    if mount == "fixed_rear" and current_facing == "rear":
        return True
    return False


# ---------------------------------------------------------------------------
# Plasma flak
# ---------------------------------------------------------------------------

def calculate_flak_hit_number(range_band: str, target_sm: int) -> int:
    """
    Calculate the flak hit number.

    Extreme range: 1 + SM
    Long or closer: 5 + SM
    """
    from m1_psi_core.combat_state import RANGE_BAND_ORDER
    band_idx = RANGE_BAND_ORDER.index(range_band)
    long_idx = RANGE_BAND_ORDER.index("long")

    if band_idx <= long_idx:
        return 5 + target_sm
    else:
        return 1 + target_sm


def get_flak_handling_penalty(in_flak_zone: bool) -> int:
    """Ships in a flak zone suffer -2 handling (rough terrain)."""
    return -2 if in_flak_zone else 0


# ---------------------------------------------------------------------------
# Cannot-attack conditions
# ---------------------------------------------------------------------------

def can_ship_attack(
    no_power: bool = False,
    weapons_destroyed: bool = False,
) -> bool:
    """Check if a ship is capable of attacking at all."""
    if no_power or weapons_destroyed:
        return False
    return True


# ---------------------------------------------------------------------------
# Full hit modifier calculation (convenience function)
# ---------------------------------------------------------------------------

def calculate_hit_modifiers(
    base_skill: int,
    range_penalty: int = 0,
    own_speed_penalty: int = 0,
    target_speed_penalty: int = 0,
    target_sm: int = 0,
    sensor_lock_bonus: int = 0,
    accuracy: int = 0,
    precision_aim_bonus: int = 0,
    deceptive_penalty: int = 0,
    rof_bonus: int = 0,
    relative_size_penalty: int = 0,
    tactical_offensive_bonus: int = 0,
    matched_speed: bool = False,
    stall_speed: int = 0,
) -> int:
    """
    Calculate total effective skill for an attack roll.

    Sums all modifiers against the base gunnery skill.
    """
    range_speed = calculate_range_speed_penalty(
        range_penalty, own_speed_penalty, target_speed_penalty,
        matched_speed, stall_speed,
    )

    return (
        base_skill
        + range_speed
        + target_sm
        + sensor_lock_bonus
        + accuracy
        + precision_aim_bonus
        + deceptive_penalty
        + rof_bonus
        + relative_size_penalty
        + tactical_offensive_bonus
    )
