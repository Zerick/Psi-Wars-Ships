"""
Emergency power allocation subsystem for M1 Psi-Core.

Ships with Emergency Power Reserves (or willing to "redline" HT)
can perform vehicular extra effort for combat advantages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMERGENCY_POWER_COST = 1  # 1 reserve point or 1 HT per use


# ---------------------------------------------------------------------------
# Option effects
# ---------------------------------------------------------------------------

@dataclass
class EmergencyPowerEffect:
    """Effect of an emergency power option."""
    chase_bonus: int = 0
    dodge_bonus: int = 0
    is_high_g: bool = False
    damage_per_die_bonus: int = 0
    restores_fdr: bool = False
    allows_ht_reroll: bool = False
    restores_half_ammo: bool = False


_OPTION_EFFECTS = {
    "all_power_to_engines": EmergencyPowerEffect(chase_bonus=2),
    "emergency_evasive": EmergencyPowerEffect(dodge_bonus=2, is_high_g=True),
    "emergency_firepower": EmergencyPowerEffect(damage_per_die_bonus=1),
    "emergency_screen_recharge": EmergencyPowerEffect(restores_fdr=True),
    "emergency_system_purge": EmergencyPowerEffect(allows_ht_reroll=True),
    "emergency_weapon_recharge": EmergencyPowerEffect(restores_half_ammo=True),
}


def get_option_effect(option: str) -> EmergencyPowerEffect:
    """Get the effect of an emergency power option."""
    return _OPTION_EFFECTS[option]


_OPTION_DESCRIPTIONS = {
    "all_power_to_engines": "All Power to Engines (+2 chase)",
    "emergency_evasive": "Emergency Evasive (+2 dodge, High-G)",
    "emergency_firepower": "Emergency Firepower (+1 dmg/die)",
    "emergency_screen_recharge": "Emergency Screen Recharge (restore fDR now)",
    "emergency_system_purge": "Emergency System Purge (reroll failed HT)",
    "emergency_weapon_recharge": "Emergency Weapon Recharge (restore half ammo)",
}


def get_available_options() -> list[tuple[str, str]]:
    """
    Get all available emergency power options as (key, description) pairs.

    Returns a list suitable for building a menu.
    """
    return [(k, v) for k, v in _OPTION_DESCRIPTIONS.items()]


# ---------------------------------------------------------------------------
# Cumulative penalties
# ---------------------------------------------------------------------------

_CUMULATIVE_PENALTIES = {
    "all_power_to_engines": -4,  # -4 per repeat
}


def get_cumulative_penalty(option: str, times_used: int) -> int:
    """
    Get the cumulative skill penalty for repeated use.

    Only All Power to Engines has a cumulative penalty: -4 per repeat.
    """
    per_use = _CUMULATIVE_PENALTIES.get(option, 0)
    return per_use * times_used


# ---------------------------------------------------------------------------
# Emergency Firepower malfunction
# ---------------------------------------------------------------------------

def get_firepower_malf(bonus_level: int) -> Optional[int]:
    """
    Get the malfunction number for emergency firepower.

    +1 damage/die: no malf change.
    +2 damage/die: Malf reduced to 14.
    """
    if bonus_level >= 2:
        return 14
    return None


# ---------------------------------------------------------------------------
# Redline (ships without reserves)
# ---------------------------------------------------------------------------

def can_redline(reserves: int, current_ht: int) -> bool:
    """
    Check if a ship can 'redline' (reduce HT instead of spending reserves).

    Requires no reserves remaining AND current HT > 0.
    """
    return reserves == 0 and current_ht > 0


# ---------------------------------------------------------------------------
# Critical failure consequences
# ---------------------------------------------------------------------------

@dataclass
class CriticalFailureEffect:
    """Consequence of a critical failure on an emergency power skill roll."""
    disables_system: Optional[str]


_CRIT_FAIL_EFFECTS = {
    "all_power_to_engines": CriticalFailureEffect(disables_system="propulsion"),
    "emergency_firepower": CriticalFailureEffect(disables_system="weaponry"),
}


def get_critical_failure_effect(option: str) -> CriticalFailureEffect:
    """Get the critical failure consequence for an emergency power option."""
    return _CRIT_FAIL_EFFECTS.get(
        option, CriticalFailureEffect(disables_system=None)
    )


# ---------------------------------------------------------------------------
# Skill requirements per option
# ---------------------------------------------------------------------------

# RAW: Each option requires a specific skill roll
_OPTION_SKILLS = {
    "all_power_to_engines": "mechanic",      # Electrician or Mechanic
    "emergency_evasive": "mechanic",          # Electrician or Mechanic
    "emergency_firepower": "armoury",         # Electrician or Armoury (Vehicular Weapons)
    "emergency_screen_recharge": "armoury",   # Electrician or Armoury (Force Screen)
    "emergency_system_purge": "mechanic",     # Electrician or Mechanic
    "emergency_weapon_recharge": "armoury",   # Electrician or Armoury (Vehicular Weapons)
}


def get_required_skill(option: str) -> str:
    """Get the skill type required for an emergency power option."""
    return _OPTION_SKILLS.get(option, "mechanic")


# ---------------------------------------------------------------------------
# Emergency Power Resolution
# ---------------------------------------------------------------------------

@dataclass
class EmergencyPowerResult:
    """Result of attempting to use emergency power."""
    option: str
    skill_target: int
    roll: int
    success: bool
    critical_success: bool
    critical_failure: bool
    margin: int
    effect: Optional[EmergencyPowerEffect]  # None if failed
    cost_type: str  # "reserves" or "redline"
    crit_fail_effect: Optional[CriticalFailureEffect]  # Only on critical failure
    redline_ht_lost: int  # 1 if redlining, 0 otherwise


def resolve_emergency_power(
    option: str,
    skill_level: int,
    reserves: int,
    ship_ht: int,
    dice_roll: int,
    times_used_this_option: int = 0,
) -> EmergencyPowerResult:
    """
    Resolve an emergency power attempt with skill roll.

    RAW flow:
    1. Pay cost: 1 reserve point, or 1 HT if redlining (no reserves)
    2. Roll against skill with cumulative penalties
    3. Success: gain the effect
    4. Failure: cost paid but no effect
    5. Critical failure: cost paid + bad consequence (disable system)

    Args:
        option: Which emergency power option.
        skill_level: The relevant skill (Mechanic or Armoury).
        reserves: Current emergency power reserves.
        ship_ht: Current ship HT (for redlining).
        dice_roll: The 3d6 roll result.
        times_used_this_option: How many times this specific option has been used.
    """
    # Determine cost
    if reserves > 0:
        cost_type = "reserves"
        redline_ht = 0
    else:
        cost_type = "redline"
        redline_ht = 1

    # Calculate effective skill with cumulative penalty
    cumulative = get_cumulative_penalty(option, times_used_this_option)
    effective_skill = skill_level + cumulative

    # Resolve roll
    margin = effective_skill - dice_roll
    success = margin >= 0
    critical_success = dice_roll <= 4 or (dice_roll <= 6 and effective_skill >= 16)
    critical_failure = dice_roll >= 17 or (dice_roll >= 16 and effective_skill <= 6)

    # Determine effect
    effect = None
    crit_effect = None

    if critical_failure:
        crit_effect = get_critical_failure_effect(option)
    elif success:
        effect = get_option_effect(option)

    return EmergencyPowerResult(
        option=option,
        skill_target=effective_skill,
        roll=dice_roll,
        success=success,
        critical_success=critical_success,
        critical_failure=critical_failure,
        margin=margin,
        effect=effect,
        cost_type=cost_type,
        crit_fail_effect=crit_effect,
        redline_ht_lost=redline_ht,
    )
