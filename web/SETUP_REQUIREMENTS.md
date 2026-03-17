# Psi-Wars Web UI — Setup Phase Requirements
## v0.5.0 Specification (FINAL DRAFT)

Date: 2026-03-17
Status: FINAL DRAFT — Pending owner sign-off

---

## 1. Overview

The setup phase is where the GM (or all players in GM-less sessions)
prepare the combat scenario: adding ships, configuring factions,
creating engagements, and assigning ships to players.

**Key principle:** Setup is freeform. There is no enforced order.
Ships, factions, engagements, and assignments can be created,
modified, or removed at any time — both during setup AND after
combat has started. The "Start Combat" button transitions the
session status but does not lock anything.

---

## 2. Permissions

| Action                       | GM session (GM) | GM session (Player) | GM-less (any player) |
|------------------------------|:---:|:---:|:---:|
| Add ship from template       | ✓ | ✗ | ✓ |
| Remove ship                  | ✓ | ✗ | ✓ |
| Edit any ship stat           | ✓ (silent) | ✗ | ✓ |
| Edit own ship stats          | ✓ | ✓ | ✓ |
| Set ship display name        | ✓ | own only | ✓ |
| Set ship faction             | ✓ | ✗ | ✓ |
| Set ship pilot details       | ✓ | own only | ✓ |
| Set ship target              | ✓ | own only | ✓ |
| Create/remove factions       | ✓ | ✗ | ✓ |
| Set faction relationships    | ✓ | ✗ | ✓ |
| Assign ship to player        | ✓ | ✗ | ✓ |
| Select own ship (select mode)| n/a | ✓ | ✓ |
| Start combat                 | ✓ | ✗ | ✓ |
| Override NPC targets         | ✓ | ✗ | ✗ |

---

## 3. Ship Management

### 3.1 Adding Ships

- Ships are added from a **template catalog** — all available ship
  classes loaded from JSON fixture files on the server.
- The catalog is grouped by category (Fighters, Interceptors,
  Strikers, Corvettes, Frigates, Cruisers, Capital Ships, Carriers,
  Specialty/Civilian) and shows summary stats per ship.
- Adding a ship from a template creates a new ship instance with all
  stats copied from the template.
- **Defaults on creation:**
  - `display_name`: matches template name (e.g. "Wildcat Class Fighter")
  - `faction`: "NPC Hostiles" (auto-created faction, see §4.1)
  - `control`: "npc"
  - `pilot`: default NPC pilot with all skills at 12, basic_speed 6.0,
    is_ace_pilot false, luck_level "none", max_fp 10
  - `target`: none (no engagement)
  - `player assignment`: none
- The new ship appears immediately as a card in the ship strip.

### 3.2 Ship Customization

After adding a ship, **everything is editable** (by users with
appropriate permissions per §2):

- **Display name** — click to edit (text input).
- **Faction** — dropdown of available factions (see §4).
- **Control mode** — "human" or "npc".
- **Target** — dropdown of other ships in the session. Selecting a
  target creates an engagement (see §5). Clearing the target
  removes the engagement.
- **Pilot block** — name, piloting skill, gunnery skill, basic speed,
  is_ace_pilot, luck_level, max_fp. All click-to-edit.
- **All ship stats** — HP, HT, Hnd, SR, accel, top speed, stall speed,
  all 6 DR faces, fDR max, ECM rating, targeting bonus, etc.
  All click-to-edit (existing v0.3.0 inline edit behavior).
- **Weapons** — display from template. Full weapon editing deferred
  to a later version.
- **Modules** — display from template. Module slot management
  deferred to a later version.

### 3.3 Removing Ships

- Ships can be removed at any time (setup or during combat).
- Removing a ship also:
  - Removes all engagements involving that ship (both as pursuer
    and as target).
  - Unassigns the ship from any player.
  - Removes the ship from any other ship's target (those ships
    revert to no target).
- Confirmation dialog before removal.

### 3.4 Ship Assignment to Players

Two modes (set at session creation, cannot change mid-session):

**GM Assign mode:**
- The GM (or any player in GM-less) assigns a ship to a connected
  player via a dropdown on the ship card.
- A ship can only be assigned to one player at a time.
- A player can control multiple ships.

**Player Select mode:**
- Unassigned ships appear in an "available" pool.
- Players click/select a ship to claim it.
- Once claimed, a ship is removed from the pool.
- The GM/host can unclaim a ship and return it to the pool.

---

## 4. Faction Management

### 4.1 Default Faction

- Every session auto-creates an **"NPC Hostiles"** faction on first
  ship creation.
- All newly added ships default to this faction.
- This faction can be renamed, and its relationships can be changed,
  just like any other faction.

### 4.2 Creating and Removing Factions

