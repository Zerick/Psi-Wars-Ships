"""
Tests for special rules subsystem.

Covers:
- Lucky breaks
- Hugging mechanics
- Force screen configuration (adjustable)
- Ramming
- Ship classification
"""
import pytest


class TestLuckyBreaks:
    """Lucky break mechanics."""

    def test_lucky_break_increase_wound(self):
        """Lucky break can increase wound severity by 2 levels."""
        from m1_psi_core.special import apply_lucky_break_wound
        result = apply_lucky_break_wound(current_wound="minor")
        assert result == "crippling"  # minor -> major -> crippling

    def test_lucky_break_ignore_attacks(self):
        """Lucky break can ignore all attacks for one round."""
        from m1_psi_core.special import LUCKY_BREAK_OPTIONS
        assert "ignore_attacks" in LUCKY_BREAK_OPTIONS

    def test_lucky_break_invoke_obstacle(self):
        """Lucky break can invoke a new obstacle or opportunity."""
        from m1_psi_core.special import LUCKY_BREAK_OPTIONS
        assert "invoke_obstacle" in LUCKY_BREAK_OPTIONS

    def test_ace_pilot_gets_free_lucky_break(self):
        """Ace Pilots get one free Lucky Break per chase scenario."""
        from m1_psi_core.special import get_free_lucky_breaks
        assert get_free_lucky_breaks(is_ace_pilot=True) == 1
        assert get_free_lucky_breaks(is_ace_pilot=False) == 0


class TestHugging:
    """Hugging a larger ship at collision range."""

    def test_hugging_attack_restrictions_on_hugged(self):
        """Hugged ship: half turrets, no fixed mounts, -2 to attacks."""
        from m1_psi_core.special import get_hugged_attack_penalties
        penalties = get_hugged_attack_penalties()
        assert penalties.turret_fraction == 0.5
        assert penalties.fixed_mounts_disabled is True
        assert penalties.attack_penalty == -2

    def test_attacking_hugging_ship_penalty(self):
        """Attacking a ship that's hugging another: -2 to hit."""
        from m1_psi_core.special import get_attack_hugging_ship_penalty
        assert get_attack_hugging_ship_penalty() == -2

    def test_miss_hugging_hits_hugged_vehicle(self):
        """Miss/dodge on hugging ship: may hit hugged on (hugged SM - 3)."""
        from m1_psi_core.special import calculate_collateral_hit_chance
        # Hugged ship SM 13: roll (13 - 3) = 10 or less on 3d6
        assert calculate_collateral_hit_chance(hugged_sm=13) == 10

    def test_6sm_larger_ignores_force_screen(self):
        """If target is 6+ SM larger, hugger ignores its force screen."""
        from m1_psi_core.special import hugging_ignores_force_screen
        # Fighter SM 4 hugging capital SM 13: 13-4 = 9 >= 6
        assert hugging_ignores_force_screen(hugger_sm=4, target_sm=13) is True
        assert hugging_ignores_force_screen(hugger_sm=4, target_sm=9) is False


class TestForceScreenConfiguration:
    """Adjustable force screen facing configuration."""

    def test_default_equal_all_facings(self):
        """Default: fDR equally distributed to all facings."""
        from m1_psi_core.special import configure_force_screen
        config = configure_force_screen(fdr_max=150, focused_facing=None)
        assert config.front == 150
        assert config.rear == 150

    def test_focused_doubles_one_halves_others(self):
        """Focusing doubles one facing, halves all others."""
        from m1_psi_core.special import configure_force_screen
        config = configure_force_screen(fdr_max=150, focused_facing="front")
        assert config.front == 300
        assert config.rear == 75
        assert config.left == 75


class TestShipClassification:
    """Classifying ships as fighter/corvette/capital."""

    def test_fighter_classification(self):
        """SM 4-7 or chase +16 or better = fighter."""
        from m1_psi_core.special import classify_ship
        assert classify_ship(sm=4, chase_bonus=20) == "fighter"
        assert classify_ship(sm=5, chase_bonus=18) == "fighter"

    def test_corvette_classification(self):
        """SM 7-10 or chase +11 to +15 = corvette."""
        from m1_psi_core.special import classify_ship
        assert classify_ship(sm=8, chase_bonus=13) == "corvette"

    def test_capital_classification(self):
        """SM 10+ or chase +10 or worse = capital."""
        from m1_psi_core.special import classify_ship
        assert classify_ship(sm=13, chase_bonus=5) == "capital"
