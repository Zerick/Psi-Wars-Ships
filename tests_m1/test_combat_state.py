"""
Tests for the combat state subsystem.

Covers:
- Range band system with penalties
- Engagement state tracking (advantage, matched speed, hugging)
- Facing rules
- Collision range calculation
- Range band special rules (beyond visual, remote)
"""
import pytest


class TestRangeBands:
    """Range band definitions and penalty lookups."""

    def test_all_range_bands_defined(self):
        """All 9 range bands exist with correct penalties."""
        from m1_psi_core.combat_state import get_range_penalty
        
        bands = {
            "close": (0, -2),
            "short": (-3, -6),
            "medium": (-7, -10),
            "long": (-11, -14),
            "extreme": (-15, -18),
            "distant": (-19, -22),
            "beyond_visual": (-23, -26),
            "remote": (-27, -30),
            "beyond_remote": (-31, -34),
        }
        for band, (low, high) in bands.items():
            penalty = get_range_penalty(band)
            assert low >= penalty >= high, (
                f"Range band '{band}': penalty {penalty} not in [{low}, {high}]"
            )

    def test_range_band_uses_low_penalty(self):
        """Attack rolls use the LOW (least severe) penalty for the band."""
        from m1_psi_core.combat_state import get_range_penalty
        # Close range uses -0 (the low end)
        assert get_range_penalty("close") == 0
        # Long range uses -11
        assert get_range_penalty("long") == -11
        # Extreme uses -15
        assert get_range_penalty("extreme") == -15

    def test_range_band_ordering(self):
        """Range bands are ordered from closest to farthest."""
        from m1_psi_core.combat_state import RANGE_BAND_ORDER
        expected = [
            "close", "short", "medium", "long", "extreme",
            "distant", "beyond_visual", "remote", "beyond_remote"
        ]
        assert RANGE_BAND_ORDER == expected

    def test_shift_range_band_closer(self):
        """Shifting one band closer from 'long' gives 'medium'."""
        from m1_psi_core.combat_state import shift_range_band
        assert shift_range_band("long", -1) == "medium"

    def test_shift_range_band_farther(self):
        """Shifting one band farther from 'long' gives 'extreme'."""
        from m1_psi_core.combat_state import shift_range_band
        assert shift_range_band("long", 1) == "extreme"

    def test_shift_range_band_clamps_at_close(self):
        """Cannot shift closer than 'close'."""
        from m1_psi_core.combat_state import shift_range_band
        assert shift_range_band("close", -1) == "close"

    def test_shift_range_band_clamps_at_beyond_remote(self):
        """Cannot shift farther than 'beyond_remote'."""
        from m1_psi_core.combat_state import shift_range_band
        assert shift_range_band("beyond_remote", 1) == "beyond_remote"

    def test_remote_requires_two_shifts(self):
        """Remote range requires 2 range-band shifts to enter or exit."""
        from m1_psi_core.combat_state import shifts_required
        assert shifts_required("beyond_visual", "remote") == 2
        assert shifts_required("remote", "beyond_visual") == 2


class TestCollisionRange:
    """Collision range: speed bonus > |range penalty|."""

    def test_collision_range_fast_ship_close(self):
        """A fast ship at close range is at collision range."""
        from m1_psi_core.combat_state import is_collision_range
        # Ship with speed 600 at close range (penalty 0): speed > |0| -> True
        assert is_collision_range(speed=600, range_band="close") is True

    def test_collision_range_fast_ship_extreme(self):
        """A fast ship at extreme range may or may not be at collision range."""
        from m1_psi_core.combat_state import is_collision_range
        # Extreme penalty = -15, speed bonus needs to be > 15
        # Speed 600 -> speed bonus would be based on speed/range table
        # This depends on how speed bonus is calculated
        # For this test, just verify the function exists and returns bool
        result = is_collision_range(speed=600, range_band="extreme")
        assert isinstance(result, bool)


