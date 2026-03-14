"""
Tests for the emergency power subsystem.

Covers:
- All 6 emergency power options
- Cost (1 reserve point or 1 HT)
- Cumulative penalties for repeated use
- Critical failure consequences
"""
import pytest


class TestEmergencyPowerOptions:
    """All six emergency power allocation options."""

    def test_all_power_to_engines(self):
        """All Power to Engines: +2 chase rolls for one turn."""
        from m1_psi_core.emergency_power import get_option_effect
        effect = get_option_effect("all_power_to_engines")
        assert effect.chase_bonus == 2

    def test_all_power_cumulative_penalty(self):
        """All Power to Engines: cumulative -4 per repeat."""
        from m1_psi_core.emergency_power import get_cumulative_penalty
        assert get_cumulative_penalty("all_power_to_engines", times_used=0) == 0
        assert get_cumulative_penalty("all_power_to_engines", times_used=1) == -4
        assert get_cumulative_penalty("all_power_to_engines", times_used=2) == -8

    def test_emergency_evasive(self):
        """Emergency Evasive: +2 to one dodge (always High-G)."""
        from m1_psi_core.emergency_power import get_option_effect
        effect = get_option_effect("emergency_evasive")
        assert effect.dodge_bonus == 2
        assert effect.is_high_g is True

    def test_emergency_firepower(self):
        """Emergency Firepower: +1 or +2 damage per die."""
        from m1_psi_core.emergency_power import get_option_effect
        effect = get_option_effect("emergency_firepower")
        assert effect.damage_per_die_bonus in [1, 2]

    def test_emergency_firepower_malf(self):
        """Emergency Firepower at +2: Malf reduced to 14."""
        from m1_psi_core.emergency_power import get_firepower_malf
        assert get_firepower_malf(bonus_level=2) == 14
        assert get_firepower_malf(bonus_level=1) is None  # No malf change

    def test_emergency_screen_recharge(self):
        """Emergency Screen Recharge: immediately restore full fDR."""
        from m1_psi_core.emergency_power import get_option_effect
        effect = get_option_effect("emergency_screen_recharge")
        assert effect.restores_fdr is True

    def test_emergency_system_purge(self):
        """Emergency System Purge: reroll failed HT for surge/operational/disabled."""
        from m1_psi_core.emergency_power import get_option_effect
        effect = get_option_effect("emergency_system_purge")
        assert effect.allows_ht_reroll is True

    def test_emergency_weapon_recharge(self):
        """Emergency Weapon Recharge: restore half shots to one weapon."""
        from m1_psi_core.emergency_power import get_option_effect
        effect = get_option_effect("emergency_weapon_recharge")
        assert effect.restores_half_ammo is True


class TestEmergencyPowerCost:
    """Emergency power costs 1 reserve or 1 HT."""

    def test_costs_one_reserve(self):
        """Each use costs 1 emergency power reserve point."""
        from m1_psi_core.emergency_power import EMERGENCY_POWER_COST
        assert EMERGENCY_POWER_COST == 1

    def test_redline_costs_ht(self):
        """Ships without reserves 'redline' by reducing HT by 1."""
        from m1_psi_core.emergency_power import can_redline
        assert can_redline(reserves=0, current_ht=12) is True
        assert can_redline(reserves=0, current_ht=0) is False


class TestCriticalFailureConsequences:
    """Critical failure on emergency power skill roll."""

    def test_engines_crit_fail_disables(self):
        """Critical failure on All Power to Engines disables engines."""
        from m1_psi_core.emergency_power import get_critical_failure_effect
        effect = get_critical_failure_effect("all_power_to_engines")
        assert effect.disables_system == "propulsion"

    def test_firepower_crit_fail_disables(self):
        """Critical failure on Emergency Firepower disables weapons."""
        from m1_psi_core.emergency_power import get_critical_failure_effect
        effect = get_critical_failure_effect("emergency_firepower")
        assert effect.disables_system == "weaponry"
