# Terminal UI Manual Test Script
## GURPS Psi-Wars Combat Simulator — Visual Inspection Checklist

**Tester:** _______________
**Date:** _______________
**Terminal:** _______________  (e.g., "xterm 120x40", "raspi console 100x30")
**Commit:** _______________

---

## Instructions

Run the game with: `python -m psi_wars_ui`  (or whatever the launch command ends up being)

For each test, follow the steps, observe the result, and mark PASS or FAIL.
Add notes for anything unexpected, even on passing tests.

---

## 1. Startup & Setup

### T-UI-01: Game launches without errors
- [P] PASS / FAIL
- Steps: Run the launch command.
- Expected: Game displays a title screen or goes directly to setup menu. No tracebacks.
- Notes: _______________

### T-UI-02: Ship selection menu displays all ships
- [p] PASS / FAIL
- Steps: Enter the ship selection flow.
- Expected: All 40 ships are listed, organized by class. Each shows name, SM, and key stats.
- Notes: _______________

### T-UI-03: Can select two ships for 1v1
- [p] PASS / FAIL
- Steps: Pick a Javelin for Player 1 and a Hornet for Player 2.
- Expected: Both ships are confirmed with their names. Prompted for faction assignment.
- Notes: _______________

### T-UI-04: Faction assignment works
- [p] PASS / FAIL
- Steps: Assign Javelin to "Empire" and Hornet to "Trader". Set them as enemies.
- Expected: Factions are displayed with colors. Relationship shown as "ENEMY".
- Notes: _______________

### T-UI-05: Control mode assignment works
- [p] PASS / FAIL
- Steps: Set Javelin to Human, Hornet to NPC.
- Expected: Control modes displayed. NPC indicator visible next to Hornet.
- Notes: _______________

### T-UI-06: Can start with both ships as NPC (full auto)
- [p] PASS / FAIL
- Steps: Restart setup. Set both ships to NPC.
- Expected: Game proceeds without requiring any human input during turns. Combat auto-resolves.
- Notes: _______________

### T-UI-07: Can start with both ships as Human (hot-seat)
- [p] PASS / FAIL
- Steps: Restart setup. Set both ships to Human.
- Expected: Game prompts each player in turn for declarations.
- Notes: _______________

### T-UI-08: Starting range band selection
- [p] PASS / FAIL
- Steps: During setup, choose a starting range band (e.g., "extreme").
- Expected: Engagement display shows the selected range band.
- Notes: _______________

---

## 2. Display Layout

### T-UI-09: Ship status table displays correctly
- [p] PASS / FAIL
- Steps: Observe the ship status area after setup completes.
- Expected: Each ship shows: faction (color-coded), display name, template name, HP current/max, fDR or "--", wound level (color-coded), active mode if non-standard.
- Notes: _______________

### T-UI-10: Engagement display shows range and advantage
- [f] PASS / FAIL
- Steps: Observe the engagement area.
- Expected: Shows both ship names with range band between them. "No advantage" or advantage indicator.
- Notes: _______________

### T-UI-11: Combat log area is visible and empty at start
- [p] PASS / FAIL
- Steps: Observe the combat log area.
- Expected: Empty or showing "Combat begins" message. Scrollable area is clearly delineated.
- Notes: _______________

### T-UI-12: Input prompt shows which ship is acting
- [p] PASS / FAIL
- Steps: Observe the input prompt at bottom of screen.
- Expected: Clearly shows the ship name and "Choose maneuver" or similar. Unambiguous which ship is being controlled.
- Notes: _______________

### T-UI-13: Terminal size detection works
- [p] PASS / FAIL
- Steps: Resize terminal before launching. Launch game.
- Expected: Layout adapts to available space. No truncated lines or overlapping sections.
- Notes: _______________

### T-UI-14: Colors display correctly
- [p] PASS / FAIL
- Steps: Observe faction colors, wound level colors, combat log event colors.
- Expected: Factions have distinct colors. Wound levels: none=green, minor=yellow, major=orange, crippling+=red. Combat log events color-coded by type.
- Notes: _______________