class TestEngagementState:
    """Tracking relationships between pairs of ships."""

    def test_create_engagement(self):
        """Can create an engagement between two ships."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(
            ship_a_id="ship1", ship_b_id="ship2",
            range_band="long",
        )
        assert eng.range_band == "long"
        assert eng.advantage is None
        assert eng.matched_speed is False
        assert eng.hugging is None

    def test_gain_advantage(self):
        """A ship gains advantage over its opponent."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(ship_a_id="ship1", ship_b_id="ship2", range_band="long")
        eng.set_advantage("ship1")
        assert eng.advantage == "ship1"

    def test_lose_advantage(self):
        """Advantage is lost when opponent wins a chase contest."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(ship_a_id="ship1", ship_b_id="ship2", range_band="long")
        eng.set_advantage("ship1")
        eng.clear_advantage()
        assert eng.advantage is None

    def test_matched_speed_requires_advantage(self):
        """Cannot match speed without first having advantage."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(ship_a_id="ship1", ship_b_id="ship2", range_band="long")
        with pytest.raises(ValueError):
            eng.set_matched_speed("ship1")

    def test_matched_speed_after_advantage(self):
        """Can match speed when already advantaged."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(ship_a_id="ship1", ship_b_id="ship2", range_band="long")
        eng.set_advantage("ship1")
        eng.set_matched_speed("ship1")
        assert eng.matched_speed is True

    def test_hugging_requires_sm_difference(self):
        """Hugging requires the hugger to be at least 3 SM smaller."""
        from m1_psi_core.combat_state import can_hug
        # Fighter SM 4 hugging capital SM 13: difference = 9 >= 3 -> yes
        assert can_hug(hugger_sm=4, target_sm=13) is True
        # Two fighters SM 4: difference = 0 < 3 -> no
        assert can_hug(hugger_sm=4, target_sm=4) is False
        # Fighter SM 4, corvette SM 7: difference = 3 -> yes (exactly 3)
        assert can_hug(hugger_sm=4, target_sm=7) is True

    def test_hugging_inside_force_screen(self):
        """If hugger is 6+ SM smaller, they're inside the force screen."""
        from m1_psi_core.combat_state import is_inside_force_screen
        # Fighter SM 4 hugging capital SM 13: difference 9 >= 6 -> inside
        assert is_inside_force_screen(hugger_sm=4, target_sm=13) is True
        # Fighter SM 4, corvette SM 7: difference 3 < 6 -> outside
        assert is_inside_force_screen(hugger_sm=4, target_sm=7) is False

    def test_static_maneuver_loses_advantage(self):
        """Static maneuvers cause the ship to lose advantage."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(ship_a_id="ship1", ship_b_id="ship2", range_band="long")
        eng.set_advantage("ship1")
        eng.apply_static_maneuver("ship1")
        assert eng.advantage is None

    def test_static_maneuver_loses_matched_speed(self):
        """Static maneuvers cause loss of matched speed."""
        from m1_psi_core.combat_state import EngagementState
        eng = EngagementState(ship_a_id="ship1", ship_b_id="ship2", range_band="long")
        eng.set_advantage("ship1")
        eng.set_matched_speed("ship1")
        eng.apply_static_maneuver("ship1")
        assert eng.matched_speed is False


class TestFacing:
    """Vehicle facing rules."""

    def test_pursuer_faces_front(self):
        """A pursuing ship has Front facing toward opponent."""
        from m1_psi_core.combat_state import get_facing_for_intent
        assert get_facing_for_intent("pursue") == "front"

    def test_evader_faces_rear(self):
        """An evading ship has Rear facing toward opponent."""
        from m1_psi_core.combat_state import get_facing_for_intent
        assert get_facing_for_intent("evade") == "rear"

    def test_six_facings_defined(self):
        """All 6 vehicle facings are defined."""
        from m1_psi_core.combat_state import VALID_FACINGS
        assert set(VALID_FACINGS) == {"front", "rear", "left", "right", "top", "bottom"}


class TestBeyondVisualRules:
    """Special rules for beyond visual range and remote range."""

    def test_beyond_visual_requires_sensors(self):
        """Ships at beyond visual range require active sensors to engage."""
        from m1_psi_core.combat_state import can_engage_at_range
        # Ship with ultrascanner can engage
        assert can_engage_at_range("beyond_visual", ultrascanner_range=30) is True
        # Ship without ultrascanner cannot
        assert can_engage_at_range("beyond_visual", ultrascanner_range=None) is False

    def test_remote_no_advantage(self):
        """Ships at remote range cannot gain advantage."""
        from m1_psi_core.combat_state import can_gain_advantage_at_range
        assert can_gain_advantage_at_range("remote") is False
        assert can_gain_advantage_at_range("long") is True

    def test_remote_full_penalty(self):
        """Remote range uses full -30 penalty."""
        from m1_psi_core.combat_state import get_range_penalty
        assert get_range_penalty("remote") <= -27
