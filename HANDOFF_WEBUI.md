# Psi-Wars Combat Simulator — Handoff Document
## For Web UI Development (v0.25 → Web UI Phase)

Date: 2026-03-15
Previous conversation: Full development from v0.1 to v0.25
Transcript: /mnt/transcripts/2026-03-15-09-16-00-psiwars-combat-sim-v018-full-dev.txt

---

## What This Project Is

A GURPS Psi-Wars space combat simulator. Think Star Wars dogfights with
GURPS tabletop rules running underneath. The user (the project owner) is
a GURPS GM who runs a Psi-Wars campaign. He wants a tool to simulate
vehicular combat — first as a terminal prototype (done), then as a web UI
(next phase).

The setting is "Psi-Wars" — a fan-made GURPS space opera setting with
its own vehicle rules layered on top of GURPS Action 2: Exploits chase
rules. The rules document is in the project files as an RTF.

---

## What's Been Built

### Raspberry Pi Setup
- **Path:** `/home/psiwars/psi-wars/`
- **Git repo:** Active, user runs custom `push` script
- **Python env:** venv at `/home/psiwars/psi-wars/venv/`
- **Launch terminal UI:** `python -m psi_wars_ui`
- **Run tests:** `python -m pytest tests/ tests_m1/ -q`
- **pyproject.toml** at project root with `--import-mode=importlib`

### Architecture (Three Layers)

```
┌─────────────────────────────────────────────┐
│  UI Layer (psi_wars_ui/)                    │  Terminal UI — will be replaced/supplemented
│  - game_loop.py (1060 lines, imperative)    │  by web UI. Calls engine through state machine.
│  - renderer.py, display.py, input_handler.py│
│  - setup.py (ship catalog, pilot config)    │
└─────────────┬───────────────────────────────┘
              │ calls
┌─────────────▼───────────────────────────────┐
│  Engine Layer (m1_psi_core/)                │  21 modules, 5844 lines
│  - engine.py — pipeline orchestrator        │  PURE FUNCTIONS. No state mutation.
│  - dice.py, combat_state.py, maneuvers.py   │  Returns dataclasses.
│  - attack.py, defense.py, damage.py         │  All randomness via DiceRoller.
│  - chase.py, subsystems.py, special.py      │  
│  - npc_ai.py, emergency_power.py            │
│  - session.py — game state management       │
│  - serialization.py — JSON export (NEW)     │
│  - turn_state_machine.py — phases (NEW)     │
└─────────────┬───────────────────────────────┘
              │ reads
┌─────────────▼───────────────────────────────┐
│  Data Layer (tests/fixtures/)               │  JSON files are source of truth
│  - 40 ships, 48 weapons, 12 modules        │  SQLite is performance layer (M3)
│  - Each ship has: stats, weapons, class     │
└─────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Pipeline architecture.** `engine.py` functions (`resolve_chase`, `resolve_attack`, 
   `resolve_defense`, `resolve_damage`) take inputs, return structured dataclasses, 
   and NEVER mutate state. The game loop applies state changes.

2. **All randomness through DiceRoller.** Seeded for deterministic testing via `MockDice`.

3. **JSON is source of truth.** Ship/weapon/module data lives in JSON fixtures. The M3 
   SQLite database is a performance cache, not authoritative.

4. **Handling adds to chase rolls** (confirmed by owner). Vehicular dodge = Piloting/2 + Handling.

5. **Ship classification is manual.** Each ship JSON has a `ship_class` field 
   ("fighter"/"corvette"/"capital") set by hand based on how the ship handles in RAW, 
   not computed from SM. This matters for the -5/-10 relative size penalty.

6. **Luck ≠ Lucky Break.** Luck is the GURPS advantage (reroll dice, real-time cooldown 
   1hr/30min/10min). Lucky Break is a narrative mechanic (Ace Pilots get 1 free per chase, 
   enables maneuvers needing "suitable scenery").

### Test Status: 568 tests, 0 failures

```
tests/          — M3 data vault tests (65 tests)
tests_m1/       — M1 engine tests (~503 tests)
  test_chase.py, test_attack.py, test_defense.py, test_damage.py
  test_facing.py, test_combat_rules.py, test_subsystems.py
  test_v015_batch.py, test_v020_coverage.py
  test_emergency_power_pipeline.py, test_serialization.py
  ... and 17 more test files