---

## 3. Declaration Phase

### T-UI-15: Maneuver menu displays all available maneuvers
- [p] PASS / FAIL
- Steps: When prompted for a maneuver, observe the menu.
- Expected: Numbered list of all valid maneuvers for this ship. Invalid maneuvers (e.g., Attack for stall-speed ship) are either absent or marked as unavailable.
- Notes: _______________

### T-UI-16: Pursue/evade intent selection
- [p] PASS / FAIL
- Steps: After selecting a maneuver, observe intent prompt.
- Expected: Asked to choose Pursue or Evade. Default should be sensible for the maneuver (e.g., Evade maneuver defaults to evade intent).
- Notes: _______________

### T-UI-17: Screen clears between human player declarations (hot-seat)
- [p] PASS / FAIL
- Steps: In a 2-human game, make Player 1's declaration. Observe what happens before Player 2's prompt.
- Expected: Screen clears or shows a "Pass to Player 2" message. Player 1's maneuver choice is NOT visible.
- Notes: _______________

### T-UI-18: NPC declaration happens silently
- [p] PASS / FAIL
- Steps: In a human-vs-NPC game, observe the NPC's declaration phase.
- Expected: No prompt for the NPC. NPC's choice is not revealed until resolution. Brief "NPC is deciding..." message or instant skip.
- Notes: _______________

---

## 4. Chase Resolution

### T-UI-19: Chase roll displayed with full detail
- [p] PASS / FAIL
- Steps: Observe the combat log after chase resolution.
- Expected: Shows both ships' effective chase skills, dice rolls, margins, and the winner. All modifiers broken down.
- Notes: _______________

### T-UI-20: Chase outcome choice offered to winner
- [p] PASS / FAIL
- Steps: When a human ship wins by 5+, observe the prompt.
- Expected: Menu offering choices (e.g., "1. Gain Advantage  2. Shift Range 1 Band"). If already advantaged, "Match Speed" offered instead.
- Notes: _______________

### T-UI-21: Range band updates after chase
- [f] PASS / FAIL
- Steps: After a range shift is chosen/applied, observe the engagement display.
- Expected: Range band label updates to new value.
- Notes: This may pass, but the display is scrolling off the screen

### T-UI-22: Advantage indicator updates after chase
- [f] PASS / FAIL
- Steps: After advantage is gained, observe the engagement display.
- Expected: Shows which ship has advantage. If matched speed, shows that too.
- Notes: this may pass, but the status is scrolling off the screen

---

## 5. Attack Resolution

### T-UI-23: Attack roll displayed with full modifier breakdown
- [p] PASS / FAIL
- Steps: Observe the combat log when a ship attacks.
- Expected: Shows: base Gunner skill, range penalty, SM bonus, sensor lock bonus, accuracy bonus, any deceptive penalty, effective skill, dice roll, HIT or MISS, margin of success/failure. Critical success/failure clearly marked if applicable.
- Notes: _______________

### T-UI-24: Defense roll displayed with full breakdown
- [p] PASS / FAIL
- Steps: After a hit, observe the dodge resolution in the combat log.
- Expected: Shows: base dodge (Piloting/2 + Handling), maneuver bonus, other modifiers, effective dodge, dice roll, DODGE or HIT, margin.
- Notes: _______________

### T-UI-25: Damage displayed with pipeline breakdown
- [p] PASS / FAIL
- Steps: After a successful hit that isn't dodged, observe damage resolution.
- Expected: Shows: raw damage rolled, force screen absorption (if any), remaining fDR, hull DR, armor divisor application, penetrating damage, wound level determined. Each step visible.
- Notes: _______________

### T-UI-26: Wound level updates in ship status
- [p] PASS / FAIL
- Steps: After a wound is inflicted, observe the ship status table.
- Expected: Wound level updates and color changes appropriately.
- Notes: _______________

### T-UI-27: HP updates after damage
- [p] PASS / FAIL
- Steps: After damage is applied, observe the ship status table.
- Expected: HP shows new current/max value.
- Notes: _______________

