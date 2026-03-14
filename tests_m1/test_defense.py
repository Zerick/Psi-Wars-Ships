"""
Tests for the defense subsystem.

Covers:
- Vehicular dodge formula: Piloting/2 + Handling (NO +3 base)
- Evade maneuver bonus
- Advantage (escaping) bonus
- Ace Pilot stunt bonus
- High-G dodge (requirements, HT roll, FP loss)
- Missile defense (-3, ESM, decoy, jamming)
- Emergency evasive bonus
- Tactical coordination defensive bonus
- Precision aiming target dodge bonus
"""
import pytest


class TestVehicularDodge:
    """Core vehicular dodge formula: Piloting/2 + Handling (no +3)."""

    def test_basic_dodge_formula(self):
        """Dodge = Piloting/2 + Handling, no +3 base."""
        from m1_psi_core.defense import calculate_base_dodge
        # Piloting 14, Handling +4: 14/2 + 4 = 11
        assert calculate_base_dodge(piloting=14, handling=4) == 11

    def test_dodge_rounds_down(self):
        """Piloting/2 rounds down for odd values."""
        from m1_psi_core.defense import calculate_base_dodge
        # Piloting 15, Handling +4: 15/2 = 7 (rounded down) + 4 = 11
        assert calculate_base_dodge(piloting=15, handling=4) == 11

    def test_spectre_dodge_matches(self):
        """Spectre: Piloting 16, Handling +6 -> Dodge 14."""
        from m1_psi_core.defense import calculate_base_dodge
        assert calculate_base_dodge(piloting=16, handling=6) == 14

    def test_capital_ship_low_dodge(self):
        """Capital ship with negative handling has very low dodge."""
        from m1_psi_core.defense import calculate_base_dodge
        # Piloting 12, Handling -4: 12/2 + (-4) = 2
        assert calculate_base_dodge(piloting=12, handling=-4) == 2

    def test_dodge_can_be_modified(self):
        """The base dodge can be further modified by future perks/traits."""
        from m1_psi_core.defense import calculate_base_dodge
        # This test documents that the formula produces a base value
        # that other modifiers stack onto
        base = calculate_base_dodge(piloting=14, handling=4)
        assert base == 11
        # Enhanced dodge or other modifiers would add to this in calculate_effective_dodge


class TestDodgeModifiers:
    """Modifiers that stack on top of base dodge."""

    def test_evade_bonus(self):
        """Evade maneuver grants +2 to dodge."""
        from m1_psi_core.defense import get_dodge_modifiers
        mods = get_dodge_modifiers(
            maneuver="evade", has_advantage_escaping=False,
            ace_pilot_stunt=False, tactical_defense=False,
            precision_aiming_aware=False,
        )
        assert mods.evade_bonus == 2

    def test_advantage_escaping_bonus(self):
        """Gaining advantage while escaping grants +1 to all defenses."""
        from m1_psi_core.defense import get_dodge_modifiers
        mods = get_dodge_modifiers(
            maneuver="move", has_advantage_escaping=True,
            ace_pilot_stunt=False, tactical_defense=False,
            precision_aiming_aware=False,
        )
        assert mods.advantage_escaping_bonus == 1

    def test_ace_pilot_stunt_bonus(self):
        """Ace Pilot with Stunt maneuver gets +1 to first dodge."""
        from m1_psi_core.defense import get_dodge_modifiers
        mods = get_dodge_modifiers(
            maneuver="stunt", has_advantage_escaping=False,
            ace_pilot_stunt=True, tactical_defense=False,
            precision_aiming_aware=False,
        )
        assert mods.ace_stunt_bonus == 1

    def test_precision_aiming_awareness_bonus(self):
        """Target aware of being precision-aimed gets +2 to dodge."""
        from m1_psi_core.defense import get_dodge_modifiers
        mods = get_dodge_modifiers(
            maneuver="move", has_advantage_escaping=False,
            ace_pilot_stunt=False, tactical_defense=False,
            precision_aiming_aware=True,
        )
        assert mods.precision_aim_awareness_bonus == 2

    def test_tactical_coordination_defensive(self):
        """Tactical coordination (defensive) grants +1 dodge to formation."""
        from m1_psi_core.defense import get_dodge_modifiers
        mods = get_dodge_modifiers(
            maneuver="move", has_advantage_escaping=False,
            ace_pilot_stunt=False, tactical_defense=True,
            precision_aiming_aware=False,
        )
        assert mods.tactical_defense_bonus == 1


