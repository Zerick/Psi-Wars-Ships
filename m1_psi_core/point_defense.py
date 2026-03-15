"""
Point defense subsystem for M1 Psi-Core.

Handles Wait and Attack (Point Defense) actions against incoming
missiles and torpedoes.
"""
from __future__ import annotations


# Combined speed/size modifiers by missile type
MISSILE_PD_MODIFIERS = {
    "100mm_light": -16,
    "160mm_standard": -16,
    "400mm_light_torpedo": -11,
    "640mm_heavy_torpedo": -10,
    "1600mm_bombardment": -8,
}


def calculate_point_defense_skill(
    gunner_skill: int,
    target_modifier: int,
    sensor_lock_bonus: int = 0,
    special_bonus: int = 0,
) -> int:
    """
    Calculate effective skill for a point defense interception.

    Ignores range penalties. Applies only:
    - Size/speed modifiers (from MISSILE_PD_MODIFIERS)
    - Sensor lock bonus
    - Special bonuses (e.g., Needle Laser +3)
    """
    return gunner_skill + target_modifier + sensor_lock_bonus + special_bonus
