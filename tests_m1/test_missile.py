"""
Tests for the missile attack subsystem.

Covers:
- Missile hit modifier pipeline (different from beam weapons)
- Air burst option (+4 to hit)
- Near miss (miss by 1 on explosive = 1/3 damage)
- Free missile rule
- Torpedo rules (not guided, Gunner (Torpedo), dodge bonuses)
"""
import pytest


class TestMissileHitModifiers:
    """Missile attacks use a completely different modifier pipeline."""

    def test_missile_uses_accuracy(self):
        """Missiles always add weapon accuracy."""
        from m1_psi_core.missile import calculate_missile_hit
        result = calculate_missile_hit(
            gunner_skill=14, weapon_acc=3,
            target_sm=4, target_ecm=-4, target_speed_penalty=-8,
        )
        # 14 + 3 (acc) + 4 (SM) + (-4) (ECM) + (-4) (half speed) = 13
        assert result == 13

    def test_missile_ignores_range_penalty(self):
        """Missiles do NOT apply range penalties."""
        from m1_psi_core.missile import calculate_missile_hit
        # Same setup regardless of range
        at_extreme = calculate_missile_hit(
            gunner_skill=14, weapon_acc=3,
            target_sm=4, target_ecm=-4, target_speed_penalty=-8,
        )
        # The function doesn't take range as input at all
        assert at_extreme == 13

    def test_missile_uses_half_speed(self):
        """Missiles use half of target speed penalty (rounded up)."""
        from m1_psi_core.missile import calculate_missile_speed_penalty
        # Speed penalty -7: half = -3.5, rounded up (more negative) = -4
        assert calculate_missile_speed_penalty(-7) == -4
        # Speed penalty -8: half = -4
        assert calculate_missile_speed_penalty(-8) == -4
        # Speed penalty 0: half = 0
        assert calculate_missile_speed_penalty(0) == 0

    def test_missile_ignores_sensor_lock(self):
        """Missiles do NOT benefit from sensor lock."""
        from m1_psi_core.missile import calculate_missile_hit
        # No sensor lock parameter in the function
        result = calculate_missile_hit(
            gunner_skill=14, weapon_acc=3,
            target_sm=4, target_ecm=-4, target_speed_penalty=-8,
        )
        assert result == 13  # Same with or without sensor lock

    def test_ace_pilot_no_extra_accuracy(self):
        """Ace pilots never add extra accuracy to missile attacks."""
        from m1_psi_core.missile import calculate_missile_hit
        # No is_ace parameter or accuracy override
        result = calculate_missile_hit(
            gunner_skill=14, weapon_acc=3,
            target_sm=4, target_ecm=-4, target_speed_penalty=-8,
        )
        assert result == 13


class TestAirBurst:
    """Air burst option for explosive missiles without armor divisors."""

    def test_air_burst_bonus(self):
        """Air burst gives +4 to hit."""
        from m1_psi_core.missile import get_air_burst_bonus
        assert get_air_burst_bonus(explosive=True, armor_divisor=None) == 4

    def test_air_burst_requires_explosive(self):
        """Non-explosive weapons cannot air burst."""
        from m1_psi_core.missile import get_air_burst_bonus
        assert get_air_burst_bonus(explosive=False, armor_divisor=None) == 0

    def test_air_burst_not_with_armor_divisor(self):
        """Explosive weapons WITH armor divisor cannot air burst."""
        from m1_psi_core.missile import get_air_burst_bonus
        assert get_air_burst_bonus(explosive=True, armor_divisor=10) == 0


class TestNearMiss:
    """Near miss on explosive weapons: miss by 1 = 1/3 damage."""

    def test_near_miss_on_explosive(self):
        """Miss by 1 on explosive weapon = near miss (1/3 damage, no AD)."""
        from m1_psi_core.missile import check_near_miss
        result = check_near_miss(margin=-1, explosive=True, armor_divisor=None)
        assert result.is_near_miss is True
        assert result.damage_multiplier == pytest.approx(1/3, rel=0.01)
        assert result.ignore_armor_divisor is True

    def test_no_near_miss_on_miss_by_2(self):
        """Miss by 2 or more is a clean miss."""
        from m1_psi_core.missile import check_near_miss
        result = check_near_miss(margin=-2, explosive=True, armor_divisor=None)
        assert result.is_near_miss is False

    def test_no_near_miss_non_explosive(self):
        """Non-explosive weapons don't get near misses."""
        from m1_psi_core.missile import check_near_miss
        result = check_near_miss(margin=-1, explosive=False, armor_divisor=None)
        assert result.is_near_miss is False

    def test_dodge_margin_0_explosive_is_near_miss(self):
        """Dodging explosive missile with margin 0 = near miss."""
        from m1_psi_core.missile import check_defense_near_miss
        result = check_defense_near_miss(
            defense_margin=0, explosive=True, armor_divisor=None,
        )
        assert result.is_near_miss is True

    def test_dodge_near_miss_on_already_near_miss(self):
        """If attack was already near miss and defense margin = 0, it misses entirely."""
        from m1_psi_core.missile import check_defense_near_miss
        result = check_defense_near_miss(
            defense_margin=0, explosive=True, armor_divisor=None,
            already_near_miss=True,
        )
        assert result.is_near_miss is False
        assert result.full_miss is True


class TestFreeMissile:
    """Free missile: fire extra missile when you would gain accuracy."""

    def test_free_missile_eligible(self):
        """When maneuver grants accuracy, may fire a free missile instead."""
        from m1_psi_core.missile import is_free_missile_eligible
        assert is_free_missile_eligible(attack_permission="full_accuracy") is True
        assert is_free_missile_eligible(attack_permission="half_accuracy") is False
        assert is_free_missile_eligible(attack_permission="none") is False


class TestTorpedoRules:
    """Torpedoes are NOT missiles - different rules apply."""

    def test_torpedo_dodge_bonus_extreme(self):
        """Torpedoes grant target +1 dodge at extreme range."""
        from m1_psi_core.missile import get_torpedo_dodge_bonus
        assert get_torpedo_dodge_bonus("extreme") == 1

    def test_torpedo_dodge_bonus_distant(self):
        """Torpedoes grant target +2 dodge at distant range."""
        from m1_psi_core.missile import get_torpedo_dodge_bonus
        assert get_torpedo_dodge_bonus("distant") == 2

    def test_torpedo_max_range_distant(self):
        """Torpedoes cannot attack beyond distant range."""
        from m1_psi_core.missile import can_torpedo_attack_at_range
        assert can_torpedo_attack_at_range("distant") is True
        assert can_torpedo_attack_at_range("beyond_visual") is False

    def test_torpedo_uses_normal_attack_rules(self):
        """Torpedoes use normal attack modifiers, not missile modifiers."""
        from m1_psi_core.missile import is_guided_weapon
        assert is_guided_weapon("missile") is True
        assert is_guided_weapon("torpedo") is False
