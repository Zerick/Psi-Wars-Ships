# Web UI API Contract
## Psi-Wars Combat Simulator — Engine/UI Interface Specification

Version: 1.0 (pre-implementation)
Date: 2026-03-15

---

## Overview

The web UI communicates with the engine through a request/response cycle.
The engine advances combat through discrete **states**, pausing at each
**decision point** where a player must make a choice.

The UI never calls engine functions directly. Instead:

1. UI sends a **decision** (JSON dict)
2. Engine processes it and returns the next **state** (JSON dict)
3. UI renders the state and collects the next decision (if needed)
4. Repeat until the turn is complete

---

## Session Lifecycle

### Setup Phase
```
POST /api/session/create
  → Creates a new empty session

POST /api/session/add-faction
  Body: { "name": "Empire", "color": "red" }

POST /api/session/set-relationship
  Body: { "faction_a": "Empire", "faction_b": "Trader", "relationship": "enemy" }

POST /api/session/add-ship
  Body: {
    "template_id": "wildcat_v1",
    "display_name": "Red Fox",
    "faction": "Empire",
    "control": "human",
    "pilot": {
      "name": "Ace McFly",
      "piloting_skill": 16,
      "gunnery_skill": 14,
      "basic_speed": 7.0,
      "is_ace_pilot": true,
      "luck_level": "luck"
    }
  }

POST /api/session/create-engagement
  Body: { "ship_a_id": "ship_1", "ship_b_id": "ship_2", "range_band": "long" }

GET /api/session/state
  → Returns full serialized session (all ships, engagements, factions)
```

### Combat Phase
```
POST /api/turn/begin
  → Returns: TurnState (first decision point or auto-advance)

POST /api/turn/decide
  Body: Decision JSON
  → Returns: TurnState (next decision point or auto-advance)

POST /api/turn/advance
  → Auto-advances through non-decision states (NPC turns, dice rolls)
  → Returns: TurnState
```

---

## TurnState Schema (Engine → UI)

Every response from the engine during combat is a TurnState:

```json
{
  "phase": "AWAITING_DECLARATIONS",
  "status": "Turn 3 begins.",
  "prompt": "Choose maneuver for Red Fox",
  "prompt_type": "maneuver_choice",
  "options": [
    {"key": "attack", "label": "Attack", "enabled": true},
    {"key": "move_and_attack", "label": "Move and Attack", "enabled": true},
    {"key": "evade", "label": "Evade", "enabled": true},
    {"key": "stunt", "label": "Stunt", "enabled": false, "reason": "Stall + opponent advantage"}
  ],
  "ship_id": "ship_1",
  "context": {
    "session": { ... full session state ... },
    "current_ship": { ... serialized ship ... }
  },
  "combat_log_entries": [
    {"message": "═══ TURN 3 ═══", "event_type": "turn", "turn": 3}
  ]
}
```

### Phase Values
| Phase | Needs Decision | Who Decides |
|-------|---------------|-------------|
| AWAITING_DECLARATIONS | Yes (per ship) | Human or NPC |
| RESOLVING_EMERGENCY_POWER | No (auto) | — |
| RESOLVING_CHASE | No (auto) | — |
| CHASE_CHOICE_NEEDED | Yes | Chase winner |
| WEAPON_CHOICE_NEEDED | Yes | Attacker (human) |
| DECEPTIVE_CHOICE_NEEDED | Yes | Attacker (human) |
| RESOLVING_ATTACK | No (auto) | — |
| LUCK_ATTACK_OFFERED | Yes | Attacker (human) |
| LUCK_CRITICAL_OFFERED | Yes | Defender (human) |
| HIGH_G_OFFERED | Yes | Defender (human) |
| RESOLVING_DEFENSE | No (auto) | — |
| LUCK_DEFENSE_OFFERED | Yes | Defender (human) |
| RESOLVING_DAMAGE | No (auto) | — |
| FLESH_WOUND_OFFERED | Yes | Defender (human) |
| NEXT_ATTACKER | No (auto) | — |
| TURN_COMPLETE | No | — |

---

## Decision Schema (UI → Engine)

```json
{
  "decision_type": "maneuver_choice",
  "ship_id": "ship_1",
  "value": {
    "maneuver": "move_and_attack",
    "intent": "pursue",
    "emergency_power": "all_power_to_engines",
    "ep_skill": 14
  }
}
```

### Decision Types

**maneuver_choice**
```json
{ "maneuver": "move_and_attack", "intent": "pursue" }
```

