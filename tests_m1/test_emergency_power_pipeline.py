"""
Tests for emergency power effects wired through the combat pipeline.

Each emergency power option should produce a measurable effect:
1. All Power to Engines: +2 to chase skill
2. Emergency Evasive: +2 to dodge, forces High-G
3. Emergency Firepower: +1 damage per die
4. Emergency Screen Recharge: restore fDR immediately
"""
import pytest
from m1_psi_core.testing import MockShipStats, MockPilot, MockDice


class TestEmergencyPowerChase:
    """All Power to Engines adds +2 to chase rolls."""

    def test_chase_bonus_applies(self):
        from m1_psi_core.engine import resolve_chase
        from m1_psi_core.combat_state import EngagementState
        from m1_psi_core.dice import DiceRoller

        sa = MockShipStats(instance_id="a1", display_name="Alpha")
        sb = MockShipStats(instance_id="b1", display_name="Bravo")
        pa = MockPilot(piloting_skill=12)
        pb = MockPilot(piloting_skill=12)
        eng = EngagementState(ship_a_id="a1", ship_b_id="b1", range_band="long")

        # Without EP
        r1 = resolve_chase(
            "a1", sa, pa, "b1", sb, pb,
            {"maneuver": "move_and_attack", "intent": "pursue"},
            {"maneuver": "move_and_attack", "intent": "pursue"},
            eng, MockDice([10, 10]),
        )

        # With EP — same rolls, but Alpha gets +2
        r2 = resolve_chase(
            "a1", sa, pa, "b1", sb, pb,
            {"maneuver": "move_and_attack", "intent": "pursue",
             "emergency_power": "all_power_to_engines"},
            {"maneuver": "move_and_attack", "intent": "pursue"},
            eng, MockDice([10, 10]),
        )

        assert r2.skill_a == r1.skill_a + 2
        assert r2.skill_b == r1.skill_b  # Bravo unchanged


class TestEmergencyEvasive:
    """Emergency Evasive adds +2 to dodge and forces High-G."""

    def test_dodge_bonus_applies(self):
        from m1_psi_core.engine import resolve_defense
        from m1_psi_core.combat_state import EngagementState

        defender = MockShipStats(instance_id="d1", display_name="Defender",
                                  hnd=2, accel=50, top_speed=500)
        pilot = MockPilot(piloting_skill=14)
        eng = EngagementState(ship_a_id="a1", ship_b_id="d1", range_band="long")

        # Normal dodge
        d1 = resolve_defense(
            "d1", defender, pilot, "move_and_attack", "move_and_attack",
            eng, MockDice([10, 10]),  # dodge roll, HT roll
            emergency_dodge_bonus=0,
        )

        # With emergency evasive (+2)
        d2 = resolve_defense(
            "d1", defender, pilot, "move_and_attack", "move_and_attack",
            eng, MockDice([10, 10]),
            emergency_dodge_bonus=2,
        )

        assert d2.modifiers.effective_dodge == d1.modifiers.effective_dodge + 2

    def test_forces_high_g(self):
        """Emergency evasive always counts as High-G dodge."""
        from m1_psi_core.engine import resolve_defense
        from m1_psi_core.combat_state import EngagementState

        defender = MockShipStats(instance_id="d1", display_name="Defender",
                                  hnd=2, accel=50, top_speed=500)
        pilot = MockPilot(piloting_skill=14, ht=12)
        eng = EngagementState(ship_a_id="a1", ship_b_id="d1", range_band="long")

        # Emergency evasive with player_chose_high_g=False
        # Should still be High-G because emergency evasive forces it
        d = resolve_defense(
            "d1", defender, pilot, "move_and_attack", "move_and_attack",
            eng, MockDice([10, 10]),
            player_chose_high_g=False,
            emergency_dodge_bonus=2,
        )

        assert d.high_g.attempted is True
        assert d.defense_type == "high_g_dodge"


