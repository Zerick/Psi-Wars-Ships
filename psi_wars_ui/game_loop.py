"""
Main game loop for the terminal UI.

Drives the five-phase turn sequence through the session manager,
collects player/NPC declarations, resolves combat, displays results,
and handles hotkeys.
"""
from __future__ import annotations

from m1_psi_core.session import GameSession
from m1_psi_core.dice import DiceRoller, check_success, resolve_quick_contest
from m1_psi_core.combat_state import get_range_penalty, shift_range_band
from m1_psi_core.chase import resolve_chase_outcome
from m1_psi_core.maneuvers import MANEUVER_CATALOG, get_attack_permission, validate_maneuver
from m1_psi_core.attack import (
    calculate_hit_modifiers, get_sensor_lock_bonus, apply_accuracy,
    get_relative_size_penalty, can_weapon_fire, can_ship_attack,
    get_sm_bonus,
)
from m1_psi_core.defense import (
    calculate_base_dodge, get_dodge_modifiers, is_high_g_available,
    get_missile_defense_modifiers, MISSILE_DODGE_PENALTY,
)
from m1_psi_core.damage import (
    apply_force_screen, calculate_penetrating_damage,
    determine_wound_level, get_subsystem_hit,
)
from m1_psi_core.special import classify_ship

from psi_wars_ui.display import (
    Color, bold, dim, colorize, clear_screen, colored_faction, event_color,
)
from psi_wars_ui.renderer import ScreenRenderer
from psi_wars_ui.input_handler import (
    menu_choice, yes_no, get_input, pause, pass_to_player,
    show_help, show_ship_inspection,
)


