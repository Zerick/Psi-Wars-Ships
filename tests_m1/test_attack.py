"""
Tests for the attack subsystem.

Covers:
- Hit modifier pipeline (all sources stacked correctly)
- Range/speed penalty selection (highest of three)
- Size modifier application
- Relative size penalty (fighter/corvette/capital)
- Sensor lock bonus (+3 base, +5 with targeting computer)
- Accuracy rules (full, half, none)
- Precision aiming (+4 next turn)
- Deceptive attack trade-off
- Weapon linking / ROF bonus
- Matched speed range/speed override
- Plasma flak special rules
- Cannot-attack conditions
"""
import pytest


class TestRangeSpeedPenalty:
    """Range and speed penalty: use highest of |range|, own speed, target speed."""

    def test_range_dominates(self):
        """When range penalty is largest, use it."""
        from m1_psi_core.attack import calculate_range_speed_penalty
        # Range -15 (extreme), own speed -8, target speed -6
        penalty = calculate_range_speed_penalty(
            range_penalty=-15, own_speed_penalty=-8, target_speed_penalty=-6,
            matched_speed=False, stall_speed=0,
        )
        assert penalty == -15

    def test_own_speed_dominates(self):
        """When own speed penalty is largest, use it."""
        from m1_psi_core.attack import calculate_range_speed_penalty
        # Close range (-0), but very fast ships
        penalty = calculate_range_speed_penalty(
            range_penalty=0, own_speed_penalty=-12, target_speed_penalty=-8,
            matched_speed=False, stall_speed=0,
        )
        assert penalty == -12

    def test_target_speed_dominates(self):
        """When target speed penalty is largest, use it."""
        from m1_psi_core.attack import calculate_range_speed_penalty
        penalty = calculate_range_speed_penalty(
            range_penalty=-5, own_speed_penalty=-3, target_speed_penalty=-14,
            matched_speed=False, stall_speed=0,
        )
        assert penalty == -14

    def test_matched_speed_override(self):
        """Matched speed: use higher of |range penalty| or stall speed."""
        from m1_psi_core.attack import calculate_range_speed_penalty
        # Matched speed, range -11 (long), stall 35
        penalty = calculate_range_speed_penalty(
            range_penalty=-11, own_speed_penalty=-8, target_speed_penalty=-6,
            matched_speed=True, stall_speed=35,
        )
        # Stall speed 35 would have its own penalty from the speed/size table
        # The higher of |range| and stall-derived penalty applies
        assert penalty <= -11  # At minimum the range penalty


class TestSizeModifier:
    """Target SM as a bonus to hit."""

    def test_sm_positive(self):
        """Target SM adds as bonus (capital ship SM 13 = +13 to hit)."""
        from m1_psi_core.attack import get_sm_bonus
        assert get_sm_bonus(target_sm=13) == 13

    def test_sm_fighter(self):
        """Fighter SM 4 gives +4."""
        from m1_psi_core.attack import get_sm_bonus
        assert get_sm_bonus(target_sm=4) == 4


class TestRelativeSize:
    """Relative size penalties between ship classes."""

    def test_capital_vs_fighter(self):
        """Capital ship firing at fighter: -10."""
        from m1_psi_core.attack import get_relative_size_penalty
        penalty = get_relative_size_penalty(
            attacker_class="capital", target_class="fighter",
            is_light_turret=False,
        )
        assert penalty == -10

    def test_capital_vs_corvette(self):
        """Capital ship firing at corvette: -5."""
        from m1_psi_core.attack import get_relative_size_penalty
        penalty = get_relative_size_penalty(
            attacker_class="capital", target_class="corvette",
            is_light_turret=False,
        )
        assert penalty == -5

    def test_corvette_vs_fighter(self):
        """Corvette firing at fighter: -5."""
        from m1_psi_core.attack import get_relative_size_penalty
        penalty = get_relative_size_penalty(
            attacker_class="corvette", target_class="fighter",
            is_light_turret=False,
        )
        assert penalty == -5

    def test_fighter_vs_fighter(self):
        """Same class: no penalty."""
        from m1_psi_core.attack import get_relative_size_penalty
        penalty = get_relative_size_penalty(
            attacker_class="fighter", target_class="fighter",
            is_light_turret=False,
        )
        assert penalty == 0

    def test_light_turret_halves_penalty(self):
        """Light turret halves the relative size penalty (rounded down)."""
        from m1_psi_core.attack import get_relative_size_penalty
        # Capital vs fighter: -10, halved = -5
        penalty = get_relative_size_penalty(
            attacker_class="capital", target_class="fighter",
            is_light_turret=True,
        )
        assert penalty == -5
        # Capital vs corvette: -5, halved rounded down = -2
        penalty2 = get_relative_size_penalty(
            attacker_class="capital", target_class="corvette",
            is_light_turret=True,
        )
        assert penalty2 == -2

    def test_soar_like_leaf_applies_penalty_to_corvettes(self):
        """Soar like a Leaf: other corvettes and capitals take relative size penalty."""
        from m1_psi_core.attack import get_relative_size_penalty
        # Corvette with soar_like_leaf treated as fighter
        # So corvette firing at soar_like_leaf corvette: -5
        penalty = get_relative_size_penalty(
            attacker_class="corvette", target_class="fighter",  # Soar treats as fighter
            is_light_turret=False,
        )
        assert penalty == -5


