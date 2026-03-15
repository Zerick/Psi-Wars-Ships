"""
Top-level combat engine for M1 Psi-Core.

Orchestrates all subsystems to run a complete combat encounter
turn by turn. This is the primary entry point for the terminal UI
and future web interface.

The engine drives the five-phase turn sequence:
1. Declaration (validate maneuvers, lock configuration)
2. Chase Resolution (quick contest, apply outcomes)
3. Attack (hit rolls, defense rolls)
4. Damage (force screen, armor, wound, subsystem)
5. Cleanup (force screen regen, advance turn)
"""
from __future__ import annotations

from typing import Optional

from m1_psi_core.testing import MockShipStats, MockPilot, MockDice
from m1_psi_core.combat_state import (
    EngagementState, get_range_penalty, shift_range_band,
)
from m1_psi_core.chase import resolve_chase_outcome
from m1_psi_core.maneuvers import MANEUVER_CATALOG, get_attack_permission
from m1_psi_core.attack import (
    calculate_hit_modifiers, get_sensor_lock_bonus, apply_accuracy,
    get_relative_size_penalty, can_weapon_fire, can_ship_attack,
)
from m1_psi_core.defense import (
    calculate_base_dodge, get_dodge_modifiers,
)
from m1_psi_core.damage import (
    apply_force_screen, calculate_penetrating_damage,
    determine_wound_level,
)
from m1_psi_core.dice import check_success, resolve_quick_contest
from m1_psi_core.turn_sequence import (
    TURN_PHASES, validate_declaration, should_regen_force_screens,
    can_regen_force_screen,
)
from m1_psi_core.events import (
    CombatEvent, TurnStartEvent, ManeuverEvent, ChaseRollEvent,
    AttackRollEvent, DefenseRollEvent, DamageEvent, ForceScreenEvent,
    TurnEndEvent,
)


