"""
Comprehensive tests for the v0.15 feature batch.

Features covered:
1. Wound accumulation (HT rolls for repeated wounds)
2. HT roll on crippling/mortal wounds to remain operational
3. Subsystem cascade mechanic
4. Stall speed chase attack restriction
5. Weapon range enforcement
6. Multiple weapons per ship (weapon selection)
7. Emergency power in pipeline
8. Deceptive attacks through pipeline
9. Luck/Impulse points
10. NPC High-G decision making
"""
import pytest
from m1_psi_core.testing import MockShipStats, MockPilot, MockDice


# ============================================================================
# 1. Wound Accumulation
# ============================================================================

class TestWoundAccumulation:
    """Repeated wounds of same or lower severity trigger HT roll to escalate."""

    def test_same_level_wound_triggers_accumulation(self):
        """Taking a second minor wound when already minor → HT roll."""
        from m1_psi_core.damage import check_wound_accumulation

        # HT roll fails → escalates
        result = check_wound_accumulation(
            current_wound="minor", new_wound="minor",
            ht_roll_succeeded=False, ht_margin=-1,
        )
        assert result.escalated is True
        assert result.new_wound_level == "major"

    def test_same_level_wound_ht_success_no_escalation(self):
        """Repeated wound, HT succeeds → no escalation."""
        from m1_psi_core.damage import check_wound_accumulation

        result = check_wound_accumulation(
            current_wound="minor", new_wound="minor",
            ht_roll_succeeded=True, ht_margin=3,
        )
        assert result.escalated is False

    def test_ht_margin_zero_extra_system_hit(self):
        """HT succeeds by exactly 0 on system-damaging wound → extra system."""
        from m1_psi_core.damage import check_wound_accumulation

        result = check_wound_accumulation(
            current_wound="major", new_wound="major",
            ht_roll_succeeded=True, ht_margin=0,
        )
        assert result.escalated is False
        assert result.extra_system_damage is True

    def test_higher_wound_no_accumulation_check(self):
        """A worse wound just applies directly, no HT roll needed."""
        from m1_psi_core.damage import check_wound_accumulation

        result = check_wound_accumulation(
            current_wound="minor", new_wound="major",
            ht_roll_succeeded=True, ht_margin=5,
        )
        assert result.escalated is False


# ============================================================================
# 2. Crippling/Mortal HT Rolls
# ============================================================================

class TestCripplingHTRoll:
    """Crippling wounds require HT roll to remain operational."""

    def test_crippling_ht_failure_disables_ship(self):
        """Crippling wound + HT fail → reduced to minimum systems."""
        from m1_psi_core.damage import check_operational_ht_roll

        result = check_operational_ht_roll(
            wound_level="crippling", ht_succeeded=False,
        )
        assert result.still_operational is False

    def test_crippling_ht_success_stays_operational(self):
        """Crippling wound + HT success → still fighting."""
        from m1_psi_core.damage import check_operational_ht_roll

        result = check_operational_ht_roll(
            wound_level="crippling", ht_succeeded=True,
        )
        assert result.still_operational is True

    def test_mortal_ht_failure_destroys(self):
        """Mortal wound + HT fail → destroyed."""
        from m1_psi_core.damage import check_operational_ht_roll

        result = check_operational_ht_roll(
            wound_level="mortal", ht_succeeded=False,
        )
        assert result.destroyed is True

    def test_mortal_ht_success_not_destroyed(self):
        """Mortal wound + HT success → not destroyed (but still rolls operational)."""
        from m1_psi_core.damage import check_operational_ht_roll

        result = check_operational_ht_roll(
            wound_level="mortal", ht_succeeded=True,
        )
        assert result.destroyed is False


# ============================================================================
# 3. Subsystem Cascade
# ============================================================================