class GameLoop:
    """
    The main combat game loop.

    Manages the turn cycle: declaration → chase → attack → damage → cleanup.
    """

    def __init__(self, session: GameSession):
        self.session = session
        self.renderer = ScreenRenderer()
        self.dice = DiceRoller()
        self._running = True

    def run(self) -> None:
        """Run the game until combat ends or player quits."""
        self.renderer.combat_log.add(
            "═══ COMBAT BEGINS ═══", "turn"
        )

        while self._running:
            # Check combat end
            if self.session.check_combat_end():
                self._display()
                self.renderer.combat_log.add(
                    "═══ COMBAT OVER — All enemies eliminated! ═══", "turn"
                )
                self._display()
                if not yes_no("Continue?", default=False):
                    break
                continue

            # --- Declaration Phase ---
            declarations = self._declaration_phase()
            if not self._running:
                break

            # --- Chase Resolution Phase ---
            self._chase_phase(declarations)

            # --- Attack Phase ---
            self._attack_phase(declarations)

            # --- Cleanup Phase ---
            self.session.regen_all_force_screens()
            self.renderer.combat_log.add(
                f"── End of Turn {self.session.current_turn} ── Force screens regenerated.",
                "force_screen",
            )
            self.session.advance_turn()

        print(f"\n {bold('Thanks for playing!')}\n")

    def _display(self, prompt: str = "", extra: str = "") -> None:
        """Redraw the full screen."""
        clear_screen()
        screen = self.renderer.render(self.session, prompt_text=prompt, extra_info=extra)
        print(screen)

    # -------------------------------------------------------------------
    # Declaration Phase
    # -------------------------------------------------------------------

    def _declaration_phase(self) -> dict[str, dict]:
        """
        Collect maneuver declarations from all ships.

        Human ships: menu prompt.
        NPC ships: AI decides.
        Returns dict mapping ship_id -> declaration dict.
        """
        declarations = {}
        order = self.session.get_declaration_order()
        human_count = sum(
            1 for sid in order
            if self.session.get_control_mode(sid) == "human"
            and not getattr(self.session.get_ship(sid), "is_destroyed", False)
        )
        previous_was_human = False

        self.renderer.combat_log.add(
            f"═══ TURN {self.session.current_turn} — Declaration Phase ═══",
            "turn",
        )

        for ship_id in order:
            ship = self.session.get_ship(ship_id)
            if ship is None or getattr(ship, "is_destroyed", False):
                continue

            control = self.session.get_control_mode(ship_id)

            if control == "npc":
                # AI decides
                decl = self.session.get_npc_declaration(ship_id)
                declarations[ship_id] = decl
                self.renderer.combat_log.add(
                    f"  {ship.display_name} (NPC): {decl['maneuver']} / {decl['intent']}",
                    "npc_reasoning",
                )
                if decl.get("reasoning"):
                    self.renderer.combat_log.add(
                        f"    → {decl['reasoning']}", "npc_reasoning",
                    )
            else:
                # Human player
                if previous_was_human and human_count > 1:
                    pass_to_player(ship.display_name)

                decl = self._get_human_declaration(ship_id)
                if decl is None:
                    self._running = False
                    return declarations
                declarations[ship_id] = decl
                previous_was_human = True

        return declarations

    def _get_human_declaration(self, ship_id: str) -> dict | None:
        """
        Prompt a human player for their maneuver declaration.

        Returns a declaration dict or None if the player wants to quit.
        """
        ship = self.session.get_ship(ship_id)
        pilot = self.session.get_pilot(ship_id)
        display_name = getattr(ship, "display_name", ship_id)

        while True:
            self._display(
                prompt=f"{bold(display_name)}: Choose maneuver  [H]elp [I]nspect [Q]uit"
            )

            # Build maneuver menu with validation
            stall = getattr(ship, "stall_speed", 0)
            engagements = self.session.get_engagements_for_ship(ship_id)
            opponent_has_adv = False
            if engagements:
                eng = engagements[0]
                opponent_id = eng.ship_b_id if eng.ship_a_id == ship_id else eng.ship_a_id
                opponent_has_adv = eng.advantage == opponent_id

            available = []
            maneuver_keys = []
            for key, m in MANEUVER_CATALOG.items():
                errors = validate_maneuver(
                    maneuver=key, stall_speed=stall,
                    opponent_has_advantage=opponent_has_adv,
                    at_collision_range=False,  # TODO: check actual collision range
                    is_stopped=False,
                )
                if errors:
                    available.append(dim(f"{m.name} (unavailable: {errors[0]})"))
                else:
                    available.append(m.name)
                maneuver_keys.append(key)

            choice = menu_choice("Maneuvers", available, prompt="Maneuver", allow_cancel=False)

            # Handle hotkeys
            if choice is None:
                raw = get_input(" Command: ").lower()
                if raw == "h":
                    show_help()
                    continue
                elif raw == "i":
                    show_ship_inspection(ship, pilot)
                    continue
                elif raw == "q":
                    if yes_no("Quit the game?", default=False):
                        return None
                    continue
                continue

            chosen_key = maneuver_keys[choice]

            # Validate
            errors = validate_maneuver(
                maneuver=chosen_key, stall_speed=stall,
                opponent_has_advantage=opponent_has_adv,
            )
            if errors:
                print(colorize(f"  Cannot use that maneuver: {errors[0]}", Color.RED))
                pause()
                continue

            # Intent
            m_def = MANEUVER_CATALOG[chosen_key]
            if m_def.facing == "rear":
                intent = "evade"
            elif m_def.facing == "front":
                intent = "pursue"
            else:
                intent_options = ["Pursue (close distance)", "Evade (increase distance)"]
                intent_choice = menu_choice("Intent", intent_options, allow_cancel=False)
                intent = "pursue" if intent_choice == 0 else "evade"

            self.renderer.combat_log.add(
                f"  {display_name}: {MANEUVER_CATALOG[chosen_key].name} / {intent}",
                "info",
            )

            return {"maneuver": chosen_key, "intent": intent}

    # -------------------------------------------------------------------
    # Chase Phase
    # -------------------------------------------------------------------

    def _chase_phase(self, declarations: dict[str, dict]) -> None:
        """Resolve chase rolls for all engagements."""
        self.renderer.combat_log.add("── Chase Resolution ──", "chase")

        seen = set()
        for ship_id in self.session.get_all_ship_ids():
            for eng in self.session.get_engagements_for_ship(ship_id):
                key = (min(eng.ship_a_id, eng.ship_b_id),
                       max(eng.ship_a_id, eng.ship_b_id))
                if key in seen:
                    continue
                seen.add(key)

                ship_a = self.session.get_ship(eng.ship_a_id)
                ship_b = self.session.get_ship(eng.ship_b_id)
                pilot_a = self.session.get_pilot(eng.ship_a_id)
                pilot_b = self.session.get_pilot(eng.ship_b_id)

                if (not ship_a or not ship_b or
                    getattr(ship_a, "is_destroyed", False) or
                    getattr(ship_b, "is_destroyed", False)):
                    continue

                # Chase skill = Piloting + Handling + maneuver modifier
                skill_a = getattr(pilot_a, "piloting_skill", 12) + getattr(ship_a, "hnd", 0)
                skill_b = getattr(pilot_b, "piloting_skill", 12) + getattr(ship_b, "hnd", 0)

                decl_a = declarations.get(eng.ship_a_id, {})
                decl_b = declarations.get(eng.ship_b_id, {})

                m_a = MANEUVER_CATALOG.get(decl_a.get("maneuver", "move"))
                m_b = MANEUVER_CATALOG.get(decl_b.get("maneuver", "move"))
                if m_a:
                    skill_a += m_a.chase_modifier
                if m_b:
                    skill_b += m_b.chase_modifier

                roll_a = self.dice.roll_3d6()
                roll_b = self.dice.roll_3d6()

                contest = resolve_quick_contest(skill_a, roll_a, skill_b, roll_b)

                name_a = getattr(ship_a, "display_name", eng.ship_a_id)
                name_b = getattr(ship_b, "display_name", eng.ship_b_id)

                self.renderer.combat_log.add(
                    f"  {name_a} (skill {skill_a}) rolled {roll_a} vs "
                    f"{name_b} (skill {skill_b}) rolled {roll_b}",
                    "chase",
                )

                if contest.winner:
                    winner_id = eng.ship_a_id if contest.winner == "a" else eng.ship_b_id
                    winner_name = name_a if contest.winner == "a" else name_b
                    winner_intent = (decl_a if contest.winner == "a" else decl_b).get("intent", "pursue")
                    winner_had_adv = eng.advantage == winner_id
                    loser_id = eng.ship_b_id if contest.winner == "a" else eng.ship_a_id
                    loser_had_adv = eng.advantage == loser_id

                    outcome = resolve_chase_outcome(
                        margin=contest.margin_of_victory,
                        winner_intent=winner_intent,
                        winner_had_advantage=winner_had_adv,
                        loser_had_advantage=loser_had_adv,
                    )

                    self.renderer.combat_log.add(
                        f"  → {winner_name} wins by {contest.margin_of_victory}!",
                        "chase",
                    )

                    # Apply outcome
                    if outcome.opponent_loses_advantage and loser_had_adv:
                        eng.clear_advantage()
                        self.renderer.combat_log.add(
                            f"    {winner_name} breaks opponent's advantage!", "chase",
                        )

                    # Auto-choose for NPC, prompt for human
                    if outcome.can_gain_advantage or outcome.can_match_speed or outcome.can_shift_range > 0:
                        self._resolve_chase_choice(
                            winner_id, eng, outcome, winner_intent, winner_name,
                        )
                else:
                    self.renderer.combat_log.add("  → Tie! No change.", "chase")

    def _resolve_chase_choice(
        self, winner_id, eng, outcome, intent, winner_name,
    ) -> None:
        """Let the winner choose their chase outcome."""
        control = self.session.get_control_mode(winner_id)

        options = []
        option_keys = []

        if outcome.can_gain_advantage and eng.advantage != winner_id:
            options.append("Gain Advantage")
            option_keys.append("advantage")
        if outcome.can_match_speed:
            options.append("Match Speed")
            option_keys.append("match_speed")
        if outcome.can_shift_range > 0:
            direction = "closer" if intent == "pursue" else "farther"
            options.append(f"Shift range 1 band {direction}")
            option_keys.append("shift")
            if outcome.can_shift_range >= 2:
                options.append(f"Shift range 2 bands {direction}")
                option_keys.append("shift2")

        if not options:
            return

        if control == "npc":
            # AI chooses
            from m1_psi_core.npc_ai import choose_chase_outcome
            ai_choice = choose_chase_outcome(
                can_gain_advantage=outcome.can_gain_advantage,
                can_match_speed=outcome.can_match_speed,
                can_shift_range=outcome.can_shift_range,
                currently_advantaged=(eng.advantage == winner_id),
                current_range=eng.range_band,
                intent=intent,
            )
            if ai_choice == "advantage":
                eng.set_advantage(winner_id)
                self.renderer.combat_log.add(
                    f"    {winner_name} gains ADVANTAGE!", "chase",
                )
            elif ai_choice == "match_speed":
                eng.set_matched_speed(winner_id)
                self.renderer.combat_log.add(
                    f"    {winner_name} MATCHES SPEED!", "chase",
                )
            elif ai_choice in ("shift_close", "shift_far"):
                shift = -1 if ai_choice == "shift_close" else 1
                eng.range_band = shift_range_band(eng.range_band, shift)
                self.renderer.combat_log.add(
                    f"    Range shifts to {eng.range_band.upper()}", "chase",
                )
        else:
            # Human chooses
            self._display()
            choice = menu_choice(f"{winner_name}'s Chase Victory", options, allow_cancel=False)
            if choice is not None:
                key = option_keys[choice]
                if key == "advantage":
                    eng.set_advantage(winner_id)
                    self.renderer.combat_log.add(
                        f"    {winner_name} gains ADVANTAGE!", "chase",
                    )
                elif key == "match_speed":
                    eng.set_matched_speed(winner_id)
                    self.renderer.combat_log.add(
                        f"    {winner_name} MATCHES SPEED!", "chase",
                    )
                elif key == "shift":
                    shift = -1 if intent == "pursue" else 1
                    eng.range_band = shift_range_band(eng.range_band, shift)
                    self.renderer.combat_log.add(
                        f"    Range shifts to {eng.range_band.upper()}", "chase",
                    )
                elif key == "shift2":
                    shift = -2 if intent == "pursue" else 2
                    eng.range_band = shift_range_band(eng.range_band, shift)
                    self.renderer.combat_log.add(
                        f"    Range shifts to {eng.range_band.upper()}", "chase",
                    )

    # -------------------------------------------------------------------
    # Attack Phase
    # -------------------------------------------------------------------

    def _attack_phase(self, declarations: dict[str, dict]) -> None:
        """Resolve attacks for all ships that can attack this turn."""
        self.renderer.combat_log.add("── Attack Phase ──", "attack")

        for ship_id in self.session.get_all_ship_ids():
            ship = self.session.get_ship(ship_id)
            pilot = self.session.get_pilot(ship_id)
            if not ship or getattr(ship, "is_destroyed", False):
                continue

            decl = declarations.get(ship_id, {})
            maneuver = decl.get("maneuver", "move")

            # Check if this ship can attack
            attack_perm = get_attack_permission(
                maneuver,
                is_ace_pilot=getattr(pilot, "is_ace_pilot", False),
                is_gunslinger=getattr(pilot, "is_gunslinger", False),
            )
            if attack_perm == "none":
                continue

            if not can_ship_attack(
                no_power=getattr(ship, "no_power", False),
                weapons_destroyed=False,
            ):
                continue

            # Find target
            engagements = self.session.get_engagements_for_ship(ship_id)
            if not engagements:
                continue

            eng = engagements[0]
            target_id = eng.ship_b_id if eng.ship_a_id == ship_id else eng.ship_a_id
            target = self.session.get_ship(target_id)
            target_pilot = self.session.get_pilot(target_id)

            if not target or getattr(target, "is_destroyed", False):
                continue

            self._resolve_attack(
                ship_id, ship, pilot,
                target_id, target, target_pilot,
                eng, attack_perm, declarations,
            )

    def _resolve_attack(
        self, attacker_id, attacker, pilot,
        target_id, target, target_pilot,
        engagement, attack_perm, declarations,
    ) -> None:
        """Resolve a single attack: hit roll, defense, damage."""
        a_name = getattr(attacker, "display_name", attacker_id)
        t_name = getattr(target, "display_name", target_id)
        is_advantaged = engagement.advantage == attacker_id

        # --- Hit roll ---
        base_skill = getattr(pilot, "gunnery_skill", 12)
        range_pen = get_range_penalty(engagement.range_band)
        sm_bonus = get_sm_bonus(getattr(target, "sm", 4))
        sensor_lock = get_sensor_lock_bonus(True, getattr(attacker, "targeting_bonus", 5))
        acc = apply_accuracy(9, attack_perm)  # Default weapon acc

        # Relative size penalty
        a_class = classify_ship(getattr(attacker, "sm", 4), 15)
        t_class = classify_ship(getattr(target, "sm", 4), 15)
        rel_size = get_relative_size_penalty(a_class, t_class)

        effective_skill = (base_skill + range_pen + sm_bonus + sensor_lock
                           + acc + rel_size)

        roll = self.dice.roll_3d6()
        result = check_success(effective_skill, roll)

        # Log the attack with full breakdown
        self.renderer.combat_log.add(
            f"  {a_name} fires at {t_name}", "attack",
        )
        mods_str = (
            f"    Gunner({base_skill}) + Range({range_pen:+d}) + SM({sm_bonus:+d}) "
            f"+ Lock({sensor_lock:+d}) + Acc({acc:+d})"
        )
        if rel_size != 0:
            mods_str += f" + RelSize({rel_size:+d})"
        mods_str += f" = {effective_skill}"
        self.renderer.combat_log.add(mods_str, "attack")

        if result.critical:
            crit_str = colorize(
                f"    Rolled {roll} → {'CRITICAL HIT!' if result.success else 'CRITICAL MISS!'}",
                event_color("critical_success" if result.success else "critical_failure"),
            )
            self.renderer.combat_log.add(crit_str, "attack")
        else:
            hit_miss = "HIT" if result.success else "MISS"
            color = Color.BRIGHT_GREEN if result.success else Color.RED
            self.renderer.combat_log.add(
                f"    Rolled {roll} → {colorize(hit_miss, color)} (margin {result.margin:+d})",
                "attack",
            )

        if not result.success:
            return

        # --- Defense roll ---
        target_maneuver = declarations.get(target_id, {}).get("maneuver", "move")
        base_dodge = calculate_base_dodge(
            getattr(target_pilot, "piloting_skill", 12),
            getattr(target, "hnd", 0),
        )
        dodge_mods = get_dodge_modifiers(maneuver=target_maneuver)
        effective_dodge = base_dodge + dodge_mods.total

        dodge_roll = self.dice.roll_3d6()
        dodge_result = check_success(effective_dodge, dodge_roll, is_defense=True)

        mods_parts = [f"Pilot({getattr(target_pilot, 'piloting_skill', 12)})//2 + Hnd({getattr(target, 'hnd', 0):+d})"]
        if dodge_mods.evade_bonus:
            mods_parts.append(f"Evade(+{dodge_mods.evade_bonus})")
        if dodge_mods.advantage_escaping_bonus:
            mods_parts.append(f"AdvEsc(+{dodge_mods.advantage_escaping_bonus})")
        if dodge_mods.ace_stunt_bonus:
            mods_parts.append(f"AceStunt(+{dodge_mods.ace_stunt_bonus})")

        self.renderer.combat_log.add(
            f"  {t_name} attempts dodge: {' + '.join(mods_parts)} = {effective_dodge}",
            "defense",
        )

        if dodge_result.success:
            self.renderer.combat_log.add(
                f"    Rolled {dodge_roll} → {colorize('DODGED', Color.BRIGHT_GREEN)} "
                f"(margin {dodge_result.margin:+d})",
                "defense",
            )
            return
        else:
            self.renderer.combat_log.add(
                f"    Rolled {dodge_roll} → {colorize('HIT!', Color.RED)} "
                f"(margin {dodge_result.margin:+d})",
                "defense",
            )

        # --- Damage ---
        # Roll damage (simplified: use a representative weapon)
        raw_damage = self.dice.roll_nd6(6) * 5  # Default: 6d×5

        self._resolve_damage(target_id, target, raw_damage, engagement, a_name)

    def _resolve_damage(
        self, target_id, target, raw_damage, engagement, attacker_name,
    ) -> None:
        """Resolve damage through the full pipeline."""
        t_name = getattr(target, "display_name", target_id)
        armor_divisor = 5.0  # Default for fighter blasters

        # Force screen
        screen_result = apply_force_screen(
            incoming_damage=raw_damage,
            current_fdr=getattr(target, "current_fdr", 0),
            armor_divisor=armor_divisor,
            force_screen_type=getattr(target, "force_screen_type", "none"),
            damage_type="burn",
        )

        target.current_fdr = screen_result.remaining_fdr

        if screen_result.absorbed > 0:
            self.renderer.combat_log.add(
                f"    Force screen absorbs {screen_result.absorbed} "
                f"(fDR: {screen_result.remaining_fdr} remaining)",
                "force_screen",
            )

        if screen_result.penetrating <= 0:
            self.renderer.combat_log.add(
                f"    {colorize('No penetration', Color.BLUE)} — "
                f"all damage absorbed by force screen.",
                "force_screen",
            )
            return

        # Hull armor
        dr = getattr(target, "dr_front", 10)  # Simplified: use front DR
        penetrating = calculate_penetrating_damage(
            screen_result.penetrating, dr, armor_divisor,
        )

        eff_dr = int(dr / armor_divisor) if armor_divisor > 0 else dr
        self.renderer.combat_log.add(
            f"    {raw_damage} raw damage → {screen_result.penetrating} past screen "
            f"→ DR {dr} (eff {eff_dr} after AD {armor_divisor}) "
            f"→ {penetrating} penetrating",
            "damage",
        )

        if penetrating <= 0:
            self.renderer.combat_log.add(
                f"    {colorize('Stopped by armor', Color.BLUE)}.", "damage",
            )
            return

        # Wound determination
        max_hp = getattr(target, "st_hp", 80)
        wound = determine_wound_level(penetrating, max_hp)
        pct = (penetrating / max_hp) * 100

        target.current_hp = max(0, target.current_hp - penetrating)

        wound_color = event_color("critical_failure") if wound in ("crippling", "mortal", "lethal") else event_color("damage")

        self.renderer.combat_log.add(
            f"    {colorize(f'{wound.upper()} WOUND', wound_color)} "
            f"({penetrating} damage = {pct:.0f}% of {max_hp} HP)",
            "damage",
        )

        # Update wound level
        from m1_psi_core.damage import WOUND_SEVERITY
        cur_sev = WOUND_SEVERITY.get(getattr(target, "wound_level", "none"), 0)
        new_sev = WOUND_SEVERITY.get(wound, 0)
        if new_sev > cur_sev:
            target.wound_level = wound

        # Check destruction
        if wound == "lethal":
            target.is_destroyed = True
            self.renderer.combat_log.add(
                colorize(f"    ✘ {t_name} DESTROYED!", Color.BRIGHT_RED + Color.BOLD),
                "system_damage",
            )
        elif wound in ("major", "crippling", "mortal"):
            # Roll for subsystem damage
            sys_roll = self.dice.roll_3d6()
            system_hit, cascade = get_subsystem_hit(sys_roll)
            status = "disabled" if wound == "major" else "destroyed"
            self.renderer.combat_log.add(
                f"    Subsystem roll: {sys_roll} → {system_hit} {status}!",
                "system_damage",
            )

        # Mook check
        if getattr(target, "is_mook", False) and new_sev >= WOUND_SEVERITY.get("major", 3):
            target.is_destroyed = True
            self.renderer.combat_log.add(
                colorize(f"    ✘ {t_name} (mook) removed from combat!", Color.RED),
                "system_damage",
            )

        self._display()
