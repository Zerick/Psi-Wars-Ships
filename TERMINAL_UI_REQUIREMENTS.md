# Terminal Combat Interface: Requirements Specification
## GURPS Psi-Wars Ship Combat Simulator — UI & Session Layer

**Version:** 1.0.0-DRAFT
**Status:** Awaiting owner review
**Last Updated:** 2026-03-14

---

## 1. System Overview

The Terminal Combat Interface provides a full-screen, color-coded terminal UI for playing GURPS Psi-Wars space combat encounters. It sits on top of the M1 rules engine and M3 data layer, orchestrating multi-ship, multi-faction battles with support for human players, GM-controlled NPCs, and AI-controlled ships.

### 1.1 Architecture

```
┌─────────────────────────────────┐
│  Terminal UI (display + input)  │  ← This document
├─────────────────────────────────┤
│  Game Session Manager           │  ← Turn loop, factions, undo, save
├─────────────────────────────────┤
│  NPC Behavior Module            │  ← AI decision-making for NPCs
├─────────────────────────────────┤
│  M1 Psi-Core (rules engine)     │  ← Combat resolution
├─────────────────────────────────┤
│  M3 Data-Vault (persistence)    │  ← Ship data, state management
└─────────────────────────────────┘
```

### 1.2 Build Order

1. **NPC Behavior Module** — must exist before UI can run NPC ships
2. **Game Session Manager** — orchestrates the full game loop
3. **Terminal UI** — display and input presentation layer

### 1.3 Technology

| Concern | Choice | Notes |
|---------|--------|-------|
| Display | Full-screen buffer redraw | Store screen state in buffer, redraw fully each update |
| Color | ANSI escape codes | Color-code factions, event types, critical rolls |
| Input | Blocking input with menu system | Numbered menus for all choices |
| Terminal | Assume 100+ lines height, 120+ columns width | Degrade gracefully on smaller terminals |
| NPC AI | Priority-based decision tree | Simple but extensible |

---

## 2. Game Modes

### 2.1 Player Configuration

The system supports three modes, selectable at game setup:

| Mode | Description |
|------|-------------|
| **PvP** | Two or more human-controlled factions. NPC factions optional. |
| **Solo** | One human faction vs one or more NPC factions. |
| **Full NPC** | All factions are NPC-controlled. Useful for testing and simulation. |

### 2.2 GM Mode

GM mode is a toggleable setting (on/off). When enabled:
- GM may override the outcome of any roll (set the die result manually)
- GM may manually control any NPC ship's maneuver declaration
- GM may add or remove ships mid-combat
- GM may toggle any ship's mook status
- GM may adjust any ship's state (HP, fDR, system status)

When GM mode is disabled:
- NPC ships are controlled by the AI behavior module
- All rolls resolve automatically
- No manual overrides are possible

### 2.3 Autoplay (NPC AI)

When a ship is NPC-controlled and GM mode is disabled, the AI module
selects maneuvers, targets, and tactical decisions automatically.

**[OPEN QUESTION: NPC AI Behavior Definition]**

The NPC AI needs at minimum:
- **Target selection**: Who to engage (closest enemy? weakest? most dangerous?)
- **Maneuver selection**: Based on ship state, range, advantage
- **Tactical decisions**: When to use emergency power, when to attempt escape
- **Missile/torpedo usage**: When to fire limited-ammo weapons

Proposed v1 AI behavior (simple priority tree):

```
IF ship is crippled or mortally wounded:
    Attempt to escape (Evade maneuver, increase range)
IF ship has stall speed and opponent has advantage:
    Stunt Escape
IF ship has advantage and is at optimal weapon range:
    Attack maneuver
IF ship does not have advantage:
    IF ship is faster: Mobility Pursuit
    IF ship is slower: Stunt (try to gain advantage)
IF at extreme+ range:
    Move (pursue to close distance)
DEFAULT:
    Move and Attack
```

This is intentionally simple. Smarter AI (formation tactics, coordinated attacks, missile timing) can be added incrementally.

---

## 3. Game Setup Phase

### 3.1 Ship Selection

- Present the full ship catalog (40 ships) organized by class
- Player selects ships by number from a menu
- Player assigns each ship to a faction
- Player assigns a display name to each ship
- Player assigns pilot stats (skill levels, perks) or uses defaults
- Player marks ships as mook or named
- No limit on number of ships per side

### 3.2 Faction Configuration

- Each faction has a name and a color (for display)
- Faction relationships are defined as: **allied**, **enemy**, or **neutral**
- Default: two factions, each enemy to the other
- Custom: arbitrary number of factions with arbitrary relationships

