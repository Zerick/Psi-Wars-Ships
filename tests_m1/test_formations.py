"""
Tests for the formation subsystem.
"""
import pytest


class TestFormationRules:
    """Multi-ship formation mechanics."""

    def test_formation_intercept(self):
        """Any member can intercept attack on another if attacker not advantaged."""
        from m1_psi_core.formations import can_intercept
        assert can_intercept(attacker_has_advantage=False) is True
        assert can_intercept(attacker_has_advantage=True) is False

    def test_area_jammer_sharing(self):
        """Area jammer protection shared with entire formation."""
        from m1_psi_core.formations import formation_has_area_jammer
        # If any ship in formation has area jammer, all benefit
        ships = [
            {"has_area_jammer": False},
            {"has_area_jammer": True},
            {"has_area_jammer": False},
        ]
        assert formation_has_area_jammer(ships) is True

    def test_no_area_jammer(self):
        """Formation without area jammer gets no benefit."""
        from m1_psi_core.formations import formation_has_area_jammer
        ships = [{"has_area_jammer": False}, {"has_area_jammer": False}]
        assert formation_has_area_jammer(ships) is False

    def test_no_formation_size_cap(self):
        """Formations have no maximum size."""
        from m1_psi_core.formations import validate_formation_size
        assert validate_formation_size(100) is True
        assert validate_formation_size(1) is False  # Need at least 2


class TestTacticalCoordination:
    """Three modes of tactical coordination."""

    def test_pursuit_tactics(self):
        """Pursuit Tactics: +2 to formation chase rolls."""
        from m1_psi_core.formations import get_tactical_coordination_effect
        effect = get_tactical_coordination_effect("pursuit")
        assert effect.chase_bonus == 2

    def test_defensive_tactics_hit_penalty(self):
        """Defensive Tactics (option A): target -2 to hit formation."""
        from m1_psi_core.formations import get_tactical_coordination_effect
        effect = get_tactical_coordination_effect("defensive")
        assert effect.enemy_hit_penalty == -2 or effect.dodge_bonus == 1

    def test_offensive_tactics_hit_bonus(self):
        """Offensive Tactics (option A): formation +2 to hit target."""
        from m1_psi_core.formations import get_tactical_coordination_effect
        effect = get_tactical_coordination_effect("offensive")
        assert effect.hit_bonus == 2 or effect.enemy_dodge_penalty == -1