class TestSubsystemCascade:
    """Hit already-disabled system → HT roll → destroyed or cascade."""

    def test_hit_disabled_system_ht_fail_destroys(self):
        """Already disabled + hit again + HT fail → destroyed + crippling."""
        from m1_psi_core.damage import resolve_subsystem_cascade

        result = resolve_subsystem_cascade(
            system="propulsion",
            current_status="disabled",
            ht_roll_succeeded=False,
            cascade_target="weaponry",
        )
        assert result.system_destroyed is True
        assert result.is_crippling_wound is True

    def test_hit_disabled_system_ht_success_cascades(self):
        """Already disabled + hit again + HT success → cascade to next system."""
        from m1_psi_core.damage import resolve_subsystem_cascade

        result = resolve_subsystem_cascade(
            system="propulsion",
            current_status="disabled",
            ht_roll_succeeded=True,
            cascade_target="weaponry",
        )
        assert result.system_destroyed is False
        assert result.cascades_to == "weaponry"

    def test_hit_destroyed_system_cascades_immediately(self):
        """Already destroyed → cascade immediately, no HT roll."""
        from m1_psi_core.damage import resolve_subsystem_cascade

        result = resolve_subsystem_cascade(
            system="propulsion",
            current_status="destroyed",
            ht_roll_succeeded=True,  # Irrelevant for destroyed
            cascade_target="weaponry",
        )
        assert result.cascades_to == "weaponry"


# ============================================================================
# 4. Stall Speed Chase Attack Restriction
# ============================================================================

class TestStallSpeedChaseRestriction:
    """Ships with stall speed that lose the chase can't fire fixed weapons."""

    def test_stall_speed_loser_cannot_fire_fixed(self):
        """Ship with stall speed, lost chase → fixed weapons blocked."""
        from m1_psi_core.engine import check_stall_attack_restriction

        can_fire = check_stall_attack_restriction(
            has_stall_speed=True, won_chase=False,
            weapon_mount="fixed_front",
        )
        assert can_fire is False

    def test_stall_speed_winner_can_fire(self):
        """Ship with stall speed, won chase → can fire."""
        from m1_psi_core.engine import check_stall_attack_restriction

        can_fire = check_stall_attack_restriction(
            has_stall_speed=True, won_chase=True,
            weapon_mount="fixed_front",
        )
        assert can_fire is True

    def test_no_stall_speed_always_fires(self):
        """Ship without stall speed → fires regardless of chase result."""
        from m1_psi_core.engine import check_stall_attack_restriction

        can_fire = check_stall_attack_restriction(
            has_stall_speed=False, won_chase=False,
            weapon_mount="fixed_front",
        )
        assert can_fire is True

    def test_stall_speed_loser_turret_still_fires(self):
        """Stall speed, lost chase, but TURRET weapon → can still fire."""
        from m1_psi_core.engine import check_stall_attack_restriction

        can_fire = check_stall_attack_restriction(
            has_stall_speed=True, won_chase=False,
            weapon_mount="turret",
        )
        assert can_fire is True


# ============================================================================
# 5. Weapon Range Enforcement
# ============================================================================

class TestWeaponRange:
    """Weapons can't fire beyond their max range."""

    def test_weapon_in_range_can_fire(self):
        """Weapon with 8000yd max range at Long (500yd) → can fire."""
        from m1_psi_core.engine import is_weapon_in_range

        assert is_weapon_in_range("2700/8000", "long") is True

    def test_weapon_out_of_range_blocked(self):
        """Weapon with 8000yd max range at Beyond Visual (10000+yd) → blocked."""
        from m1_psi_core.engine import is_weapon_in_range

        assert is_weapon_in_range("2700/8000", "beyond_visual") is False

    def test_weapon_reaches_distant(self):
        """Weapon with 8000yd max range at Distant (2001-10000yd) → can fire."""
        from m1_psi_core.engine import is_weapon_in_range

        assert is_weapon_in_range("2700/8000", "distant") is True

    def test_weapon_at_extreme_edge(self):
        """Weapon with 8000yd max range at Extreme (2000yd) → can fire."""
        from m1_psi_core.engine import is_weapon_in_range

        assert is_weapon_in_range("2700/8000", "extreme") is True

    def test_no_range_data_always_fires(self):
        """Weapon with no range data → always allowed (graceful fallback)."""
        from m1_psi_core.engine import is_weapon_in_range

        assert is_weapon_in_range("", "distant") is True
        assert is_weapon_in_range(None, "distant") is True