**Relationship rules:**
- Allied ships never target each other (the UI prevents it)
- Enemy ships are valid targets
- Neutral ships are not targeted by default
- If a neutral ship attacks another faction, it becomes enemy to that faction automatically
- Accidental friendly fire: **not possible through normal play** — the system prevents targeting allies. However, collateral effects (flak in an area, missed shot hitting hugged ally) follow the existing rules. The combat log clearly marks any allied damage as "FRIENDLY FIRE" in a warning color.

### 3.3 Engagement Setup

- Default starting range band between all enemy pairs (e.g., "long")
- Optional: set specific range bands between specific pairs
- Default facing: neutral (front-to-front)
- Formation assignment: group ships together by designation

### 3.4 Starting Conditions

- All ships start at full HP, full fDR, all systems operational
- Mode set to "standard" unless player specifies otherwise
- Emergency power reserves set to ship's maximum

---

## 4. Turn Flow

### 4.1 Turn Sequence (per Psi-Wars Action Vehicular Combat)

Each turn follows the five-phase structure from M1:

1. **Declaration Phase**: All ships declare maneuvers
2. **Chase Resolution Phase**: Resolve all chase contests
3. **Attack Phase**: Resolve all attacks and defenses
4. **Damage Phase**: Apply all damage, resolve wounds and subsystems
5. **Cleanup Phase**: Force screens regen, advance turn counter

### 4.2 Declaration Order

Per the Psi-Wars rules: higher Basic Speed (or advantaged) declares **second** and resolves **first**. In the hot-seat UI:

- Ships are sorted by declaration order (slower/disadvantaged first)
- Each ship's controller is prompted in order
- **Screen clear between player declarations** so the second player cannot see the first player's choice (hot-seat blind declaration)
- NPC ships declare silently (AI or GM picks, no display until resolution)
- After all declarations are collected, resolution proceeds

### 4.3 Player Decision Points

During resolution, certain outcomes require player choice:

| Decision | When It Occurs | How Handled |
|----------|---------------|-------------|
| Chase outcome choice (advantage vs range shift) | After chase roll | Prompt winner immediately |
| Lucky break usage | After any adverse roll | Prompt: "Use Lucky Break? (Y/N)" |
| Just a Scratch | After taking a wound | Prompt: "Spend CP for Just a Scratch? (Y/N)" |
| Deceptive attack level | During attack declaration | Part of attack options menu |
| Emergency power option | During declaration or as reaction | Menu of available options |
| Targeted system (-5) | During attack declaration | Optional sub-menu |
| Force screen facing | During declaration | Sub-menu if ship has adjustable screen |
| Point defense | When missile incoming | Prompt passengers with PD capability |

For NPC ships, the AI makes these decisions automatically. With GM mode on, the GM is prompted instead.

### 4.4 Undo/Redo System

- The game stores a snapshot of the complete state before each turn
- Snapshots are stored in a list with a position pointer
- **Undo** moves the pointer back one position, restoring that state
- **Redo** moves the pointer forward one position (if available)
- Any new action taken after an undo clears all forward history (same as text editors)
- Multiple undo/redo levels supported
- Undo/redo clears or restores the combat log entries accordingly

---

## 5. Display Layout

### 5.1 Screen Regions