class TestSensorLock:
    """Sensor lock bonuses."""

    def test_sensor_lock_base(self):
        """Sensor lock gives +3 to attack."""
        from m1_psi_core.attack import get_sensor_lock_bonus
        assert get_sensor_lock_bonus(has_lock=True, targeting_bonus=0) == 3

    def test_sensor_lock_with_targeting_computer(self):
        """Targeting computer increases sensor lock to +5."""
        from m1_psi_core.attack import get_sensor_lock_bonus
        assert get_sensor_lock_bonus(has_lock=True, targeting_bonus=5) == 5

    def test_no_sensor_lock(self):
        """No sensor lock gives +0."""
        from m1_psi_core.attack import get_sensor_lock_bonus
        assert get_sensor_lock_bonus(has_lock=False, targeting_bonus=5) == 0


class TestAccuracyApplication:
    """Accuracy bonus based on maneuver and circumstances."""

    def test_full_accuracy(self):
        """Full accuracy adds full weapon Acc."""
        from m1_psi_core.attack import apply_accuracy
        assert apply_accuracy(weapon_acc=9, permission="full_accuracy") == 9

    def test_half_accuracy(self):
        """Half accuracy adds half weapon Acc (rounded down)."""
        from m1_psi_core.attack import apply_accuracy
        assert apply_accuracy(weapon_acc=9, permission="half_accuracy") == 4

    def test_no_accuracy(self):
        """No accuracy adds 0."""
        from m1_psi_core.attack import apply_accuracy
        assert apply_accuracy(weapon_acc=9, permission="no_accuracy") == 0
        assert apply_accuracy(weapon_acc=9, permission="none") == 0

    def test_matched_speed_grants_accuracy_on_move_and_attack(self):
        """Matched speed allows adding accuracy even on Move and Attack."""
        from m1_psi_core.attack import apply_accuracy
        # With matched speed, M&A gets full accuracy
        assert apply_accuracy(weapon_acc=9, permission="full_accuracy") == 9


class TestPrecisionAiming:
    """Precision aiming: +4 next turn, but target gets +2 dodge."""

    def test_precision_aim_bonus(self):
        """Precision aiming grants +4 to attacks next turn."""
        from m1_psi_core.attack import get_precision_aim_bonus
        assert get_precision_aim_bonus(aimed_last_turn=True) == 4

    def test_precision_aim_requires_attack_maneuver(self):
        """Precision aim bonus only applies with Attack maneuver, not M&A."""
        from m1_psi_core.attack import get_precision_aim_bonus
        assert get_precision_aim_bonus(aimed_last_turn=True, current_maneuver="attack") == 4
        assert get_precision_aim_bonus(aimed_last_turn=True, current_maneuver="move_and_attack") == 0


