"""
Defense subsystem for M1 Psi-Core.

Implements vehicular dodge calculation, all dodge modifiers,
High-G dodge mechanics, missile defense, and missile jamming.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIGH_G_DODGE_BONUS = 1
MISSILE_DODGE_PENALTY = -3


# ---------------------------------------------------------------------------
# Vehicular dodge
# ---------------------------------------------------------------------------

def calculate_base_dodge(piloting: int, handling: int) -> int:
    """
    Calculate the base vehicular dodge.

    Formula: Piloting/2 + Handling (NO +3 base).
    Piloting/2 rounds down for odd values.

    This is confirmed by the Spectre stats:
    Piloting 16, Handling +6 -> Dodge 14.
    """
    return (piloting // 2) + handling


# ---------------------------------------------------------------------------
# Dodge modifiers
# ---------------------------------------------------------------------------

@dataclass
class DodgeModifiers:
    """Collection of all dodge modifiers for a given turn."""
    evade_bonus: int = 0
    advantage_escaping_bonus: int = 0
    ace_stunt_bonus: int = 0
    precision_aim_awareness_bonus: int = 0
    tactical_defense_bonus: int = 0

    @property
    def total(self) -> int:
        return (
            self.evade_bonus
            + self.advantage_escaping_bonus
            + self.ace_stunt_bonus
            + self.precision_aim_awareness_bonus
            + self.tactical_defense_bonus
        )


def get_dodge_modifiers(
    maneuver: str = "move",
    has_advantage_escaping: bool = False,
    ace_pilot_stunt: bool = False,
    tactical_defense: bool = False,
    precision_aiming_aware: bool = False,
) -> DodgeModifiers:
    """
    Calculate all situational dodge modifiers for a turn.

    These stack on top of the base dodge from calculate_base_dodge().
    """
    mods = DodgeModifiers()

    # Evade maneuver: +2 to dodge
    if maneuver == "evade":
        mods.evade_bonus = 2

    # Gained advantage while escaping: +1 to all defenses
    if has_advantage_escaping:
        mods.advantage_escaping_bonus = 1

    # Ace Pilot with Stunt maneuver: +1 to first dodge
    if ace_pilot_stunt and maneuver in ("stunt", "stunt_escape"):
        mods.ace_stunt_bonus = 1

    # Target aware of precision aiming: +2 to dodge against the aimer
    if precision_aiming_aware:
        mods.precision_aim_awareness_bonus = 2

    # Tactical coordination (defensive): +1 dodge to formation
    if tactical_defense:
        mods.tactical_defense_bonus = 1

    return mods


# ---------------------------------------------------------------------------
# High-G dodge
# ---------------------------------------------------------------------------

def is_high_g_available(accel: int, top_speed: int) -> bool:
    """
    Check if a ship can make a High-G dodge.

    Available if acceleration >= 40 OR top_speed >= 400.
    """
    return accel >= 40 or top_speed >= 400


def get_high_g_ht_modifier(has_g_chair: bool = False) -> int:
    """
    Get the HT roll modifier for High-G dodge.

    G-chair or G-suit: +2 to HT roll.
    """
    return 2 if has_g_chair else 0


def calculate_high_g_fp_loss(ht: int, roll: int) -> int:
    """
    Calculate FP loss from a failed High-G HT roll.

    On failure, lose FP equal to margin of failure.
    On success, lose 0 FP.
    """
    margin = ht - roll
    if margin >= 0:
        return 0
    return abs(margin)


# ---------------------------------------------------------------------------
# Missile defense
# ---------------------------------------------------------------------------

@dataclass
class MissileDefenseModifiers:
    """Modifiers specific to defending against missiles."""
    base_penalty: int = MISSILE_DODGE_PENALTY  # Always -3
    esm_bonus: int = 0
    decoy_bonus: int = 0

    @property
    def total(self) -> int:
        return self.base_penalty + self.esm_bonus + self.decoy_bonus


def get_missile_defense_modifiers(
    has_tactical_esm: bool = False,
    has_decoy: bool = False,
) -> MissileDefenseModifiers:
    """
    Get defense modifiers against a missile attack.

    Base: -3 to dodge.
    Tactical ESM: +1.
    Decoy launcher: +1 (limited charges).
    """
    mods = MissileDefenseModifiers()
    if has_tactical_esm:
        mods.esm_bonus = 1
    if has_decoy:
        mods.decoy_bonus = 1
    return mods


# ---------------------------------------------------------------------------
# Missile jamming (alternative to dodging)
# ---------------------------------------------------------------------------

@dataclass
class JamMissileResult:
    """Result of calculating missile jamming effective skill."""
    effective_skill: int
    base_skill: int
    ecm_bonus: int
    decoy_bonus: int


def calculate_jam_missile(
    ecm_skill: int,
    vehicle_ecm_rating: int,
    has_decoy: bool = False,
) -> JamMissileResult:
    """
    Calculate effective skill for jamming a missile.

    Base: EO(ECM) / 2.
    Bonus: half vehicle's ECM rating (absolute value).
    Bonus: +2 if using decoy launcher.
    """
    base = ecm_skill // 2
    ecm_bonus = abs(vehicle_ecm_rating) // 2
    decoy_bonus = 2 if has_decoy else 0

    return JamMissileResult(
        effective_skill=base + ecm_bonus + decoy_bonus,
        base_skill=base,
        ecm_bonus=ecm_bonus,
        decoy_bonus=decoy_bonus,
    )