# ============================================================================
# 6. Multiple Weapons (weapon selection helpers)
# ============================================================================

class TestMultipleWeapons:
    """Ships with multiple weapons can select which to fire."""

    def test_resolve_all_weapons_returns_list(self):
        """resolve_all_weapons returns all available weapons for a ship."""
        from m1_psi_core.engine import resolve_all_weapons

        ship = MockShipStats(weapons=[
            {"weapon_ref": "imperial_fighter_blaster", "mount": "fixed_front",
             "linked_count": 2, "arc": "front"},
        ])
        weapons = resolve_all_weapons(ship)
        assert len(weapons) >= 1
        assert weapons[0].name == "Imperial Fighter Blaster"

    def test_fallback_weapon_when_no_data(self):
        """Ship with no weapon refs gets a fallback weapon."""
        from m1_psi_core.engine import resolve_all_weapons

        ship = MockShipStats(weapons=[])
        weapons = resolve_all_weapons(ship)
        assert len(weapons) == 1  # Fallback
        assert weapons[0].name == "Fighter Blaster"


# ============================================================================
# 7. Emergency Power in Pipeline
# ============================================================================

class TestEmergencyPowerPipeline:
    """Emergency power options produce correct effects."""

    def test_all_power_to_engines_chase_bonus(self):
        """All Power to Engines: +2 to chase rolls."""
        from m1_psi_core.emergency_power import get_option_effect

        effect = get_option_effect("all_power_to_engines")
        assert effect.chase_bonus == 2

    def test_emergency_evasive_dodge_bonus(self):
        """Emergency Evasive: +2 to dodge, counts as High-G."""
        from m1_psi_core.emergency_power import get_option_effect

        effect = get_option_effect("emergency_evasive")
        assert effect.dodge_bonus == 2
        assert effect.is_high_g is True

    def test_emergency_firepower_damage_bonus(self):
        """Emergency Firepower: +1 damage per die."""
        from m1_psi_core.emergency_power import get_option_effect

        effect = get_option_effect("emergency_firepower")
        assert effect.damage_per_die_bonus == 1

    def test_emergency_screen_recharge(self):
        """Emergency Screen Recharge: immediate fDR restore."""
        from m1_psi_core.emergency_power import get_option_effect

        effect = get_option_effect("emergency_screen_recharge")
        assert effect.restores_fdr is True


# ============================================================================
# 8. Deceptive Attacks
# ============================================================================

