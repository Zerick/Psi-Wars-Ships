"""
Tests for the electronic warfare subsystem.

Covers:
- Automatic detection at scanner range
- Stealth detection (sensor contest)
- Visual detection (closer than beyond visual)
- Ambush mechanics
- Active sensor jamming
- Sensor lock rules
"""
import pytest


class TestDetection:
    """Ship detection at range."""

    def test_auto_detect_within_scanner_range(self):
        """Ships automatically detect each other within scanner range."""
        from m1_psi_core.electronic_warfare import check_auto_detection
        assert check_auto_detection(scanner_range=30, range_miles=25) is True

    def test_no_auto_detect_beyond_scanner(self):
        """Ships beyond scanner range are not auto-detected."""
        from m1_psi_core.electronic_warfare import check_auto_detection
        assert check_auto_detection(scanner_range=30, range_miles=50) is False


class TestStealthDetection:
    """Sensor-based stealth detection contest."""

    def test_stealth_detection_modifiers(self):
        """ECM penalty applies to the scanner's EO(Sensors) roll."""
        from m1_psi_core.electronic_warfare import calculate_stealth_detection_modifiers
        mods = calculate_stealth_detection_modifiers(
            target_ecm=-4, has_stealth_coating=True, in_nebula=False,
        )
        # ECM -4, stealth coating -4 (if applicable) 
        assert mods.total_penalty <= -4

    def test_nebula_penalty(self):
        """Nebula imposes -10 to sensor detection."""
        from m1_psi_core.electronic_warfare import calculate_stealth_detection_modifiers
        mods = calculate_stealth_detection_modifiers(
            target_ecm=-4, has_stealth_coating=False, in_nebula=True,
        )
        assert mods.nebula_penalty == -10

    def test_stealth_success_allows_ambush(self):
        """If stealthy ship wins, it may ambush from beyond visual."""
        from m1_psi_core.electronic_warfare import resolve_stealth_contest
        result = resolve_stealth_contest(stealthy_won=True)
        assert result.can_ambush is True
        assert result.ambush_range == "beyond_visual"


class TestVisualDetection:
    """Visual detection for ships closer than beyond visual."""

    def test_visual_detection_modifiers(self):
        """Visual detection uses SM bonus and various penalties."""
        from m1_psi_core.electronic_warfare import calculate_visual_detection_modifiers
        mods = calculate_visual_detection_modifiers(
            target_sm=4, has_chameleon=True, in_nebula=False,
            in_asteroid_field=False,
        )
        assert mods.sm_bonus == 4
        assert mods.chameleon_penalty == -4

    def test_asteroid_and_nebula_combined(self):
        """Nebula + asteroid field = -10."""
        from m1_psi_core.electronic_warfare import calculate_visual_detection_modifiers
        mods = calculate_visual_detection_modifiers(
            target_sm=4, has_chameleon=False,
            in_nebula=True, in_asteroid_field=True,
        )
        assert mods.environment_penalty == -10

    def test_visual_stealth_approach_distance(self):
        """Every 4 margin of success allows approaching 1 band closer."""
        from m1_psi_core.electronic_warfare import calculate_stealth_approach
        # Margin of success 8: 8/4 = 2 extra bands closer
        assert calculate_stealth_approach(margin_of_success=8) == 2
        assert calculate_stealth_approach(margin_of_success=4) == 1
        assert calculate_stealth_approach(margin_of_success=3) == 0


class TestAmbush:
    """Ambush mechanics when a stealthy ship initiates combat."""

    def test_ambush_defender_iq_roll(self):
        """Defenders roll IQ to react. Failure = no action/defense turn 1."""
        from m1_psi_core.electronic_warfare import get_ambush_defense_modifiers
        mods = get_ambush_defense_modifiers(
            has_combat_reflexes=False, has_danger_sense=False,
        )
        assert mods.iq_modifier == 0  # No special modifiers

    def test_ambush_combat_reflexes_bonus(self):
        """Combat Reflexes gives +6 to IQ roll during ambush."""
        from m1_psi_core.electronic_warfare import get_ambush_defense_modifiers
        mods = get_ambush_defense_modifiers(
            has_combat_reflexes=True, has_danger_sense=False,
        )
        assert mods.combat_reflexes_bonus == 6

    def test_ambush_failure_penalties(self):
        """Failed IQ roll during ambush: cannot act or defend on turn 1."""
        from m1_psi_core.electronic_warfare import resolve_ambush_reaction
        result = resolve_ambush_reaction(iq_roll_succeeded=False)
        assert result.can_act is False
        assert result.can_defend is False

    def test_ambush_success_penalties(self):
        """Successful IQ roll: can act and defend at -4."""
        from m1_psi_core.electronic_warfare import resolve_ambush_reaction
        result = resolve_ambush_reaction(iq_roll_succeeded=True)
        assert result.can_act is True
        assert result.can_defend is True
        assert result.defense_penalty == -4


class TestActiveJamming:
    """Active sensor jamming as a passenger action."""

    def test_jamming_removes_sensor_lock(self):
        """Successful jam removes enemy sensor lock for one turn."""
        from m1_psi_core.electronic_warfare import resolve_active_jamming
        result = resolve_active_jamming(jammer_won=True)
        assert result.lock_removed is True
        assert result.duration_turns == 1

    def test_sensor_lock_auto_with_ultrascanner(self):
        """Sensor lock is automatic with ultrascanner unless target jams."""
        from m1_psi_core.electronic_warfare import check_auto_sensor_lock
        assert check_auto_sensor_lock(
            has_ultrascanner=True, target_in_range=True,
            target_is_jamming=False,
        ) is True
        assert check_auto_sensor_lock(
            has_ultrascanner=True, target_in_range=True,
            target_is_jamming=True,
        ) is False
