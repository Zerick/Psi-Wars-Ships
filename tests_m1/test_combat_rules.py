"""
Tests for three combat rules fixes:

1. Force Screen Hardened DR
   RAW: Force screens are "hardened 1" — armor divisors reduced one step.
   Against plasma/plasma lance/shaped charge, force screens ignore ALL
   armor divisors AND eliminate the AD for armor underneath.
   Heavy force screens ignore ALL armor divisors from all attacks.

2. Matched Speed Full Accuracy
   RAW: "You may add accuracy to your attack even if making a Move and
   Attack (or any other attack that does not normally grant accuracy)."
   Also: "Use the higher of |range penalty| or Stall Speed as penalty."

3. Speed Penalty in Range Calculation
   RAW: "Always use the highest of the absolute value of your range
   penalty, your own speed penalty, or your opponent's speed penalty
   as your range penalty."
"""
import pytest
from m1_psi_core.testing import MockShipStats, MockPilot


# ============================================================================
# Force Screen Tests
# ============================================================================

class TestForceScreenHardened:
    """Force screens are hardened 1: armor divisors reduced one step."""

    def test_hardened_reduces_ad_one_step(self):
        """AD(5) becomes AD(3) against hardened 1 force screen."""
        from m1_psi_core.damage import reduce_armor_divisor_hardened

        assert reduce_armor_divisor_hardened(5.0, hardened_level=1) == 3.0

    def test_hardened_reduces_ad3_to_ad2(self):
        """AD(3) becomes AD(2) against hardened 1."""
        from m1_psi_core.damage import reduce_armor_divisor_hardened

        assert reduce_armor_divisor_hardened(3.0, hardened_level=1) == 2.0

    def test_hardened_reduces_ad2_to_ad1(self):
        """AD(2) becomes AD(1) — no armor divisor."""
        from m1_psi_core.damage import reduce_armor_divisor_hardened

        assert reduce_armor_divisor_hardened(2.0, hardened_level=1) == 1.0

    def test_hardened_ad1_stays_ad1(self):
        """AD(1) is already no divisor, stays at 1."""
        from m1_psi_core.damage import reduce_armor_divisor_hardened

        assert reduce_armor_divisor_hardened(1.0, hardened_level=1) == 1.0

    def test_ad10_reduces_to_ad5(self):
        """AD(10) becomes AD(5) against hardened 1."""
        from m1_psi_core.damage import reduce_armor_divisor_hardened

        assert reduce_armor_divisor_hardened(10.0, hardened_level=1) == 5.0


class TestForceScreenPlasma:
    """Force screens vs plasma: ignore ALL armor divisors."""

    def test_plasma_ad_negated_by_standard_screen(self):
        """Standard force screen negates AD for plasma damage."""
        from m1_psi_core.damage import apply_force_screen

        # 100 damage, 200 fDR, AD(5), plasma
        result = apply_force_screen(
            incoming_damage=100, current_fdr=200,
            armor_divisor=5.0, force_screen_type="standard",
            damage_type="burn",  # plasma is "burn" type
        )
        # Screen uses full fDR (AD negated), absorbs all 100
        assert result.absorbed == 100
        assert result.penetrating == 0

    def test_standard_screen_returns_negated_ad_flag(self):
        """When screen absorbs plasma, hull AD should also be negated."""
        from m1_psi_core.damage import apply_force_screen

        result = apply_force_screen(
            incoming_damage=300, current_fdr=200,
            armor_divisor=5.0, force_screen_type="standard",
            damage_type="burn",
        )
        # 200 absorbed, 100 penetrates, but hull AD should be negated
        assert result.absorbed == 200
        assert result.penetrating == 100
        assert result.hull_ad_negated is True

    def test_screen_depleted_hull_ad_still_negated(self):
        """Even if screen is depleted by the hit, hull AD stays negated
        as long as screen had SOME DR remaining."""
        from m1_psi_core.damage import apply_force_screen

        result = apply_force_screen(
            incoming_damage=300, current_fdr=1,  # Just 1 fDR left
            armor_divisor=5.0, force_screen_type="standard",
            damage_type="burn",
        )
        assert result.hull_ad_negated is True

    def test_no_screen_hull_ad_not_negated(self):
        """Without a force screen, hull AD is applied normally."""
        from m1_psi_core.damage import apply_force_screen

        result = apply_force_screen(
            incoming_damage=100, current_fdr=0,
            armor_divisor=5.0, force_screen_type="none",
            damage_type="burn",
        )
        assert result.hull_ad_negated is False