class TestHighGDodge:
    """High-G dodge: +1 dodge but requires HT roll."""

    def test_high_g_available_high_accel(self):
        """High-G dodge available if acceleration >= 40."""
        from m1_psi_core.defense import is_high_g_available
        assert is_high_g_available(accel=40, top_speed=300) is True
        assert is_high_g_available(accel=39, top_speed=300) is False

    def test_high_g_available_high_speed(self):
        """High-G dodge available if top_speed >= 400."""
        from m1_psi_core.defense import is_high_g_available
        assert is_high_g_available(accel=10, top_speed=400) is True
        assert is_high_g_available(accel=10, top_speed=399) is False

    def test_high_g_dodge_bonus(self):
        """High-G dodge grants +1."""
        from m1_psi_core.defense import HIGH_G_DODGE_BONUS
        assert HIGH_G_DODGE_BONUS == 1

    def test_high_g_ht_roll_g_chair_bonus(self):
        """G-chair or G-suit gives +2 to HT roll for High-G."""
        from m1_psi_core.defense import get_high_g_ht_modifier
        assert get_high_g_ht_modifier(has_g_chair=True) == 2
        assert get_high_g_ht_modifier(has_g_chair=False) == 0

    def test_high_g_failure_fp_loss(self):
        """Failed HT roll causes FP loss equal to margin of failure."""
        from m1_psi_core.defense import calculate_high_g_fp_loss
        # HT 12, rolled 15: margin of failure = 3 -> lose 3 FP
        assert calculate_high_g_fp_loss(ht=12, roll=15) == 3
        # HT 12, rolled 12: success -> 0 FP loss
        assert calculate_high_g_fp_loss(ht=12, roll=12) == 0


class TestMissileDefense:
    """Additional defense modifiers against missiles."""

    def test_missile_dodge_penalty(self):
        """Missiles impose -3 to dodge."""
        from m1_psi_core.defense import MISSILE_DODGE_PENALTY
        assert MISSILE_DODGE_PENALTY == -3

    def test_tactical_esm_bonus(self):
        """Tactical ESM gives +1 vs missiles."""
        from m1_psi_core.defense import get_missile_defense_modifiers
        mods = get_missile_defense_modifiers(
            has_tactical_esm=True, has_decoy=False,
        )
        assert mods.esm_bonus == 1

    def test_decoy_launcher_bonus(self):
        """Decoy launcher gives +1 vs missiles."""
        from m1_psi_core.defense import get_missile_defense_modifiers
        mods = get_missile_defense_modifiers(
            has_tactical_esm=False, has_decoy=True,
        )
        assert mods.decoy_bonus == 1

    def test_combined_missile_defense(self):
        """ESM + decoy stack: -3 + 1 + 1 = -1 net modifier."""
        from m1_psi_core.defense import get_missile_defense_modifiers
        mods = get_missile_defense_modifiers(
            has_tactical_esm=True, has_decoy=True,
        )
        total = -3 + mods.esm_bonus + mods.decoy_bonus
        assert total == -1


class TestMissileJamming:
    """Jamming missiles as an alternative to dodging."""

    def test_jam_missile_skill(self):
        """Jam missile uses EO(ECM)/2."""
        from m1_psi_core.defense import calculate_jam_missile
        # ECM skill 14: base = 14/2 = 7
        result = calculate_jam_missile(
            ecm_skill=14, vehicle_ecm_rating=-4, has_decoy=False,
        )
        assert result.effective_skill == 9  # 7 + half of 4

    def test_jam_missile_ecm_bonus(self):
        """Jam missile adds half vehicle ECM rating."""
        from m1_psi_core.defense import calculate_jam_missile
        # ECM skill 14: 14/2 = 7, ECM rating -4: bonus = 2
        result = calculate_jam_missile(
            ecm_skill=14, vehicle_ecm_rating=-4, has_decoy=False,
        )
        assert result.ecm_bonus == 2

    def test_jam_missile_decoy_bonus(self):
        """Decoy launcher adds +2 to missile jamming."""
        from m1_psi_core.defense import calculate_jam_missile
        result = calculate_jam_missile(
            ecm_skill=14, vehicle_ecm_rating=-4, has_decoy=True,
        )
        assert result.decoy_bonus == 2
        # Total: 7 + 2 + 2 = 11
        assert result.effective_skill == 11
