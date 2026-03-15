"""
Special rules subsystem for M1 Psi-Core.

Handles lucky breaks, hugging mechanics, force screen configuration,
ramming, and ship classification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Lucky breaks
# ---------------------------------------------------------------------------

LUCKY_BREAK_OPTIONS = frozenset({
    "invoke_obstacle",
    "increase_wound_severity",
    "ignore_attacks",
})


def apply_lucky_break_wound(current_wound: str) -> str:
    """
    Apply lucky break to increase wound severity by 2 levels.

    Returns the new wound level.
    """
    from m1_psi_core.damage import WOUND_LEVELS, WOUND_SEVERITY
    cur_idx = WOUND_SEVERITY.get(current_wound, 0)
    new_idx = min(cur_idx + 2, len(WOUND_LEVELS) - 1)
    return WOUND_LEVELS[new_idx]


def get_free_lucky_breaks(is_ace_pilot: bool) -> int:
    """
    Get the number of free lucky breaks per chase scenario.

    Ace Pilots get 1 free. Others get 0 (must spend CP/Serendipity).
    """
    return 1 if is_ace_pilot else 0


# ---------------------------------------------------------------------------
# Hugging
# ---------------------------------------------------------------------------

@dataclass
class HuggedAttackPenalties:
    """Attack restrictions on a ship that is being hugged."""
    turret_fraction: float  # Only this fraction of turrets can fire
    fixed_mounts_disabled: bool
    attack_penalty: int


def get_hugged_attack_penalties() -> HuggedAttackPenalties:
    """
    Get the attack restrictions for a hugged ship.

    Half turrets (proper facing), no fixed mounts, -2 to all attacks.
    """
    return HuggedAttackPenalties(
        turret_fraction=0.5,
        fixed_mounts_disabled=True,
        attack_penalty=-2,
    )


def get_attack_hugging_ship_penalty() -> int:
    """Penalty for attacking a ship that is hugging another: -2."""
    return -2


def calculate_collateral_hit_chance(hugged_sm: int) -> int:
    """
    Calculate the roll needed to hit the hugged vehicle on a miss.

    If you miss or dodge the hugging ship, roll 3d6: hit the
    hugged vehicle on (hugged SM - 3) or less.
    """
    return hugged_sm - 3


def hugging_ignores_force_screen(hugger_sm: int, target_sm: int) -> bool:
    """
    Check if a hugging ship ignores the target's force screen.

    Requires the hugger to be 6+ SM smaller than the target.
    """
    return (target_sm - hugger_sm) >= 6


# ---------------------------------------------------------------------------
# Force screen configuration
# ---------------------------------------------------------------------------

@dataclass
class ForceScreenConfig:
    """Force screen DR distribution across facings."""
    front: int
    rear: int
    left: int
    right: int
    top: int
    bottom: int


def configure_force_screen(
    fdr_max: int,
    focused_facing: Optional[str] = None,
) -> ForceScreenConfig:
    """
    Configure force screen DR distribution.

    Default: equal on all facings.
    Focused: double DR on one facing, halve all others.
    """
    if focused_facing is None:
        return ForceScreenConfig(
            front=fdr_max, rear=fdr_max,
            left=fdr_max, right=fdr_max,
            top=fdr_max, bottom=fdr_max,
        )

    halved = fdr_max // 2
    doubled = fdr_max * 2

    config = ForceScreenConfig(
        front=halved, rear=halved,
        left=halved, right=halved,
        top=halved, bottom=halved,
    )

    if focused_facing == "front":
        config.front = doubled
    elif focused_facing == "rear":
        config.rear = doubled
    elif focused_facing == "left":
        config.left = doubled
    elif focused_facing == "right":
        config.right = doubled
    elif focused_facing == "top":
        config.top = doubled
    elif focused_facing == "bottom":
        config.bottom = doubled

    return config


# ---------------------------------------------------------------------------
# Ship classification
# ---------------------------------------------------------------------------

def classify_ship(sm: int, chase_bonus: int, ship_class: str = "") -> str:
    """
    Classify a ship as fighter, corvette, or capital.

    If ship_class is provided (from JSON data), use it directly.
    Otherwise fall back to SM/chase-based heuristic:
        Fighter: SM 4-7 or chase +16 or better.
        Corvette: SM 7-10 or chase +11 to +15.
        Capital: SM 10+ or chase +10 or worse.

    This matters for relative size penalties (-5/-10 to hit)
    and piloting skill specialization.
    """
    # Prefer explicit classification from ship data
    if ship_class in ("fighter", "corvette", "capital"):
        return ship_class

    # SM-based classification
    if sm <= 7:
        if sm >= 4:
            return "fighter"
    if 7 < sm <= 10:
        return "corvette"
    if sm > 10:
        return "capital"

    # Chase-based classification for edge cases
    if chase_bonus >= 16:
        return "fighter"
    elif chase_bonus >= 11:
        return "corvette"
    else:
        return "capital"


# ---------------------------------------------------------------------------
# Luck advantage (GURPS B66) — real-time cooldown tracking
# ---------------------------------------------------------------------------

import time as _time

# Cooldown in seconds for each Luck level
LUCK_COOLDOWNS = {
    "luck": 3600,           # 1 hour
    "extraordinary": 1800,  # 30 minutes
    "ridiculous": 600,      # 10 minutes
}


@dataclass
class LuckRerollResult:
    """Result of applying Luck to reroll dice."""
    original_roll: int
    rerolls: list[int]
    chosen_roll: int
    pick_mode: str  # "best" or "worst"


class LuckTracker:
    """
    Tracks Luck advantage usage with real-time cooldowns.

    RAW (GURPS B66):
    - Luck (15 pts): reroll once per hour of real time
    - Extraordinary Luck (30 pts): once per 30 minutes
    - Ridiculous Luck (60 pts): once per 10 minutes

    Usage: reroll a bad roll twice, take the best of 3.
    Or force an attacker to reroll twice, take the worst of 3.

    Cannot share Luck between characters.
    Cannot save up — must wait the full cooldown between uses.
    """

    def __init__(self):
        # ship_id -> luck level ("none", "luck", "extraordinary", "ridiculous")
        self._levels: dict[str, str] = {}
        # ship_id -> timestamp of last use (0 = never used)
        self._last_used: dict[str, float] = {}

    def register(self, ship_id: str, luck_level: str) -> None:
        """Register a ship's Luck level."""
        self._levels[ship_id] = luck_level
        self._last_used[ship_id] = 0.0

    def is_available(self, ship_id: str) -> bool:
        """Check if Luck is available (off cooldown) for this ship."""
        level = self._levels.get(ship_id, "none")
        if level == "none":
            return False

        cooldown = LUCK_COOLDOWNS.get(level, 3600)
        last = self._last_used.get(ship_id, 0.0)
        elapsed = _time.time() - last

        return elapsed >= cooldown

    def use(self, ship_id: str) -> None:
        """Mark Luck as used (starts the cooldown timer)."""
        self._last_used[ship_id] = _time.time()

    def get_cooldown_remaining(self, ship_id: str) -> int:
        """Get seconds remaining on cooldown. 0 = ready."""
        level = self._levels.get(ship_id, "none")
        if level == "none":
            return -1  # No Luck at all

        cooldown = LUCK_COOLDOWNS.get(level, 3600)
        last = self._last_used.get(ship_id, 0.0)
        elapsed = _time.time() - last
        remaining = cooldown - elapsed

        return max(0, int(remaining))

    def get_cooldown_str(self, ship_id: str) -> str:
        """Human-readable cooldown status."""
        remaining = self.get_cooldown_remaining(ship_id)
        if remaining < 0:
            return "no Luck"
        if remaining == 0:
            return "ready"
        minutes = remaining // 60
        seconds = remaining % 60
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def get_level(self, ship_id: str) -> str:
        """Get the Luck level for a ship."""
        return self._levels.get(ship_id, "none")


