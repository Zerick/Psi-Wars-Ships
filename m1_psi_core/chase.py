"""
Chase subsystem for M1 Psi-Core.

Implements the Psi-Wars Action Vehicular Combat chase roll system:
Quick Contests of piloting skill, victory margin interpretation,
range band shifting, and escape conditions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChaseOutcome:
    """Result of resolving a chase roll victory margin."""
    range_shift: int  # Actual range shift applied (0 if no shift chosen)
    advantage_gained: bool
    opponent_loses_advantage: bool
    can_gain_advantage: bool  # Option available to winner
    can_match_speed: bool     # Option available to winner
    can_shift_range: int      # Maximum bands the winner may shift


@dataclass
class StaticManeuverEffects:
    """Effects of a static maneuver on the chase state."""
    opponent_free_range_shift: int
    loses_matched_speed: bool


def resolve_chase_outcome(
    margin: int,
    winner_intent: str,
    winner_had_advantage: bool,
    loser_had_advantage: bool,
) -> ChaseOutcome:
    """
    Determine chase outcome from the margin of victory.

    This returns the OPTIONS available. The actual choice of what
    to do with the victory is made by the player/AI.
    """
    opponent_loses_advantage = loser_had_advantage and margin >= 0

    if margin >= 10:
        return ChaseOutcome(
            range_shift=0,
            advantage_gained=False,
            opponent_loses_advantage=opponent_loses_advantage,
            can_gain_advantage=True,
            can_match_speed=True,
            can_shift_range=2,
        )
    elif margin >= 5:
        can_match = winner_had_advantage
        return ChaseOutcome(
            range_shift=0,
            advantage_gained=False,
            opponent_loses_advantage=opponent_loses_advantage,
            can_gain_advantage=True,
            can_match_speed=can_match,
            can_shift_range=1,
        )
    else:
        # Victory by 0-4: no range change, opponent loses advantage
        return ChaseOutcome(
            range_shift=0,
            advantage_gained=False,
            opponent_loses_advantage=opponent_loses_advantage,
            can_gain_advantage=False,
            can_match_speed=False,
            can_shift_range=0,
        )


def can_fire_fixed_weapons(stall_speed: int, chase_margin: int) -> bool:
    """
    Check if a ship with stall speed can fire fixed weapons.

    Ships with stall speed must succeed in the chase roll (margin >= 0)
    to fire fixed-mount weapons. Ships without stall speed can always fire.
    """
    if stall_speed == 0:
        return True
    return chase_margin >= 0


def validate_range_shift(intent: str, shift_direction: int) -> bool:
    """
    Validate a range shift against the pursuer/evader intent.

    Pursuers may only reduce range (shift < 0).
    Evaders may only increase range (shift > 0).
    """
    if intent == "pursue":
        return shift_direction < 0
    elif intent == "evade":
        return shift_direction > 0
    return False


def can_pursue(stall_speed: int, opponent_has_advantage: bool) -> bool:
    """
    Check if a ship can pursue.

    Ships with stall speed cannot pursue a target that has advantage
    against them.
    """
    if stall_speed > 0 and opponent_has_advantage:
        return False
    return True


def get_static_maneuver_effects() -> StaticManeuverEffects:
    """
    Get the effects of choosing a static maneuver.

    Static maneuvers grant the opponent one free range band shift
    and cause loss of matched speed.
    """
    return StaticManeuverEffects(
        opponent_free_range_shift=1,
        loses_matched_speed=True,
    )


def check_escape(
    range_band: str = "extreme",
    hyperspace_ready: bool = False,
) -> bool:
    """
    Check if escape conditions are met.

    Escape occurs when:
    - Target reaches beyond_remote range
    - Target successfully shunts into hyperspace
    """
    if range_band == "beyond_remote":
        return True
    if hyperspace_ready:
        return True
    return False


def voluntary_shift_allowed(
    intent_a: str, intent_b: str, both_agree: bool,
) -> bool:
    """
    Check if a voluntary range shift is allowed.

    If both pursue and agree: one extra band closer.
    If both evade and agree: one extra band farther or both escape.
    """
    if not both_agree:
        return False
    return (intent_a == intent_b)