**emergency_power**
```json
{ "option": "all_power_to_engines", "skill_target": 14 }
```

**chase_choice**
```json
{ "choice": "advantage" }
// Options: "advantage", "match_speed", "shift_close", "shift_far", "shift2"
```

**weapon_choice**
```json
{ "weapon_index": 0 }
```

**deceptive_choice**
```json
{ "levels": 2 }
// 0 = no deceptive, 1-3 = levels
```

**high_g_choice**
```json
{ "attempt": true }
```

**luck_reroll**
```json
{ "use_luck": true }
```

**flesh_wound**
```json
{ "use_impulse": true }
```

---

## Serialized Ship Schema

This is what the UI receives for each ship. Every field needed
to render the ship card, status bar, and inspection panel.

```json
{
  "ship_id": "ship_1",
  "template_id": "wildcat_v1",
  "display_name": "Red Fox",
  "faction": "Empire",
  "control": "human",
  "sm": 5,
  "ship_class": "fighter",

  "st_hp": 120,
  "current_hp": 95,
  "wound_level": "minor",
  "is_destroyed": false,
  "ht": "13",

  "hnd": 2,
  "sr": 4,
  "accel": 10,
  "top_speed": 400,
  "stall_speed": 60,

  "dr_front": 50,
  "dr_rear": 25,
  "dr_left": 25,
  "dr_right": 25,
  "dr_top": 25,
  "dr_bottom": 25,

  "fdr_max": 0,
  "current_fdr": 0,
  "force_screen_type": "none",

  "ecm_rating": -4,
  "targeting_bonus": 5,
  "has_tactical_esm": true,
  "has_decoy_launcher": true,

  "disabled_systems": [],
  "destroyed_systems": [],
  "emergency_power_reserves": 0,

  "weapons": [
    {
      "name": "SP74-TR Heavy Plasma Gatling",
      "damage_str": "6d×15(2) burn ex",
      "acc": 6,
      "rof": 8,
      "weapon_type": "beam",
      "armor_divisor": 2.0,
      "mount": "fixed_front",
      "range_str": "3 mi/8 mi",
      "is_explosive": true
    }
  ],

  "pilot": {
    "name": "Ace McFly",
    "piloting_skill": 16,
    "gunnery_skill": 14,
    "basic_speed": 7.0,
    "is_ace_pilot": true,
    "luck_level": "luck",
    "current_fp": 10,
    "max_fp": 10
  }
}
```

---

## Engagement Schema

```json
{
  "ship_a_id": "ship_1",
  "ship_b_id": "ship_2",
  "range_band": "long",
  "advantage": "ship_1",
  "matched_speed": false,
  "hugging": null
}
```

---

## Combat Log Entry Schema

```json
{
  "message": "Red Fox fires SP74-TR Heavy Plasma Gatling at Blue Jay",
  "event_type": "attack",
  "turn": 3
}
```

### Event Types (for UI styling)
| Type | Color/Style |
|------|-------------|
| turn | Bold, yellow border |
| chase | Cyan |
| attack | White/bright |
| defense | Green (success) or Red (fail) |
| damage | Yellow/orange |
| system_damage | Red |
| force_screen | Blue |
| critical_success | Bright green, bold |
| critical_failure | Bright red, bold |
| info | Dim/gray |
| npc_reasoning | Magenta/purple |

---

## Ship Catalog Schema (for setup)

```
GET /api/catalog/ships
→ Returns list of all available ship templates grouped by category:

{
  "categories": [
    {
      "label": "FIGHTERS",
      "ships": [
        {
          "template_id": "javelin_v1",
          "name": "Javelin Class Fighter",
          "sm": 4,
          "ship_class": "fighter",
          "st_hp": 50,
          "top_speed": 600,
          "dr_front": 15,
          "fdr_max": 0,
          "weapon_count": 4
        }
      ]
    }
  ]
}
```

---

## Notes for Web UI Implementation

### Terminal Test Harness
The terminal test script will exercise every UI state by:
1. Creating sessions with specific ship configurations
2. Stepping through turns with predetermined decisions
3. Pausing after each visual state change for human verification

### State Machine Benefits
- The web UI doesn't need to understand GURPS rules
- All rule logic stays in the engine
- The UI just renders states and collects decisions
- Multiple UIs (terminal, web, mobile) share the same engine
- Replay/undo becomes possible by storing decision history

### Real-Time Considerations
For the web UI, the combat log entries should stream to the client
as they're generated (via websocket or SSE), not batched at the end.
The state machine supports this — each advance() call can emit
multiple log entries in the combat_log_entries list.
