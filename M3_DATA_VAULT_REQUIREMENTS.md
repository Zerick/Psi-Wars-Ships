# M3 Data-Vault: Canonical Requirements Specification
## GURPS Psi-Wars Ship Combat Simulator — Persistence & Validation Layer

**Version:** 1.0.0-DRAFT
**Status:** Awaiting owner approval before implementation
**Last Updated:** 2026-03-13

---

## 1. System Overview

The Data-Vault (M3) is the persistence, validation, and data-access layer for a GURPS Psi-Wars space combat simulator. It manages two categories of data:

- **Templates**: Read-only ship blueprints, authored as individual JSON files (the Source of Truth), ingested into a relational database for fast querying.
- **Instances**: Mutable, session-specific ship state (current HP, damaged systems, active mode, etc.) that changes every combat turn.

M3 is **strictly** a data layer. It does not resolve game rules (no 3d6 rolls, no margin-of-success calculations, no chase roll resolution). Those belong to M1 (Psi-Core rules engine). M3 validates, stores, retrieves, and calculates effective stat blocks by applying mode deltas and checking component status.

### 1.1 Technology Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Language | Python 3.11+ | Strict type hinting throughout |
| Validation | Pydantic v2 | All JSON validated before DB insertion |
| ORM | SQLAlchemy 2.0 (or SQLModel) | |
| Database (Dev) | SQLite | Zero-config, file-based |
| Database (Prod) | PostgreSQL | Migration path via SQLAlchemy |
| Testing | pytest | Test suite must pass before implementation is considered complete |

### 1.2 Design Principles

- **JSON-First**: Individual JSON files per ship class are the Source of Truth. The database is a performance and query layer built on top of them.
- **Strict Isolation**: M3 never imports or depends on the rules engine. It exposes data; the engine interprets it.
- **Future-Proofing for Custom Weapons**: The weapon and module systems must support arbitrary weapon definitions and non-standard weapon-to-ship pairings introduced at runtime.

---

## 2. JSON Schema & Pydantic Validation

### 2.1 ShipTemplate Model

The top-level blueprint for a ship class. One JSON file per template.

```
template_id     : str           # PK. Slug identifier, e.g. "javelin_v1", "hornet_v1"
version         : str           # Semver string, e.g. "1.0.0"
name            : str           # Display name, e.g. "Javelin Class Fighter"
faction_origin  : str           # Originating faction tag, e.g. "empire", "trader", "redjack"
sm              : int           # Size Modifier, e.g. 4, 8, 14
ship_class      : str           # Classification tag: "fighter", "striker", "interceptor",
                                #   "corvette", "frigate", "cruiser", "battleship",
                                #   "dreadnought", "carrier", "shuttle", "racer", "yacht", "other"
```

#### 2.1.1 Attributes Block

```
attributes:
  st_hp           : int         # Total Hit Points (always real/tactical scale)
  ht              : str         # Health value as string. Supports suffixes:
                                #   "9f" = fragile, "8x" = explosive/redundant,
                                #   "12" = plain integer stored as string.
                                #   M3 stores and passes through; M1 parses.
  hnd             : int         # Handling modifier
  sr              : int         # Stability Rating
```

#### 2.1.2 Mobility Block

```
mobility:
  accel           : int         # Acceleration (G-equivalent), first number of Move X/Y
  top_speed       : int         # Top speed in mph, second number of Move X/Y
  stall_speed     : int         # Stall speed. 0 = no stall (VTOL capable).
```

#### 2.1.3 Afterburner Block (Optional)

Many ships have afterburners that alter mobility. If present:

```
afterburner:                    # Optional. Null/absent = no afterburner.
  accel           : int         # Afterburner acceleration
  top_speed       : int         # Afterburner top speed
  hnd_mod         : int         # Handling modifier delta (e.g. +1). Default 0.
  fuel_multiplier : float       # Fuel consumption multiplier (typically 4.0)
  range_override  : int | null  # Reduced range in miles if afterburner used continuously
  is_high_g       : bool        # If true, afterburner use always counts as High-G. Default false.
```

#### 2.1.4 Defense Block

```
defense:
  dr_front        : int         # Hull DR from the front
  dr_rear         : int         # Hull DR from the rear
  dr_left         : int         # Hull DR from the left
  dr_right        : int         # Hull DR from the right
  dr_top          : int         # Hull DR from above
  dr_bottom       : int         # Hull DR from below
  dr_material     : str | null  # Material tag for special interactions, e.g.
                                #   "carbide_composite", "nanopolymer", "cerablate", "ema"
                                #   M1 uses this to resolve "double DR vs plasma" etc.
  fdr_max         : int         # Maximum Force Screen DR. 0 = no force screen.
  force_screen_type : str       # "none", "standard", "heavy"
                                #   "heavy" = ignores all armor divisors (capital ships)
                                #   "standard" = ignores plasma/shaped-charge armor divisors
```

