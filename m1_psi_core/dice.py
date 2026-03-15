"""
Dice subsystem for M1 Psi-Core.

All randomness in the engine flows through this module. The DiceRoller
class supports seeding for deterministic test replay, and all game
mechanics that involve dice delegate here.

Also provides:
- GURPS damage string parsing ("6d×5(5) burn" -> structured components)
- Success roll resolution with critical detection
- Quick contest resolution
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes for structured results
# ---------------------------------------------------------------------------

@dataclass
class DamageSpec:
    """Parsed damage string components."""
    dice: int
    multiplier: int
    adds: int
    armor_divisor: Optional[float]
    damage_type: str
    explosive: bool
    raw: str


@dataclass
class SuccessResult:
    """Result of a GURPS 3d6 success roll."""
    success: bool
    margin: int
    critical: bool
    critical_type: Optional[str]  # "success", "failure", or None
    auto_fail: bool = False


@dataclass
class ContestResult:
    """Result of a GURPS Quick Contest."""
    winner: Optional[str]  # "a", "b", or None (tie)
    margin_of_victory: int
    margin_a: int
    margin_b: int


# ---------------------------------------------------------------------------
# DiceRoller
# ---------------------------------------------------------------------------

class DiceRoller:
    """
    Seedable dice roller for GURPS mechanics.

    All random rolls in M1 flow through this class.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def roll_1d6(self) -> int:
        """Roll a single six-sided die."""
        return self._rng.randint(1, 6)

    def roll_nd6(self, n: int) -> int:
        """Roll n six-sided dice and return the sum."""
        return sum(self._rng.randint(1, 6) for _ in range(n))

    def roll_3d6(self) -> int:
        """Roll 3d6 — the standard GURPS success roll."""
        return self.roll_nd6(3)

    def roll_damage(self, damage_str: str) -> int:
        """
        Parse a damage string and roll the damage.

        Returns the raw damage total (dice * multiplier + adds).
        """
        spec = parse_damage_string(damage_str)
        if spec.dice == 0:
            return 0
        dice_total = self.roll_nd6(spec.dice)
        return dice_total * spec.multiplier + spec.adds


# ---------------------------------------------------------------------------
# Damage string parsing
# ---------------------------------------------------------------------------

_DAMAGE_PATTERN = re.compile(
    r"^(\d+)d"                        # Dice count
    r"(?:[×xX](\d+))?"               # Optional multiplier
    r"(?:\(([0-9.]+)\))?"            # Optional armor divisor
    r"(?:\s+(.+))?$"                  # Remainder: type and flags
)

_DAMAGE_TYPES = {
    "burn", "cr", "cut", "tox", "sur", "imp", "pi",
    "fat", "cor", "aff", "tbb", "spec",
}


def parse_damage_string(raw: str) -> DamageSpec:
    """
    Parse a GURPS damage string into structured components.

    Handles all formats found in the Psi-Wars weapon catalog.
    """
    raw = raw.strip()

    if raw == "0":
        return DamageSpec(
            dice=0, multiplier=0, adds=0,
            armor_divisor=None, damage_type="special",
            explosive=False, raw=raw,
        )

    match = _DAMAGE_PATTERN.match(raw)
    if not match:
        return DamageSpec(
            dice=0, multiplier=0, adds=0,
            armor_divisor=None, damage_type="unknown",
            explosive=False, raw=raw,
        )

    dice = int(match.group(1))
    multiplier = int(match.group(2)) if match.group(2) else 1

    # Parse armor divisor
    armor_divisor = None
    if match.group(3):
        ad_val = float(match.group(3))
        # Keep as int if it's a whole number >= 1
        if ad_val >= 1 and ad_val == int(ad_val):
            armor_divisor = int(ad_val)
        else:
            armor_divisor = ad_val

    # Parse remainder for damage type and flags
    remainder = match.group(4) or ""
    tokens = remainder.lower().split()

    damage_type = "unknown"
    explosive = False

    for token in tokens:
        if token in _DAMAGE_TYPES:
            damage_type = token
        elif token == "ex":
            explosive = True

    if damage_type == "unknown" and tokens:
        damage_type = tokens[0]

    return DamageSpec(
        dice=dice, multiplier=multiplier, adds=0,
        armor_divisor=armor_divisor, damage_type=damage_type,
        explosive=explosive, raw=raw,
    )


# ---------------------------------------------------------------------------
# Success roll resolution
# ---------------------------------------------------------------------------

def check_success(
    effective_skill: int,
    roll: int,
    is_defense: bool = False,
) -> SuccessResult:
    """
    Resolve a GURPS 3d6 success roll.

    Implements all critical success/failure rules from GURPS Lite.
    """
    # Minimum skill rule
    if effective_skill < 3 and not is_defense:
        return SuccessResult(
            success=False, margin=effective_skill - roll,
            critical=False, critical_type=None, auto_fail=True,
        )

    margin = effective_skill - roll

    # Determine basic success (3-4 always succeed, 17-18 always fail)
    if roll <= 4:
        success = True
    elif roll >= 17:
        success = False
    else:
        success = roll <= effective_skill

    # Check critical success
    is_critical = False
    critical_type = None

    if roll == 3 or roll == 4:
        is_critical = True
        critical_type = "success"
        success = True
    elif roll == 5 and effective_skill >= 15:
        is_critical = True
        critical_type = "success"
        success = True
    elif roll == 6 and effective_skill >= 16:
        is_critical = True
        critical_type = "success"
        success = True

    # Check critical failure (only if not already critical success)
    if not is_critical:
        if roll == 18:
            is_critical = True
            critical_type = "failure"
            success = False
        elif roll == 17 and effective_skill <= 15:
            is_critical = True
            critical_type = "failure"
            success = False
        elif roll >= effective_skill + 10:
            is_critical = True
            critical_type = "failure"
            success = False

    return SuccessResult(
        success=success, margin=margin,
        critical=is_critical, critical_type=critical_type,
    )


# ---------------------------------------------------------------------------
# Quick contest resolution
# ---------------------------------------------------------------------------

def resolve_quick_contest(
    skill_a: int, roll_a: int,
    skill_b: int, roll_b: int,
) -> ContestResult:
    """
    Resolve a GURPS Quick Contest.

    Both sides roll. Compare margins. The winner has the better margin.
    Ties go to neither side. Margin of victory is the difference.
    """
    margin_a = skill_a - roll_a
    margin_b = skill_b - roll_b

    if margin_a > margin_b:
        return ContestResult("a", margin_a - margin_b, margin_a, margin_b)
    elif margin_b > margin_a:
        return ContestResult("b", margin_b - margin_a, margin_a, margin_b)
    else:
        return ContestResult(None, 0, margin_a, margin_b)
