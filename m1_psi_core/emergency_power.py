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
