"""
Main game loop for the Psi-Wars terminal UI.

THIS FILE CONTAINS NO RULES LOGIC. It is a pure UI orchestrator that:
1. Collects declarations (human menus or NPC AI)
2. Calls engine pipeline functions (resolve_chase, resolve_attack, etc.)
3. Formats the structured results for display via ScreenBuffer
4. Applies state changes from pipeline results to ship objects

All combat math lives in m1_psi_core/engine.py. If you need to
change how combat works, edit engine.py. If you need to change
how combat is DISPLAYED, edit this file.

Modification guide:
    - To change what's shown in the combat log: modify _log_* methods
    - To change turn flow: modify run()
    - To change NPC pacing: modify NPC_TURN_DELAY_SECONDS
    - To add new player decisions: add to _declaration_phase or run
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from m1_psi_core.session import GameSession
from m1_psi_core.dice import DiceRoller
from m1_psi_core.combat_state import shift_range_band
from m1_psi_core.maneuvers import MANEUVER_CATALOG, validate_maneuver
from m1_psi_core.npc_ai import choose_chase_outcome as ai_choose_chase

# Pipeline functions — ALL combat resolution goes through these
from m1_psi_core.engine import (
    resolve_chase, resolve_attack, resolve_defense, resolve_damage,
    resolve_weapon, regen_force_screen,
    ChaseResult, AttackResult, DefenseResult, DamageResult, WeaponInfo,
)

from psi_wars_ui.display import Color, bold, dim, colorize, event_color
from psi_wars_ui.renderer import ScreenBuffer
from psi_wars_ui.input_handler import (
    menu_choice, yes_no, pass_to_player,
    show_help, show_ship_inspection, pause_with_buffer,
    HOTKEY_HELP, HOTKEY_INSPECT, HOTKEY_QUIT,
)

NPC_TURN_DELAY_SECONDS = 1.0


class GameLoop:
    """
    UI orchestrator. Collects input, calls the engine pipeline,
    displays results. Contains zero rules logic.
    """

    def __init__(self, session: GameSession, fixtures_dir: Optional[Path] = None):
        self.session = session
        self.buf = ScreenBuffer()
        self.dice = DiceRoller()
        self._running = True
        self._fixtures_dir = fixtures_dir

    def _refresh(self) -> None:
        """Update status bar and redraw."""
        self.buf.set_status(self.session)
        self.buf.clear_action()
        self.buf.draw()

    def _is_all_npc(self) -> bool:
        """Check if all surviving ships are NPC."""
        for sid in self.session.get_all_ship_ids():
            ship = self.session.get_ship(sid)
            if ship and not getattr(ship, "is_destroyed", False):
                if self.session.get_control_mode(sid) == "human":
                    return False
        return True

    # ===================================================================
    # Main loop
    # ===================================================================

    def run(self) -> None:
        """Run until combat ends or player quits."""
        self.buf.combat_log.add("═══ COMBAT BEGINS ═══", "turn")

        while self._running:
            self.buf.set_status(self.session)

            if self.session.check_combat_end():
                self.buf.combat_log.add("═══ COMBAT OVER ═══", "turn")
                self._refresh()
                if not yes_no("Continue?", default=False):
                    break
                continue

            # Phase 1: Declarations
            declarations = self._declaration_phase()
            if not self._running:
                break

            # Phase 2: Chase
            self._chase_phase(declarations)
            self.buf.set_status(self.session)
            self._refresh()

            # Phase 3+4: Attack + Damage
            self._attack_damage_phase(declarations)
            self.buf.set_status(self.session)
            self._refresh()

            # Pause for humans
            if not self._is_all_npc():
                pause_with_buffer(self.buf, "Press Enter for next turn...")

            # Phase 5: Cleanup
            self._cleanup_phase()

            if self._is_all_npc():
                self.buf.set_status(self.session)
                self._refresh()
                time.sleep(NPC_TURN_DELAY_SECONDS)

        self.buf.set_action([f" {bold('Thanks for playing!')}"])
        self.buf.draw()

    # ===================================================================
    # Phase 1: Declaration
    # ===================================================================

    def _declaration_phase(self) -> dict[str, dict]:
        """Collect declarations from all ships."""
        declarations: dict[str, dict] = {}
        order = self.session.get_declaration_order()
        human_ships = [
            s for s in order
            if self.session.get_control_mode(s) == "human"
            and not getattr(self.session.get_ship(s), "is_destroyed", False)
        ]
        prev_human = False

        self.buf.combat_log.add(f"═══ TURN {self.session.current_turn} ═══", "turn")

        for sid in order:
            ship = self.session.get_ship(sid)
            if not ship or getattr(ship, "is_destroyed", False):
                continue

            ctrl = self.session.get_control_mode(sid)
            name = getattr(ship, "display_name", sid)

            if ctrl == "npc":
                decl = self.session.get_npc_declaration(sid)
                declarations[sid] = decl
                self.buf.combat_log.add(
                    f"  {name} [NPC]: {decl['maneuver']} / {decl['intent']}",
                    "npc_reasoning")
                if decl.get("reasoning"):
                    self.buf.combat_log.add(f"    → {decl['reasoning']}", "npc_reasoning")
            else:
                if prev_human and len(human_ships) > 1:
                    pass_to_player(name)
                decl = self._human_declaration(sid)
                if decl is None:
                    self._running = False
                    return declarations
                declarations[sid] = decl
                prev_human = True

        return declarations

    def _human_declaration(self, sid: str) -> Optional[dict]:
        """Prompt a human player for maneuver + intent."""
        ship = self.session.get_ship(sid)
        pilot = self.session.get_pilot(sid)
        name = getattr(ship, "display_name", sid)

        while True:
            self.buf.set_status(self.session)
            stall = getattr(ship, "stall_speed", 0)
            engs = self.session.get_engagements_for_ship(sid)
            opp_adv = False
            if engs:
                e = engs[0]
                oid = e.ship_b_id if e.ship_a_id == sid else e.ship_a_id
                opp_adv = e.advantage == oid

            options = []
            keys = []
            for k, m in MANEUVER_CATALOG.items():
                errs = validate_maneuver(k, stall_speed=stall, opponent_has_advantage=opp_adv)
                options.append(dim(f"{m.name} — {errs[0][:50]}") if errs else m.name)
                keys.append(k)

            c = menu_choice(f"{name}: Choose Maneuver", options, self.buf,
                            prompt="Maneuver", allow_cancel=False)

            if c == HOTKEY_HELP:
                show_help(); continue
            elif c == HOTKEY_INSPECT:
                show_ship_inspection(ship, pilot); continue
            elif c == HOTKEY_QUIT:
                if yes_no("Quit?", default=False): return None
                continue
            elif c is None or c < 0:
                continue

            chosen = keys[c]
            if validate_maneuver(chosen, stall_speed=stall, opponent_has_advantage=opp_adv):
                continue

            m_def = MANEUVER_CATALOG[chosen]
            if m_def.facing == "rear":
                intent = "evade"
            elif m_def.facing == "front":
                intent = "pursue"
            else:
                ic = menu_choice("Intent",
                    ["Pursue (close)", "Evade (increase distance)"],
                    self.buf, allow_cancel=False)
                intent = "pursue" if (ic is not None and ic == 0) else "evade"

            self.buf.combat_log.add(f"  {name} [YOU]: {m_def.name} / {intent}", "info")
            return {"maneuver": chosen, "intent": intent}

    # ===================================================================
    # Phase 2: Chase
    # ===================================================================

    def _chase_phase(self, decls: dict[str, dict]) -> None:
        """Resolve all chase contests via the pipeline."""
        self.buf.combat_log.add("── Chase ──", "chase")
        seen: set[tuple[str, str]] = set()

        for sid in self.session.get_all_ship_ids():
            for eng in self.session.get_engagements_for_ship(sid):
                key = (min(eng.ship_a_id, eng.ship_b_id), max(eng.ship_a_id, eng.ship_b_id))
                if key in seen:
                    continue
                seen.add(key)

                sa = self.session.get_ship(eng.ship_a_id)
                sb = self.session.get_ship(eng.ship_b_id)
                pa = self.session.get_pilot(eng.ship_a_id)
                pb = self.session.get_pilot(eng.ship_b_id)
                if not sa or not sb:
                    continue
                if getattr(sa, "is_destroyed", False) or getattr(sb, "is_destroyed", False):
                    continue

                da = decls.get(eng.ship_a_id, {})
                db = decls.get(eng.ship_b_id, {})

                # PIPELINE CALL: resolve chase
                result = resolve_chase(
                    eng.ship_a_id, sa, pa,
                    eng.ship_b_id, sb, pb,
                    da, db, eng, self.dice,
                )

                # DISPLAY: log the chase result
                self._log_chase(result, sa, sb)

                # APPLY: state changes
                if result.opponent_loses_advantage:
                    eng.clear_advantage()
                    self.buf.combat_log.add("    Breaks opponent's advantage!", "chase")

                if result.winner_id and (result.can_gain_advantage or result.can_shift_range > 0):
                    self._handle_chase_choice(result, eng, decls)

    def _log_chase(self, r: ChaseResult, sa, sb) -> None:
        """Format chase result for the combat log."""
        na = getattr(sa, "display_name", "?")
        nb = getattr(sb, "display_name", "?")
        self.buf.combat_log.add(
            f"  {na} rolled {r.roll_a} vs skill {r.skill_a}, margin {r.margin_a:+d}", "chase")
        self.buf.combat_log.add(
            f"  {nb} rolled {r.roll_b} vs skill {r.skill_b}, margin {r.margin_b:+d}", "chase")
        if r.winner_id:
            self.buf.combat_log.add(f"  → {r.winner_name} wins by {r.margin_of_victory}!", "chase")
        else:
            self.buf.combat_log.add("  → Tie! No change.", "chase")

    def _handle_chase_choice(self, result: ChaseResult, eng, decls) -> None:
        """Let winner choose chase outcome (NPC=auto, human=menu)."""
        wid = result.winner_id
        ctrl = self.session.get_control_mode(wid)
        cur_adv = eng.advantage == wid
        wintert = decls.get(wid, {}).get("intent", "pursue")

        opts, okeys = [], []
        if result.can_gain_advantage and not cur_adv:
            opts.append("Gain Advantage"); okeys.append("advantage")
        if result.can_match_speed and cur_adv:
            opts.append("Match Speed (full accuracy!)"); okeys.append("match_speed")
        if result.can_shift_range > 0:
            d = "closer" if wintert == "pursue" else "farther"
            opts.append(f"Shift range 1 band {d}"); okeys.append("shift")
            if result.can_shift_range >= 2:
                opts.append(f"Shift range 2 bands {d}"); okeys.append("shift2")

        if not opts:
            return

        if ctrl == "npc":
            choice = ai_choose_chase(
                result.can_gain_advantage, result.can_match_speed and cur_adv,
                result.can_shift_range, cur_adv, eng.range_band, wintert)
        else:
            self.buf.set_status(self.session)
            c = menu_choice(f"{result.winner_name}'s Chase Victory", opts, self.buf, allow_cancel=False)
            choice = okeys[c] if c is not None and c >= 0 else "advantage"

        # Apply choice
        if choice == "advantage":
            eng.set_advantage(wid)
            self.buf.combat_log.add(f"    {result.winner_name} gains ADVANTAGE!", "chase")
        elif choice == "match_speed" and eng.advantage == wid:
            eng.set_matched_speed(wid)
            self.buf.combat_log.add(f"    {result.winner_name} MATCHES SPEED!", "chase")
        elif choice in ("shift_close", "shift"):
            eng.range_band = shift_range_band(eng.range_band, -1)
            self.buf.combat_log.add(f"    Range → {eng.range_band.upper()}", "chase")
        elif choice in ("shift_far",):
            eng.range_band = shift_range_band(eng.range_band, 1)
            self.buf.combat_log.add(f"    Range → {eng.range_band.upper()}", "chase")
        elif choice == "shift2":
            s = -2 if wintert == "pursue" else 2
            eng.range_band = shift_range_band(eng.range_band, s)
            self.buf.combat_log.add(f"    Range → {eng.range_band.upper()}", "chase")

    # ===================================================================
    # Phase 3+4: Attack and Damage
    # ===================================================================

    def _attack_damage_phase(self, decls: dict[str, dict]) -> None:
        """Resolve attacks for all ships that can attack. Each ship attacks once."""
        self.buf.combat_log.add("── Attack ──", "attack")
        attacked: set[str] = set()  # Track who has already attacked
        first_attack = True

        for sid in self.session.get_all_ship_ids():
            if sid in attacked:
                continue

            ship = self.session.get_ship(sid)
            pilot = self.session.get_pilot(sid)
            if not ship or getattr(ship, "is_destroyed", False):
                continue

            engs = self.session.get_engagements_for_ship(sid)
            if not engs:
                continue
            eng = engs[0]
            tid = eng.ship_b_id if eng.ship_a_id == sid else eng.ship_a_id
            target = self.session.get_ship(tid)
            tpilot = self.session.get_pilot(tid)
            if not target or getattr(target, "is_destroyed", False):
                continue

            decl = decls.get(sid, {})

            # PIPELINE: Resolve weapon
            weapon = resolve_weapon(ship, self._fixtures_dir)

            # PIPELINE: Attack roll
            atk = resolve_attack(
                sid, ship, pilot, tid, target, eng, decl, weapon, self.dice)

            attacked.add(sid)  # Mark as attacked regardless of result

            if not atk.can_attack:
                continue

            # DISPLAY: visual separator between each ship's attack sequence
            if not first_attack:
                self.buf.combat_log.add("", "info")
            first_attack = False

            # DISPLAY: log attack
            self._log_attack(atk)

            if not atk.hit:
                continue

            # CRITICAL HIT: defense is skipped entirely (GURPS RAW)
            if atk.critical and atk.hit:
                self.buf.combat_log.add(
                    f"  Critical hit — no defense allowed!", "critical_success")
            else:
                # PIPELINE: Defense roll
                t_maneuver = decls.get(tid, {}).get("maneuver", "move")

                # Determine if we should offer High-G to human
                ctrl = self.session.get_control_mode(tid)
                high_g_choice = None  # None = NPC decides
                if ctrl == "human":
                    from m1_psi_core.defense import is_high_g_available
                    if is_high_g_available(getattr(target, "accel", 0), getattr(target, "top_speed", 0)):
                        self.buf.set_status(self.session)
                        self._refresh()
                        high_g_choice = yes_no("Attempt High-G dodge? (costs FP on failure)", default=True)

                defense = resolve_defense(
                    tid, target, tpilot, t_maneuver,
                    decl.get("maneuver", "move"), eng, self.dice,
                    deceptive_penalty=0,
                    player_chose_high_g=high_g_choice,
                )

                # DISPLAY: log defense
                self._log_defense(defense)

                if defense.success:
                    continue

            # PIPELINE: Damage
            dmg = resolve_damage(tid, target, weapon, self.dice)

            # DISPLAY: log damage
            self._log_damage(dmg)

            # APPLY: state changes from damage
            target.current_fdr = dmg.fdr_remaining
            target.current_hp = dmg.new_hp
            if dmg.new_wound_level:
                from m1_psi_core.damage import WOUND_SEVERITY
                cur = WOUND_SEVERITY.get(getattr(target, "wound_level", "none"), 0)
                new = WOUND_SEVERITY.get(dmg.new_wound_level, 0)
                if new > cur:
                    target.wound_level = dmg.new_wound_level
            if dmg.is_destroyed:
                target.is_destroyed = True

            # APPLY: subsystem damage
            if dmg.subsystem_hit:
                from m1_psi_core.subsystems import disable_system, destroy_system
                if dmg.subsystem_status == "destroyed":
                    destroy_system(target, dmg.subsystem_hit)
                elif dmg.subsystem_status == "disabled":
                    disable_system(target, dmg.subsystem_hit)

    def _log_attack(self, a: AttackResult) -> None:
        """Format attack result for combat log."""
        m = a.modifiers
        self.buf.combat_log.add(f"  {a.attacker_name} fires {a.weapon.name} at {a.target_name}", "attack")
        parts = [f"Gunner({m.base_skill})", f"Range({m.range_penalty:+d})",
                 f"SM({m.sm_bonus:+d})", f"Lock({m.sensor_lock_bonus:+d})",
                 f"Acc({m.accuracy:+d})"]
        if m.rof_bonus:
            parts.append(f"ROF({m.rof_bonus:+d})")
        if m.relative_size_penalty:
            parts.append(f"RelSize({m.relative_size_penalty:+d})")
        if m.deceptive_penalty:
            parts.append(f"Deceptive({m.deceptive_penalty:+d})")
        self.buf.combat_log.add(f"    {' '.join(parts)} = {m.effective_skill}", "attack")

        if a.critical:
            ct = "CRITICAL HIT!" if a.hit else "CRITICAL MISS!"
            cc = event_color("critical_success" if a.hit else "critical_failure")
            self.buf.combat_log.add(
                f"    Rolled {a.roll} → {colorize(ct, cc)} (margin {a.margin:+d})", "attack")
        else:
            lbl = "HIT" if a.hit else "MISS"
            c = Color.BRIGHT_GREEN if a.hit else Color.RED
            self.buf.combat_log.add(
                f"    Rolled {a.roll} → {colorize(lbl, c)} (margin {a.margin:+d})", "attack")

    def _log_defense(self, d: DefenseResult) -> None:
        """Format defense result for combat log."""
        m = d.modifiers
        parts = [f"Pilot({m.piloting_skill})//2+Hnd({m.handling:+d})"]
        if m.evade_bonus:
            parts.append(f"Evade(+{m.evade_bonus})")
        if m.advantage_escaping_bonus:
            parts.append(f"AdvEsc(+{m.advantage_escaping_bonus})")
        if m.ace_stunt_bonus:
            parts.append(f"AceStunt(+{m.ace_stunt_bonus})")
        if m.high_g_bonus:
            parts.append(f"HighG(+{m.high_g_bonus})")
        if m.deceptive_penalty:
            parts.append(f"Deceptive({m.deceptive_penalty:+d})")
        if m.controls_penalty:
            parts.append(f"Controls({m.controls_penalty:+d})")

        dtype = "High-G dodge" if d.defense_type == "high_g_dodge" else "dodge"
        self.buf.combat_log.add(
            f"  {d.defender_name} {dtype}: {' '.join(parts)} = {m.effective_dodge}", "defense")

        if d.success:
            self.buf.combat_log.add(
                f"    Rolled {d.roll} → {colorize('DODGED', Color.BRIGHT_GREEN)} "
                f"(margin {d.margin:+d})", "defense")
        else:
            self.buf.combat_log.add(
                f"    Rolled {d.roll} → {colorize('FAILS', Color.RED)} "
                f"(margin {d.margin:+d})", "defense")

        # High-G HT result
        if d.high_g.attempted:
            if d.high_g.ht_succeeded:
                self.buf.combat_log.add(
                    f"    High-G HT roll: {d.high_g.ht_roll} vs {d.high_g.ht_target} — OK", "defense")
            else:
                self.buf.combat_log.add(
                    f"    High-G HT roll: {d.high_g.ht_roll} vs {d.high_g.ht_target} — "
                    f"{colorize(f'FAIL, {d.high_g.fp_lost} FP lost', Color.YELLOW)}", "defense")

    def _log_damage(self, d: DamageResult) -> None:
        """Format damage result for combat log using the pipeline's step list."""
        for step in d.steps:
            if step.label == "Result" and "DESTROYED" in step.value:
                self.buf.combat_log.add(
                    colorize(f"    ✘ {d.target_name} DESTROYED!", Color.BRIGHT_RED + Color.BOLD),
                    "system_damage")
            elif step.label == "Wound":
                wc = Color.BRIGHT_RED if d.wound_level in ("crippling", "mortal", "lethal") else Color.YELLOW
                self.buf.combat_log.add(f"    {colorize(step.value, wc)}", "damage")
            elif step.label == "Subsystem":
                self.buf.combat_log.add(f"    {step.value}", "system_damage")
            elif step.label == "Force screen":
                self.buf.combat_log.add(f"    {step.value}", "force_screen")
            elif step.label == "Mook":
                self.buf.combat_log.add(
                    colorize(f"    ✘ {d.target_name} (mook) removed!", Color.RED), "system_damage")
            elif step.label == "Result" and "Blocked" in step.value:
                self.buf.combat_log.add(
                    f"    {colorize(step.value, Color.BLUE)}", "force_screen")
            elif step.label == "Result" and "Stopped" in step.value:
                self.buf.combat_log.add(
                    f"    {colorize(step.value, Color.BLUE)}", "damage")
            else:
                self.buf.combat_log.add(f"    {step.label}: {step.value}", "damage")

    # ===================================================================
    # Phase 5: Cleanup
    # ===================================================================

    def _cleanup_phase(self) -> None:
        """End-of-turn cleanup: regen force screens, advance turn."""
        for sid in self.session.get_all_ship_ids():
            ship = self.session.get_ship(sid)
            if ship and not getattr(ship, "is_destroyed", False):
                ship.current_fdr = regen_force_screen(ship)

        self.buf.combat_log.add(
            f"── End of Turn {self.session.current_turn} ──", "force_screen")
        self.session.advance_turn()