class TestDeceptiveAttacks:
    """Deceptive attack: -2 to hit per -1 to target's defense."""

    def test_deceptive_reduces_hit_and_defense(self):
        """1 level deceptive: -2 to hit, -1 to target dodge."""
        from m1_psi_core.engine import resolve_attack, resolve_defense, WeaponInfo
        from m1_psi_core.combat_state import EngagementState
        from m1_psi_core.dice import DiceRoller

        attacker = MockShipStats(instance_id="a1", display_name="Attacker")
        target = MockShipStats(instance_id="b1", display_name="Target", hnd=4)
        pilot = MockPilot(gunnery_skill=16)
        tpilot = MockPilot(piloting_skill=14)
        eng = EngagementState(ship_a_id="a1", ship_b_id="b1", range_band="long")

        weapon = WeaponInfo(
            name="Blaster", damage_str="6d×5(5) burn", acc=9, rof=3,
            weapon_type="beam", armor_divisor=5.0, mount="fixed_front",
            linked_count=1, is_explosive=False,
        )

        # Attack with 1 level deceptive
        atk = resolve_attack(
            "a1", attacker, pilot, "b1", target, eng,
            {"maneuver": "move_and_attack", "intent": "pursue"},
            weapon, DiceRoller(seed=42), deceptive_levels=1,
        )

        assert atk.modifiers.deceptive_penalty == -2

    def test_deceptive_penalty_flows_to_defense(self):
        """Deceptive penalty reduces effective dodge."""
        from m1_psi_core.engine import resolve_defense
        from m1_psi_core.combat_state import EngagementState

        defender = MockShipStats(instance_id="b1", display_name="Target", hnd=4)
        pilot = MockPilot(piloting_skill=14)
        eng = EngagementState(ship_a_id="a1", ship_b_id="b1", range_band="long")

        # Normal defense
        d_normal = resolve_defense(
            "b1", defender, pilot, "move_and_attack", "move_and_attack",
            eng, MockDice([10]), deceptive_penalty=0,
            player_chose_high_g=False,
        )

        # Deceptive defense (-1)
        d_deceptive = resolve_defense(
            "b1", defender, pilot, "move_and_attack", "move_and_attack",
            eng, MockDice([10]), deceptive_penalty=-1,
            player_chose_high_g=False,
        )

        assert d_deceptive.modifiers.effective_dodge == d_normal.modifiers.effective_dodge - 1


# ============================================================================
# 9. Luck/Impulse Points
# ============================================================================

class TestLuckPoints:
    """Luck: reroll an attack/defense, take worst/best of 3."""

    def test_luck_reroll_returns_best_of_three(self):
        """Luck defensive: roll 2 more times, take the best (lowest) roll."""
        from m1_psi_core.special import apply_luck_reroll

        result = apply_luck_reroll(
            original_roll=15,
            rerolls=[8, 12],
            pick="best",  # Defensive: best for the user = lowest
        )
        assert result.chosen_roll == 8  # Best of 15, 8, 12

    def test_luck_offensive_takes_worst(self):
        """Luck offensive (forced on opponent): take worst (highest) roll."""
        from m1_psi_core.special import apply_luck_reroll

        result = apply_luck_reroll(
            original_roll=8,
            rerolls=[15, 12],
            pick="worst",
        )
        assert result.chosen_roll == 15  # Worst of 8, 15, 12


class TestImpulsePoints:
    """Impulse: flesh wound reduces severity to minor."""

    def test_flesh_wound_reduces_to_minor(self):
        """Flesh Wound (1 character point): reduce any wound to minor."""
        from m1_psi_core.special import apply_flesh_wound

        result = apply_flesh_wound("crippling")
        assert result == "minor"

    def test_flesh_wound_on_minor_stays_minor(self):
        """Flesh wound on minor → still minor."""
        from m1_psi_core.special import apply_flesh_wound

        result = apply_flesh_wound("minor")
        assert result == "minor"


# ============================================================================
# 10. NPC High-G Decision Making
# ============================================================================

class TestNPCHighGDecision:
    """NPC should weigh FP cost vs threat when deciding High-G."""

    def test_npc_attempts_high_g_when_healthy(self):
        """Healthy NPC with available FP → attempt High-G."""
        from m1_psi_core.npc_ai import should_attempt_high_g

        assert should_attempt_high_g(
            current_fp=10, max_fp=10, wound_level="none",
            attacker_margin=3,
        ) is True

    def test_npc_skips_high_g_when_exhausted(self):
        """NPC with low FP → skip High-G to conserve energy."""
        from m1_psi_core.npc_ai import should_attempt_high_g

        assert should_attempt_high_g(
            current_fp=1, max_fp=10, wound_level="none",
            attacker_margin=1,
        ) is False

    def test_npc_attempts_high_g_when_desperate(self):
        """Badly wounded NPC → attempt High-G even with low FP."""
        from m1_psi_core.npc_ai import should_attempt_high_g

        assert should_attempt_high_g(
            current_fp=2, max_fp=10, wound_level="crippling",
            attacker_margin=5,
        ) is True