```

### What's Working in Combat

- Chase quick contests with proper outcome options (0-4, 5-9, 10+)
- Facing enforcement (fixed weapons need correct facing, advantage targets rear)
- Force screens: hardened 1, plasma AD negation, heavy screen rules
- Matched Speed: full accuracy on Move and Attack
- Speed penalty in range calculation (max of range/own speed/opponent speed)
- Wound accumulation with HT rolls (repeated wounds escalate)
- Crippling/mortal HT rolls to remain operational
- Subsystem cascade mechanic
- Stall speed chase attack restriction
- Weapon range enforcement (supports mile notation)
- Multiple weapon selection per ship
- Deceptive attacks (shows effective skill at each level, only on attack maneuvers)
- Emergency power: 6 options with skill rolls, redline HT cost, critical failure consequences
- Luck advantage with real-time cooldown (configurable per pilot)
- Lucky Break tracking (Ace Pilots get 1 free per chase)
- Flesh Wound / Impulse points
- NPC AI with priority tree and smart weapon selection
- NPC High-G decision making (weighs FP cost vs threat)
- Combat end summary screen
- Real weapon data loaded from 48 weapon JSON files
- Correct sensor lock bonus per ship (+4 obsolete, +5 standard)
- ROF bonus per GURPS B373 rapid fire table

---

## Web UI Prep (What's Ready)

### State Machine (`turn_state_machine.py`)
Defines all combat phases as discrete states:
```
AWAITING_DECLARATIONS → RESOLVING_CHASE → CHASE_CHOICE_NEEDED → 
RESOLVING_ATTACK → WEAPON_CHOICE_NEEDED → DECEPTIVE_CHOICE_NEEDED →
LUCK_ATTACK_OFFERED → LUCK_CRITICAL_OFFERED → HIGH_G_OFFERED → 
RESOLVING_DEFENSE → LUCK_DEFENSE_OFFERED → RESOLVING_DAMAGE → 
FLESH_WOUND_OFFERED → NEXT_ATTACKER → TURN_COMPLETE
```

Each state is a `TurnState` dataclass with: phase, status, prompt, prompt_type, 
options, context, ship_id, combat_log_entries. Serializes to JSON via `to_dict()`.

The UI sends back a `Decision` dataclass with: decision_type, value, ship_id.

**Note:** The actual TurnResolver class that walks through these states has NOT 
been implemented yet. The state definitions and data contracts are ready. The 
resolver needs to be built — it will replace the imperative game_loop.py logic 
with a pausable state machine.

### Serialization (`serialization.py`)
Complete JSON serialization for:
- Ships (all stats, weapons, pilot, subsystem damage, EP reserves)
- Engagements (range, advantage, matched speed)
- Full session snapshots
- Attack/defense/damage/chase results
- Combat log entries

All verified with tests — round-trips through JSON cleanly.

### API Contract (`WEB_UI_API_CONTRACT.md`)
Complete specification of:
- Session lifecycle endpoints
- TurnState schema (engine → UI)
- Decision schema (UI → engine)
- Serialized ship/engagement/log schemas
- Event type color mapping
- Ship catalog schema for setup screen

---

## Web UI Development Roadmap

### Phase 1: Web Server Setup
Get the Raspberry Pi serving a basic web page. The machine already hosts 
other services — need to discover what's running and set up alongside them 
without breaking anything. Likely nginx reverse proxy + a Python web framework 
(Flask/FastAPI) on a separate port.

### Phase 2: UI Skeleton with Mock Data
Build visual components using hardcoded JSON matching the API contract:
- Ship status cards (HP bar, DR, fDR, wound level, subsystem status)
- Engagement display (range band, advantage indicator, matched speed)
- Combat log (scrolling event feed with color-coded entries)
- Maneuver selection menu
- Dice roller display (3d6 with animation)
- Weapon selection panel
- Chase outcome chooser
- Emergency power menu
- Ship catalog/setup screen

Use static mock data — no engine integration yet.

### Phase 3: Terminal Test Harness
A script that drives the web UI through every visual state:
- "Adding a Wildcat to the Empire faction..." → verify ship card appears
- "Setting HP to 20%..." → verify HP bar changes color
- "Disabling propulsion..." → verify ↓prop indicator appears
- "Rolling attack: 8 vs skill 14, HIT..." → verify combat log entry
- Each state change pauses for human feedback

The harness communicates with the web UI the same way the engine will — 
through the serialized JSON API. This means the test harness IS the mock 
backend.

### Phase 4: Dice Roller Integration
Animated 3d6 display connected through the harness. Trigger rolls, 
see them animate, verify the result displays correctly.

### Phase 5: Chat/Combat Log Window
The combat log as a rich, scrollable feed with:
- Color-coded entries by event type
- Turn separators
- Expandable damage breakdowns
- Dice roll details

### Phase 6: Engine Integration (Last)
Replace the test harness mock backend with the real engine:
- Build the TurnResolver state machine
- Connect it to the web API endpoints
- The UI doesn't change — it's already tested against the same JSON format

---

## Known Issues / Things to Fix

1. **Ship data not fully verified.** Only the Wildcat has been line-by-line 
   verified against RAW text. The owner plans to provide plain text versions 
   of all 40 ship PDFs for verification.

2. **The game_loop.py is imperative.** The `_attack_damage_phase` method is 
   ~200 lines of nested conditionals. When the TurnResolver is built, this 
   logic should be decomposed into the state machine's step functions.

3. **Speed penalty might feel wrong in play.** Fast fighters (Tempest at 800) 
   get -17 range penalty at Long range instead of -11. This is RAW but the 
   owner noted "we may have ignored speed penalties" in past play. Keep it 
   for now, flag for review if playtesting shows issues.

4. **Emergency power UI asks for skill target number.** The player types their 
   own skill level (from their character sheet) rather than the system tracking 
   which specific Mechanic/Armoury/Electrician specialty applies. This is 
   intentional — keeps it flexible.

5. **No multi-ship combat yet.** The engine supports multiple engagements in 
   theory but the UI and game loop are designed for 1v1. Multi-ship is a 
   future feature.

6. **No missile attack pipeline in the UI.** The engine has missile rules 
   (missile.py, point_defense.py) but they're not wired into the game loop.

---

## Owner's Preferences & Communication Style

- Deeply knowledgeable about GURPS. Will correct rules errors and provide 
  RAW text when needed. Trust his rules knowledge.
- Prefers modular, testable code. Values the pipeline architecture.
- Wants to see every change tested before committing.
- Uses a Raspberry Pi as the development/hosting platform.
- Plans to eventually run AI combat simulations ("data sieve") to optimize 
  NPC behavior based on statistical analysis of thousands of fights.
- Appreciates when things are built independently then composed — hence the 
  "build web UI first, hook engine in last" approach.
- Will provide ship data as plain text when available.
- Runs `push` to commit and push to git after each version.

---

## File Inventory

```
/home/psiwars/psi-wars/
├── m1_psi_core/               # Combat engine (21 modules)
│   ├── engine.py              # Pipeline orchestrator (resolve_*)
│   ├── dice.py                # DiceRoller, damage parsing
│   ├── combat_state.py        # Range bands, speed penalty, engagement state
│   ├── maneuvers.py           # Maneuver catalog and validation
│   ├── attack.py              # Attack modifiers (sensor lock, ROF, etc.)
│   ├── defense.py             # Dodge calculation, High-G
│   ├── damage.py              # Force screens, wound levels, accumulation
│   ├── chase.py               # Chase outcome resolution
│   ├── subsystems.py          # Subsystem damage tracking
│   ├── special.py             # Luck, Lucky Break, ship classification, hugging
│   ├── npc_ai.py              # AI personality tree, weapon selection
│   ├── emergency_power.py     # EP options, skill rolls, redline
│   ├── session.py             # GameSession state management
│   ├── serialization.py       # JSON export for web UI
│   ├── turn_state_machine.py  # State definitions for web UI
│   ├── testing.py             # MockShipStats, MockPilot, MockDice
│   ├── electronic_warfare.py  # Detection, jamming, stealth
│   ├── missile.py             # Missile attack rules
│   ├── point_defense.py       # Point defense interception
│   ├── formations.py          # Formation tactics
│   ├── passengers.py          # Crew actions, boarding
│   ├── events.py              # Event system
│   └── turn_sequence.py       # Turn phase ordering
├── m3_data_vault/             # Database layer (SQLite cache)
├── psi_wars_ui/               # Terminal UI (will keep alongside web UI)
│   ├── game_loop.py           # Main combat loop
│   ├── renderer.py            # Screen buffer, status bar
│   ├── display.py             # ANSI colors, formatting
│   ├── input_handler.py       # Menus, prompts, ship inspection
│   ├── setup.py               # Ship catalog, pilot config
│   └── __main__.py            # Entry point
├── tests/                     # M3 data tests + fixtures
│   └── fixtures/
│       ├── ships/             # 40 ship JSON files
│       ├── weapons/           # 48 weapon JSON files
│       └── modules/           # 12 module JSON files
├── tests_m1/                  # M1 engine tests (28 test files)
├── M1_PSI_CORE_REQUIREMENTS.md
├── M3_DATA_VAULT_REQUIREMENTS.md
├── TERMINAL_UI_REQUIREMENTS.md
├── WEB_UI_API_CONTRACT.md     # ← Key document for web UI phase
├── RULES_AUDIT.md
├── MANUAL_TEST_SCRIPT.md
└── pyproject.toml
```

---

## How to Start the Next Conversation

1. Reference this handoff document
2. First task: investigate the Raspberry Pi's existing web services 
   (what's running on ports 80/443/8080/etc.) to plan the web server setup
3. Then: build the UI skeleton with mock data matching WEB_UI_API_CONTRACT.md
4. Then: build the test harness to iterate on visual states
5. Engine integration comes last

The engine is solid. The data is ready. The API contract is defined. 
The next phase is purely about making it look and feel right in a browser.