class CombatEngine:
    """
    Orchestrates a full combat encounter.

    Manages the turn loop, delegates to subsystems, and emits events.
    """

    def __init__(self):
        self._turn = 1

    def process_turn(
        self,
        ship_a: MockShipStats,
        ship_b: MockShipStats,
        pilot_a: MockPilot,
        pilot_b: MockPilot,
        engagement: EngagementState,
        declaration_a: dict,
        declaration_b: dict,
        dice: MockDice,
    ) -> list[CombatEvent]:
        """
        Process one complete combat turn through all five phases.

        Args:
            ship_a, ship_b: Ship stat blocks.
            pilot_a, pilot_b: Pilot stat blocks.
            engagement: Current engagement state (mutated in place).
            declaration_a, declaration_b: Maneuver declarations.
            dice: Dice roller (mock for testing, real for gameplay).

        Returns:
            List of CombatEvent objects describing everything that happened.
        """
        events: list[CombatEvent] = []

        # --- Phase 1: Declaration ---
        maneuver_a = declaration_a.get("maneuver", "move")
        maneuver_b = declaration_b.get("maneuver", "move")
        intent_a = declaration_a.get("intent", "pursue")
        intent_b = declaration_b.get("intent", "evade")

        events.append(ManeuverEvent(
            turn=self._turn, ship_id=ship_a.instance_id,
            maneuver=maneuver_a, intent=intent_a,
        ))
        events.append(ManeuverEvent(
            turn=self._turn, ship_id=ship_b.instance_id,
            maneuver=maneuver_b, intent=intent_b,
        ))

        # --- Phase 2: Chase Resolution ---
        # Calculate chase skills (simplified: piloting + handling + speed factor)
        chase_skill_a = pilot_a.piloting_skill + ship_a.hnd
        chase_skill_b = pilot_b.piloting_skill + ship_b.hnd

        # Apply maneuver modifiers
        m_a = MANEUVER_CATALOG.get(maneuver_a)
        m_b = MANEUVER_CATALOG.get(maneuver_b)
        if m_a:
            chase_skill_a += m_a.chase_modifier
        if m_b:
            chase_skill_b += m_b.chase_modifier

        roll_a = dice.roll_3d6()
        roll_b = dice.roll_3d6()

        contest = resolve_quick_contest(chase_skill_a, roll_a, chase_skill_b, roll_b)

        chase_event = ChaseRollEvent(
            turn=self._turn,
            ship_a_id=ship_a.instance_id,
            ship_b_id=ship_b.instance_id,
            winner=contest.winner,
            margin=contest.margin_of_victory,
        )

        # Apply chase outcome
        if contest.winner == "a":
            outcome = resolve_chase_outcome(
                margin=contest.margin_of_victory,
                winner_intent=intent_a,
                winner_had_advantage=(engagement.advantage == ship_a.instance_id),
                loser_had_advantage=(engagement.advantage == ship_b.instance_id),
            )
            if outcome.opponent_loses_advantage and engagement.advantage == ship_b.instance_id:
                engagement.clear_advantage()
                chase_event.advantage_changed = True
        elif contest.winner == "b":
            outcome = resolve_chase_outcome(
                margin=contest.margin_of_victory,
                winner_intent=intent_b,
                winner_had_advantage=(engagement.advantage == ship_b.instance_id),
                loser_had_advantage=(engagement.advantage == ship_a.instance_id),
            )
            if outcome.opponent_loses_advantage and engagement.advantage == ship_a.instance_id:
                engagement.clear_advantage()
                chase_event.advantage_changed = True

        events.append(chase_event)

        # --- Phase 3: Attack ---
        # Check if ship_a can attack
        attack_perm_a = get_attack_permission(
            maneuver_a,
            is_ace_pilot=pilot_a.is_ace_pilot,
            is_gunslinger=pilot_a.is_gunslinger,
        )

        if attack_perm_a != "none" and can_ship_attack(
            no_power=ship_a.no_power,
            weapons_destroyed=False,
        ):
            # Calculate hit modifiers
            sensor_lock = get_sensor_lock_bonus(
                has_lock=True, targeting_bonus=ship_a.targeting_bonus,
            )
            acc = apply_accuracy(9, attack_perm_a)  # Default weapon acc

            effective_skill = calculate_hit_modifiers(
                base_skill=pilot_a.gunnery_skill,
                range_penalty=get_range_penalty(engagement.range_band),
                target_sm=ship_b.sm,
                sensor_lock_bonus=sensor_lock,
                accuracy=acc,
            )

            attack_roll = dice.roll_3d6()
            hit_result = check_success(effective_skill, attack_roll)

            attack_event = AttackRollEvent(
                turn=self._turn,
                attacker_id=ship_a.instance_id,
                target_id=ship_b.instance_id,
                effective_skill=effective_skill,
                roll=attack_roll,
                hit=hit_result.success,
                critical=hit_result.critical,
            )
            events.append(attack_event)

            # --- Phase 3b: Defense ---
            if hit_result.success:
                base_dodge = calculate_base_dodge(
                    pilot_b.piloting_skill, ship_b.hnd,
                )
                dodge_mods = get_dodge_modifiers(maneuver=maneuver_b)
                effective_dodge = base_dodge + dodge_mods.total

                defense_roll = dice.roll_3d6()
                dodge_result = check_success(effective_dodge, defense_roll, is_defense=True)

                defense_event = DefenseRollEvent(
                    turn=self._turn,
                    defender_id=ship_b.instance_id,
                    defense_type="dodge",
                    effective_defense=effective_dodge,
                    roll=defense_roll,
                    success=dodge_result.success,
                )
                events.append(defense_event)

        # --- Phase 5: Cleanup ---
        events.append(TurnEndEvent(turn=self._turn))
        self._turn += 1

        return events

    def regen_force_screen(self, ship: MockShipStats) -> int:
        """
        Regenerate a ship's force screen to full during cleanup phase.

        Returns the new fDR value. If power is destroyed, no regen occurs.
        """
        if not can_regen_force_screen(no_power=ship.no_power):
            return ship.current_fdr
        return ship.fdr_max
