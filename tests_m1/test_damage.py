"""
Tests for the damage subsystem.

Covers:
- Force screen ablation (standard and heavy)
- Armor divisor application
- Hull DR penetration
- Wound level determination
- Subsystem damage table (3d6)
- Cascade logic
- Wound accumulation
- Cinematic injury (mook rules, Just a Scratch)
- Targeted system attacks (-5)
"""
import pytest


class TestForceScreenAblation:
    """Force screen DR: hardened 1, ablative."""

    def test_force_screen_absorbs_damage(self):
        """Force screen absorbs damage first, reducing remaining."""
        from m1_psi_core.damage import apply_force_screen
        result = apply_force_screen(
            incoming_damage=100, current_fdr=150,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert result.absorbed == 100
        assert result.penetrating == 0
        assert result.remaining_fdr == 50

    def test_force_screen_fully_depleted(self):
        """Damage exceeding fDR penetrates through."""
        from m1_psi_core.damage import apply_force_screen
        result = apply_force_screen(
            incoming_damage=200, current_fdr=150,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert result.absorbed == 150
        assert result.penetrating == 50
        assert result.remaining_fdr == 0

    def test_standard_screen_ignores_ad_vs_plasma(self):
        """Standard force screens ignore armor divisors vs plasma/shaped charge."""
        from m1_psi_core.damage import apply_force_screen
        # 100 damage with AD 10 vs 150 fDR standard screen, plasma damage
        # Screen ignores the AD, so full 150 fDR applies
        result = apply_force_screen(
            incoming_damage=100, current_fdr=150,
            armor_divisor=10, force_screen_type="standard",
            damage_type="burn",  # plasma burn counts
        )
        assert result.absorbed == 100
        assert result.penetrating == 0

    def test_heavy_screen_ignores_all_ad(self):
        """Heavy force screens ignore ALL armor divisors."""
        from m1_psi_core.damage import apply_force_screen
        # Any damage type with any AD vs heavy screen
        result = apply_force_screen(
            incoming_damage=500, current_fdr=10000,
            armor_divisor=3, force_screen_type="heavy",
            damage_type="cr",  # crushing, not plasma
        )
        # Heavy screen ignores AD entirely
        assert result.absorbed == 500
        assert result.remaining_fdr == 9500

    def test_no_force_screen(self):
        """Ship without force screen: all damage passes through."""
        from m1_psi_core.damage import apply_force_screen
        result = apply_force_screen(
            incoming_damage=100, current_fdr=0,
            armor_divisor=5, force_screen_type="none",
            damage_type="burn",
        )
        assert result.penetrating == 100


class TestArmorDivisorApplication:
    """Armor divisor modifies effective DR."""

    def test_divisor_5(self):
        """AD (5) divides DR by 5."""
        from m1_psi_core.damage import apply_armor_divisor
        assert apply_armor_divisor(dr=100, divisor=5.0) == 20

    def test_divisor_10(self):
        """AD (10) divides DR by 10."""
        from m1_psi_core.damage import apply_armor_divisor
        assert apply_armor_divisor(dr=100, divisor=10.0) == 10

    def test_divisor_1(self):
        """No divisor (1): DR unchanged."""
        from m1_psi_core.damage import apply_armor_divisor
        assert apply_armor_divisor(dr=100, divisor=1.0) == 100

    def test_fractional_divisor_doubles_dr(self):
        """AD (0.5) doubles DR."""
        from m1_psi_core.damage import apply_armor_divisor
        assert apply_armor_divisor(dr=100, divisor=0.5) == 200

    def test_fractional_divisor_5x_dr(self):
        """AD (0.2) quintuples DR."""
        from m1_psi_core.damage import apply_armor_divisor
        assert apply_armor_divisor(dr=100, divisor=0.2) == 500

    def test_rounding(self):
        """Division rounds down."""
        from m1_psi_core.damage import apply_armor_divisor
        assert apply_armor_divisor(dr=15, divisor=5.0) == 3


class TestHullPenetration:
    """Damage penetration through hull DR."""

    def test_damage_exceeds_dr(self):
        """Damage > DR: penetrating damage = damage - effective DR."""
        from m1_psi_core.damage import calculate_penetrating_damage
        result = calculate_penetrating_damage(
            damage=100, dr=15, armor_divisor=5.0,
        )
        # Effective DR = 15/5 = 3
        assert result == 97

    def test_damage_less_than_dr(self):
        """Damage < DR: no penetration."""
        from m1_psi_core.damage import calculate_penetrating_damage
        result = calculate_penetrating_damage(
            damage=10, dr=100, armor_divisor=1.0,
        )
        assert result == 0

    def test_minimum_zero(self):
        """Penetrating damage cannot go negative."""
        from m1_psi_core.damage import calculate_penetrating_damage
        result = calculate_penetrating_damage(
            damage=5, dr=500, armor_divisor=1.0,
        )
        assert result == 0


class TestWoundLevel:
    """Wound level determination from single-hit penetrating damage vs max HP."""

    def test_scratch(self):
        """Damage < 10% HP = scratch."""
        from m1_psi_core.damage import determine_wound_level
        assert determine_wound_level(damage=7, max_hp=80) == "scratch"

    def test_minor(self):
        """Damage 10%-49% HP = minor."""
        from m1_psi_core.damage import determine_wound_level
        assert determine_wound_level(damage=20, max_hp=80) == "minor"

    def test_major(self):
        """Damage 50%-99% HP = major. Disables a system."""
        from m1_psi_core.damage import determine_wound_level
        assert determine_wound_level(damage=60, max_hp=80) == "major"

    def test_crippling(self):
        """Damage 100%-199% HP = crippling. Destroys a system."""
        from m1_psi_core.damage import determine_wound_level
        assert determine_wound_level(damage=120, max_hp=80) == "crippling"

    def test_mortal(self):
        """Damage 200%-499% HP = mortal. Destroys system + HT roll or destroyed."""
        from m1_psi_core.damage import determine_wound_level
        assert determine_wound_level(damage=300, max_hp=80) == "mortal"

    def test_lethal(self):
        """Damage 500%+ HP = lethal. Instantly destroyed."""
        from m1_psi_core.damage import determine_wound_level
        assert determine_wound_level(damage=500, max_hp=80) == "lethal"


class TestSubsystemDamageTable:
    """3d6 subsystem damage table with cascade."""

    def test_all_rolls_mapped(self):
        """Every roll from 3-18 maps to a valid system."""
        from m1_psi_core.damage import get_subsystem_hit
        for roll in range(3, 19):
            system, cascade = get_subsystem_hit(roll)
            assert system is not None
            assert isinstance(system, str)

    def test_specific_rolls(self):
        """Spot-check specific roll mappings."""
        from m1_psi_core.damage import get_subsystem_hit
        assert get_subsystem_hit(3) == ("fuel", "power")
        assert get_subsystem_hit(5) == ("propulsion", "weaponry")
        assert get_subsystem_hit(7) == ("equipment", "controls")
        assert get_subsystem_hit(9) == ("weaponry", "equipment")
        assert get_subsystem_hit(10) == ("armor", "fuel")
        assert get_subsystem_hit(14) == ("cargo_hangar", None)

    def test_cascade_on_already_disabled(self):
        """If system already disabled, roll HT. Failure -> destroyed (crippling)."""
        from m1_psi_core.damage import resolve_subsystem_cascade
        # Mock: system is disabled, HT roll fails
        result = resolve_subsystem_cascade(
            system="propulsion", current_status="disabled",
            ht_roll_succeeded=False, cascade_target="weaponry",
        )
        assert result.system_destroyed is True
        assert result.is_crippling_wound is True

    def test_cascade_on_already_disabled_ht_success(self):
        """If system disabled and HT succeeds, cascade to next system."""
        from m1_psi_core.damage import resolve_subsystem_cascade
        result = resolve_subsystem_cascade(
            system="propulsion", current_status="disabled",
            ht_roll_succeeded=True, cascade_target="weaponry",
        )
        assert result.system_destroyed is False
        assert result.cascades_to == "weaponry"

    def test_cascade_on_already_destroyed(self):
        """If system already destroyed, cascade to next system."""
        from m1_psi_core.damage import resolve_subsystem_cascade
        result = resolve_subsystem_cascade(
            system="propulsion", current_status="destroyed",
            ht_roll_succeeded=True, cascade_target="weaponry",
        )
        assert result.cascades_to == "weaponry"

    def test_no_cascade_target(self):
        """Cargo/Hangar has no cascade target."""
        from m1_psi_core.damage import get_subsystem_hit
        system, cascade = get_subsystem_hit(6)
        assert system == "cargo_hangar"
        assert cascade is None


class TestWoundAccumulation:
    """Wound accumulation: repeated wounds of same or lower severity may escalate."""

    def test_accumulation_ht_failure_escalates(self):
        """Failed HT roll on accumulation escalates wound level by one."""
        from m1_psi_core.damage import check_wound_accumulation
        result = check_wound_accumulation(
            current_wound="minor", new_wound="minor",
            ht_roll_succeeded=False,
        )
        assert result.escalated is True
        assert result.new_wound_level == "major"

    def test_accumulation_ht_success_no_escalation(self):
        """Successful HT roll: no escalation."""
        from m1_psi_core.damage import check_wound_accumulation
        result = check_wound_accumulation(
            current_wound="minor", new_wound="minor",
            ht_roll_succeeded=True,
        )
        assert result.escalated is False

    def test_accumulation_ht_margin_0_extra_system(self):
        """HT success by exactly 0 on wound that damages systems = extra system hit."""
        from m1_psi_core.damage import check_wound_accumulation
        result = check_wound_accumulation(
            current_wound="major", new_wound="major",
            ht_roll_succeeded=True, ht_margin=0,
        )
        assert result.extra_system_damage is True

    def test_higher_wound_does_not_accumulate(self):
        """A wound HIGHER than current level applies directly, no accumulation."""
        from m1_psi_core.damage import check_wound_accumulation
        result = check_wound_accumulation(
            current_wound="minor", new_wound="major",
            ht_roll_succeeded=False,
        )
        assert result.escalated is False  # Direct application, not accumulation


class TestTargetedSystem:
    """Attacking a specific system by taking -5 to hit."""

    def test_targeted_system_penalty(self):
        """Targeting a specific system imposes -5 to hit."""
        from m1_psi_core.damage import TARGETED_SYSTEM_PENALTY
        assert TARGETED_SYSTEM_PENALTY == -5


class TestCinematicInjury:
    """Mook rules and Just a Scratch."""

    def test_mook_major_wound_removes(self):
        """Mook vehicle taking a major wound is removed from combat."""
        from m1_psi_core.damage import apply_mook_rules
        result = apply_mook_rules(wound_level="major")
        assert result.removed is True

    def test_mook_minor_wound_continues(self):
        """Mook vehicle taking a minor wound continues fighting."""
        from m1_psi_core.damage import apply_mook_rules
        result = apply_mook_rules(wound_level="minor")
        assert result.removed is False

    def test_mook_scratch_continues(self):
        """Mook vehicle taking a scratch continues."""
        from m1_psi_core.damage import apply_mook_rules
        result = apply_mook_rules(wound_level="scratch")
        assert result.removed is False

    def test_mook_flag_toggleable(self):
        """Any ship can be marked as mook or not at any time."""
        from m1_psi_core.testing import MockShipStats
        ship = MockShipStats(is_mook=False)
        assert ship.is_mook is False
        ship.is_mook = True
        assert ship.is_mook is True

    def test_just_a_scratch_reduces_to_minor(self):
        """'Just a Scratch' reduces any wound to minor."""
        from m1_psi_core.damage import apply_just_a_scratch
        result = apply_just_a_scratch(wound_level="crippling")
        assert result.reduced_level == "minor"

    def test_just_a_scratch_accumulation_cap(self):
        """Accumulation from Just a Scratch can only trigger disabled, never worse."""
        from m1_psi_core.damage import apply_just_a_scratch
        result = apply_just_a_scratch(wound_level="mortal")
        assert result.max_accumulation_effect == "disabled"