def apply_luck_reroll(
    original_roll: int,
    rerolls: list[int],
    pick: str = "best",
) -> LuckRerollResult:
    """
    Apply Luck to a dice roll.

    RAW: Roll 2 more times, take the best or worst of all 3.
    - Own roll (defensive): pick="best" → lowest roll wins
    - Opponent's roll (offensive): pick="worst" → highest roll wins

    For success rolls (roll-under), lower is better.
    """
    all_rolls = [original_roll] + rerolls

    if pick == "best":
        chosen = min(all_rolls)
    else:
        chosen = max(all_rolls)

    return LuckRerollResult(
        original_roll=original_roll,
        rerolls=rerolls,
        chosen_roll=chosen,
        pick_mode=pick,
    )


# ---------------------------------------------------------------------------
# Lucky Break (separate from Luck advantage!)
# ---------------------------------------------------------------------------
# Lucky Breaks enable maneuvers that require "suitable scenery."
# They can also:
#   - Invoke new obstacles/terrain
#   - Increase wound severity by 2 levels
#   - Ignore all attacks for 1 round
# Ace Pilots get 1 free Lucky Break per chase.
# Others must spend a character point or use Serendipity.
# These are tracked separately from the Luck advantage.

class LuckyBreakTracker:
    """Tracks Lucky Break uses per ship."""

    def __init__(self):
        self._uses: dict[str, int] = {}

    def register(self, ship_id: str, is_ace_pilot: bool) -> None:
        """Ace pilots get 1 free Lucky Break per chase."""
        self._uses[ship_id] = 1 if is_ace_pilot else 0

    def available(self, ship_id: str) -> int:
        return self._uses.get(ship_id, 0)

    def use(self, ship_id: str) -> bool:
        if self._uses.get(ship_id, 0) > 0:
            self._uses[ship_id] -= 1
            return True
        return False


# ---------------------------------------------------------------------------
# Flesh Wound (Impulse / Character Points)
# ---------------------------------------------------------------------------

def apply_flesh_wound(wound_level: str) -> str:
    """
    Apply Flesh Wound cinematic rule.

    RAW: Spending 1 character point reduces any wound severity to Minor.
    Accumulation after flesh wound can only trigger disabled systems,
    nothing worse.

    Args:
        wound_level: Current wound level to reduce.

    Returns:
        "minor" (always).
    """
    return "minor"