- Any user with setup powers can create a new faction (text input +
  color selection from palette).
- Any user with setup powers can remove a faction.
- **When a faction is removed:** ships assigned to that faction keep
  their faction tag but it is flagged as **"orphaned."** An alert is
  shown to all users: "Faction 'X' was removed. N ship(s) still
  reference it: [list]." Users can then reassign those ships or
  leave them.

### 4.3 Faction Relationships

Relationships are **asymmetric (directional)**. Each ordered pair
`(Faction A → Faction B)` has its own relationship:

| Relationship | Meaning |
|-------------|---------|
| **Hostile** | Faction A considers Faction B an enemy. NPC ships of Faction A will auto-target Faction B ships (once engine is wired in). |
| **Neutral** | Faction A has no strong stance toward Faction B. Targeting Faction B ships triggers a one-time warning. |
| **Friendly**| Faction A considers Faction B an ally. Targeting Faction B ships triggers a one-time warning. |

- Relationships are **per-direction**: Empire→Alliance can be
  "hostile" while Alliance→Empire is "neutral."
- Default relationship for new factions: Neutral in both directions
  toward all existing factions.
- The UI displays the relationship as a matrix or paired list showing
  both directions.

### 4.4 Relationship Auto-Escalation (NPC factions)

When a ship belonging to Faction A attacks a ship belonging to NPC
Faction B, and Faction B's outgoing relationship toward Faction A is
**friendly or neutral**, the relationship auto-escalates:

- Friendly → Neutral (on first attack)
- Neutral → Hostile (on subsequent attack)

This only applies to NPC-controlled factions. Player-controlled
factions do not auto-escalate (the players decide their own stance).

The GM can override any relationship at any time.

### 4.5 Targeting Warnings

When a player assigns a target, the **attacker's outgoing
relationship** toward the target's faction governs warnings:

- **Hostile → no warning.** Expected behavior.
- **Neutral → one-time warning:** "Ship X's faction considers
  [target faction] neutral. Continue targeting?"
- **Friendly → one-time warning:** "Ship X's faction considers
  [target faction] friendly. Continue targeting?"

The warning is per-session, per-attacker-faction, per-target-faction.
Once acknowledged, it does not repeat for that combination.

Players can always target any ship regardless of warnings.
GM can always target any ship without warnings.

### 4.6 Faction Colors

- Each faction has an associated display color for ship name badges,
  card borders, and engagement display.
- Colors are assigned from a preset palette on creation.
- Colors can be changed at any time.

---

## 5. Engagements (Target Assignment)

### 5.1 How Engagements Are Created

There is no separate "create engagement" step. **Setting a ship's
target creates the engagement:**

- On each ship card, there is a **target dropdown** listing all other
  ships in the session.
- Selecting a target creates an engagement between the two ships.
- The user is prompted to set:
  - **Starting range band:** close, short, medium, long, extreme,
    distant, beyond visual (default: long)
  - **Starting advantage:** none (default), or assigned to pursuer
    or target
  - **Matched speed:** yes/no (default: no; only valid if advantage
    is set)

### 5.2 Engagement Rules (from source material)

- **One target per ship:** A ship can only pursue one target at a time.
  If a ship's target is changed, the old engagement is removed and a
  new one is created.
- **No limit on pursuers per target:** Multiple ships can all target
  the same ship. Ship A→C and Ship B→C are both valid, each with
  their own range/advantage state.
- **Mutual pursuit is valid:** Ship A targets Ship B AND Ship B
  targets Ship A. These are two separate engagements, each with
  their own range and advantage. (In practice the engine will resolve
  them as one chase contest, but the data model tracks both.)
- **Pursuit vs evasion is per-turn:** Whether a ship is pursuing or
  evading is declared with the maneuver each turn, not set in the
  engagement. The engagement just tracks which two ships are
  linked and at what range.

### 5.3 Engagement Display

Each engagement shows in the engagement strip:
- Pursuer name → [RANGE BAND] Target name
- Range band color coded (close=red, short=orange, medium=yellow,
  long=blue, extreme=gray, distant=dim, beyond visual=very dim)
- Advantage indicator: arrow toward advantaged ship, or "NO ADV"
- Tags: MATCHED SPD (green), HUGGING (red)
- Ship names colored by faction

### 5.4 Removing Engagements

- Clearing a ship's target removes the engagement.
- Removing a ship removes all its engagements (as pursuer and as
  target of other ships — those other ships revert to no target).

### 5.5 NPC Targeting

- For v0.5.0: NPCs start with no target. The GM can manually assign
  targets to NPC ships at any time.
- Future (engine integration): the engine will auto-select targets for
  NPC ships that don't have a manually assigned target. The GM can
  override engine-selected targets at any time.

---

## 6. UI Layout

### 6.1 No Separate Setup Screen

