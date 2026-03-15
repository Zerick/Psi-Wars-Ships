"""
Damage subsystem for M1 Psi-Core.

Implements the complete damage resolution pipeline:
force screen ablation -> armor penetration -> wound determination ->
subsystem damage (3d6 table + cascade) -> wound accumulation.

Also includes cinematic injury rules (mook vehicles, Just a Scratch).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGETED_SYSTEM_PENALTY = -5

# Wound level ordering for escalation
WOUND_SEVERITY = {
    "none": 0, "scratch": 1, "minor": 2, "major": 3,
    "crippling": 4, "mortal": 5, "lethal": 6,
}

WOUND_LEVELS = ["none", "scratch", "minor", "major", "crippling", "mortal", "lethal"]


# ---------------------------------------------------------------------------
# Force screen ablation
# ---------------------------------------------------------------------------

@dataclass
class ForceScreenResult:
    """Result of force screen damage absorption."""
    absorbed: int
    penetrating: int
    remaining_fdr: int
    hull_ad_negated: bool = False  # True if hull armor should ignore AD


# Standard GURPS armor divisor progression for hardened DR
# Each level of hardened reduces the AD one step down this chain
_AD_PROGRESSION = [1.0, 2.0, 3.0, 5.0, 10.0, 100.0]


def reduce_armor_divisor_hardened(armor_divisor: float, hardened_level: int = 1) -> float:
    """
    Reduce an armor divisor by the hardened level.

    Hardened 1: AD goes down one step on the progression.
    AD progression: (100) → (10) → (5) → (3) → (2) → (1)
    So AD(5) with hardened 1 becomes AD(3).
    AD(2) with hardened 1 becomes AD(1) — no divisor.
    """
    if armor_divisor <= 1.0:
        return 1.0

    # Find current position in the progression
    for i, val in enumerate(_AD_PROGRESSION):
        if armor_divisor <= val:
            # Step down by hardened_level positions
            new_idx = max(0, i - hardened_level)
            return _AD_PROGRESSION[new_idx]

    # Off the top of the scale, step down
    return _AD_PROGRESSION[max(0, len(_AD_PROGRESSION) - 1 - hardened_level)]


# Damage types where standard force screens negate ALL armor divisors
_PLASMA_DAMAGE_TYPES = {"burn", "burn_ex", "plasma", "plasma_lance", "shaped_charge"}


def apply_force_screen(
    incoming_damage: int,
    current_fdr: int,
    armor_divisor: Optional[float],
    force_screen_type: str,
    damage_type: str,
) -> ForceScreenResult:
    """
    Apply force screen damage absorption.

    Force screens are hardened 1 and ablative.

    RAW rules:
    - Hardened 1: armor divisors reduced one step against the screen.
    - Against plasma/plasma lance/shaped charge: force screens ignore ALL
      armor divisors AND eliminate the AD for armor underneath the screen
      (as long as the screen had some DR remaining).
    - Heavy force screens: ignore ALL armor divisors from ALL attacks.
    - Every point absorbed reduces fDR by 1.
    - If force screen has any DR remaining when hit, hull armor AD is
      also negated for that attack.
    """
    if current_fdr <= 0 or force_screen_type == "none":
        return ForceScreenResult(
            absorbed=0, penetrating=incoming_damage,
            remaining_fdr=current_fdr,
            hull_ad_negated=False,
        )

    # Determine if this screen negates the armor divisor entirely
    ad = armor_divisor if armor_divisor else 1.0
    is_plasma = damage_type.lower() in _PLASMA_DAMAGE_TYPES
    is_heavy = force_screen_type == "heavy"

    if is_heavy or is_plasma:
        # Screen ignores ALL armor divisors — use full fDR
        effective_fdr = current_fdr
        hull_ad_negated = True  # Hull armor also ignores AD for this hit
    else:
        # Hardened 1: reduce AD one step, then apply to screen fDR
        reduced_ad = reduce_armor_divisor_hardened(ad, hardened_level=1)
        if reduced_ad > 1.0:
            effective_fdr = int(current_fdr / reduced_ad)
        else:
            effective_fdr = current_fdr
        hull_ad_negated = False

    # Ablative absorption
    absorbed = min(incoming_damage, effective_fdr)
    penetrating = incoming_damage - absorbed
    # fDR reduction is always 1:1 with damage absorbed (ablative)
    remaining_fdr = current_fdr - absorbed

    return ForceScreenResult(
        absorbed=absorbed,
        penetrating=penetrating,
        remaining_fdr=max(0, remaining_fdr),
        hull_ad_negated=hull_ad_negated,
    )


# ---------------------------------------------------------------------------
# Armor divisor application
# ---------------------------------------------------------------------------

def apply_armor_divisor(dr: int, divisor: float) -> int:
    """
    Apply an armor divisor to DR.

    Divisor > 1: divides DR (e.g., (5) means DR/5).
    Divisor < 1: multiplies DR (e.g., (0.5) means DR*2).
    Divisor = 1: no change.

    Always rounds down.
    """
    if divisor == 1.0:
        return dr
    elif divisor > 1.0:
        return int(dr / divisor)
    else:
        # Fractional divisor multiplies DR
        return int(dr / divisor)


# ---------------------------------------------------------------------------
# Hull penetration
# ---------------------------------------------------------------------------

def calculate_penetrating_damage(
    damage: int,
    dr: int,
    armor_divisor: float = 1.0,
) -> int:
    """
    Calculate penetrating damage after armor.

    Penetrating = damage - effective_DR, minimum 0.
    """
    effective_dr = apply_armor_divisor(dr, armor_divisor)
    return max(0, damage - effective_dr)


# ---------------------------------------------------------------------------
# Wound level
# ---------------------------------------------------------------------------

def determine_wound_level(damage: int, max_hp: int) -> str:
    """
    Determine wound level from penetrating damage vs max HP.

    This is per-hit, not cumulative.
    """
    if damage <= 0 or max_hp <= 0:
        return "none"

    ratio = damage / max_hp

    if ratio >= 5.0:
        return "lethal"
    elif ratio >= 2.0:
        return "mortal"
    elif ratio >= 1.0:
        return "crippling"
    elif ratio >= 0.5:
        return "major"
    elif ratio >= 0.1:
        return "minor"
    else:
        return "scratch"


# ---------------------------------------------------------------------------
# Subsystem damage table (3d6)
# ---------------------------------------------------------------------------

# (system_hit, cascade_target) — cascade_target is None for cargo/hangar
_SUBSYSTEM_TABLE = {
    3: ("fuel", "power"),
    4: ("habitat", "cargo_hangar"),
    5: ("propulsion", "weaponry"),
    6: ("cargo_hangar", None),
    7: ("equipment", "controls"),
    8: ("power", "propulsion"),
    9: ("weaponry", "equipment"),
    10: ("armor", "fuel"),
    11: ("fuel", "power"),
    12: ("habitat", "cargo_hangar"),
    13: ("propulsion", "weaponry"),
    14: ("cargo_hangar", None),
    15: ("equipment", "controls"),
    16: ("power", "propulsion"),
    17: ("weaponry", "equipment"),
    18: ("armor", "fuel"),
}


def get_subsystem_hit(roll: int) -> tuple[str, Optional[str]]:
    """
    Look up which subsystem was hit and its cascade target.

    Returns: (system_hit, cascade_target_or_none)
    """
    return _SUBSYSTEM_TABLE[roll]


# ---------------------------------------------------------------------------
# Cascade logic
# ---------------------------------------------------------------------------

@dataclass
class CascadeResult:
    """Result of subsystem cascade resolution."""
    system_destroyed: bool
    is_crippling_wound: bool
    cascades_to: Optional[str]


def resolve_subsystem_cascade(
    system: str,
    current_status: str,
    ht_roll_succeeded: bool,
    cascade_target: Optional[str],
) -> CascadeResult:
    """
    Resolve cascade when a subsystem that's already damaged is hit again.

    If disabled: roll HT. Failure -> destroyed (counts as crippling wound).
                         Success -> cascade to next system.
    If destroyed: cascade to next system.
    """
    if current_status == "disabled":
        if not ht_roll_succeeded:
            return CascadeResult(
                system_destroyed=True,
                is_crippling_wound=True,
                cascades_to=None,
            )
        else:
            return CascadeResult(
                system_destroyed=False,
                is_crippling_wound=False,
                cascades_to=cascade_target,
            )
    elif current_status == "destroyed":
        return CascadeResult(
            system_destroyed=False,
            is_crippling_wound=False,
            cascades_to=cascade_target,
        )
    else:
        # System is operational — it gets disabled/destroyed by the wound level
        return CascadeResult(
            system_destroyed=False,
            is_crippling_wound=False,
            cascades_to=None,
        )


# ---------------------------------------------------------------------------
# Wound accumulation
# ---------------------------------------------------------------------------

@dataclass
class AccumulationResult:
    """Result of wound accumulation check."""
    escalated: bool
    new_wound_level: str
    extra_system_damage: bool


def check_wound_accumulation(
    current_wound: str,
    new_wound: str,
    ht_roll_succeeded: bool,
    ht_margin: int = 1,
) -> AccumulationResult:
    """
    Check if a wound accumulates (escalates).

    A wound accumulates if the new wound is equal to or less severe
    than the current wound level. The ship rolls HT; failure escalates
    by one level. HT success with margin 0 on a system-damaging wound
    triggers an extra system hit.
    """
    cur_sev = WOUND_SEVERITY.get(current_wound, 0)
    new_sev = WOUND_SEVERITY.get(new_wound, 0)

    # Higher wound applies directly, no accumulation
    if new_sev > cur_sev:
        return AccumulationResult(
            escalated=False,
            new_wound_level=new_wound,
            extra_system_damage=False,
        )

    # Same or lower severity: accumulation check
    if not ht_roll_succeeded:
        # Escalate by one level
        escalated_idx = min(cur_sev + 1, len(WOUND_LEVELS) - 1)
        return AccumulationResult(
            escalated=True,
            new_wound_level=WOUND_LEVELS[escalated_idx],
            extra_system_damage=False,
        )
    else:
        # HT succeeded — check for margin 0 extra system damage
        extra = (ht_margin == 0 and cur_sev >= WOUND_SEVERITY["major"])
        return AccumulationResult(
            escalated=False,
            new_wound_level=current_wound,
            extra_system_damage=extra,
        )


# ---------------------------------------------------------------------------
# Cinematic injury
# ---------------------------------------------------------------------------

@dataclass
class MookResult:
    """Result of applying mook rules."""
    removed: bool


def apply_mook_rules(wound_level: str) -> MookResult:
    """
    Apply mook vehicle rules.

    Mook taking major wound or worse: removed from combat.
    Anything less: continues with sparks.
    """
    severity = WOUND_SEVERITY.get(wound_level, 0)
    return MookResult(removed=severity >= WOUND_SEVERITY["major"])


@dataclass
class JustAScratchResult:
    """Result of applying Just a Scratch."""
    reduced_level: str
    max_accumulation_effect: str


def apply_just_a_scratch(wound_level: str) -> JustAScratchResult:
    """
    Apply 'Just a Scratch' cinematic rule.

    Reduces any wound to minor. Accumulation from this can only
    trigger disabled systems, never worse.
    """
    return JustAScratchResult(
        reduced_level="minor",
        max_accumulation_effect="disabled",
    )
