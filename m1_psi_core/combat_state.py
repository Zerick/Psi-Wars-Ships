"""
Combat state tracking for M1 Psi-Core.

Manages the dynamic state of a combat encounter: range bands between
ship pairs, advantage/matched speed, facing, and special conditions
like hugging. This state is NOT persisted to the database — it exists
only during an active combat session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RANGE_BAND_ORDER = [
    "close", "short", "medium", "long", "extreme",
    "distant", "beyond_visual", "remote", "beyond_remote",
]

# Penalty is the LOW (least severe) value for each band
# Used for all attack rolls per Psi-Wars rules
RANGE_BAND_PENALTIES = {
    "close": 0,
    "short": -3,
    "medium": -7,
    "long": -11,
    "extreme": -15,
    "distant": -19,
    "beyond_visual": -23,
    "remote": -27,
    "beyond_remote": -31,
}

VALID_FACINGS = ["front", "rear", "left", "right", "top", "bottom"]


# ---------------------------------------------------------------------------
# Range band functions
# ---------------------------------------------------------------------------

def get_range_penalty(band: str) -> int:
    """
    Get the range penalty for a given range band.

    Returns the LOW (least severe) penalty, per Psi-Wars rules:
    "Use the low range penalty for all ranged attacks."
    """
    return RANGE_BAND_PENALTIES[band]


def shift_range_band(current_band: str, shift: int) -> str:
    """
    Shift a range band by the given number of steps.

    Positive = farther, negative = closer. Clamps at close/beyond_remote.
    """
    idx = RANGE_BAND_ORDER.index(current_band)
    new_idx = max(0, min(len(RANGE_BAND_ORDER) - 1, idx + shift))
    return RANGE_BAND_ORDER[new_idx]


def shifts_required(from_band: str, to_band: str) -> int:
    """
    Calculate how many range-band shifts are needed to move between bands.

    Remote range requires 2 shifts to enter or exit (per Psi-Wars rules).
    """
    from_idx = RANGE_BAND_ORDER.index(from_band)
    to_idx = RANGE_BAND_ORDER.index(to_band)

    # Special rule: remote requires 2 shifts to enter/exit
    remote_idx = RANGE_BAND_ORDER.index("remote")
    bv_idx = RANGE_BAND_ORDER.index("beyond_visual")
    br_idx = RANGE_BAND_ORDER.index("beyond_remote")

    if (from_band == "beyond_visual" and to_band == "remote") or \
       (from_band == "remote" and to_band == "beyond_visual"):
        return 2

    if (from_band == "remote" and to_band == "beyond_remote") or \
       (from_band == "beyond_remote" and to_band == "remote"):
        return 2

    return abs(to_idx - from_idx)


# ---------------------------------------------------------------------------
# Collision range
# ---------------------------------------------------------------------------

def is_collision_range(speed: int, range_band: str) -> bool:
    """
    Check if a ship is at collision range.

    A ship is at collision range when its speed bonus exceeds the
    absolute value of the range penalty. For simplicity, we use
    the ship's top_speed as a proxy for its speed bonus.

    In GURPS, speed translates to a speed/range penalty via the
    Size and Speed/Range table. For vehicular combat, if the speed
    bonus > |range penalty|, you're at collision range.
    """
    range_penalty = abs(get_range_penalty(range_band))

    # Simplified speed-to-penalty mapping for vehicular combat
    # GURPS Speed/Range table: roughly -1 per doubling of 2 yards
    # For space combat speeds (hundreds of mph), this approximation works
    if speed <= 0:
        speed_penalty = 0
    elif speed <= 3:
        speed_penalty = 1
    elif speed <= 7:
        speed_penalty = 3
    elif speed <= 15:
        speed_penalty = 5
    elif speed <= 30:
        speed_penalty = 7
    elif speed <= 70:
        speed_penalty = 9
    elif speed <= 150:
        speed_penalty = 11
    elif speed <= 300:
        speed_penalty = 13
    elif speed <= 700:
        speed_penalty = 15
    elif speed <= 1500:
        speed_penalty = 17
    else:
        speed_penalty = 19

    return speed_penalty > range_penalty


# ---------------------------------------------------------------------------
# Facing
# ---------------------------------------------------------------------------

def get_facing_for_intent(intent: str) -> str:
    """
    Determine facing based on pursue/evade intent.

    Pursuers face front toward opponent.
    Evaders face rear toward opponent.
    """
    if intent == "pursue":
        return "front"
    elif intent == "evade":
        return "rear"
    else:
        raise ValueError(f"Invalid intent '{intent}': must be 'pursue' or 'evade'")


# ---------------------------------------------------------------------------
# Beyond Visual / Remote special rules
# ---------------------------------------------------------------------------

def can_engage_at_range(range_band: str, ultrascanner_range: Optional[int] = None) -> bool:
    """
    Check if a ship can engage in combat at the given range band.

    Beyond visual range requires active sensors (ultrascanner).
    Beyond remote is beyond tactical consideration entirely.
    """
    if range_band == "beyond_remote":
        return False
    if range_band in ("beyond_visual", "remote"):
        return ultrascanner_range is not None and ultrascanner_range > 0
    return True


def can_gain_advantage_at_range(range_band: str) -> bool:
    """
    Check if advantage can be gained at the given range band.

    Remote and beyond remote: advantage cannot be gained.
    """
    if range_band in ("remote", "beyond_remote"):
        return False
    return True


# ---------------------------------------------------------------------------
# Hugging helpers
# ---------------------------------------------------------------------------

def can_hug(hugger_sm: int, target_sm: int) -> bool:
    """
    Check if a ship can hug a larger ship.

    Requires the hugger to be at least 3 SM smaller than the target.
    Also requires matched speed at collision range (checked elsewhere).
    """
    return (target_sm - hugger_sm) >= 3


def is_inside_force_screen(hugger_sm: int, target_sm: int) -> bool:
    """
    Check if a hugging ship is inside the target's force screen.

    Requires the hugger to be at least 6 SM smaller.
    """
    return (target_sm - hugger_sm) >= 6


# ---------------------------------------------------------------------------
# Engagement State
# ---------------------------------------------------------------------------

@dataclass
class EngagementState:
    """
    Tracks the relationship between two ships in combat.

    This is the per-pair state that changes each turn based on
    chase roll outcomes, maneuver choices, and combat events.
    """
    ship_a_id: str
    ship_b_id: str
    range_band: str = "long"

    advantage: Optional[str] = None      # Ship ID that has advantage, or None
    matched_speed: bool = False
    hugging: Optional[str] = None        # Ship ID that is hugging, or None

    facing_a: str = "front"
    facing_b: str = "front"

    def set_advantage(self, ship_id: str) -> None:
        """Grant advantage to a ship."""
        if ship_id not in (self.ship_a_id, self.ship_b_id):
            raise ValueError(f"Ship '{ship_id}' not in this engagement")
        self.advantage = ship_id

    def clear_advantage(self) -> None:
        """Remove advantage."""
        self.advantage = None
        self.matched_speed = False

    def set_matched_speed(self, ship_id: str) -> None:
        """Set matched speed. Requires the ship to already have advantage."""
        if self.advantage != ship_id:
            raise ValueError(
                f"Ship '{ship_id}' must have advantage before matching speed"
            )
        self.matched_speed = True

    def apply_static_maneuver(self, ship_id: str) -> None:
        """
        Apply the consequences of a static maneuver.

        The ship loses advantage and matched speed.
        """
        if self.advantage == ship_id:
            self.advantage = None
        self.matched_speed = False