Setup uses the same combat layout. The ship strip populates as
ships are added. The engagement strip populates as targets are
assigned. The combat log shows setup actions as info entries.

### 6.2 Setup Controls

A **toolbar** above the ship strip contains:
- **Add Ship** button → opens ship template picker (searchable
  dropdown grouped by category)
- **Factions** button → opens faction management panel (create,
  remove, set colors, set relationships)
- **Start Combat** button → transitions to ACTIVE status with
  confirmation and validation warnings

Ship-level controls (target, faction, assignment, remove) live on
each ship card directly.

### 6.3 Ship Card Enhancements

During setup (and combat), ship cards show:
- **Faction badge** (colored label)
- **Target indicator** (target ship name, or "No target")
- **Assigned player name** (or "Unassigned" / "NPC")
- **Control mode badge** (HUMAN / NPC)
- **Remove button** (× icon) for users with setup powers
- Target dropdown, faction dropdown, and player assignment dropdown
  accessible from the card

---

## 7. Combat Transition

### 7.1 Start Combat

- Triggered by the "Start Combat" button.
- Changes session status from SETUP to ACTIVE.
- Turn counter starts at Turn 1.
- Combat log entry: "═══ COMBAT BEGINS ═══"
- **All setup controls remain available.** Ships, factions, targets,
  and assignments can still be modified during combat.

### 7.2 Validation Warnings (non-blocking)

Before starting combat, the UI shows advisory warnings:
- Ships with no target assigned
- Ships with no pilot configured (still default values)
- Ships with no player assigned (in multiplayer)
- Ships in the orphaned "NPC Hostiles" faction that haven't been
  reassigned
- Factions with no relationships defined

These are warnings only. The user can proceed regardless.

---

## 8. Ship Template Catalog

### 8.1 Server-Side

- Templates loaded from JSON fixture files at startup.
- Location: the M3 data vault fixture files, or a dedicated
  `web/ship_templates/` directory.
- REST endpoint: `GET /api/catalog/ships` returns all templates
  grouped by category with summary stats.

### 8.2 Template Categories

Ships are grouped by role/size:
- **Fighters** (SM +4 to +5): Javelin, Flanker, Piranha, Wildcat,
  Valiant, Valkyrie, Drifter
- **Interceptors** (SM +4 to +5): Hornet, Tempest, Vespa
- **Strikers** (SM +5 to +6): Hammerhead, Peltast, Raptor
- **Assault Boats** (SM +5 to +6): Grappler
- **Corvettes** (SM +7 to +8): Skirmisher, Wrangler, Nomad, Toad,
  Tigershark
- **Frigates** (SM +8 to +9): Scarab, Lancer
- **Cruisers** (SM +9 to +10): Kodiak, Regal, Dominion, Executioner
- **Capital Ships** (SM +10+): Sword, Imperator, Spire
- **Carriers** (SM +9+): Arcana, Raider, Mauler, Legion
- **Specialty/Civilian**: Fugitive, Prestige, High Roller, Gypsy Moth,
  Trader Ark, Trader Ark Tender

### 8.3 Template Summary (shown in picker)

Each template in the picker shows: name, SM, ship_class, ST/HP,
top speed, DR (front), fDR max, weapon count, and a one-line
description if available.

---

## 9. Data Model Changes

### 9.1 Session State Additions

```
factions: [
  {
    "name": "NPC Hostiles",
    "color": "#f87171",
    "is_default": true
  },
  {
    "name": "Empire",
    "color": "#60a5fa",
    "is_default": false
  }
]

faction_relationships: {
  "Empire→Pirates": "hostile",
  "Pirates→Empire": "hostile",
  "Empire→NPC Hostiles": "hostile",
  "NPC Hostiles→Empire": "hostile"
}

targeting_warnings_acknowledged: [
  "Alliance→NPC Hostiles"
]
```

### 9.2 Ship Data Additions

Each ship gains:
```
"target_id": "ship_2" | null,
"assigned_player": "Alice" | null,
"control": "human" | "npc"
```

### 9.3 Engagement Model Change

Engagements are **derived from target assignments**, not stored
independently. When Ship A has `target_id: "ship_2"`, an engagement
exists between Ship A and Ship 2. The engagement's range/advantage
state is stored in a separate engagement record keyed by pursuer→target:

```
engagements: {
  "ship_1→ship_2": {
    "range_band": "long",
    "advantage": null,
    "matched_speed": false,
    "hugging": false
  }
}
```

This replaces the v0.3.0 engagement list. The engagement strip
renders from this map, and clearing a ship's target_id removes the
corresponding entry.

---

## 10. Version History

| Version | Date       | Status |
|---------|------------|--------|
| 0.5.0   | 2026-03-17 | FINAL DRAFT |
