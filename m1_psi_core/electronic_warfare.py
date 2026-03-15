"""
Electronic warfare subsystem for M1 Psi-Core.

Handles detection, stealth, visual detection, ambush mechanics,
active sensor jamming, and sensor lock rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------

def check_auto_detection(scanner_range: int, range_miles: float) -> bool:
    """Ships automatically detect each other within scanner range."""
    return range_miles <= scanner_range


# ---------------------------------------------------------------------------
# Stealth detection (sensor contest)
# ---------------------------------------------------------------------------

@dataclass
class StealthDetectionModifiers:
    """Modifiers applied to the scanner's EO(Sensors) roll."""
    ecm_penalty: int
    stealth_penalty: int
    nebula_penalty: int
    total_penalty: int


def calculate_stealth_detection_modifiers(
    target_ecm: int,
    has_stealth_coating: bool = False,
    in_nebula: bool = False,
) -> StealthDetectionModifiers:
    """
    Calculate modifiers for sensor-based stealth detection.

    ECM penalty: target's ECM value (e.g., -4).
    Stealth coating: additional -4.
    Nebula: -10.
    """
    ecm_pen = target_ecm  # Already negative
    stealth_pen = -4 if has_stealth_coating else 0
    nebula_pen = -10 if in_nebula else 0
    total = ecm_pen + stealth_pen + nebula_pen

    return StealthDetectionModifiers(
        ecm_penalty=ecm_pen,
        stealth_penalty=stealth_pen,
        nebula_penalty=nebula_pen,
        total_penalty=total,
    )


@dataclass
class StealthContestResult:
    """Result of a stealth detection contest."""
    can_ambush: bool
    ambush_range: str
    can_pass: bool


def resolve_stealth_contest(stealthy_won: bool) -> StealthContestResult:
    """
    Resolve the outcome of a stealth detection contest.

    If the stealthy ship wins, it may pass or ambush from beyond visual.
    """
    if stealthy_won:
        return StealthContestResult(
            can_ambush=True,
            ambush_range="beyond_visual",
            can_pass=True,
        )
    return StealthContestResult(
        can_ambush=False,
        ambush_range="",
        can_pass=False,
    )


# ---------------------------------------------------------------------------
# Visual detection (closer than beyond visual)
# ---------------------------------------------------------------------------

@dataclass
class VisualDetectionModifiers:
    """Modifiers for visual detection rolls."""
    sm_bonus: int
    chameleon_penalty: int
    environment_penalty: int
    total: int


def calculate_visual_detection_modifiers(
    target_sm: int,
    has_chameleon: bool = False,
    in_nebula: bool = False,
    in_asteroid_field: bool = False,
) -> VisualDetectionModifiers:
    """
    Calculate modifiers for visual stealth detection.

    SM: bonus to Vision roll.
    Chameleon: -4.
    Nebula: -5, Asteroid: -5, Both: -10.
    """
    sm_bonus = target_sm
    chameleon_pen = -4 if has_chameleon else 0

    env_pen = 0
    if in_nebula and in_asteroid_field:
        env_pen = -10
    elif in_nebula:
        env_pen = -5
    elif in_asteroid_field:
        env_pen = -5

    total = sm_bonus + chameleon_pen + env_pen

    return VisualDetectionModifiers(
        sm_bonus=sm_bonus,
        chameleon_penalty=chameleon_pen,
        environment_penalty=env_pen,
        total=total,
    )


def calculate_stealth_approach(margin_of_success: int) -> int:
    """
    Calculate how many extra range bands closer a stealthy ship can approach.

    Every 4 points of margin allows approaching 1 band closer.
    """
    if margin_of_success < 4:
        return 0
    return margin_of_success // 4


# ---------------------------------------------------------------------------
# Ambush mechanics
# ---------------------------------------------------------------------------

@dataclass
class AmbushDefenseModifiers:
    """Modifiers for defending against an ambush."""
    iq_modifier: int
    combat_reflexes_bonus: int


def get_ambush_defense_modifiers(
    has_combat_reflexes: bool = False,
    has_danger_sense: bool = False,
) -> AmbushDefenseModifiers:
    """
    Get modifiers for the defender's IQ roll during an ambush.

    Combat Reflexes: +6 to IQ roll.
    Danger Sense: separate IQ roll (handled elsewhere).
    """
    cr_bonus = 6 if has_combat_reflexes else 0
    return AmbushDefenseModifiers(
        iq_modifier=0,
        combat_reflexes_bonus=cr_bonus,
    )


@dataclass
class AmbushReactionResult:
    """Result of an ambush reaction roll."""
    can_act: bool
    can_defend: bool
    defense_penalty: int


def resolve_ambush_reaction(iq_roll_succeeded: bool) -> AmbushReactionResult:
    """
    Resolve the defender's reaction to an ambush.

    Failed IQ roll: cannot act or defend on turn 1.
    Succeeded: can act and defend at -4.
    """
    if iq_roll_succeeded:
        return AmbushReactionResult(
            can_act=True, can_defend=True, defense_penalty=-4,
        )
    return AmbushReactionResult(
        can_act=False, can_defend=False, defense_penalty=0,
    )


# ---------------------------------------------------------------------------
# Active jamming (passenger action)
# ---------------------------------------------------------------------------

@dataclass
class ActiveJammingResult:
    """Result of an active jamming attempt."""
    lock_removed: bool
    duration_turns: int


def resolve_active_jamming(jammer_won: bool) -> ActiveJammingResult:
    """
    Resolve an active sensor jamming attempt.

    Success: target loses sensor lock for one turn.
    """
    if jammer_won:
        return ActiveJammingResult(lock_removed=True, duration_turns=1)
    return ActiveJammingResult(lock_removed=False, duration_turns=0)


# ---------------------------------------------------------------------------
# Sensor lock
# ---------------------------------------------------------------------------

def check_auto_sensor_lock(
    has_ultrascanner: bool,
    target_in_range: bool,
    target_is_jamming: bool,
) -> bool:
    """
    Check if sensor lock is automatic.

    Auto-lock with ultrascanner if target is in range and not jamming.
    """
    if not has_ultrascanner or not target_in_range:
        return False
    return not target_is_jamming
