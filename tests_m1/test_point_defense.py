"""
Tests for point defense subsystem.
"""
import pytest


class TestPointDefenseInterception:
    """Wait and Attack (Point Defense) against incoming missiles/torpedoes."""

    def test_point_defense_ignores_range(self):
        """Point defense ignores range penalties."""
        from m1_psi_core.point_defense import calculate_point_defense_skill
        # Only applies size/speed modifiers and sensor lock
        result = calculate_point_defense_skill(
            gunner_skill=14, target_modifier=-16,
            sensor_lock_bonus=5, special_bonus=0,
        )
        # 14 + (-16) + 5 = 3
        assert result == 3

    def test_standard_missile_modifier(self):
        """160mm standard missile combined speed/size = -16."""
        from m1_psi_core.point_defense import MISSILE_PD_MODIFIERS
        assert MISSILE_PD_MODIFIERS["160mm_standard"] == -16

    def test_light_missile_modifier(self):
        """100mm light missile combined speed/size = -16."""
        from m1_psi_core.point_defense import MISSILE_PD_MODIFIERS
        assert MISSILE_PD_MODIFIERS["100mm_light"] == -16

    def test_light_torpedo_modifier(self):
        """400mm light torpedo combined speed/size = -11."""
        from m1_psi_core.point_defense import MISSILE_PD_MODIFIERS
        assert MISSILE_PD_MODIFIERS["400mm_light_torpedo"] == -11

    def test_heavy_torpedo_modifier(self):
        """640mm heavy torpedo combined speed/size = -10."""
        from m1_psi_core.point_defense import MISSILE_PD_MODIFIERS
        assert MISSILE_PD_MODIFIERS["640mm_heavy_torpedo"] == -10

    def test_bombardment_torpedo_modifier(self):
        """1600mm bombardment torpedo combined speed/size = -8."""
        from m1_psi_core.point_defense import MISSILE_PD_MODIFIERS
        assert MISSILE_PD_MODIFIERS["1600mm_bombardment"] == -8

    def test_needle_laser_special_bonus(self):
        """Needle laser point defense gets +3 special bonus."""
        from m1_psi_core.point_defense import calculate_point_defense_skill
        result = calculate_point_defense_skill(
            gunner_skill=14, target_modifier=-16,
            sensor_lock_bonus=5, special_bonus=3,
        )
        # 14 - 16 + 5 + 3 = 6
        assert result == 6
