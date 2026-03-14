"""
Tests for passenger actions.

Covers:
- Crew skill default
- Emergency repair mechanics
- Hyperspace navigation calculation
- Tactical coordination
- Internal movement timing
"""
import pytest


class TestCrewSkill:
    """Capital ship crew skill defaults."""

    def test_default_crew_skill(self):
        """Default crew skill is 12."""
        from m1_psi_core.passengers import DEFAULT_CREW_SKILL
        assert DEFAULT_CREW_SKILL == 12

    def test_crew_skill_range(self):
        """Crew skill ranges from 10 to 15."""
        from m1_psi_core.passengers import CREW_SKILL_MIN, CREW_SKILL_MAX
        assert CREW_SKILL_MIN == 10
        assert CREW_SKILL_MAX == 15


class TestEmergencyRepairs:
    """Jury-rigging disabled systems in combat."""

    def test_repair_base_penalty(self):
        """Emergency repair is Mechanic at -10."""
        from m1_psi_core.passengers import EMERGENCY_REPAIR_PENALTY
        assert EMERGENCY_REPAIR_PENALTY == -10

    def test_quick_gadgeteer_halves_penalty(self):
        """Quick Gadgeteer halves the repair penalty to -5."""
        from m1_psi_core.passengers import get_repair_penalty
        assert get_repair_penalty(has_quick_gadgeteer=True) == -5
        assert get_repair_penalty(has_quick_gadgeteer=False) == -10

    def test_jury_rigged_ht_check(self):
        """Jury-rigged component must roll HT first time used in battle."""
        from m1_psi_core.passengers import is_jury_rigged_check_needed
        assert is_jury_rigged_check_needed(jury_rigged=True, checked_this_battle=False) is True
        assert is_jury_rigged_check_needed(jury_rigged=True, checked_this_battle=True) is False


class TestHyperspaceNavigation:
    """Charting a hyperspace route."""

    def test_base_turns_required(self):
        """Base navigation takes 5 turns."""
        from m1_psi_core.passengers import HYPERSPACE_BASE_TURNS
        assert HYPERSPACE_BASE_TURNS == 5

    def test_time_reduction_penalty(self):
        """Each turn reduced imposes -2 to Navigation roll."""
        from m1_psi_core.passengers import calculate_navigation_penalty
        # Reduce from 5 to 3 turns: -4 penalty
        assert calculate_navigation_penalty(turns_reduced=2) == -4
        # Reduce to 1 turn: -8 penalty
        assert calculate_navigation_penalty(turns_reduced=4) == -8

    def test_quick_shunt_perk(self):
        """Quick Shunt ignores up to -2 in time taken modifiers."""
        from m1_psi_core.passengers import calculate_navigation_penalty
        # 2 turns reduced = -4, Quick Shunt removes -2: effective -2
        assert calculate_navigation_penalty(turns_reduced=2, has_quick_shunt=True) == -2


class TestInternalMovement:
    """Moving between stations takes time based on ship size."""

    def test_starfighter_movement(self):
        """Starfighters: 0 turns (free movement)."""
        from m1_psi_core.passengers import get_internal_movement_turns
        assert get_internal_movement_turns("fighter") == 0

    def test_corvette_movement(self):
        """Corvettes: 1 turn."""
        from m1_psi_core.passengers import get_internal_movement_turns
        assert get_internal_movement_turns("corvette") == 1

    def test_capital_ship_movement(self):
        """Capital ships: 2 turns."""
        from m1_psi_core.passengers import get_internal_movement_turns
        assert get_internal_movement_turns("capital") == 2