Note: Force screen regeneration is a **rule** (regens to full at start of owner's turn), not a per-ship stat. Ships with non-standard regen behavior express this via a trait flag.

#### 2.1.5 Electronics Block

```
electronics:
  ultrascanner_range  : int | null    # Scan range in miles. Null = none.
  targeting_bonus     : int           # Bonus to hit from targeting computer with scan-lock.
                                      # Typically +4 (obsolete) or +5 (standard).
  ecm_rating          : int           # ECM penalty applied to incoming missiles. Negative number.
                                      # e.g. -4. 0 = no ECM.
  night_vision        : int           # Night vision bonus, typically +9
  comm_range          : int | null    # Radio range in miles
  ftl_comm_range      : int | null    # FTL comm range in parsecs. Null = none.
  has_decoy_launcher  : bool          # +1 dodge missiles, +2 jam missiles
  has_tactical_esm    : bool          # +1 dodge missiles
  has_distortion_scrambler : bool     # Can jam comms
  has_neural_interface : bool         # Requires neural interface to pilot
  sensor_notes        : str           # Freeform notes for unusual electronics
```

#### 2.1.6 Occupancy & Location Strings

Stored as raw strings. Parsing is deferred to a utility layer outside M3.

```
occ_raw         : str           # Raw occupancy string, e.g. "1SV", "15ASV", "1ASV+1rx"
loc_raw         : str           # Raw location code, e.g. "g3rR2Wi", "gGs40t"
```

#### 2.1.7 Logistics Block

```
logistics:
  lwt             : float       # Loaded weight in tons
  load            : float       # Cargo capacity in tons
  range_miles     : int | null  # Range in miles. Null = NA (battery/reactor powered).
  cost            : str         # Cost as string to preserve formatting, e.g. "$2M", "$190B"
  hyperdrive_rating : int | null  # Hyperdrive rating. Null = no hyperdrive.
  jump_capacity   : int | null  # Number of hyperspace shunts available
  endurance       : str | null  # Reactor/fuel endurance as freeform string,
                                #   e.g. "24 hours", "50-year lifespan", "1 month"
  signature_cost  : int | null  # Character point cost for Signature Ship advantage
```

#### 2.1.8 Traits List

A list of string tags that encode special properties. M3 stores them; M1 interprets them.

```
traits          : list[str]     # Examples:
                                #   "responsive_structure"
                                #   "unshielded_hyperium"
                                #   "ablative_armor"
                                #   "double_dr_vs_plasma"
                                #   "double_dr_vs_shaped_charge"
                                #   "fragile"
                                #   "explosive_fuel"
                                #   "vtol"
                                #   "neural_interface_required"
                                #   "ejection_seat"
                                #   "trader_tech_penalty"
                                #   "obsolete_electronics"
                                #   "ace_pilot_lucky_break"
```

#### 2.1.9 Modes (Optional)

Ships may have named operational modes that alter their stat block. All mode values are **absolute overrides** — they replace the base stat entirely. If a stat is not mentioned in a mode definition, it inherits unchanged from the base template.

This matches the source material, which almost always expresses modes as full replacement stat lines (e.g., "in high maneuverability mode, handling increases to +7, Move drops to 3/250"). If this approach proves insufficient as we encounter edge cases, it can be revised to support deltas — the modular design makes this a localized change.

```
modes:                          # Optional dict. Key = mode name string.
  "High Maneuverability":       # Example: Hornet
    hnd: 7                      # Override: handling becomes 7
    accel: 3                    # Override: accel becomes 3
    top_speed: 250              # Override: top speed becomes 250
  "Afterburner":                # Example: Javelin
    accel: 30                   # Override: accel becomes 30
    top_speed: 750              # Override: top speed becomes 750
```

#### 2.1.10 Weapon References

Ships reference weapons from a **shared weapon catalog** (see Section 2.3). Many weapons are shared across ship classes (e.g., the B00-M Heavy Plasma Cannon appears on both Wildcats and Nomads, capital-scale cannons appear on multiple capital ships). The catalog is the single source of truth for weapon stats.

```
weapons:                        # list of ShipWeaponMount
  - weapon_ref    : str         # References a weapon_id in the weapon catalog
    mount         : str         # Mount type: "fixed_front", "turret", "rear_turret",
                                #   "wing_left", "wing_right", "spine", etc.
    linked_count  : int         # Number of linked weapons (for ROF calculations). Default 1.
    arc           : str         # Firing arc: "front", "rear", "all", "front_left", etc.
    notes         : str         # Ship-specific notes, e.g. "Double ROF (to 6, +1 to hit)
                                #   in Action vehicular combat scenes"
```

Custom/grafted weapons at runtime are handled via `custom_weapons` on ship instances (see Section 3.3), which store full weapon definitions inline to avoid polluting the catalog with one-off modifications.

#### 2.1.11 Module Slots

Ships with modular hardpoints define their available slots. Each slot has a type and weight class.

```
module_slots:                   # list of ModuleSlot. Empty list = no modularity.
  - slot_id     : str           # Unique within template, e.g. "main_weapon", "wing_left"
    slot_type   : str           # "weapon", "engine", "armor", "accessory", "cargo",
                                #   "fuel", "hardpoint", "electronics"
    weight_class: str           # "light", "heavy", "any" — for stat penalty calculations
    max_weight  : float | null  # Maximum module weight in lbs. Null = no limit.
    notes       : str           # Freeform, e.g. "rated for 1200 lbs"
```

#### 2.1.12 Reserved — Module definitions are in Section 2.4 (shared catalog).

---

### 2.3 Weapon Catalog

Weapons are defined in a **shared catalog** as individual JSON files (one per weapon). Ships reference weapons by `weapon_id`. This avoids duplicating stats for weapons used across multiple ship classes.

```
WeaponDefinition:
  weapon_id     : str           # Unique ID, e.g. "imperial_fighter_blaster",
                                #   "capital_scale_cannon", "boom_heavy_plasma_cannon"
  name          : str           # Display name, e.g. "Imperial Fighter Blaster"
  damage        : str           # Raw GURPS damage string, e.g. "6d×5(5) burn"
  acc           : int           # Accuracy
  range         : str           # Range string, e.g. "2700/8000" or "1 mi/3 mi"
  rof           : str           # Rate of fire as string. "3", "8", "1/3" (once per 3 turns), "20"
  rcl           : int           # Recoil
  shots         : str           # Ammo string, e.g. "200/Fp", "NA", "15/2F", "1"
  ewt           : str           # Emplacement weight, e.g. "1000", "500t", "4000"
  st_requirement: str           # ST requirement, e.g. "75M", "150M", "M"
  bulk          : str           # Bulk value, e.g. "-10", "-15"
  weapon_type   : str           # "beam", "plasma", "missile", "torpedo", "flak", "tractor",
                                #   "mining_laser", "particle"
  damage_type   : str           # "burn", "burn_ex", "cut_inc", "cr_ex", etc.
  armor_divisor : str | null    # e.g. "(5)", "(10)", "(15)", "(2)". Null = none.
  notes         : str           # Freeform rules text, e.g. overheating rules, air-burst option
  tags          : list[str]     # e.g. ["fighter_scale", "capital_scale", "redjack", "imperial"]
  version       : str           # Semver string
```

**Catalog storage**: Weapon JSON files live in a `weapons/` directory alongside the `ships/` directory. The same hash-check sync system applies.

**Catalog DB table**: `weapon_catalog` with `weapon_id` PK, `data_json` blob, `file_hash`, `ingested_at`.

---

### 2.4 Module Catalog

Modules follow the same shared-catalog pattern as weapons. Many modules are reused across ship classes (e.g., the B00-M cannon, ZIP-3R gatling, Silverback force screen, Longstrider fuel module appear on multiple Redjack ships).

```
ModuleDefinition:
  module_id     : str           # Unique ID, e.g. "boom_heavy_plasma_cannon",
                                #   "silverback_force_screen", "longstrider_fuel"
  name          : str           # Display name, e.g. "B00-M Heavy Plasma Cannon Module"
  slot_type     : str           # Must match a slot_type it can be installed in
  weight_class  : str           # "light" or "heavy" — affects ship stat penalties
  weight_lbs    : float         # Actual weight
  cost          : str           # Cost string
  stat_effects  : dict | null   # Stat modifications when installed (override format)
                                # e.g. {"dr_front": 110, "dr_rear": 55, ...}
  weapon_ref    : str | null    # If this module provides a weapon, reference to weapon catalog
  grants_traits : list[str]     # Traits added when installed, e.g. ["force_screen"]
  fdr_provided  : int | null    # If module provides a force screen, its DR value
  notes         : str           # Freeform rules text
  tags          : list[str]     # e.g. ["redjack", "armor", "heavy"]
  version       : str           # Semver string
```

**Catalog storage**: Module JSON files live in a `modules/` directory. Same hash-check sync system.

**Catalog DB table**: `module_catalog` with `module_id` PK, `data_json` blob, `file_hash`, `ingested_at`.

#### 2.1.13 Onboard Craft Complement (Optional)

Capital ships and carriers may have onboard craft.

```
craft_complement:               # list of CraftEntry. Optional.
  - template_ref : str          # References another ShipTemplate by template_id
    count        : int          # Number carried
    notes        : str          # e.g. "5 Prestige-Class Shuttles"
```

#### 2.1.14 Description & Metadata

```
description     : str           # Freeform "Look and Feel" text
tags            : list[str]     # Arbitrary tags for search/filtering,
                                #   e.g. ["empire", "starfighter", "vehicle"]
source_url      : str | null    # URL of the wiki page this data was extracted from
```

---

### 2.2 Validation Rules

The Pydantic model shall enforce:

| Rule | Constraint |
|------|-----------|
| `template_id` | Non-empty string, slug format (lowercase, underscores, digits) |
| `sm` | Integer, typically +3 to +15 |
| `st_hp` | Positive integer |
| `ht` | String matching pattern: digits optionally followed by a single letter suffix (e.g. `"9f"`, `"12"`, `"8x"`, `"14"`) |
| `hnd` | Integer (may be negative for capital ships) |
| `sr` | Positive integer |
| `accel`, `top_speed` | Non-negative integers |
| `stall_speed` | Non-negative integer. 0 = VTOL / no stall. |
| `dr_front`, `dr_rear`, `dr_left`, `dr_right`, `dr_top`, `dr_bottom` | Non-negative integers |
| `fdr_max` | Non-negative integer. 0 = no force screen. |
| `ecm_rating` | Integer, typically 0 to -6 |
| `weapons` | Each mount must have non-empty `weapon_ref` that exists in the weapon catalog, and a valid `mount` |
| `module_slots` | Each slot must have unique `slot_id` within the template |
| `modes` | If present, all referenced stat fields must be valid stat names |
| `version` | Non-empty string |

Invalid JSON must raise a `ValidationError` with clear field-level error messages.

---

## 3. Relational Database Schema (SQLAlchemy)

### 3.1 Table: `ship_templates`

Stores validated template data. Populated by ingesting JSON files.

| Column | Type | Notes |
|--------|------|-------|
| `template_id` | `str` PK | Matches JSON `template_id` |
| `version` | `str` | Template version string |
| `name` | `str` | Display name |
| `data_json` | `TEXT` | Full validated JSON blob (for reconstruction) |
| `file_hash` | `str` | SHA-256 hash of source JSON file |
| `file_modified_at` | `datetime` | Filesystem mtime of source JSON |
| `ingested_at` | `datetime` | When this record was inserted/updated |

**Rationale**: The full JSON is stored as a blob because the template structure is complex and hierarchical (nested weapons, modules, modes). Rather than fully normalizing into dozens of tables, we store the validated blob and use the Pydantic model to deserialize it on read. This keeps the schema simple and maintainable while the game design is still evolving.

### 3.2 Table: `weapon_catalog`

Stores validated weapon definitions from the shared weapon catalog.

| Column | Type | Notes |
|--------|------|-------|
| `weapon_id` | `str` PK | Matches JSON `weapon_id` |
| `name` | `str` | Display name |
| `data_json` | `TEXT` | Full validated JSON blob |
| `file_hash` | `str` | SHA-256 hash of source JSON file |
| `ingested_at` | `datetime` | When this record was inserted/updated |

### 3.3 Table: `module_catalog`

Stores validated module definitions from the shared module catalog.

| Column | Type | Notes |
|--------|------|-------|
| `module_id` | `str` PK | Matches JSON `module_id` |
| `name` | `str` | Display name |
| `data_json` | `TEXT` | Full validated JSON blob |
| `file_hash` | `str` | SHA-256 hash of source JSON file |
| `ingested_at` | `datetime` | When this record was inserted/updated |

### 3.4 Table: `controllers`

Represents players, NPCs, or AI entities that can control ships. This is a **lightweight stub** for M3 purposes — full crew/NPC/player character stat blocks will be developed as a separate module when the rules engine needs them. M3 only needs enough to track who is controlling what and their faction alignment.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | Auto-generated |
| `name` | `str` | Display name |
| `faction` | `str` | Faction alignment tag |
| `is_ace_pilot` | `bool` | Grants Lucky Break and +1 first dodge |
| `crew_skill` | `int` | Default crew skill level (default 12). Used for capital ship crews. |
| `notes` | `str` | Freeform, for any additional context |

### 3.5 Table: `ship_instances`

Live ship state during a combat session. Created by spawning from a template.

| Column | Type | Notes |
|--------|------|-------|
| `instance_id` | `UUID` PK | Auto-generated |
| `template_id` | `str` FK → `ship_templates` | Which blueprint this ship was spawned from |
| `controller_id` | `UUID` FK → `controllers`, nullable | Who's flying it. Null = uncontrolled. |
| `display_name` | `str` | Instance-specific name, e.g. "Red Five" |
| `current_hp` | `int` | Current hit points (initialized from `st_hp`) |
| `wound_level` | `str` | "none", "scratch", "minor", "major", "crippling", "mortal", "lethal" |
| `current_fdr` | `int` | Current force screen DR (initialized from `fdr_max`) |
| `active_mode` | `str` | Currently active mode name, or "standard" |
| `is_disabled` | `bool` | Ship is non-functional but not destroyed |
| `is_destroyed` | `bool` | Ship is destroyed |
| `session_id` | `str` | Groups instances by combat session |
| `installed_modules` | `TEXT` | JSON blob mapping slot_id → module_id for current loadout |
| `custom_weapons` | `TEXT` | JSON list of additional WeaponDefinition objects grafted onto this instance (full inline definitions, not catalog references, to avoid polluting the shared catalog) |

### 3.6 Table: `system_status`

Tracks damage to individual ship subsystems per the Psi-Wars subsystem damage rules.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `int` PK | Auto-increment |
| `instance_id` | `UUID` FK → `ship_instances` | |
| `system_type` | `str` | ENUM: "fuel", "habitat", "propulsion", "cargo_hangar", "equipment", "power", "weaponry", "armor", "controls" |
| `status` | `str` | "operational", "disabled", "destroyed" |

**Note**: The cascade logic (what system takes damage when a system is already destroyed) is a **rules concern** belonging to M1, not M3. M3 only tracks current status. The 3d6 subsystem table and cascade targets are universal rules, not per-ship data.

Each ship instance is initialized with one `system_status` row per system type (all "operational"). The set of system types is universal across all ships.

---

## 4. Core Logic Methods (Data Access Layer)

### 4.1 `ingest_template(json_filepath: Path) -> str`

Reads a JSON file, validates it against the Pydantic ShipTemplate model, computes the file's SHA-256 hash, and performs an UPSERT into `ship_templates`. Returns the `template_id`.

If the hash matches the existing record, the ingestion is skipped (no-op).

Logs: `"Template 'Hornet' ingested (v1.2.0, hash abc123...)"` or `"Template 'Hornet' unchanged, skipping."`

### 4.2 `sync_all_templates(json_directory: Path) -> SyncReport`

Scans a directory for all `*.json` files. For each file, computes the SHA-256 hash and compares against the stored `file_hash`. Only re-ingests files whose hash has changed.

Returns a `SyncReport` dataclass with counts: `added`, `updated`, `unchanged`, `errors`.

### 4.3 `ingest_weapon(json_filepath: Path) -> str`

Same pattern as `ingest_template` but for weapon catalog entries. Validates against `WeaponDefinition`, upserts into `weapon_catalog`. Returns `weapon_id`.

### 4.4 `sync_all_weapons(json_directory: Path) -> SyncReport`

Same pattern as `sync_all_templates` but for the weapons directory.

### 4.5 `ingest_module(json_filepath: Path) -> str`

Same pattern for module catalog entries. Validates against `ModuleDefinition`, upserts into `module_catalog`. Returns `module_id`.

### 4.6 `sync_all_modules(json_directory: Path) -> SyncReport`

Same pattern for the modules directory.

**Design note**: The sync logic should be generic — a single `sync_catalog(directory, validator, table)` internal function that all three catalog types delegate to. This avoids triplicated sync code.

### 4.7 `spawn_ship(template_id: str, controller_id: UUID | None, display_name: str, session_id: str, module_loadout: dict | None = None) -> UUID`

Creates a new `ship_instance` row and associated `system_status` rows. Initializes:

- `current_hp` = template's `st_hp`
- `current_fdr` = template's `fdr_max`
- `wound_level` = "none"
- `active_mode` = "standard"
- `is_disabled` = False
- `is_destroyed` = False
- `installed_modules` = provided loadout or template's default (if any)
- `custom_weapons` = empty list

Returns the `instance_id`.

### 4.4 `get_effective_stats(instance_id: UUID) -> EffectiveStatBlock`

Calculates and returns the ship's **current** effective statistics. Resolution order:

1. Fetch the base template (deserialize `data_json` via Pydantic).
2. If `installed_modules` modifies stats (e.g., engine module changes speed), apply those.
3. If `active_mode` != "standard", apply mode overrides to the stat block.
4. Check `system_status` for disabled/destroyed systems and apply penalties:
   - Propulsion disabled → halve `top_speed`
   - Propulsion destroyed → `top_speed` = 0, `accel` = 0
   - Controls disabled → `hnd` reduced by 2
   - Controls destroyed → ship cannot be controlled
   - Power disabled → flag `half_power` = True
   - Power destroyed → flag `no_power` = True
5. Merge `custom_weapons` with template weapons.
6. Return an `EffectiveStatBlock` dataclass containing all resolved values.

**Note**: Stat penalties from disabled systems are *data-level effects* (simple arithmetic on stat values), not rules resolution. M3 applies them because they affect the stat block. M1 handles the *game-mechanical consequences* (e.g., what "half power" means for force screen regen).

### 4.5 `set_mode(instance_id: UUID, mode_name: str) -> None`

Updates `active_mode` on the ship instance. Validates that the mode name exists in the template's modes dict, or is "standard". Raises `ValueError` for invalid mode names.

### 4.6 `transfer_control(instance_id: UUID, new_controller_id: UUID | None) -> None`

Updates the `controller_id` foreign key. The ship's apparent faction alignment is **always** derived from its current controller, not from the template's `faction_origin`.

### 4.7 `apply_damage(instance_id: UUID, hp_damage: int) -> None`

Reduces `current_hp` by the given amount. Updates `wound_level` based on damage thresholds relative to the template's `st_hp`:

| Wound Level | Damage Threshold (% of max HP) |
|-------------|-------------------------------|
| scratch | < 10% |
| minor | 10% – 49% |
| major | 50% – 99% |
| crippling | 100% – 199% |
| mortal | 200% – 499% |
| lethal | 500%+ |

**Note**: M3 only tracks the wound level and HP. The *consequences* of wound levels (HT rolls, system destruction) are M1's responsibility.

### 4.8 `update_system_status(instance_id: UUID, system_type: str, new_status: str) -> None`

Updates the status of a specific subsystem. Validates that `system_type` and `new_status` are valid enum values.

### 4.9 `apply_fdr_damage(instance_id: UUID, damage: int) -> int`

Reduces `current_fdr` by the given amount (minimum 0). Returns the amount of damage that penetrated through the force screen (i.e., damage beyond what fdr could absorb).

### 4.10 `reset_fdr(instance_id: UUID) -> None`

Restores `current_fdr` to the template's `fdr_max`. Called by M1 at the start of each turn per force screen regen rules.

### 4.11 `install_module(instance_id: UUID, slot_id: str, module_id: str) -> None`

Updates the `installed_modules` JSON for the given instance. Validates that the slot exists in the template and that the module's `slot_type` matches.

### 4.12 `add_custom_weapon(instance_id: UUID, weapon: WeaponEntry) -> None`

Appends a weapon to the instance's `custom_weapons` list. This supports grafting non-standard weapons onto ships.

### 4.13 `export_session_snapshot(session_id: str) -> dict`

Exports all `ship_instances`, their `system_status` rows, and associated `controllers` for the given session as a single JSON-serializable dict. Used for session saving.

### 4.14 `import_session_snapshot(snapshot: dict) -> str`

Recreates all instances, system statuses, and controllers from a previously exported snapshot. Returns the `session_id`.

---

## 5. Hash-Check Sync System

### 5.1 Rationale

The sync system ensures the relational database stays aligned with the JSON Source of Truth files without manual intervention.

- **Modularity**: M3 autonomously monitors its own data. No external module needs to signal "a file changed."
- **Auditability**: SHA-256 hashes provide a cryptographic record of exactly which template version was used in each session.
- **Maintainability**: Eliminates "stale database" bugs where code is correct but the DB has old data.

### 5.2 Behavior

On application startup, `sync_all_templates()` is called automatically. It:

1. Lists all `*.json` files in the configured template directory.
2. For each file, computes SHA-256 of the file contents.
3. Compares against `file_hash` in `ship_templates`.
4. If hashes differ (or no record exists): validates and upserts.
5. If hashes match: skips (fast path).
6. Logs all changes.

### 5.3 Legacy Instance Policy

| Scenario | Behavior |
|----------|----------|
| New ships spawned after template update | Use new template stats |
| Existing active instances | Retain their stats (snapshot at spawn time) |
| Explicit patch command | `patch_instances(template_id)` updates `current_hp` ceiling and other maxima |

---

## 6. Documentation Standards

- Every class and public method must have a docstring.
- All function signatures must use Python 3.11 type hints.
- Complex logic (stat resolution, mode application) must include inline comments explaining the GURPS rule being implemented.
- The module's `__init__.py` must include a module-level docstring explaining M3's role and boundaries.

---

## 7. Mandatory Test Suite (pytest)

Implementation is **incomplete** until all tests pass. Tests are organized by concern.

### 7.1 Ingestion & Validation Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-01 | `test_load_valid_template` | A well-formed ship JSON passes Pydantic validation and returns a ShipTemplate object. |
| T-02 | `test_reject_invalid_template` | A JSON with missing required fields (e.g., no `st_hp`) raises `ValidationError`. |
| T-03 | `test_ht_suffix_acceptance` | HT values `"9f"`, `"8x"`, `"12"`, `"14"`, `"13"` all pass validation. |
| T-04 | `test_ht_suffix_rejection` | HT value `"12z"` or `"abc"` raises `ValidationError`. |
| T-05 | `test_ingest_writes_to_db` | After `ingest_template()`, a matching row exists in `ship_templates` with correct hash. |
| T-06 | `test_ingest_upsert_on_change` | Modifying a JSON file and re-ingesting updates the record (new hash, new `ingested_at`). |
| T-07 | `test_ingest_skip_unchanged` | Re-ingesting an unchanged file is a no-op (same hash, same `ingested_at`). |

### 7.2 Instance Lifecycle Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-08 | `test_spawn_initializes_hp` | `spawn_ship()` creates an instance with `current_hp == template.st_hp`. |
| T-09 | `test_spawn_initializes_fdr` | `spawn_ship()` creates an instance with `current_fdr == template.fdr_max`. |
| T-10 | `test_spawn_creates_system_status` | `spawn_ship()` creates one `system_status` row per system type, all "operational". |
| T-11 | `test_spawn_with_module_loadout` | `spawn_ship()` with a `module_loadout` dict stores it in `installed_modules`. |

### 7.3 Effective Stats Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-12 | `test_base_stats_no_mode` | `get_effective_stats()` on a fresh instance returns base template values. |
| T-13 | `test_mode_override` | Switching a Hornet to "High Maneuverability" mode returns `hnd=7`, `top_speed=250`. |
| T-14 | `test_mode_standard_reset` | Setting mode back to "standard" restores base stats. |
| T-15 | `test_disabled_propulsion_halves_speed` | Disabling propulsion halves `top_speed` in effective stats. |
| T-16 | `test_destroyed_propulsion_zeroes_speed` | Destroying propulsion sets `top_speed` and `accel` to 0. |
| T-17 | `test_disabled_controls_reduces_handling` | Disabling controls reduces `hnd` by 2. |
| T-18 | `test_module_affects_stats` | Installing an engine module that changes speed is reflected in effective stats. |

### 7.4 Controller & Faction Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-19 | `test_controller_assignment` | A ship instance inherits its apparent faction from its controller, not its template. |
| T-20 | `test_transfer_control` | `transfer_control()` changes the controller and thus the apparent faction. |
| T-21 | `test_uncontrolled_ship` | A ship with `controller_id = None` returns faction as "uncontrolled". |

### 7.5 Damage & State Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-22 | `test_wound_level_thresholds` | Applying damage at each threshold boundary produces the correct wound level. |
| T-23 | `test_fdr_absorbs_damage` | `apply_fdr_damage(100)` on a ship with `current_fdr=150` results in `current_fdr=50` and 0 penetrating. |
| T-24 | `test_fdr_penetration` | `apply_fdr_damage(200)` on a ship with `current_fdr=150` results in `current_fdr=0` and 50 penetrating. |
| T-25 | `test_fdr_reset` | `reset_fdr()` restores `current_fdr` to `fdr_max`. |
| T-26 | `test_system_status_update` | `update_system_status("propulsion", "disabled")` sets the correct row. |

### 7.6 Sync & Snapshot Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-27 | `test_hash_sync_detects_change` | Changing a JSON file's content changes its hash; `sync_all_templates()` re-ingests. |
| T-28 | `test_hash_sync_skips_unchanged` | `sync_all_templates()` on unchanged files reports 0 updated. |
| T-29 | `test_session_snapshot_roundtrip` | `export_session_snapshot()` → `import_session_snapshot()` produces identical instance state. |

### 7.7 Custom Weapon Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-30 | `test_add_custom_weapon` | `add_custom_weapon()` adds a weapon visible in `get_effective_stats().weapons`. |
| T-31 | `test_custom_weapon_persists` | Custom weapons survive a session snapshot roundtrip. |

### 7.8 Module Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-32 | `test_install_module_valid_slot` | Installing a weapon module in a weapon slot succeeds. |
| T-33 | `test_install_module_invalid_slot` | Installing a weapon module in an armor slot raises `ValueError`. |
| T-34 | `test_module_weapon_in_effective_stats` | A weapon module's weapon appears in the effective stat block. |

### 7.9 Weapon Catalog Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-35 | `test_ingest_valid_weapon` | A well-formed weapon JSON passes validation and is stored in `weapon_catalog`. |
| T-36 | `test_reject_invalid_weapon` | A weapon JSON missing required fields raises `ValidationError`. |
| T-37 | `test_ship_weapon_ref_resolves` | A ship template's `weapon_ref` correctly resolves to a weapon in the catalog when computing effective stats. |

### 7.10 Module Catalog Tests

| Test ID | Test Name | Asserts |
|---------|-----------|---------|
| T-38 | `test_ingest_valid_module` | A well-formed module JSON passes validation and is stored in `module_catalog`. |
| T-39 | `test_reject_invalid_module` | A module JSON missing required fields raises `ValidationError`. |
| T-40 | `test_module_with_weapon_ref` | A module that provides a weapon correctly resolves its `weapon_ref` from the weapon catalog. |

---

## 8. File Structure

```
m3_data_vault/
├── __init__.py                  # Module docstring, version
├── models/
│   ├── __init__.py
│   ├── template.py              # Pydantic ShipTemplate, ShipWeaponMount, ModuleSlot, etc.
│   ├── weapon.py                # Pydantic WeaponDefinition
│   ├── module.py                # Pydantic ModuleDefinition
│   └── effective_stats.py       # EffectiveStatBlock dataclass
├── db/
│   ├── __init__.py
│   ├── engine.py                # SQLAlchemy engine setup (SQLite/PostgreSQL)
│   ├── tables.py                # Table definitions: ship_templates, weapon_catalog,
│   │                            #   module_catalog, ship_instances, controllers, system_status
│   └── session.py               # Session factory
├── dal/
│   ├── __init__.py
│   ├── ingestion.py             # ingest_template(), ingest_weapon(), ingest_module(),
│   │                            #   sync_all_templates(), sync_all_weapons(), sync_all_modules()
│   ├── instances.py             # spawn_ship(), get_effective_stats(), apply_damage(), etc.
│   ├── controllers.py           # Controller CRUD, transfer_control()
│   └── snapshots.py             # export/import session snapshots
├── sync.py                      # Hash-check sync logic (generic, works for all catalog types)
└── exceptions.py                # Custom exceptions: TemplateNotFoundError,
                                 #   WeaponNotFoundError, ModuleNotFoundError,
                                 #   InvalidModeError, SlotMismatchError, etc.

tests/
├── conftest.py                  # Fixtures: in-memory SQLite, sample JSON for all catalogs
├── test_validation.py           # T-01 through T-07
├── test_instances.py            # T-08 through T-11
├── test_effective_stats.py      # T-12 through T-18
├── test_controllers.py          # T-19 through T-21
├── test_damage.py               # T-22 through T-26
├── test_sync.py                 # T-27, T-28
├── test_snapshots.py            # T-29
├── test_custom_weapons.py       # T-30, T-31
├── test_modules.py              # T-32 through T-34
├── test_weapon_catalog.py       # T-35 through T-37
├── test_module_catalog.py       # T-38 through T-40
└── fixtures/
    ├── ships/
    │   ├── javelin_v1.json      # Sample valid template
    │   ├── hornet_v1.json       # Sample with modes and force screen
    │   ├── wildcat_v1.json      # Sample with module slots
    │   └── invalid_ship.json    # Intentionally malformed for rejection tests
    ├── weapons/
    │   ├── imperial_fighter_blaster.json
    │   ├── boom_heavy_plasma_cannon.json
    │   ├── capital_scale_cannon.json
    │   └── invalid_weapon.json
    └── modules/
        ├── silverback_force_screen.json
        ├── longstrider_fuel.json
        └── invalid_module.json
```

**Data directory structure** (the Source of Truth JSON files, separate from code):

```
data/
├── ships/                       # One JSON per ship class
│   ├── javelin_v1.json
│   ├── hornet_v1.json
│   ├── wildcat_v1.json
│   └── ...
├── weapons/                     # One JSON per weapon definition
│   ├── imperial_fighter_blaster.json
│   ├── boom_heavy_plasma_cannon.json
│   ├── capital_scale_cannon.json
│   └── ...
└── modules/                     # One JSON per module definition
    ├── silverback_force_screen.json
    ├── longstrider_fuel.json
    └── ...
```

---

## 9. Resolved Design Decisions

Decisions made during requirements review, recorded for audit trail.

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Mode value semantics: override vs delta? | **All overrides.** | Matches source data format. Easy to change later due to modular design. |
| 2 | Weapon catalog: shared from day one or inline? | **Shared catalog from day one.** | Many weapons are reused across ships (capital cannons, B00-M, ZIP-3R, etc.). |
| 3 | Module catalog: shared from day one or inline? | **Shared catalog from day one.** | Same rationale as weapons. Wildcats, Drifters, Nomads share modules. Treat identically to weapons. |
| 4 | Crew skill on controllers? | **Lightweight stub with `crew_skill` default.** | Real crew/NPC/player stats are a future module. M3 only needs faction and control assignment. |
| 5 | DR facings: 2 or 6? | **Six facings: front, rear, left, right, top, bottom.** | Source material has ships with non-uniform side/rear DR (e.g., Scarab). More facings is more correct and avoids hacks. |
| 6 | Session lifecycle ownership? | **Deferred.** | Not needed for the database or rules modules. Will be resolved when the web layer is designed. |