class TestHeavyForceScreen:
    """Heavy force screens ignore ALL armor divisors."""

    def test_heavy_screen_ignores_all_ad(self):
        """Heavy screen ignores AD regardless of damage type."""
        from m1_psi_core.damage import apply_force_screen

        result = apply_force_screen(
            incoming_damage=100, current_fdr=200,
            armor_divisor=10.0, force_screen_type="heavy",
            damage_type="kinetic",  # Non-plasma, AD still negated
        )
        assert result.absorbed == 100
        assert result.hull_ad_negated is True


# ============================================================================
# Matched Speed Tests
# ============================================================================

class TestMatchedSpeedAccuracy:
    """Matched Speed grants full accuracy on Move and Attack."""

    def test_matched_speed_full_acc_on_move_and_attack(self):
        """With Matched Speed, Move and Attack gets full weapon Acc."""
        from m1_psi_core.attack import apply_accuracy

        # Normal Move and Attack: half accuracy
        half_acc = apply_accuracy(9, "half_accuracy")
        assert half_acc == 4  # 9 // 2 = 4

        # With Matched Speed: full accuracy
        full_acc = apply_accuracy(9, "full_accuracy")
        assert full_acc == 9

    def test_matched_speed_range_uses_stall_speed(self):
        """Matched Speed: range penalty = max(|range_pen|, stall_speed)."""
        from m1_psi_core.combat_state import get_matched_speed_range_penalty

        # Long range penalty is -11, stall speed 35
        # max(11, 35) = -35... that can't be right.
        # Actually stall speed IS the penalty, not added to it.
        # RAW: "use the higher of the absolute value of the range penalty
        # or your Stall Speed as your Range/Speed penalty"
        # Stall speed of 35 means penalty of -35?? No, stall speed maps
        # to the speed/size table. A stall of 35 yards/sec ≈ -7 penalty.
        # Let's use the speed-to-penalty mapping.
        penalty = get_matched_speed_range_penalty("long", stall_speed=35)
        # Long range = -11, stall speed 35 maps to ~-7
        # max(11, 7) = 11, so range dominates = -11
        assert penalty == -11

    def test_matched_speed_at_close_range_uses_stall(self):
        """At close range, stall speed penalty may exceed range penalty."""
        from m1_psi_core.combat_state import get_matched_speed_range_penalty

        # Close range = 0, stall speed 100 maps to ~-11
        penalty = get_matched_speed_range_penalty("close", stall_speed=100)
        # max(0, ~11) = -11
        assert penalty < 0  # Stall speed dominates at close range


# ============================================================================
# Speed Penalty Tests
# ============================================================================

class TestSpeedPenaltyInRange:
    """Range penalty = max(|range|, own speed, opponent speed)."""

    def test_range_dominates_at_long_range(self):
        """At long range with moderate speeds, range penalty dominates."""
        from m1_psi_core.combat_state import get_effective_range_penalty

        # Long = -11, speed 400 ≈ -13, speed 500 ≈ -13
        penalty = get_effective_range_penalty("long", own_speed=400, opponent_speed=500)
        # Should use the largest absolute value
        assert penalty <= -11

    def test_speed_dominates_at_close_range(self):
        """At close range with fast ships, speed penalty dominates."""
        from m1_psi_core.combat_state import get_effective_range_penalty

        # Close = 0, speed 600 ≈ -15
        penalty = get_effective_range_penalty("close", own_speed=600, opponent_speed=600)
        assert penalty < -2  # Much worse than close range penalty

    def test_zero_speed_uses_range(self):
        """Stationary ships just use range penalty."""
        from m1_psi_core.combat_state import get_effective_range_penalty

        penalty = get_effective_range_penalty("long", own_speed=0, opponent_speed=0)
        assert penalty == -11

    def test_opponent_speed_can_dominate(self):
        """If opponent is faster, their speed penalty is used."""
        from m1_psi_core.combat_state import get_effective_range_penalty

        # Close range, I'm slow, opponent is fast
        penalty = get_effective_range_penalty("close", own_speed=50, opponent_speed=1000)
        # Opponent speed 1000 ≈ -17 dominates
        assert penalty < -10