```
┌──────────────────────────────────────────────────────────────────────┐
│ TURN 3                              PSI-WARS COMBAT SIMULATOR       │
├──────────────────────────────────────────────────────────────────────┤
│ SHIP STATUS                                                         │
│ [EMPIRE]  Red Five (Javelin)    HP: 65/80  fDR: --   Wound: Minor  │
│ [EMPIRE]  Gold Two (Peltast)    HP: 85/85  fDR: --   Wound: None   │
│ [TRADER]  Stinger One (Hornet)  HP: 95/95  fDR: 120  Wound: None   │
│ [TRADER]  Wasp (Vespa)          HP: 95/95  fDR: 150  Wound: None   │
├──────────────────────────────────────────────────────────────────────┤
│ ENGAGEMENTS                                                         │
│ Red Five ←[LONG]→ Stinger One   | Red Five has ADVANTAGE           │
│ Gold Two ←[EXTREME]→ Wasp       | No advantage                     │
├──────────────────────────────────────────────────────────────────────┤
│ COMBAT LOG                                                    [3/3] │
│ Red Five fires Imperial Fighter Blaster at Stinger One              │
│   Hit roll: Gunner 14 + Range(-11) + SM(+4) + Lock(+5) + Acc(+9)  │
│   = Effective 21, rolled 9 → HIT (margin +12)                      │
│ Stinger One attempts dodge                                          │
│   Dodge: Pilot(7) + Hnd(+6) + Evade(+2) = 15, rolled 13 → DODGE  │
│ Gold Two fires at Wasp — MISS (effective 12, rolled 15)            │
│                                                                      │
│                                                                      │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│ > Red Five: Choose maneuver [1-15] or [H]elp [I]nspect [Q]uit      │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Ship Status Table

For each ship, display in a single line:
- Faction tag (color-coded)
- Display name (ship template name in parentheses)
- HP: current/max
- fDR: current value or "--" if no force screen
- Wound level (color-coded: none=green, minor=yellow, major=orange, crippling+=red)
- Active mode (if not "standard")
- Disabled systems (if any, abbreviated)

### 5.3 Engagement Map

For each engagement pair:
- Ship names with range band between them
- Who has advantage (and matched speed if applicable)
- Facing indicators if relevant

### 5.4 Combat Log

- Scrolling region showing detailed resolution of each action
- Color-coded by event type:
  - **Chase rolls**: cyan
  - **Attack rolls**: yellow
  - **Defense rolls**: green
  - **Damage**: red
  - **System damage**: bright red
  - **Force screen**: blue
  - **Electronic warfare**: magenta
  - **Friendly fire**: bright yellow on red background (warning)
  - **Critical success**: bright green, bold
  - **Critical failure**: bright red, bold
- Shows full modifier breakdown for every roll
- Shows dice values, margin of success/failure, critical detection

### 5.5 Input Area

- Always at the bottom of the screen
- Shows which ship is currently being prompted
- Menu-driven numbered choices
- Supports single-keypress selection for common actions

### 5.6 Help Overlay

Pressing `H` at any prompt displays a hotkey reference overlay:

| Key | Action |
|-----|--------|
| H | Show/hide this help |
| I | Inspect a ship's full stat block |
| L | Scroll combat log up/down |
| U | Undo last turn |
| Ctrl+R | Redo undone turn |
| S | Save game state |
| G | Toggle GM mode |
| M | Toggle mook status on a ship |
| A | Add a ship mid-combat |
| R | Remove a ship from combat |
| Q | Quit (with confirmation) |

---

## 6. Ship Inspection View

Pressing `I` then selecting a ship shows a detailed overlay:

```
┌─ SHIP INSPECTION: Stinger One (Hornet-Class Interceptor) ──────────┐
│ Faction: TRADER          SM: 4         Class: Interceptor           │
│ HP: 95/95    HT: 13     Handling: +6   SR: 3                       │
│ Move: 15/500  Stall: 0 (VTOL)  Afterburner: None                  │
│                                                                      │
│ DEFENSE                                                              │
│ DR: F:10 R:10 L:10 R:10 T:10 B:10  Material: nanopolymer          │
│ fDR: 150/150 (standard)                                             │
│                                                                      │
│ ELECTRONICS                                                          │
│ ECM: -4  Scanner: 30mi  Targeting: +5  ESM: Yes  Decoy: No        │
│                                                                      │
│ WEAPONS                                                              │
│ 1. Muonic Fighter Cannon (×2 linked) [fixed front]                 │
│    6d×5(10) burn  Acc 9  ROF 8  Range 1mi/3mi                     │
│ 2. Particle Cannon Stinger [fixed front]                            │
│    6d×15(15) burn  Acc 9  ROF 1/3  Range 1mi/3mi                  │
│                                                                      │
│ SYSTEMS: All Operational                                             │
│ TRAITS: configurable_wings, vtol, trader_tech_penalty               │
│ MODES: High Maneuverability (hnd:7, accel:3, top_speed:250)        │
│                                                                      │
│ [Press any key to return]                                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 7. NPC Behavior Module

### 7.1 AI Decision Framework

The NPC AI operates on a simple priority-based decision tree. Each NPC ship evaluates its situation and picks the highest-priority applicable action.

### 7.2 Target Selection

NPCs select targets based on:
1. **Already engaged**: Continue engaging current target unless it's destroyed/escaped
2. **Threat assessment**: Prefer targeting ships that are targeting allies
3. **Opportunity**: Prefer weakened ships (damaged, low fDR)
4. **Proximity**: Prefer closer range bands
5. **Class matching**: Fighters prefer fighters, capitals prefer capitals (unless no choice)

### 7.3 Maneuver Selection (Priority Tree)

```
1. IF ship is crippled+ wounded AND escape is possible:
     → Evade (attempt escape)

2. IF ship has stall speed AND opponent has advantage:
     → Stunt Escape

3. IF ship has advantage AND at good weapon range (long or closer):
     → Attack (if no stall speed) or Move and Attack

4. IF ship has matched speed:
     → Attack (maximize damage output with accuracy bonus)

5. IF no advantage AND ship is faster than opponent:
     → Mobility Pursuit (try to gain advantage through speed)

6. IF no advantage AND ship is slower:
     → Stunt (try to gain advantage through maneuver)

7. IF range is extreme or farther:
     → Move (pursue, close distance)

8. IF ship has force screen AND screen is depleted:
     → Evade for one turn (let screen regen)

9. DEFAULT:
     → Move and Attack (pursue)
```