---

## 6. Force Screen Behavior

### T-UI-28: Force screen takes ablative damage
- [p] PASS / FAIL
- Steps: Attack a ship with a force screen. Observe fDR in status table.
- Expected: fDR decreases by the damage absorbed. Combat log shows absorption.
- Notes: _______________

### T-UI-29: Force screen regenerates between turns
- [p] PASS / FAIL
- Steps: After a turn where fDR was reduced, observe the status table at the start of the next turn.
- Expected: fDR restored to maximum. Combat log notes "Force screens regenerated".
- Notes: _______________

---

## 7. Combat End

### T-UI-30: Ship destruction displayed
- [f] PASS / FAIL
- Steps: Destroy an enemy ship (may take several turns or use a powerful weapon).
- Expected: Combat log announces destruction. Ship status shows DESTROYED. Ship is removed from future turn declarations.
- Notes: never got this far, but did disable a ton of systems

### T-UI-31: Combat end detected and announced
- [f] PASS / FAIL
- Steps: Destroy the last enemy ship.
- Expected: Game announces combat is over. Shows final status of all ships. Prompts to quit or continue.
- Notes: failed to every destroy ships

### T-UI-32: NPC-vs-NPC combat runs to completion
- [f] PASS / FAIL
- Steps: Start a game with both ships as NPC. Let it auto-resolve.
- Expected: Combat runs turn by turn, combat log scrolls, eventually one ship is destroyed or escapes. End detected.
- Notes: it shows Mortal level of damage, but the combat rages on forever

---

## 8. Help & Navigation

### T-UI-33: Help overlay displays on H key
- [f] PASS / FAIL
- Steps: Press H at any prompt.
- Expected: Overlay appears showing all hotkeys. Press any key to dismiss.
- Notes: there is no time I can access these

### T-UI-34: Ship inspection works on I key
- [f] PASS / FAIL
- Steps: Press I at any prompt, select a ship.
- Expected: Detailed ship stat block displayed: HP, HT, handling, DR, fDR, weapons, traits, modes. Press any key to return.
- Notes: I am only able to select actions 1-15

### T-UI-35: Quit with confirmation on Q key
- [f] PASS / FAIL
- Steps: Press Q at any prompt.
- Expected: "Are you sure you want to quit? (Y/N)" confirmation. Y exits cleanly, N returns to game.
- Notes: I am only able to select action 1-15

---

## 9. Edge Cases

### T-UI-36: Stall-speed ship cannot select Attack maneuver
- [p] PASS / FAIL
- Steps: Control a Javelin (stall speed 35). Observe the maneuver menu.
- Expected: Attack maneuver is either not listed or marked unavailable with explanation.
- Notes: _______________

### T-UI-37: Very long combat log scrolls properly
- [f] PASS / FAIL
- Steps: Play several turns. Observe combat log.
- Expected: New entries appear at bottom. Old entries scroll up. No display corruption.
- Notes: the maneuver menu scrolls what is supposed to be the persistent display off the screen

### T-UI-38: Invalid input handled gracefully
- [p] PASS / FAIL
- Steps: At a menu prompt, type garbage (letters when numbers expected, out-of-range numbers).
- Expected: Error message displayed. Re-prompts. No crash.
- Notes: this works: Invalid Choice. Enter 1-15.

### T-UI-39: NPC ship makes reasonable decisions
- [p] PASS / FAIL
- Steps: Play a human ship vs NPC. Observe NPC behavior over 5+ turns.
- Expected: NPC pursues, attacks when advantaged, evades when damaged, doesn't do anything obviously stupid. AI reasoning shown in combat log.
- Notes: _______________

### T-UI-40: Combat with ships of very different sizes works
- [p] PASS / FAIL
- Steps: Set up a Javelin (SM 4) vs Sword Battleship (SM 13).
- Expected: Relative size penalties displayed (-10 for capital vs fighter). Damage largely absorbed by force screen. Game doesn't crash on extreme stat differences.
- Notes: _______________