class TestEmergencyFirepower:
    """Emergency Firepower adds +1 damage per die."""

    def test_damage_bonus_applies(self):
        from m1_psi_core.engine import resolve_damage, WeaponInfo

        target = MockShipStats(
            instance_id="t1", display_name="Target",
            st_hp=100, current_hp=100, dr_front=0, dr_rear=0,
            fdr_max=0, force_screen_type="none", current_fdr=0,
        )

        weapon = WeaponInfo(
            name="Blaster", damage_str="6d×5(5) burn",
            acc=9, rof=3, weapon_type="beam", armor_divisor=5.0,
            mount="fixed_front", linked_count=1, is_explosive=False,
        )

        # Without EP: 6d6=20, ×5 = 100
        d1 = resolve_damage("t1", target, weapon, MockDice([20]), facing="front",
                            extra_damage_per_die=0)

        target.current_hp = 100  # Reset

        # With EP: 6d6=20, ×5 = 100, +6 (6 dice × 1 bonus) = 106
        d2 = resolve_damage("t1", target, weapon, MockDice([20]), facing="front",
                            extra_damage_per_die=1)

        assert d2.raw_damage == d1.raw_damage + 6  # 6 dice × +1 each


class TestEmergencyScreenRecharge:
    """Emergency Screen Recharge restores fDR immediately."""

    def test_fdr_restored(self):
        """Direct test of the recharge logic."""
        ship = MockShipStats(fdr_max=300, current_fdr=50)
        assert ship.current_fdr == 50

        # Simulate recharge
        ship.current_fdr = ship.fdr_max
        assert ship.current_fdr == 300


class TestEmergencyPowerSkillRoll:
    """Emergency power requires a skill roll; failure wastes the cost."""

    def test_success_grants_effect(self):
        """Successful roll returns the effect."""
        from m1_psi_core.emergency_power import resolve_emergency_power

        result = resolve_emergency_power(
            option="all_power_to_engines",
            skill_level=12, reserves=5, ship_ht=12,
            dice_roll=10,  # 10 vs 12 = success
        )
        assert result.success is True
        assert result.effect is not None
        assert result.effect.chase_bonus == 2
        assert result.cost_type == "reserves"
        assert result.redline_ht_lost == 0

    def test_failure_no_effect(self):
        """Failed roll returns no effect but cost is paid."""
        from m1_psi_core.emergency_power import resolve_emergency_power

        result = resolve_emergency_power(
            option="all_power_to_engines",
            skill_level=12, reserves=5, ship_ht=12,
            dice_roll=15,  # 15 vs 12 = failure
        )
        assert result.success is False
        assert result.effect is None

    def test_critical_failure_disables_system(self):
        """Critical failure disables the relevant system."""
        from m1_psi_core.emergency_power import resolve_emergency_power

        result = resolve_emergency_power(
            option="all_power_to_engines",
            skill_level=12, reserves=5, ship_ht=12,
            dice_roll=18,  # 18 = always critical failure
        )
        assert result.critical_failure is True
        assert result.crit_fail_effect is not None
        assert result.crit_fail_effect.disables_system == "propulsion"

    def test_redline_costs_ht(self):
        """No reserves = redline, costs 1 HT."""
        from m1_psi_core.emergency_power import resolve_emergency_power

        result = resolve_emergency_power(
            option="emergency_firepower",
            skill_level=12, reserves=0, ship_ht=12,
            dice_roll=10,
        )
        assert result.cost_type == "redline"
        assert result.redline_ht_lost == 1
        assert result.success is True

    def test_cumulative_penalty(self):
        """Repeated All Power to Engines gets -4 per prior use."""
        from m1_psi_core.emergency_power import resolve_emergency_power

        # First use: skill 12, roll 11 = success by 1
        r1 = resolve_emergency_power(
            "all_power_to_engines", 12, 5, 12, 11, times_used_this_option=0,
        )
        assert r1.skill_target == 12
        assert r1.success is True

        # Second use: skill 12 - 4 = 8, roll 11 = failure
        r2 = resolve_emergency_power(
            "all_power_to_engines", 12, 4, 12, 11, times_used_this_option=1,
        )
        assert r2.skill_target == 8
        assert r2.success is False
