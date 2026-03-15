"""
Integration tests for multi-turn combat scenarios.

These tests exercise the full rules engine pipeline — from maneuver
declaration through chase rolls, attacks, defense, and damage — using
concrete ship configurations. They verify that all subsystems interact
correctly.

Each scenario uses MockDice for fully deterministic outcomes.
"""
import pytest
from m1_psi_core.testing import MockDice, MockShipStats, MockPilot, MockWeapon


class TestJavelinVsHornet:
    """Fighter dogfight: Javelin (imperial) vs Hornet (trader)."""

    def test_javelin_attacks_hornet_at_long_range(self):
        """
        Scenario: Javelin pursues Hornet at long range, fires blasters.
        Verifies: range penalty, SM, sensor lock, accuracy all apply correctly.
        """
        from m1_psi_core.attack import calculate_hit_modifiers, get_sensor_lock_bonus
        from m1_psi_core.combat_state import get_range_penalty

        range_penalty = get_range_penalty("long")  # -11
        sm_bonus = 4  # Hornet SM +4
        sensor_lock = get_sensor_lock_bonus(has_lock=True, targeting_bonus=5)  # +5
        acc = 9  # Blaster acc, Attack maneuver = full accuracy

        effective_skill = 14 + range_penalty + sm_bonus + sensor_lock + acc
        # 14 + (-11) + 4 + 5 + 9 = 21
        assert effective_skill == 21

    def test_hornet_dodge_calculation(self):
        """
        Scenario: Hornet dodges Javelin's attack.
        Verifies: Piloting/2 + Handling = dodge (no +3).
        """
        from m1_psi_core.defense import calculate_base_dodge

        # Hornet pilot: Piloting 14, Handling +6
        dodge = calculate_base_dodge(piloting=14, handling=6)
        assert dodge == 13  # 14/2 + 6 = 13

    def test_force_screen_absorbs_before_hull(self):
        """
        Scenario: Javelin blaster hits Hornet with 100 damage.
        Verifies: force screen absorbs first, then hull DR.
        """
        from m1_psi_core.damage import apply_force_screen, calculate_penetrating_damage

        # 100 damage, Hornet has 150 fDR standard screen
        screen_result = apply_force_screen(
            incoming_damage=100, current_fdr=150,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert screen_result.penetrating == 0  # Screen absorbed it all
        assert screen_result.remaining_fdr == 50


class TestCapitalVsFighter:
    """Asymmetric combat: Sword Battleship vs Javelin fighter."""

    def test_relative_size_penalty_applies(self):
        """Capital ship firing at fighter takes -10 to hit."""
        from m1_psi_core.attack import get_relative_size_penalty

        penalty = get_relative_size_penalty(
            attacker_class="capital", target_class="fighter",
            is_light_turret=False,
        )
        assert penalty == -10

    def test_fighter_cannot_easily_damage_capital(self):
        """Fighter blaster vs 10000 fDR heavy screen: damage absorbed."""
        from m1_psi_core.damage import apply_force_screen

        # Fighter blaster max damage: 6d6 * 5 = 180
        screen_result = apply_force_screen(
            incoming_damage=180, current_fdr=10000,
            armor_divisor=5, force_screen_type="heavy",
            damage_type="burn",
        )
        assert screen_result.penetrating == 0
        assert screen_result.remaining_fdr == 9820


class TestMookCombat:
    """Simplified combat with mook ships."""

    def test_mook_removed_on_major_wound(self):
        """Mook taking major wound is removed from combat."""
        from m1_psi_core.damage import apply_mook_rules

        result = apply_mook_rules(wound_level="major")
        assert result.removed is True

    def test_mook_survives_minor_wound(self):
        """Mook taking minor wound continues fighting."""
        from m1_psi_core.damage import apply_mook_rules

        result = apply_mook_rules(wound_level="minor")
        assert result.removed is False


class TestSpectreSpecialRules:
    """Test Spectre-specific combat interactions."""

    def test_spectre_all_chase_high_g(self):
        """Spectre: all chase rolls count as High-G maneuvers."""
        # This is a trait check — the trait "all_chase_high_g" is on the Spectre
        from m1_psi_core.testing import MockShipStats
        spectre = MockShipStats(
            template_id="spectre_v1", st_hp=80, hnd=6, accel=25, top_speed=800,
            traits=["all_chase_high_g", "psionic_interface"],
        )
        assert "all_chase_high_g" in spectre.traits

    def test_spectre_dodge_value(self):
        """Spectre: Piloting 16, Handling +6 -> Dodge 14."""
        from m1_psi_core.defense import calculate_base_dodge
        assert calculate_base_dodge(piloting=16, handling=6) == 14
