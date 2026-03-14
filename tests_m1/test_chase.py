"""
Tests for the chase subsystem.

Covers:
- Chase roll resolution at all victory margins
- Range band shifting rules
- Pursuer/evader direction constraints
- Stall speed restrictions
- Escape conditions
- Voluntary range shifts
- Remote range double-shift requirement
"""
import pytest


class TestChaseRollResolution:
    """Chase roll outcome determination based on margin of victory."""

    def test_victory_0_to_4_no_change(self):
        """Victory by 0-4: no range change, opponent loses advantage."""
        from m1_psi_core.chase import resolve_chase_outcome
        result = resolve_chase_outcome(
            margin=3, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=True,
        )
        assert result.range_shift == 0
        assert result.advantage_gained is False
        assert result.opponent_loses_advantage is True

    def test_victory_5_to_9_gain_advantage(self):
        """Victory by 5-9: may gain advantage OR shift range 1 band."""
        from m1_psi_core.chase import resolve_chase_outcome
        result = resolve_chase_outcome(
            margin=7, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=False,
        )
        # Should offer choice: advantage or range shift
        assert result.can_gain_advantage is True
        assert result.can_shift_range == 1

    def test_victory_5_to_9_match_speed_if_advantaged(self):
        """Victory by 5-9 when already advantaged: may match speed."""
        from m1_psi_core.chase import resolve_chase_outcome
        result = resolve_chase_outcome(
            margin=6, winner_intent="pursue",
            winner_had_advantage=True, loser_had_advantage=False,
        )
        assert result.can_match_speed is True

    def test_victory_10_plus_big_win(self):
        """Victory by 10+: match speed OR (1 band + advantage) OR 2 bands."""
        from m1_psi_core.chase import resolve_chase_outcome
        result = resolve_chase_outcome(
            margin=12, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=False,
        )
        assert result.can_match_speed is True
        assert result.can_shift_range >= 1
        assert result.can_gain_advantage is True

    def test_stall_speed_must_succeed_for_fixed_weapons(self):
        """A stall-speed pursuer must succeed by 0+ to fire fixed weapons."""
        from m1_psi_core.chase import can_fire_fixed_weapons
        assert can_fire_fixed_weapons(stall_speed=35, chase_margin=0) is True
        assert can_fire_fixed_weapons(stall_speed=35, chase_margin=-1) is False
        assert can_fire_fixed_weapons(stall_speed=0, chase_margin=-1) is True  # No stall


class TestPursuevaderConstraints:
    """Direction constraints on range shifting."""

    def test_pursuer_can_only_reduce_range(self):
        """A pursuing ship may only shift range closer."""
        from m1_psi_core.chase import validate_range_shift
        # Pursuer trying to increase range: invalid
        assert validate_range_shift("pursue", shift_direction=1) is False
        # Pursuer reducing range: valid
        assert validate_range_shift("pursue", shift_direction=-1) is True

    def test_evader_can_only_increase_range(self):
        """An evading ship may only shift range farther."""
        from m1_psi_core.chase import validate_range_shift
        assert validate_range_shift("evade", shift_direction=-1) is False
        assert validate_range_shift("evade", shift_direction=1) is True


class TestStallSpeedRestrictions:
    """Stall speed imposes maneuver restrictions."""

    def test_stall_cannot_pursue_advantaged_opponent(self):
        """A ship with stall speed cannot pursue a target that is advantaged against it."""
        from m1_psi_core.chase import can_pursue
        assert can_pursue(stall_speed=35, opponent_has_advantage=True) is False
        assert can_pursue(stall_speed=35, opponent_has_advantage=False) is True
        assert can_pursue(stall_speed=0, opponent_has_advantage=True) is True  # No stall


class TestStaticManeuvers:
    """Static maneuver consequences."""

    def test_static_grants_opponent_range_shift(self):
        """Static maneuvers grant opponent one free range band shift."""
        from m1_psi_core.chase import get_static_maneuver_effects
        effects = get_static_maneuver_effects()
        assert effects.opponent_free_range_shift == 1

    def test_static_loses_matched_speed(self):
        """Static maneuver causes loss of matched speed if opponent is not static."""
        from m1_psi_core.chase import get_static_maneuver_effects
        effects = get_static_maneuver_effects()
        assert effects.loses_matched_speed is True


class TestEscape:
    """Escape condition checking."""

    def test_escape_by_exceeding_max_range(self):
        """Escape when target shifts beyond the maximum attackable range."""
        from m1_psi_core.chase import check_escape
        assert check_escape(range_band="beyond_remote") is True
        assert check_escape(range_band="extreme") is False

    def test_escape_by_hyperspace(self):
        """Escape by successfully shunting into hyperspace."""
        from m1_psi_core.chase import check_escape
        assert check_escape(range_band="long", hyperspace_ready=True) is True


class TestVoluntaryShifts:
    """Voluntary range shifts when both parties agree."""

    def test_both_pursue_voluntary_close(self):
        """If both pursue and agree, grant one additional range band closer."""
        from m1_psi_core.chase import voluntary_shift_allowed
        assert voluntary_shift_allowed(
            intent_a="pursue", intent_b="pursue", both_agree=True
        ) is True

    def test_both_evade_voluntary_escape(self):
        """If both evade and agree, they may simply escape."""
        from m1_psi_core.chase import voluntary_shift_allowed
        assert voluntary_shift_allowed(
            intent_a="evade", intent_b="evade", both_agree=True
        ) is True