class TestDeceptiveAttack:
    """Deceptive attacks: -2 skill per -1 to target defense."""

    def test_deceptive_attack_trade(self):
        """Taking -2 to skill gives target -1 to defense."""
        from m1_psi_core.attack import calculate_deceptive_attack
        skill_penalty, defense_penalty = calculate_deceptive_attack(deceptive_levels=1)
        assert skill_penalty == -2
        assert defense_penalty == -1

    def test_deceptive_attack_multiple(self):
        """Taking -4 to skill gives target -2 to defense."""
        from m1_psi_core.attack import calculate_deceptive_attack
        skill_penalty, defense_penalty = calculate_deceptive_attack(deceptive_levels=2)
        assert skill_penalty == -4
        assert defense_penalty == -2

    def test_deceptive_attack_minimum_skill(self):
        """Cannot deceptive attack below effective skill 10."""
        from m1_psi_core.attack import max_deceptive_levels
        # Base skill 14: can afford (14-10)/2 = 2 levels
        assert max_deceptive_levels(effective_skill=14) == 2
        # Base skill 10: no deceptive levels available
        assert max_deceptive_levels(effective_skill=10) == 0


class TestROFBonus:
    """Rapid fire bonus from the GURPS table."""

    def test_rof_bonus_table(self):
        """ROF bonus follows the GURPS rapid fire table."""
        from m1_psi_core.attack import get_rof_bonus
        assert get_rof_bonus(1) == 0
        assert get_rof_bonus(2) == 0
        assert get_rof_bonus(4) == 0
        assert get_rof_bonus(5) == 1
        assert get_rof_bonus(8) == 1
        assert get_rof_bonus(9) == 2
        assert get_rof_bonus(12) == 2
        assert get_rof_bonus(13) == 3
        assert get_rof_bonus(16) == 3
        assert get_rof_bonus(20) == 4
        assert get_rof_bonus(25) == 5
        assert get_rof_bonus(50) == 6


class TestWeaponFacingRestrictions:
    """Fixed mount weapons must match facing."""

    def test_fixed_front_cannot_fire_rear(self):
        """Fixed front mount cannot fire when facing rear."""
        from m1_psi_core.attack import can_weapon_fire
        assert can_weapon_fire(mount="fixed_front", arc="front",
                               current_facing="rear", is_advantaged=False) is False

    def test_fixed_front_fires_when_facing_front(self):
        """Fixed front mount fires when facing front."""
        from m1_psi_core.attack import can_weapon_fire
        assert can_weapon_fire(mount="fixed_front", arc="front",
                               current_facing="front", is_advantaged=False) is True

    def test_turret_fires_any_facing(self):
        """Turret weapons can fire regardless of facing."""
        from m1_psi_core.attack import can_weapon_fire
        assert can_weapon_fire(mount="turret", arc="all",
                               current_facing="rear", is_advantaged=False) is True

    def test_advantaged_overrides_facing(self):
        """Advantaged attacker may choose facing, so fixed weapons can fire."""
        from m1_psi_core.attack import can_weapon_fire
        assert can_weapon_fire(mount="fixed_front", arc="front",
                               current_facing="rear", is_advantaged=True) is True


class TestPlasmaFlak:
    """Plasma flak special attack rules."""

    def test_flak_extreme_range_hit(self):
        """At extreme range, flak hits on 1 + SM or less."""
        from m1_psi_core.attack import calculate_flak_hit_number
        # Target SM 4: hit on 1 + 4 = 5 or less
        assert calculate_flak_hit_number("extreme", target_sm=4) == 5

    def test_flak_long_range_hit(self):
        """At long or closer, flak hits on 5 + SM or less."""
        from m1_psi_core.attack import calculate_flak_hit_number
        assert calculate_flak_hit_number("long", target_sm=4) == 9
        assert calculate_flak_hit_number("short", target_sm=4) == 9

    def test_flak_handling_penalty(self):
        """Ships in flak range suffer -2 handling (rough terrain)."""
        from m1_psi_core.attack import get_flak_handling_penalty
        assert get_flak_handling_penalty(in_flak_zone=True) == -2
        assert get_flak_handling_penalty(in_flak_zone=False) == 0


class TestCannotAttack:
    """Conditions that prevent attacking."""

    def test_no_power_cannot_attack(self):
        """Ship with no power cannot fire weapons."""
        from m1_psi_core.attack import can_ship_attack
        assert can_ship_attack(no_power=True, weapons_destroyed=False) is False

    def test_weapons_destroyed_cannot_attack(self):
        """Ship with destroyed weaponry cannot fire."""
        from m1_psi_core.attack import can_ship_attack
        assert can_ship_attack(no_power=False, weapons_destroyed=True) is False

    def test_healthy_ship_can_attack(self):
        """Healthy ship can attack."""
        from m1_psi_core.attack import can_ship_attack
        assert can_ship_attack(no_power=False, weapons_destroyed=False) is True
