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

def classify_ship(sm: int, chase_bonus: int) -> str:
    """
    Classify a ship as fighter, corvette, or capital.

    Fighter: SM 4-7 or chase +16 or better.
    Corvette: SM 7-10 or chase +11 to +15.
    Capital: SM 10+ or chase +10 or worse.

    SM takes priority, then chase bonus as tiebreaker.
    """
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
