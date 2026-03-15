# Terminal UI Manual Test Script
## GURPS Psi-Wars Combat Simulator v0.19 — Visual Inspection Checklist

**Tester:** _______________
**Date:** _______________
**Terminal:** _______________ (e.g., "xterm 120x40", "raspi console 100x30")
**Commit:** _______________

---

## Instructions

Run the game with: `python -m psi_wars_ui`

For each test, follow the steps, observe the result, and mark PASS or FAIL.
Add notes for anything unexpected, even on passing tests.

### What's New in v0.19
- Real weapon data from JSON (48 weapons across 40 ships)
- Multiple weapon selection for human players
- NPC smart weapon selection (picks best for situation)
- Deceptive attacks (shows effective skill at each level, only on attack maneuvers)
- Luck advantage with real-time cooldown (configurable: Luck/Extraordinary/Ridiculous)
- Lucky Break separate from Luck (Ace Pilots get 1 free per chase)
- Impulse/Flesh Wound (reduce any wound to minor)
- Wound accumulation (repeated wounds escalate via HT roll)
- Crippling/mortal HT rolls to remain operational
- Subsystem cascade mechanic
- Force screen hardened 1 DR, plasma AD negation, heavy screen rules
- Matched Speed full accuracy on Move and Attack
- Speed penalty in range calculation
- Facing enforcement (fixed weapons need correct facing, advantage targets rear)
- Stall speed chase attack restriction
- Weapon range enforcement (mile notation supported)
- Visual separator between attack sequences
- Subsystem status in status bar (↓prop, ✘weap)
- Emergency power menu for human players
- Combat end summary screen
- Ship inspection shows weapons with ranges and Luck level
- Smarter NPC High-G decisions

---

## 1. Startup & Setup (8 tests)

### T-01: Game launches without errors
- [ ] PASS / FAIL
- Steps: `python -m psi_wars_ui`
- Expected: Title screen displays, no tracebacks.
- Notes: _______________

### T-02: Ship catalog displays sorted by SM
- [ ] PASS / FAIL
- Steps: Enter ship selection. Observe the list.
- Expected: SM 4 fighters at top (Spectre, Drifter, Hornet, Javelin, etc.),
  SM 5 next, then corvettes, frigates, capitals. Category headers
  (FIGHTERS, CORVETTES, etc.) shown as non-selectable separators.
- Notes: _______________

### T-03: Ship numbers are correct (no off-by-one)
- [ ] PASS / FAIL
- Steps: Select ship #1.
- Expected: Confirms "Aegis-7 'Spectre' Psionic Interceptor" (first SM 4 ship).
  NOT a category header.
- Notes: _______________

