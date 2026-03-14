"""
Tests for the turn sequence subsystem.

Covers:
- 5-phase turn structure
- Declaration phase: configuration locked with maneuver
- Chase resolution phase ordering
- Force screen regeneration timing
- Turn counter advancement
"""
import pytest


class TestTurnPhases:
    """The five phases of a combat turn."""

    def test_phase_order(self):
        """Phases execute in correct order."""
        from m1_psi_core.turn_sequence import TURN_PHASES
        assert TURN_PHASES == [
            "declaration",
            "chase_resolution",
            "attack",
            "damage",
            "cleanup",
        ]

    def test_declaration_locks_configuration(self):
        """Vehicle configuration (afterburner, mode, screen facing) is locked at declaration."""
        from m1_psi_core.turn_sequence import validate_declaration
        # A valid declaration includes maneuver, intent, and configuration
        result = validate_declaration(
            maneuver="move", intent="pursue",
            configuration={"afterburner": True, "force_screen_facing": None},
        )
        assert result.is_valid is True

    def test_declaration_requires_maneuver(self):
        """Declaration must include a maneuver choice."""
        from m1_psi_core.turn_sequence import validate_declaration
        result = validate_declaration(
            maneuver=None, intent="pursue", configuration={},
        )
        assert result.is_valid is False

    def test_declaration_requires_intent(self):
        """Declaration must include pursue or evade intent."""
        from m1_psi_core.turn_sequence import validate_declaration
        result = validate_declaration(
            maneuver="move", intent=None, configuration={},
        )
        assert result.is_valid is False


class TestForceScreenRegen:
    """Force screens regenerate between turns."""

    def test_force_screen_regens_at_cleanup(self):
        """Force screens recover to full DR during the cleanup phase."""
        from m1_psi_core.turn_sequence import should_regen_force_screens
        assert should_regen_force_screens(phase="cleanup") is True
        assert should_regen_force_screens(phase="attack") is False

    def test_force_screen_regen_only_with_power(self):
        """Force screen does not regen if power system is destroyed."""
        from m1_psi_core.turn_sequence import can_regen_force_screen
        assert can_regen_force_screen(no_power=True) is False
        assert can_regen_force_screen(no_power=False) is True


class TestTurnOrder:
    """Initiative and declaration order."""

    def test_higher_speed_declares_second(self):
        """Higher Basic Speed (or advantaged) declares second, resolves first."""
        from m1_psi_core.turn_sequence import determine_turn_order
        order = determine_turn_order(
            ships=[
                {"id": "slow", "basic_speed": 5.0, "has_advantage": False},
                {"id": "fast", "basic_speed": 7.0, "has_advantage": False},
            ]
        )
        # Fast ship declares second (sees opponent's declaration)
        assert order.declares_first == "slow"
        assert order.declares_second == "fast"
        # Fast ship resolves first
        assert order.resolves_first == "fast"

    def test_advantage_overrides_speed(self):
        """Advantaged ship declares second regardless of speed."""
        from m1_psi_core.turn_sequence import determine_turn_order
        order = determine_turn_order(
            ships=[
                {"id": "fast", "basic_speed": 7.0, "has_advantage": False},
                {"id": "slow", "basic_speed": 5.0, "has_advantage": True},
            ]
        )
        assert order.declares_second == "slow"  # Advantage wins


class TestTurnCounter:
    """Turn counter management."""

    def test_turn_starts_at_one(self):
        """First turn is turn 1."""
        from m1_psi_core.turn_sequence import TurnTracker
        tracker = TurnTracker()
        assert tracker.current_turn == 1

    def test_turn_advances(self):
        """Turn counter advances after cleanup phase."""
        from m1_psi_core.turn_sequence import TurnTracker
        tracker = TurnTracker()
        tracker.advance()
        assert tracker.current_turn == 2
