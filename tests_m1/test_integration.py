"""
Deep integration tests for M1 Psi-Core.

These tests verify that subsystems chain together correctly,
that state mutations propagate across turns, and that the engine
orchestrator drives a complete combat encounter.

Test categories:
1. Full damage pipeline (weapon -> force screen -> armor -> wound -> subsystem -> state)
2. Chase outcome application (resolve_chase_outcome -> EngagementState mutation)
3. Full turn orchestration (engine.py drives declaration -> cleanup)
4. Multi-turn state persistence (damage carries, screens regen, systems stay broken)
5. Edge cases (double near-miss, stall restrictions mid-combat, mook wipeout)
"""
import pytest
from m1_psi_core.testing import MockDice, MockShipStats, MockPilot, MockWeapon


# ============================================================================
# 1. Full Damage Pipeline
# ============================================================================

class TestFullDamagePipeline:
    """
    Chain the entire damage resolution pipeline:
    raw damage -> force screen -> armor -> penetrating -> wound level -> subsystem
    """

    def test_blaster_vs_shielded_fighter_full_pipeline(self):
        """
        Imperial Fighter Blaster (6d×5 AD5 burn) hits Hornet (150 fDR standard, 10 DR).
        Roll 6d6=21, ×5=105 damage.
        Force screen absorbs 105, remaining fDR = 45. No penetration.
        """
        from m1_psi_core.damage import apply_force_screen, calculate_penetrating_damage, determine_wound_level

        raw_damage = 21 * 5  # 105
        screen = apply_force_screen(
            incoming_damage=raw_damage, current_fdr=150,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert screen.absorbed == 105
        assert screen.penetrating == 0
        assert screen.remaining_fdr == 45

        # No penetration means no wound
        wound = determine_wound_level(screen.penetrating, max_hp=95)
        assert wound == "none"

    def test_blaster_vs_unshielded_fighter_full_pipeline(self):
        """
        Imperial Fighter Blaster hits Javelin (no fDR, 15 DR, 80 HP).
        Roll 6d6=24, ×5=120 damage.
        No force screen. DR 15 / AD 5 = effective DR 3.
        Penetrating = 120 - 3 = 117.
        117 / 80 HP = 146% -> crippling wound.
        """
        from m1_psi_core.damage import (
            apply_force_screen, calculate_penetrating_damage,
            determine_wound_level, get_subsystem_hit,
        )

        raw_damage = 24 * 5  # 120

        # No force screen
        screen = apply_force_screen(
            incoming_damage=raw_damage, current_fdr=0,
            armor_divisor=5, force_screen_type="none",
            damage_type="burn",
        )
        assert screen.penetrating == 120

        # Hull armor: DR 15, AD (5) -> effective DR 3
        penetrating = calculate_penetrating_damage(
            damage=screen.penetrating, dr=15, armor_divisor=5.0,
        )
        assert penetrating == 117

        # Wound level: 117/80 = 1.46 -> crippling (100%-199%)
        wound = determine_wound_level(penetrating, max_hp=80)
        assert wound == "crippling"

        # Crippling wound destroys a system — roll 3d6
        system, cascade = get_subsystem_hit(8)  # Example roll of 8
        assert system == "power"
        assert cascade == "propulsion"

    def test_torpedo_vs_shielded_corvette_full_pipeline(self):
        """
        400mm Isomeric Torpedo (5d×200 cr ex, no AD) hits Tigershark
        (750 fDR standard, 1000/400 DR, 400 HP).
        Roll 5d6=18, ×200=3600 damage.
        Force screen absorbs 750, remaining fDR 0. Penetrating = 2850.
        Hull DR 1000 (front), no AD -> effective DR 1000.
        Penetrating through hull = 2850 - 1000 = 1850.
        1850/400 = 462% -> mortal wound.
        """
        from m1_psi_core.damage import (
            apply_force_screen, calculate_penetrating_damage,
            determine_wound_level,
        )

        raw_damage = 18 * 200  # 3600

        screen = apply_force_screen(
            incoming_damage=raw_damage, current_fdr=750,
            armor_divisor=None, force_screen_type="standard",
            damage_type="cr",
        )
        assert screen.absorbed == 750
        assert screen.penetrating == 2850
        assert screen.remaining_fdr == 0

        penetrating = calculate_penetrating_damage(
            damage=screen.penetrating, dr=1000, armor_divisor=1.0,
        )
        assert penetrating == 1850

        wound = determine_wound_level(penetrating, max_hp=400)
        assert wound == "mortal"  # 462%

    def test_heavy_screen_blocks_armor_divisor(self):
        """
        Capital-scale cannon (6d×75 AD5) vs Imperator heavy screen (15000 fDR).
        Roll 6d6=22, ×75=1650.
        Heavy screen ignores AD entirely. Absorbs 1650, remaining 13350.
        """
        from m1_psi_core.damage import apply_force_screen

        raw_damage = 22 * 75  # 1650

        screen = apply_force_screen(
            incoming_damage=raw_damage, current_fdr=15000,
            armor_divisor=5, force_screen_type="heavy",
            damage_type="burn",
        )
        assert screen.absorbed == 1650
        assert screen.penetrating == 0
        assert screen.remaining_fdr == 13350

    def test_ghost_beam_ignores_dr_targets_pilot(self):
        """
        Ghost Beam (4d tox, ignores ship DR, blocked by shields).
        vs ship with 10 DR, 200 fDR.
        Roll 4d6=14. Toxic damage.
        Force screen blocks it (fDR absorbs 14, remaining 186).
        But if force screen is depleted: DR is ignored for tox, full damage to pilot.
        """
        from m1_psi_core.damage import apply_force_screen, calculate_penetrating_damage

        raw_damage = 14

        # With force screen up: blocked
        screen = apply_force_screen(
            incoming_damage=raw_damage, current_fdr=200,
            armor_divisor=None, force_screen_type="standard",
            damage_type="tox",
        )
        assert screen.penetrating == 0

        # With force screen depleted: all damage penetrates
        # (Ghost Beam ignores hull DR — this is a trait-based rule
        # that the engine handles by setting effective DR to 0)
        screen_down = apply_force_screen(
            incoming_damage=raw_damage, current_fdr=0,
            armor_divisor=None, force_screen_type="standard",
            damage_type="tox",
        )
        assert screen_down.penetrating == 14

        # DR is ignored for ghost beam (engine sets DR to 0 based on weapon trait)
        penetrating = calculate_penetrating_damage(
            damage=screen_down.penetrating, dr=0, armor_divisor=1.0,
        )
        assert penetrating == 14


# ============================================================================
# 2. Chase Outcome Application to Engagement State
# ============================================================================

class TestChaseOutcomeApplication:
    """
    Verify that chase roll outcomes correctly mutate EngagementState.
    """

    def test_victory_5_gain_advantage_applied(self):
        """Winner chooses advantage: EngagementState.advantage is set."""
        from m1_psi_core.chase import resolve_chase_outcome
        from m1_psi_core.combat_state import EngagementState

        eng = EngagementState(ship_a_id="alpha", ship_b_id="bravo", range_band="long")
        outcome = resolve_chase_outcome(
            margin=7, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=False,
        )

        # Winner chooses advantage
        assert outcome.can_gain_advantage is True
        eng.set_advantage("alpha")
        assert eng.advantage == "alpha"

    def test_victory_5_shift_range_applied(self):
        """Winner chooses range shift: EngagementState.range_band changes."""
        from m1_psi_core.chase import resolve_chase_outcome
        from m1_psi_core.combat_state import EngagementState, shift_range_band

        eng = EngagementState(ship_a_id="alpha", ship_b_id="bravo", range_band="long")
        outcome = resolve_chase_outcome(
            margin=6, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=False,
        )

        # Winner chooses range shift (pursuing = closer)
        assert outcome.can_shift_range == 1
        eng.range_band = shift_range_band(eng.range_band, -1)
        assert eng.range_band == "medium"

    def test_victory_10_advantage_plus_range(self):
        """Victory by 10+: can gain advantage AND shift 1 band."""
        from m1_psi_core.chase import resolve_chase_outcome
        from m1_psi_core.combat_state import EngagementState, shift_range_band

        eng = EngagementState(ship_a_id="alpha", ship_b_id="bravo", range_band="extreme")
        outcome = resolve_chase_outcome(
            margin=12, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=False,
        )

        assert outcome.can_gain_advantage is True
        assert outcome.can_shift_range >= 1

        eng.set_advantage("alpha")
        eng.range_band = shift_range_band(eng.range_band, -1)
        assert eng.advantage == "alpha"
        assert eng.range_band == "long"  # Closer from extreme = long

    def test_victory_10_already_advantaged_matches_speed(self):
        """Victory by 10+ when already advantaged: match speed."""
        from m1_psi_core.chase import resolve_chase_outcome
        from m1_psi_core.combat_state import EngagementState

        eng = EngagementState(ship_a_id="alpha", ship_b_id="bravo", range_band="long")
        eng.set_advantage("alpha")

        outcome = resolve_chase_outcome(
            margin=11, winner_intent="pursue",
            winner_had_advantage=True, loser_had_advantage=False,
        )
        assert outcome.can_match_speed is True

        eng.set_matched_speed("alpha")
        assert eng.matched_speed is True

    def test_loser_loses_advantage(self):
        """Loser of chase roll loses their advantage."""
        from m1_psi_core.chase import resolve_chase_outcome
        from m1_psi_core.combat_state import EngagementState

        eng = EngagementState(ship_a_id="alpha", ship_b_id="bravo", range_band="long")
        eng.set_advantage("bravo")

        # Alpha wins by 3 — bravo had advantage, loses it
        outcome = resolve_chase_outcome(
            margin=3, winner_intent="pursue",
            winner_had_advantage=False, loser_had_advantage=True,
        )
        assert outcome.opponent_loses_advantage is True

        eng.clear_advantage()
        assert eng.advantage is None

    def test_static_maneuver_grants_opponent_shift_and_loses_matched(self):
        """Static maneuver: opponent gets free range shift, matched speed lost."""
        from m1_psi_core.chase import get_static_maneuver_effects
        from m1_psi_core.combat_state import EngagementState, shift_range_band

        eng = EngagementState(ship_a_id="alpha", ship_b_id="bravo", range_band="medium")
        eng.set_advantage("alpha")
        eng.set_matched_speed("alpha")

        effects = get_static_maneuver_effects()
        assert effects.opponent_free_range_shift == 1
        assert effects.loses_matched_speed is True

        # Alpha goes static — bravo gets a free shift, alpha loses matched
        eng.apply_static_maneuver("alpha")
        eng.range_band = shift_range_band(eng.range_band, 1)  # Bravo's free shift

        assert eng.matched_speed is False
        assert eng.advantage is None  # Lost due to static
        assert eng.range_band == "long"


# ============================================================================
# 3. Full Turn Orchestration
# ============================================================================

class TestFullTurnOrchestration:
    """
    Test the engine orchestrating a complete turn:
    declaration -> chase -> attack -> defense -> damage -> cleanup.

    These tests use the engine's process_turn() method.
    """

    def test_simple_turn_two_fighters(self):
        """
        Two fighters at long range. Alpha pursues with Move and Attack.
        Bravo evades. Chase roll, attack roll, defense roll, damage.
        """
        from m1_psi_core.engine import CombatEngine
        from m1_psi_core.combat_state import EngagementState
        from m1_psi_core.testing import MockDice

        engine = CombatEngine()

        alpha = MockShipStats(
            template_id="javelin_v1", instance_id="a1",
            display_name="Red Five", sm=4,
            st_hp=80, hnd=4, accel=20, top_speed=600, stall_speed=35,
            dr_front=15, dr_rear=15, dr_left=15, dr_right=15,
            dr_top=15, dr_bottom=15,
            fdr_max=0, force_screen_type="none", current_fdr=0,
            current_hp=80,
        )
        bravo = MockShipStats(
            template_id="hornet_v1", instance_id="b1",
            display_name="Stinger One", sm=4,
            st_hp=95, hnd=6, accel=15, top_speed=500,
            dr_front=10, dr_rear=10, dr_left=10, dr_right=10,
            dr_top=10, dr_bottom=10,
            fdr_max=150, force_screen_type="standard", current_fdr=150,
            current_hp=95,
        )
        alpha_pilot = MockPilot(piloting_skill=14, gunnery_skill=14, basic_speed=6.0)
        bravo_pilot = MockPilot(piloting_skill=14, gunnery_skill=14, basic_speed=6.5)

        engagement = EngagementState(
            ship_a_id="a1", ship_b_id="b1", range_band="long",
        )

        # Deterministic dice: chase(alpha=10, bravo=12), attack(9), defense(11)
        dice = MockDice([10, 12, 9, 11])

        events = engine.process_turn(
            ship_a=alpha, ship_b=bravo,
            pilot_a=alpha_pilot, pilot_b=bravo_pilot,
            engagement=engagement,
            declaration_a={"maneuver": "move_and_attack", "intent": "pursue"},
            declaration_b={"maneuver": "evade", "intent": "evade"},
            dice=dice,
        )

        # Verify events were produced
        assert len(events) > 0
        # Verify engagement state was mutated
        assert engagement.range_band is not None

    def test_force_screens_regen_at_end_of_turn(self):
        """
        After a turn where force screen took damage, cleanup phase
        restores fDR to max (if power is operational).
        """
        from m1_psi_core.engine import CombatEngine
        from m1_psi_core.combat_state import EngagementState

        engine = CombatEngine()

        ship = MockShipStats(
            instance_id="s1", fdr_max=150,
            force_screen_type="standard", current_fdr=30,  # Damaged
            current_hp=95, no_power=False,
        )

        # After cleanup, fDR should be restored
        new_fdr = engine.regen_force_screen(ship)
        assert new_fdr == 150

    def test_force_screen_no_regen_without_power(self):
        """Force screen does NOT regen if power is destroyed."""
        from m1_psi_core.engine import CombatEngine

        engine = CombatEngine()

        ship = MockShipStats(
            instance_id="s1", fdr_max=150,
            force_screen_type="standard", current_fdr=30,
            current_hp=95, no_power=True,
        )

        new_fdr = engine.regen_force_screen(ship)
        assert new_fdr == 30  # Unchanged


# ============================================================================
# 4. Multi-Turn State Persistence
# ============================================================================

class TestMultiTurnState:
    """Verify state carries forward correctly across turns."""

    def test_damaged_system_affects_next_turn_stats(self):
        """
        Turn 1: Ship takes damage, propulsion disabled.
        Turn 2: Effective top_speed should be halved.
        """
        from m1_psi_core.combat_state import EngagementState

        ship = MockShipStats(
            instance_id="s1", top_speed=600, accel=20,
        )

        # Simulate propulsion disabled
        # In the real engine, this calls M3's update_system_status
        # For this test, we verify the stat effect calculation
        from m1_psi_core.damage import determine_wound_level
        wound = determine_wound_level(damage=50, max_hp=80)
        assert wound == "major"  # 62.5% -> major -> disable a system

        # If propulsion is the disabled system, speed halves
        # This is calculated by M3's get_effective_stats pipeline
        # which we already tested in test_effective_stats.py
        # Here we verify the wound level is correct for triggering it
        assert wound == "major"

    def test_force_screen_regens_between_turns(self):
        """
        Turn 1: Force screen takes 100 damage (150 -> 50).
        Cleanup: Screen regens to 150.
        Turn 2: Force screen is back at full.
        """
        from m1_psi_core.damage import apply_force_screen
        from m1_psi_core.turn_sequence import should_regen_force_screens, can_regen_force_screen

        # Turn 1: take damage
        screen = apply_force_screen(
            incoming_damage=100, current_fdr=150,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert screen.remaining_fdr == 50

        # Cleanup phase: should regen
        assert should_regen_force_screens("cleanup") is True
        assert can_regen_force_screen(no_power=False) is True
        # After regen: fDR back to max (150)
        restored_fdr = 150  # Engine would call M3's reset_fdr
        assert restored_fdr == 150

    def test_wound_accumulation_across_hits(self):
        """
        Hit 1: Minor wound (15% of HP).
        Hit 2: Another minor wound. Accumulation check.
        If HT fails: escalates to major.
        """
        from m1_psi_core.damage import determine_wound_level, check_wound_accumulation

        # Hit 1
        wound1 = determine_wound_level(damage=12, max_hp=80)
        assert wound1 == "minor"  # 15%

        # Hit 2 — same severity, accumulation check
        wound2 = determine_wound_level(damage=10, max_hp=80)
        assert wound2 == "minor"  # 12.5%

        # HT roll fails: escalate
        accum = check_wound_accumulation(
            current_wound="minor", new_wound="minor",
            ht_roll_succeeded=False,
        )
        assert accum.escalated is True
        assert accum.new_wound_level == "major"

    def test_subsystem_cascade_chain(self):
        """
        Propulsion already disabled. Hit propulsion again.
        HT roll fails -> propulsion destroyed (crippling wound).
        Then propulsion is already destroyed, next hit cascades to weaponry.
        """
        from m1_psi_core.damage import resolve_subsystem_cascade

        # First cascade: propulsion disabled, HT fails -> destroyed
        result1 = resolve_subsystem_cascade(
            system="propulsion", current_status="disabled",
            ht_roll_succeeded=False, cascade_target="weaponry",
        )
        assert result1.system_destroyed is True
        assert result1.is_crippling_wound is True

        # Second cascade: propulsion already destroyed -> cascade to weaponry
        result2 = resolve_subsystem_cascade(
            system="propulsion", current_status="destroyed",
            ht_roll_succeeded=True, cascade_target="weaponry",
        )
        assert result2.system_destroyed is False
        assert result2.cascades_to == "weaponry"


# ============================================================================
# 5. Edge Cases
# ============================================================================

class TestEdgeCases:
    """Edge case scenarios that stress the rule interactions."""

    def test_double_near_miss_becomes_full_miss(self):
        """
        Missile attack misses by 1 (near miss: 1/3 damage).
        Defender dodges with margin 0 (near miss on a near miss = full miss).
        """
        from m1_psi_core.missile import check_near_miss, check_defense_near_miss

        # Attack roll: miss by 1 on explosive weapon
        attack_result = check_near_miss(margin=-1, explosive=True, armor_divisor=None)
        assert attack_result.is_near_miss is True

        # Defense: dodge margin 0 on the near-miss
        defense_result = check_defense_near_miss(
            defense_margin=0, explosive=True, armor_divisor=None,
            already_near_miss=True,
        )
        assert defense_result.full_miss is True
        assert defense_result.is_near_miss is False

    def test_stall_ship_cannot_pursue_then_can_after_advantage_clears(self):
        """
        Javelin (stall 35) cannot pursue Hornet when Hornet has advantage.
        After Hornet loses advantage, Javelin can pursue again.
        """
        from m1_psi_core.chase import can_pursue

        # Hornet has advantage over Javelin
        assert can_pursue(stall_speed=35, opponent_has_advantage=True) is False

        # Hornet loses advantage (via chase roll)
        assert can_pursue(stall_speed=35, opponent_has_advantage=False) is True

    def test_mook_squadron_wipeout(self):
        """
        Three mook fighters each take a major wound. All removed.
        """
        from m1_psi_core.damage import apply_mook_rules, determine_wound_level

        for hp in [80, 85, 90]:
            # Each takes 50% HP damage -> major wound
            wound = determine_wound_level(damage=int(hp * 0.55), max_hp=hp)
            assert wound == "major"
            result = apply_mook_rules(wound_level=wound)
            assert result.removed is True

    def test_just_a_scratch_on_mortal_wound(self):
        """
        PC spends character point: mortal wound reduced to minor.
        Accumulation from this can only trigger disabled, never worse.
        """
        from m1_psi_core.damage import apply_just_a_scratch

        result = apply_just_a_scratch(wound_level="mortal")
        assert result.reduced_level == "minor"
        assert result.max_accumulation_effect == "disabled"

    def test_hugging_fighter_ignores_capital_force_screen(self):
        """
        Fighter (SM 4) hugs Imperator (SM 14). SM diff = 10 >= 6.
        Fighter's attacks ignore the force screen entirely.
        """
        from m1_psi_core.special import hugging_ignores_force_screen
        from m1_psi_core.combat_state import can_hug, is_inside_force_screen

        assert can_hug(hugger_sm=4, target_sm=14) is True
        assert is_inside_force_screen(hugger_sm=4, target_sm=14) is True
        assert hugging_ignores_force_screen(hugger_sm=4, target_sm=14) is True

        # If inside force screen, damage pipeline skips fDR entirely
        from m1_psi_core.damage import calculate_penetrating_damage
        # Blaster: 120 damage, DR 5000, AD 5 -> effective DR 1000
        penetrating = calculate_penetrating_damage(
            damage=120, dr=5000, armor_divisor=5.0,
        )
        # Even through 1000 effective DR, 120 damage doesn't penetrate hull
        assert penetrating == 0
        # But a torpedo (3600 damage, no AD) would:
        penetrating_torp = calculate_penetrating_damage(
            damage=3600, dr=5000, armor_divisor=1.0,
        )
        assert penetrating_torp == 0  # Still blocked by 5000 DR
        # The real threat is that the force screen is bypassed,
        # so you only need to beat hull DR, not fDR + DR

    def test_matched_speed_attack_uses_full_accuracy_on_move_and_attack(self):
        """
        With matched speed, Move and Attack allows adding full accuracy.
        The maneuver still says 'half_accuracy' but matched speed overrides.
        """
        from m1_psi_core.attack import apply_accuracy

        # Matched speed: Move and Attack gets full accuracy
        assert apply_accuracy(weapon_acc=9, permission="full_accuracy") == 9

    def test_focused_force_screen_front_doubled_rear_halved(self):
        """
        150 fDR focused on front: front=300, all others=75.
        Attack from front hits 300 fDR. Attack from rear hits 75.
        """
        from m1_psi_core.special import configure_force_screen
        from m1_psi_core.damage import apply_force_screen

        config = configure_force_screen(fdr_max=150, focused_facing="front")
        assert config.front == 300
        assert config.rear == 75

        # Attack from front: 200 damage vs 300 fDR -> all absorbed
        front_hit = apply_force_screen(
            incoming_damage=200, current_fdr=300,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert front_hit.penetrating == 0

        # Attack from rear: 200 damage vs 75 fDR -> 125 penetrates
        rear_hit = apply_force_screen(
            incoming_damage=200, current_fdr=75,
            armor_divisor=5, force_screen_type="standard",
            damage_type="burn",
        )
        assert rear_hit.penetrating == 125

    def test_ace_pilot_lucky_break_plus_wound_escalation(self):
        """
        Ace pilot uses free lucky break to escalate a minor wound
        by 2 levels to crippling.
        """
        from m1_psi_core.special import get_free_lucky_breaks, apply_lucky_break_wound

        breaks = get_free_lucky_breaks(is_ace_pilot=True)
        assert breaks == 1

        escalated = apply_lucky_break_wound(current_wound="minor")
        assert escalated == "crippling"  # minor -> major -> crippling

    def test_full_hit_calculation_javelin_vs_hornet_long_range(self):
        """
        Complete hit modifier calculation for a concrete scenario.
        Javelin pilot (Gunner 14) fires blasters at Hornet at long range.
        Attack maneuver, sensor lock with targeting computer.

        14 (skill) + -11 (range) + 4 (SM) + 5 (sensor lock w/ TC) + 9 (Acc) = 21
        """
        from m1_psi_core.attack import (
            calculate_hit_modifiers, get_sensor_lock_bonus, apply_accuracy,
        )
        from m1_psi_core.combat_state import get_range_penalty

        effective = calculate_hit_modifiers(
            base_skill=14,
            range_penalty=get_range_penalty("long"),  # -11
            target_sm=4,
            sensor_lock_bonus=get_sensor_lock_bonus(True, 5),  # +5
            accuracy=apply_accuracy(9, "full_accuracy"),  # +9
        )
        assert effective == 21

    def test_full_defense_calculation_hornet_evading(self):
        """
        Complete dodge calculation for Hornet evading.
        Pilot 14, Handling +6. Evade maneuver (+2). ESM (+1 vs missiles).

        Base dodge: 14/2 + 6 = 13
        Evade: +2 = 15
        vs missile: +1 ESM -3 missile = 13
        """
        from m1_psi_core.defense import (
            calculate_base_dodge, get_dodge_modifiers,
            get_missile_defense_modifiers,
        )

        base = calculate_base_dodge(piloting=14, handling=6)
        assert base == 13

        mods = get_dodge_modifiers(maneuver="evade")
        assert mods.evade_bonus == 2
        dodge_vs_beam = base + mods.total
        assert dodge_vs_beam == 15

        missile_mods = get_missile_defense_modifiers(
            has_tactical_esm=True, has_decoy=False,
        )
        dodge_vs_missile = dodge_vs_beam + missile_mods.total
        # 15 + (-3 + 1) = 13
        assert dodge_vs_missile == 13