### 7.4 Tactical Decisions

| Decision | NPC AI Behavior |
|----------|----------------|
| Chase outcome choice | Prefer advantage if not already advantaged. If advantaged, prefer match speed. Otherwise shift range toward optimal weapon range. |
| Lucky break | Never use (NPC mooks don't have them; named NPCs use on mortal+ wounds) |
| Emergency power | Use "All Power to Engines" if losing chase contests. Use "Emergency Screen Recharge" if screen depleted and under fire. Use "Emergency Evasive" if facing a critical incoming attack. |
| Deceptive attack | Use if effective skill is 14+ (can afford -2 and still hit reliably) |
| Targeted system | Randomly target systems only if effective skill is 16+ |
| Missile usage | Fire missiles at extreme+ range. Save torpedoes for matched speed or close range. |
| Point defense | Always attempt if available |
| Force screen facing | Focus toward the most dangerous attacker |

### 7.5 NPC Personality Variants (Future)

Eventually, different NPC types could have different AI profiles:
- **Aggressive**: Always pursue, prefer Attack maneuver, liberal emergency power use
- **Defensive**: Prefer Evade, disengage when damaged, conservative
- **Tactical**: Use formations, coordinate attacks, exploit flanking
- **Reckless**: Mook behavior — charge in, never retreat, ram if possible

For v1, all NPCs use the same standard priority tree.

---

## 8. Game Session Manager

### 8.1 Session State

The session manager tracks:
- All ships and their current state (via M3)
- All engagement pairs and their state (via M1 combat_state)
- Faction definitions and relationships
- Turn counter
- Undo history (stack of state snapshots)
- GM mode toggle
- Per-ship control mode (human / AI / GM)

### 8.2 Session Lifecycle

```
Setup → [Turn Loop] → End
         ↑        ↓
         └─ Undo ─┘
```

**Setup**: Ship selection, faction config, engagement setup
**Turn Loop**: Declaration → Resolution → Display → (Player choices) → Next turn
**End**: All enemies destroyed, all enemies escaped, or player quits

### 8.3 Mid-Combat Actions

Available at any prompt via hotkeys:
- Add ship (reinforcements arrive)
- Remove ship (voluntary retreat / narrative exit)
- Toggle mook status
- Toggle GM mode
- Save state
- Undo turn
- Inspect ship
- Quit

---

## 9. Resolved Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Menu-driven input, not command-line parsing | Easier for players unfamiliar with the system |
| 2 | Full-screen buffer redraw, not curses | Simpler, portable, matches owner's preferred approach |
| 3 | ANSI colors for faction and event coding | Modern terminals all support this |
| 4 | Screen clear between player declarations | Hot-seat blind declaration for fairness |
| 5 | NPC AI is a simple priority tree for v1 | Extensible later without rewriting the UI |
| 6 | Undo stores full state snapshots | Simple implementation, multi-level undo |
| 7 | Accidental friendly fire prevented by targeting rules | System won't let you target allies; collateral follows existing combat rules |
| 8 | All modifier breakdowns shown in combat log | Helps players learn and verify the GURPS math |
| 9 | GM mode is a toggle, not a separate game type | Flexibility to switch mid-session |

---

## 10. Resolved Open Questions

| # | Question | Resolution |
|---|----------|------------|
| 1 | Engagement pairing | Persistent but switchable. Each ship declares a target with its maneuver. Switching targets loses advantage on previous target. Written for ease of change. |
| 2 | Passenger actions | Single "crew actions" submenu listing all available actions with numbered choices. |
| 3 | Formation management | Dedicated menu option: "Form up with [allied ships]" / "Break formation". Formation benefits displayed as a reminder when forming up. |
| 4 | Combat end conditions | Auto-detect when all enemies destroyed/escaped. Prompt GM to end combat or continue. |
| 5 | Terminal size detection | Auto-detect via os.get_terminal_size(). Adapt layout to available space. Minimum 80×24. |

---

## 11. Implementation Plan

### Phase 1: NPC Behavior Module
- Build `npc_ai.py` in m1_psi_core
- Implement target selection, maneuver selection, tactical decisions
- Test with mock scenarios (no UI needed)

### Phase 2: Game Session Manager
- Build `session.py` as a new module
- Implement setup flow, turn loop, faction management, undo
- Integrate with M1 engine and M3 data layer
- Test the full game loop programmatically (no display)

### Phase 3: Terminal UI
- Build `terminal_ui.py`
- Implement screen buffer, layout regions, color system
- Wire up to session manager for display and input
- First playable: 1v1 dogfight (Javelin vs Hornet)

### Phase 4: Polish
- Multi-ship battles
- Formation support
- Full passenger action menus
- Ship inspection overlay
- Save/load
- Help overlay
