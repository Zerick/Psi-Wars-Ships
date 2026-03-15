"""
Main game loop for the Psi-Wars terminal UI — v0.15 batch update.

ALL DISPLAY OUTPUT GOES THROUGH THE SCREEN BUFFER.
ALL COMBAT LOGIC GOES THROUGH THE ENGINE PIPELINE.

New in v0.15:
    - Multiple weapon selection for human players
    - Deceptive attack option
    - Emergency power allocation
    - Luck/Impulse points (reroll, flesh wound)
    - Wound accumulation with HT rolls
    - Crippling/mortal HT rolls to remain operational
    - Stall speed chase attack restriction
    - Weapon range enforcement
    - Subsystem status in display
    - Smarter NPC High-G decisions
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from m1_psi_core.session import GameSession
from m1_psi_core.dice import DiceRoller, check_success
from m1_psi_core.combat_state import shift_range_band
from m1_psi_core.maneuvers import MANEUVER_CATALOG, validate_maneuver
from m1_psi_core.npc_ai import choose_chase_outcome as ai_choose_chase
from m1_psi_core.damage import (
    WOUND_SEVERITY, check_wound_accumulation, check_operational_ht_roll,
)
from m1_psi_core.subsystems import (
    disable_system, destroy_system, get_disabled, get_destroyed,
)

from m1_psi_core.engine import (
    resolve_chase, resolve_attack, resolve_defense, resolve_damage,
    resolve_weapon, resolve_all_weapons, regen_force_screen,
    get_target_facing_hit, is_weapon_in_range, check_stall_attack_restriction,
    ChaseResult, AttackResult, DefenseResult, DamageResult, WeaponInfo,
)

from psi_wars_ui.display import Color, bold, dim, colorize, event_color
from psi_wars_ui.renderer import ScreenBuffer
from psi_wars_ui.input_handler import (
    menu_choice, yes_no, pass_to_player,
    show_help, show_ship_inspection, pause_with_buffer, get_input,
    HOTKEY_HELP, HOTKEY_INSPECT, HOTKEY_QUIT,
)

NPC_TURN_DELAY_SECONDS = 1.0


class GameLoop:
    """UI orchestrator. Zero rules logic — delegates everything to the engine."""

    def __init__(self, session: GameSession, fixtures_dir: Optional[Path] = None):
        self.session = session
        self.buf = ScreenBuffer()
        self.dice = DiceRoller()
        self._running = True
        self._fixtures_dir = fixtures_dir
        # Track chase winners per turn for stall speed restriction
        self._chase_winners: dict[str, bool] = {}
        # Player resources
        self._luck_uses: dict[str, int] = {}  # ship_id -> uses remaining
        self._luck_cooldowns: dict[str, str] = {}  # ship_id -> cooldown description
        self._impulse_points: dict[str, int] = {}  # ship_id -> points remaining

    def _refresh(self) -> None:
        self.buf.set_status(self.session)
        self.buf.clear_action()
        self.buf.draw()

    def _is_all_npc(self) -> bool:
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
        self.buf.combat_log.add("═══ COMBAT BEGINS ═══", "turn")

        # Initialize luck (1 per ace pilot, 0 otherwise)
        for sid in self.session.get_all_ship_ids():
            pilot = self.session.get_pilot(sid)
            is_ace = getattr(pilot, "is_ace_pilot", False)
            self._luck_uses[sid] = 1 if is_ace else 0
            self._impulse_points[sid] = 1  # 1 impulse point per ship

        while self._running:
            self.buf.set_status(self.session)

            if self.session.check_combat_end():
                self.buf.combat_log.add("═══ COMBAT OVER ═══", "turn")
                self._refresh()
                if not yes_no("Continue?", default=False):
                    break
                continue

            declarations = self._declaration_phase()
            if not self._running:
                break

            self._chase_phase(declarations)
            self.buf.set_status(self.session)
            self._refresh()

            self._attack_damage_phase(declarations)
            self.buf.set_status(self.session)
            self._refresh()

            if not self._is_all_npc():
                pause_with_buffer(self.buf, "Press Enter for next turn...")

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
        self.buf.combat_log.add("── Chase ──", "chase")
        self._chase_winners.clear()
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

                result = resolve_chase(
                    eng.ship_a_id, sa, pa, eng.ship_b_id, sb, pb,
                    da, db, eng, self.dice,
                )

                self._log_chase(result, sa, sb)

                # Track chase winners for stall speed restriction
                if result.winner_id:
                    self._chase_winners[result.winner_id] = True
                    loser = eng.ship_b_id if result.winner_id == eng.ship_a_id else eng.ship_a_id
                    self._chase_winners[loser] = False
                else:
                    # Tie: both "won" for stall restriction purposes
                    self._chase_winners[eng.ship_a_id] = True
                    self._chase_winners[eng.ship_b_id] = True

                if result.opponent_loses_advantage:
                    eng.clear_advantage()
                    self.buf.combat_log.add("    Breaks opponent's advantage!", "chase")

                if result.winner_id and (result.can_gain_advantage or result.can_shift_range > 0):
                    self._handle_chase_choice(result, eng, decls)

    def _log_chase(self, r: ChaseResult, sa, sb) -> None:
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

        if choice == "advantage":
            eng.set_advantage(wid)
            self.buf.combat_log.add(f"    {result.winner_name} gains ADVANTAGE!", "chase")
        elif choice == "match_speed" and eng.advantage == wid:
            eng.set_matched_speed(wid)
            self.buf.combat_log.add(f"    {result.winner_name} MATCHES SPEED!", "chase")
        elif choice in ("shift_close", "shift"):
            eng.range_band = shift_range_band(eng.range_band, -1)
            self.buf.combat_log.add(f"    Range → {eng.range_band.upper()}", "chase")
        elif choice == "shift_far":
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
        self.buf.combat_log.add("── Attack ──", "attack")
        attacked: set[str] = set()
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
            ctrl = self.session.get_control_mode(sid)

            # Resolve all available weapons
            all_weapons = resolve_all_weapons(ship, self._fixtures_dir)

            # Human: choose weapon if multiple available
            if ctrl == "human" and len(all_weapons) > 1:
                weapon = self._choose_weapon(sid, all_weapons, eng)
            else:
                weapon = all_weapons[0]  # NPC/single weapon: use first

            # Check weapon range
            weapon_range = getattr(weapon, "damage_str", "")
            # Get actual range string from weapon data
            weapons_list = getattr(ship, "weapons", [])
            range_str = None
            for w in weapons_list:
                if isinstance(w, dict):
                    from m1_psi_core.engine import load_weapon_data
                    wd = load_weapon_data(w.get("weapon_ref", ""), self._fixtures_dir)
                    if wd and wd.get("name") == weapon.name:
                        range_str = wd.get("range")
                        break

            if range_str and not is_weapon_in_range(range_str, eng.range_band):
                if not first_attack:
                    self.buf.combat_log.add("", "info")
                first_attack = False
                name = getattr(ship, "display_name", sid)
                self.buf.combat_log.add(
                    f"  {name}: {weapon.name} out of range at {eng.range_band.upper()}", "info")
                attacked.add(sid)
                continue

            # Check stall speed chase restriction
            has_stall = getattr(ship, "stall_speed", 0) > 0
            won_chase = self._chase_winners.get(sid, True)
            if not check_stall_attack_restriction(has_stall, won_chase, weapon.mount):
                if not first_attack:
                    self.buf.combat_log.add("", "info")
                first_attack = False
                name = getattr(ship, "display_name", sid)
                self.buf.combat_log.add(
                    f"  {name}: Lost chase — fixed weapons can't fire (stall speed)", "info")
                attacked.add(sid)
                continue

            # Deceptive attack (human choice, only on attack maneuvers)
            deceptive = 0
            from m1_psi_core.maneuvers import get_attack_permission
            atk_perm = get_attack_permission(
                decl.get("maneuver", "move"),
                is_ace_pilot=getattr(pilot, "is_ace_pilot", False),
                is_gunslinger=getattr(pilot, "is_gunslinger", False),
            )
            if ctrl == "human" and atk_perm != "none":
                deceptive = self._choose_deceptive(sid, pilot, weapon, target, eng, atk_perm)

            # Attack roll
            atk = resolve_attack(
                sid, ship, pilot, tid, target, eng, decl, weapon, self.dice,
                deceptive_levels=deceptive,
            )
            attacked.add(sid)

            if not atk.can_attack:
                continue

            if not first_attack:
                self.buf.combat_log.add("", "info")
            first_attack = False

            self._log_attack(atk)

            # LUCK: Human attacker missed — offer reroll
            if not atk.hit and ctrl == "human" and self._luck_uses.get(sid, 0) > 0:
                luck_result = self._offer_luck_reroll(sid, atk.roll, atk.modifiers.effective_skill, "attack")
                if luck_result is not None:
                    # Rerolled — check if the new roll hits
                    new_result = check_success(atk.modifiers.effective_skill, luck_result)
                    if new_result.success:
                        atk = AttackResult(
                            attacker_id=atk.attacker_id, attacker_name=atk.attacker_name,
                            target_id=atk.target_id, target_name=atk.target_name,
                            weapon=atk.weapon, modifiers=atk.modifiers,
                            roll=luck_result, margin=new_result.margin,
                            hit=True, critical=new_result.critical,
                            critical_type=new_result.critical_type,
                        )
                        self.buf.combat_log.add(
                            f"    → Rerolled {luck_result}: {colorize('HIT!', Color.BRIGHT_GREEN)}", "attack")

            # LUCK: Human defender vs opponent critical — force reroll
            if atk.critical and atk.hit:
                t_ctrl = self.session.get_control_mode(tid)
                if t_ctrl == "human" and self._luck_uses.get(tid, 0) > 0:
                    luck_result = self._offer_luck_reroll(
                        tid, atk.roll, atk.modifiers.effective_skill,
                        "force_opponent_reroll", pick="worst")
                    if luck_result is not None:
                        new_result = check_success(atk.modifiers.effective_skill, luck_result)
                        if not new_result.success:
                            self.buf.combat_log.add(
                                f"    → Forced reroll {luck_result}: {colorize('MISS!', Color.BRIGHT_GREEN)}", "attack")
                            continue
                        elif not new_result.critical:
                            self.buf.combat_log.add(
                                f"    → Forced reroll {luck_result}: Hit but NOT critical — defense allowed!", "attack")
                            atk = AttackResult(
                                attacker_id=atk.attacker_id, attacker_name=atk.attacker_name,
                                target_id=atk.target_id, target_name=atk.target_name,
                                weapon=atk.weapon, modifiers=atk.modifiers,
                                roll=luck_result, margin=new_result.margin,
                                hit=True, critical=False, critical_type=None,
                            )

            if not atk.hit:
                continue

            # Critical hit: skip defense
            if atk.critical and atk.hit:
                self.buf.combat_log.add(
                    f"  Critical hit — no defense allowed!", "critical_success")
            else:
                # Defense
                t_maneuver = decls.get(tid, {}).get("maneuver", "move")
                t_ctrl = self.session.get_control_mode(tid)

                # High-G decision
                high_g_choice = None
                if t_ctrl == "human":
                    from m1_psi_core.defense import is_high_g_available
                    if is_high_g_available(getattr(target, "accel", 0), getattr(target, "top_speed", 0)):
                        self.buf.set_status(self.session)
                        self._refresh()
                        high_g_choice = yes_no("Attempt High-G dodge? (costs FP on failure)", default=True)
                else:
                    from m1_psi_core.npc_ai import should_attempt_high_g
                    from m1_psi_core.defense import is_high_g_available
                    if is_high_g_available(getattr(target, "accel", 0), getattr(target, "top_speed", 0)):
                        high_g_choice = should_attempt_high_g(
                            current_fp=getattr(tpilot, "current_fp", 10),
                            max_fp=getattr(tpilot, "max_fp", 10),
                            wound_level=getattr(target, "wound_level", "none"),
                            attacker_margin=atk.margin,
                        )

                deceptive_def_penalty = -deceptive if deceptive > 0 else 0

                defense = resolve_defense(
                    tid, target, tpilot, t_maneuver,
                    decl.get("maneuver", "move"), eng, self.dice,
                    deceptive_penalty=deceptive_def_penalty,
                    player_chose_high_g=high_g_choice,
                )
                self._log_defense(defense)

                # LUCK: Human defender failed dodge — offer reroll
                if not defense.success and t_ctrl == "human" and self._luck_uses.get(tid, 0) > 0:
                    luck_result = self._offer_luck_reroll(
                        tid, defense.roll, defense.modifiers.effective_dodge, "dodge")
                    if luck_result is not None:
                        if luck_result <= defense.modifiers.effective_dodge:
                            self.buf.combat_log.add(
                                f"    → Rerolled {luck_result}: {colorize('DODGED!', Color.BRIGHT_GREEN)}", "defense")
                            continue

                if defense.success:
                    continue

            # Determine target facing for damage
            attacker_has_adv = eng.advantage == sid
            t_decl = decls.get(tid, {})
            target_facing = get_target_facing_hit(
                attacker_has_advantage=attacker_has_adv,
                target_maneuver=t_decl.get("maneuver", "move"),
                target_intent=t_decl.get("intent", "pursue"),
            )

            if attacker_has_adv:
                self.buf.combat_log.add(
                    f"    → Targeting {target_facing} facing (advantage)", "attack")

            # Damage
            dmg = resolve_damage(tid, target, weapon, self.dice, facing=target_facing)
            self._log_damage(dmg)

            # Flesh wound option (human only)
            if dmg.penetrating_damage > 0 and self.session.get_control_mode(tid) == "human":
                if self._impulse_points.get(tid, 0) > 0:
                    sev = WOUND_SEVERITY.get(dmg.wound_level, 0)
                    if sev >= WOUND_SEVERITY.get("major", 3):
                        if yes_no(f"Use Impulse Point for Flesh Wound? ({self._impulse_points[tid]} left)", default=False):
                            self._impulse_points[tid] -= 1
                            from m1_psi_core.special import apply_flesh_wound
                            dmg.wound_level = apply_flesh_wound(dmg.wound_level)
                            dmg.new_wound_level = "minor"
                            self.buf.combat_log.add(
                                f"    {colorize('FLESH WOUND! Reduced to minor.', Color.BRIGHT_YELLOW)}", "info")

            # Apply state changes
            self._apply_damage(tid, target, dmg)

    def _choose_weapon(self, sid: str, weapons: list[WeaponInfo], eng) -> WeaponInfo:
        """Let human player choose which weapon to fire."""
        opts = []
        for w in weapons:
            opts.append(f"{w.name} ({w.damage_str}) [{w.mount}]")
        c = menu_choice("Choose weapon", opts, self.buf, allow_cancel=False)
        if c is not None and 0 <= c < len(weapons):
            return weapons[c]
        return weapons[0]

    def _offer_luck_reroll(
        self, sid: str, original_roll: int, target_num: int,
        context: str, pick: str = "best",
    ) -> Optional[int]:
        """
        Offer a Luck reroll to a human player.

        Args:
            sid: Ship ID of the player using Luck.
            original_roll: The original dice roll.
            target_num: The skill/defense number being rolled against.
            context: Description ("attack", "dodge", "force_opponent_reroll").
            pick: "best" (take lowest) or "worst" (take highest for forcing opponent).

        Returns:
            The chosen roll after Luck, or None if Luck was declined.
        """
        uses = self._luck_uses.get(sid, 0)
        if uses <= 0:
            return None

        # Calculate cooldown info
        cooldown = self._luck_cooldowns.get(sid, "")
        cooldown_str = f" (cooldown: {cooldown})" if cooldown else ""

        if context == "force_opponent_reroll":
            prompt = f"Use Luck to force opponent reroll? ({uses} uses left{cooldown_str})"
        elif context == "dodge":
            prompt = f"Use Luck to reroll dodge? ({uses} uses left{cooldown_str})"
        else:
            prompt = f"Use Luck to reroll attack? ({uses} uses left{cooldown_str})"

        if not yes_no(prompt, default=False):
            return None

        self._luck_uses[sid] -= 1

        # Track cooldown (15min / 30min / 1hr depending on Luck advantage level)
        # For now, track as "used" — cooldown is per-session
        self._luck_cooldowns[sid] = "1 hour"

        from m1_psi_core.special import apply_luck_reroll
        r1 = self.dice.roll_3d6()
        r2 = self.dice.roll_3d6()
        luck = apply_luck_reroll(original_roll, [r1, r2], pick)

        self.buf.combat_log.add(
            f"    {colorize('LUCK!', Color.BRIGHT_YELLOW)} Original {original_roll}, "
            f"rerolls [{r1}, {r2}] → chose {luck.chosen_roll}", "info")

        return luck.chosen_roll

    def _choose_deceptive(self, sid: str, pilot, weapon, target, eng, atk_perm) -> int:
        """Let human player choose deceptive attack level, showing effective skill."""
        from m1_psi_core.attack import (
            get_sensor_lock_bonus, apply_accuracy, get_sm_bonus,
            get_rof_bonus, get_relative_size_penalty,
        )
        from m1_psi_core.combat_state import get_effective_range_penalty
        from m1_psi_core.special import classify_ship

        base = getattr(pilot, "gunnery_skill", 12)
        attacker = self.session.get_ship(sid)
        own_spd = getattr(attacker, "top_speed", 0)
        opp_spd = getattr(target, "top_speed", 0)
        rng = get_effective_range_penalty(eng.range_band, own_spd, opp_spd)
        sm = get_sm_bonus(getattr(target, "sm", 4))
        lock = get_sensor_lock_bonus(True, getattr(attacker, "targeting_bonus", 5))
        acc = apply_accuracy(weapon.acc, atk_perm)
        rof = get_rof_bonus(weapon.rof)
        ac = classify_ship(getattr(attacker, "sm", 4), 15)
        tc = classify_ship(getattr(target, "sm", 4), 15)
        rel = get_relative_size_penalty(ac, tc)

        eff_base = base + rng + sm + lock + acc + rof + rel
        max_levels = max(0, (eff_base - 10) // 2)
        if max_levels <= 0:
            return 0

        opts = [f"No deceptive (effective skill {eff_base})"]
        for i in range(1, min(max_levels + 1, 4)):
            eff = eff_base - (i * 2)
            opts.append(f"Level {i}: skill {eff} (−{i*2} hit, −{i} dodge)")

        c = menu_choice("Deceptive Attack?", opts, self.buf, allow_cancel=False)
        if c is not None and c > 0:
            return c
        return 0

    def _apply_damage(self, tid: str, target, dmg: DamageResult) -> None:
        """Apply all state changes from a damage result."""
        target.current_fdr = dmg.fdr_remaining
        target.current_hp = dmg.new_hp

        if dmg.new_wound_level:
            cur = WOUND_SEVERITY.get(getattr(target, "wound_level", "none"), 0)
            new = WOUND_SEVERITY.get(dmg.new_wound_level, 0)

            # Wound accumulation check
            if new <= cur and cur > 0:
                ht = int(str(getattr(target, "ht", 12)).replace("f", "").replace("F", ""))
                ht_roll = self.dice.roll_3d6()
                ht_result = check_success(ht, ht_roll)
                accum = check_wound_accumulation(
                    getattr(target, "wound_level", "none"),
                    dmg.wound_level, ht_result.success, ht_result.margin,
                )
                if accum.escalated:
                    target.wound_level = accum.new_wound_level
                    self.buf.combat_log.add(
                        f"    Wound accumulates! HT roll {ht_roll} vs {ht} — "
                        f"{colorize(f'ESCALATES to {accum.new_wound_level.upper()}', Color.BRIGHT_RED)}",
                        "damage")
                elif accum.extra_system_damage:
                    self.buf.combat_log.add(
                        f"    HT roll {ht_roll} vs {ht} — margin 0, extra subsystem hit!", "system_damage")
                else:
                    self.buf.combat_log.add(
                        f"    Wound accumulation: HT roll {ht_roll} vs {ht} — held.", "damage")
            elif new > cur:
                target.wound_level = dmg.new_wound_level

        # Crippling/mortal HT roll
        if dmg.wound_level in ("crippling", "mortal") and not dmg.is_destroyed:
            ht = int(str(getattr(target, "ht", 12)).replace("f", "").replace("F", ""))
            ht_roll = self.dice.roll_3d6()
            ht_result = check_success(ht, ht_roll)
            op = check_operational_ht_roll(dmg.wound_level, ht_result.success)

            if op.destroyed:
                target.is_destroyed = True
                t_name = getattr(target, "display_name", tid)
                self.buf.combat_log.add(
                    f"    HT roll {ht_roll} vs {ht} — "
                    f"{colorize(f'FAILED! {t_name} DESTROYED!', Color.BRIGHT_RED + Color.BOLD)}",
                    "system_damage")
            elif not op.still_operational:
                self.buf.combat_log.add(
                    f"    HT roll {ht_roll} vs {ht} — "
                    f"{colorize('FAILED! Reduced to minimum systems.', Color.RED)}",
                    "system_damage")
            else:
                self.buf.combat_log.add(
                    f"    HT roll {ht_roll} vs {ht} — operational!", "info")

        if dmg.is_destroyed:
            target.is_destroyed = True

        # Subsystem damage
        if dmg.subsystem_hit:
            if dmg.subsystem_status == "destroyed":
                destroy_system(target, dmg.subsystem_hit)
            elif dmg.subsystem_status == "disabled":
                disable_system(target, dmg.subsystem_hit)

    # ===================================================================
    # Display helpers
    # ===================================================================

    def _log_attack(self, a: AttackResult) -> None:
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

        if d.high_g.attempted:
            if d.high_g.ht_succeeded:
                self.buf.combat_log.add(
                    f"    High-G HT roll: {d.high_g.ht_roll} vs {d.high_g.ht_target} — OK", "defense")
            else:
                self.buf.combat_log.add(
                    f"    High-G HT: {d.high_g.ht_roll} vs {d.high_g.ht_target} — "
                    f"{colorize(f'FAIL, {d.high_g.fp_lost} FP lost', Color.YELLOW)}", "defense")

    def _log_damage(self, d: DamageResult) -> None:
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
                self.buf.combat_log.add(f"    {colorize(step.value, Color.BLUE)}", "force_screen")
            elif step.label == "Result" and "Stopped" in step.value:
                self.buf.combat_log.add(f"    {colorize(step.value, Color.BLUE)}", "damage")
            else:
                self.buf.combat_log.add(f"    {step.label}: {step.value}", "damage")

    # ===================================================================
    # Phase 5: Cleanup
    # ===================================================================

    def _cleanup_phase(self) -> None:
        for sid in self.session.get_all_ship_ids():
            ship = self.session.get_ship(sid)
            if ship and not getattr(ship, "is_destroyed", False):
                ship.current_fdr = regen_force_screen(ship)

        self.buf.combat_log.add(
            f"── End of Turn {self.session.current_turn} ──", "force_screen")
        self.session.advance_turn()