### T-04: Can select two ships for 1v1
- [ ] PASS / FAIL
- Steps: Pick a Javelin (#5) for faction 1 and a Hornet (#4) for faction 2.
- Expected: Both confirmed by name. Prompted for display name, control mode, pilot.
- Notes: _______________

### T-05: Faction assignment and enemy relationship
- [ ] PASS / FAIL
- Steps: Accept default factions (Empire vs Trader).
- Expected: Factions color-coded. "ENEMIES" displayed in red.
- Notes: _______________

### T-06: NPC vs NPC game runs automatically
- [ ] PASS / FAIL
- Steps: Set both ships to NPC. Start combat.
- Expected: Turns auto-resolve with ~1 second delay. Combat log scrolls.
  Eventually one ship is destroyed. "COMBAT OVER" announced.
- Notes: _______________

### T-07: Human vs NPC game prompts correctly
- [ ] PASS / FAIL
- Steps: Set one Human, one NPC. Start combat.
- Expected: Human gets maneuver menu. NPC declares silently.
  [NPC] and [YOU] indicators visible in status bar.
- Notes: _______________

### T-08: Human vs Human hot-seat works
- [ ] PASS / FAIL
- Steps: Set both to Human. Start combat.
- Expected: Screen clears between declarations. "Pass to: [name]" prompt.
  Previous player's choice hidden.
- Notes: _______________

---

## 2. Display Layout (7 tests)

### T-09: Status bar always visible at top
- [ ] PASS / FAIL
- Steps: Play several turns. Observe that ship status and engagement
  info remain at the top of every screen, including during menus.
- Expected: Status bar NEVER scrolls off. Always shows turn number,
  ship HP/fDR/wound, and engagement range/advantage.
- Notes: _______________

### T-10: Ship status shows correct data
- [ ] PASS / FAIL
- Steps: Observe the status bar.
- Expected: Each ship shows: [FACTION] [YOU/NPC] Name HP:cur/max fDR:cur/max Wound.
  HP color-coded (green/yellow/red). Wound color-coded.
- Notes: _______________

### T-11: Engagement shows range and advantage
- [ ] PASS / FAIL
- Steps: Observe engagement line in status bar.
- Expected: "ShipA ←[LONG]→ ShipB | No advantage" or similar.
  Range band in cyan. Advantage in yellow. Matched speed in green.
- Notes: _______________

### T-12: Combat log visible between status and menu
- [ ] PASS / FAIL
- Steps: Play a few turns. Observe the area between status bar and menu.
- Expected: Combat log shows recent events with color coding.
  Log truncates (oldest messages drop) to fit available space.
- Notes: _______________

### T-13: Terminal size adaptation
- [ ] PASS / FAIL
- Steps: Use different terminal sizes (try small and large).
- Expected: Layout adapts. No truncated lines on wide terminals.
  Small terminals show less combat log but status bar still visible.
- Notes: _______________

### T-14: Colors display correctly
- [ ] PASS / FAIL
- Steps: Observe various colored elements.
- Expected: Factions colored. Chase events in cyan. Attacks in yellow.
  Defense in green. Damage in red. Criticals bold. Wound levels colored.
- Notes: _______________

### T-15: Destroyed ship marked clearly
- [ ] PASS / FAIL
- Steps: Destroy an enemy ship.
- Expected: Status bar shows "✘ ShipName" dimmed, "DESTROYED" in bright red.
  Ship no longer takes turns.
- Notes: _______________

---

## 3. Hotkeys (3 tests)

### T-16: Help overlay on H
- [ ] PASS / FAIL
- Steps: At any maneuver menu, type H.
- Expected: Help overlay with hotkey list, advantage explanation,
  and formation benefits. Press Enter returns to menu.
- Notes: _______________

### T-17: Ship inspection on I
- [ ] PASS / FAIL
- Steps: At any maneuver menu, type I.
- Expected: Detailed ship stats: SM, HP, HT, Hnd, Move, DR, fDR,
  electronics, pilot skills, traits. Press Enter returns.
- Notes: _______________

### T-18: Quit confirmation on Q
- [ ] PASS / FAIL
- Steps: At any maneuver menu, type Q.
- Expected: "Quit? (Y/n)" prompt. N returns to game. Y exits cleanly.
- Notes: _______________

---

## 4. Chase Resolution (5 tests)

### T-19: Chase roll shows full detail
- [ ] PASS / FAIL
- Steps: Observe chase log after a turn.
- Expected: Each ship shows: "ShipName rolled X vs skill Y, margin +/-Z"
  Then: "→ WinnerName wins by N!"
- Notes: _______________

### T-20: Chase outcome choice offered to human winner
- [ ] PASS / FAIL
- Steps: Play human ship, win a chase by 5+.
- Expected: Menu: "1. Gain Advantage" and/or "2. Shift range 1 band closer".
  If already advantaged: "Match Speed" offered.
- Notes: _______________

### T-21: Range updates after chase shift
- [ ] PASS / FAIL
- Steps: Choose "Shift range" in chase outcome.
- Expected: Status bar engagement line shows new range band.
  Log shows "Range → [NEW BAND]".
- Notes: _______________

### T-22: Advantage updates after chase
- [ ] PASS / FAIL
- Steps: Choose "Gain Advantage" in chase outcome.
- Expected: Status bar shows "ShipName has ADVANTAGE" in yellow.
  Log shows "ShipName gains ADVANTAGE!"
- Notes: _______________

### T-23: Matched speed display
- [ ] PASS / FAIL
- Steps: Win chase while already advantaged, choose Match Speed.
- Expected: Status bar shows "ShipName MATCHED SPEED" in bright green.
- Notes: _______________

---

## 5. Attack Resolution (5 tests)

### T-24: Attack shows actual weapon name and modifiers
- [ ] PASS / FAIL
- Steps: Observe an attack in the combat log.
- Expected: "ShipName fires [Actual Weapon Name] at Target"
  Then modifier breakdown: Gunner(X) Range(+/-Y) SM(+/-Z) Lock(+/-W) Acc(+/-V)
  ROF bonus shown if applicable. Relative size penalty if applicable.
  "= EffectiveSkill" at the end.
- Notes: _______________

### T-25: Hit/miss with margin displayed
- [ ] PASS / FAIL
- Steps: Observe attack result.
- Expected: "Rolled X → HIT (margin +Y)" in green, or
  "Rolled X → MISS (margin -Y)" in red.
- Notes: _______________

### T-26: Critical hit/miss highlighted
- [ ] PASS / FAIL
- Steps: Play until a critical occurs (roll 3-4 or 17-18).
- Expected: "CRITICAL HIT!" in bold bright green, or
  "CRITICAL MISS!" in bold bright red.
- Notes: _______________

### T-27: Defense shows dodge calculation
- [ ] PASS / FAIL
- Steps: After a hit, observe the dodge resolution.
- Expected: "ShipName dodge: Pilot(X)//2+Hnd(+/-Y)" with any bonuses
  (Evade, HighG, etc.) "= EffectiveDodge"
  Then "Rolled X → DODGED/FAILS (margin +/-Y)"
- Notes: _______________

### T-28: High-G dodge appears when available
- [ ] PASS / FAIL
- Steps: Play a human ship with accel >= 40 or top_speed >= 400.
  Get hit by an attack.
- Expected: "Attempt High-G dodge? (costs FP on failure) (Y/n)" prompt.
  If yes: dodge shows "+HighG(+1)" modifier.
  HT roll result shown: "High-G HT roll: X vs Y — OK/FAIL, Z FP lost"
- Notes: _______________

---

## 6. Damage Resolution (5 tests)

### T-29: Damage pipeline fully displayed
- [ ] PASS / FAIL
- Steps: Get a hit that deals damage.
- Expected: Step-by-step display:
  "Raw damage: XdY=Z × M = Total"
  "Force screen: Absorbs N (fDR: X → Y)" (only for shielded ships)
  "Hull armor: X vs DR Y (eff Z w/ AD W) → N penetrating"
  "WOUND LEVEL (Xhp = Y% of Z HP)"
- Notes: _______________

### T-30: Force screen absorption (shielded ship)
- [ ] PASS / FAIL
- Steps: Attack a ship with force screen (e.g., Hornet, fDR 150).
- Expected: "Absorbs N" shown. fDR in status bar decreases.
  If all absorbed: "Blocked by force screen" message.
- Notes: _______________

### T-31: No shield messages for unshielded ships
- [ ] PASS / FAIL
- Steps: Attack an unshielded ship (e.g., Javelin).
- Expected: No "force screen" or "past shield" messages.
  Damage goes directly to "Raw → DR → penetrating".
- Notes: _______________

### T-32: HP and wound update after damage
- [ ] PASS / FAIL
- Steps: Deal penetrating damage.
- Expected: Status bar HP decreases. Wound level updates and
  color changes (green → yellow → red as severity increases).
- Notes: _______________

### T-33: Subsystem damage on major+ wound
- [ ] PASS / FAIL
- Steps: Deal enough damage for a major or crippling wound.
- Expected: "Subsystem: [system_name] disabled/destroyed! (roll X)"
- Notes: _______________

---

## 7. Force Screen Behavior (2 tests)

### T-34: Force screen regenerates between turns
- [ ] PASS / FAIL
- Steps: Deal damage to a shielded ship's fDR. Observe next turn.
- Expected: fDR in status bar returns to max at turn end.
  (Note: regen happens silently in cleanup phase)
- Notes: _______________

### T-35: Force screen shows in status bar
- [ ] PASS / FAIL
- Steps: Observe fDR display for shielded vs unshielded ships.
- Expected: Shielded ship: "fDR:150/150" in blue. After damage: lower
  number, color changes to yellow/red as it depletes.
  Unshielded ship: "fDR:--" in dim.
- Notes: _______________

---

## 8. Combat End (2 tests)

### T-36: Ship destruction ends combat
- [ ] PASS / FAIL
- Steps: Destroy the enemy ship (may take several turns).
- Expected: "✘ ShipName DESTROYED!" in combat log.
  "COMBAT OVER" announced. Prompted to continue or quit.
- Notes: _______________

### T-37: NPC vs NPC reaches conclusion
- [ ] PASS / FAIL
- Steps: Run an all-NPC combat. Wait for it to finish.
- Expected: Combat eventually ends with one ship destroyed.
  Does not run forever. (If it takes >50 turns, note that.)
- Notes: _______________

---

## 9. Edge Cases (5 tests)

### T-38: Stall-speed ship restrictions
- [ ] PASS / FAIL
- Steps: Pick a Javelin (stall speed 35). Observe maneuver menu.
- Expected: "Attack" maneuver shown as unavailable with explanation.
  Ship uses Move and Attack or other valid maneuvers.
- Notes: _______________

### T-39: Invalid input handled gracefully
- [ ] PASS / FAIL
- Steps: At menu prompts, enter garbage (letters, out-of-range numbers).
- Expected: Error message. Re-prompts. No crash.
- Notes: _______________

### T-40: NPC makes reasonable decisions
- [ ] PASS / FAIL
- Steps: Play human vs NPC for 5+ turns. Read NPC reasoning in log.
- Expected: NPC pursues when healthy, evades when damaged, uses
  appropriate maneuvers. Reasoning shown: "→ [explanation]"
- Notes: _______________

### T-41: Capital vs fighter size penalty
- [ ] PASS / FAIL
- Steps: Set up Javelin (SM 4) vs Sword Battleship (SM 13).
- Expected: Battleship's attack shows "RelSize(-10)" modifier.
  Fighter's attack does not show RelSize penalty.
  No crashes on extreme stat differences.
- Notes: _______________

### T-42: Very long combat log doesn't break display
- [ ] PASS / FAIL
- Steps: Play 10+ turns. Observe display.
- Expected: Combat log scrolls correctly. Oldest entries drop off.
  Status bar remains at top. Menu remains at bottom.
  No display corruption or overlapping text.
- Notes: _______________

---

## Summary

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Startup & Setup | 8 | ___ | ___ |
| Display Layout | 7 | ___ | ___ |
| Hotkeys | 3 | ___ | ___ |
| Chase Resolution | 5 | ___ | ___ |
| Attack Resolution | 5 | ___ | ___ |
| Damage Resolution | 5 | ___ | ___ |
| Force Screen | 2 | ___ | ___ |
| Combat End | 2 | ___ | ___ |
| Edge Cases | 5 | ___ | ___ |
| **TOTAL** | **42** | ___ | ___ |

**Overall Result:** PASS / FAIL

**Blocking Issues:**
_______________

**Non-Blocking Issues:**
_______________

**Notes:**
_______________
