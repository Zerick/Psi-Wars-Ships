"""
combat_manager.py  —  Psi-Wars Slice 3 v2
Combat turn engine: range matrix, player-driven dice rolls, no GM review mode.
Follows same aiosqlite patterns as scenario_manager.py.
"""

import json
import uuid
import random
from typing import Optional

import aiosqlite


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row) -> dict:
    return dict(row)


def _roll_3d6() -> int:
    return random.randint(1, 6) + random.randint(1, 6) + random.randint(1, 6)


def _roll_1d6() -> int:
    return random.randint(1, 6)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Each statement run separately so ALTER TABLE failures (column exists) are
# swallowed gracefully.

_ALTER_COLUMNS = [
    ("pilots", "basic_speed",         "INTEGER NOT NULL DEFAULT 6"),
    ("pilots", "initiative_modifier", "INTEGER NOT NULL DEFAULT 0"),
    ("pilots", "faction",             "TEXT NOT NULL DEFAULT 'player'"),
    ("ships",  "initiative_modifier", "INTEGER NOT NULL DEFAULT 0"),
]

_COMBAT_TABLES = [
    # Core combat record — no gm_review_rolls column
    """CREATE TABLE IF NOT EXISTS combats (
        combat_id             TEXT PRIMARY KEY,
        scenario_id           TEXT NOT NULL REFERENCES scenarios(scenario_id),
        status                TEXT NOT NULL DEFAULT 'active',
        current_round         INTEGER NOT NULL DEFAULT 1,
        current_phase         TEXT NOT NULL DEFAULT 'setup',
        initiative_roll_style TEXT NOT NULL DEFAULT 'stat_only',
        created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Fixed initiative order for the whole combat
    """CREATE TABLE IF NOT EXISTS combat_initiative (
        initiative_id    TEXT PRIMARY KEY,
        combat_id        TEXT NOT NULL REFERENCES combats(combat_id),
        ship_id          TEXT NOT NULL REFERENCES ships(ship_id),
        initiative_value INTEGER NOT NULL,
        initiative_roll  INTEGER,
        turn_order       INTEGER NOT NULL,
        has_acted        BOOLEAN NOT NULL DEFAULT 0
    )""",

    # Range matrix — one row per ship pair, ship_a_id < ship_b_id lexicographically
    """CREATE TABLE IF NOT EXISTS combat_ranges (
        range_id          TEXT PRIMARY KEY,
        combat_id         TEXT NOT NULL REFERENCES combats(combat_id),
        ship_a_id         TEXT NOT NULL REFERENCES ships(ship_id),
        ship_b_id         TEXT NOT NULL REFERENCES ships(ship_id),
        range_band        TEXT NOT NULL DEFAULT 'medium',
        advantage_ship_id TEXT,
        matched_speed     BOOLEAN NOT NULL DEFAULT 0,
        facing_a_to_b     TEXT NOT NULL DEFAULT 'F',
        facing_b_to_a     TEXT NOT NULL DEFAULT 'F',
        UNIQUE(combat_id, ship_a_id, ship_b_id)
    )""",

    # Per-round, per-ship declarations
    # chase_resolution_choice is nullable now; Slice 4 will populate it
    # when we add winner-choice UI (advantage vs range shift at 5-9)
    """CREATE TABLE IF NOT EXISTS combat_declarations (
        declaration_id        TEXT PRIMARY KEY,
        combat_id             TEXT NOT NULL REFERENCES combats(combat_id),
        ship_id               TEXT NOT NULL REFERENCES ships(ship_id),
        round_number          INTEGER NOT NULL,
        maneuver              TEXT NOT NULL,
        pursuit_target_id     TEXT,
        afterburner_active    BOOLEAN NOT NULL DEFAULT 0,
        active_config         TEXT,
        chase_roll_result     INTEGER,
        chase_mos             INTEGER,
        chase_bonus_used      INTEGER,
        chase_resolution_choice TEXT,
        submitted             BOOLEAN NOT NULL DEFAULT 0,
        revealed              BOOLEAN NOT NULL DEFAULT 0,
        UNIQUE(combat_id, ship_id, round_number)
    )""",

    # Combat actions (attack → defense → damage chain)
    """CREATE TABLE IF NOT EXISTS combat_actions (
        action_id              TEXT PRIMARY KEY,
        combat_id              TEXT NOT NULL REFERENCES combats(combat_id),
        round_number           INTEGER NOT NULL,
        acting_ship_id         TEXT NOT NULL REFERENCES ships(ship_id),
        target_ship_id         TEXT NOT NULL REFERENCES ships(ship_id),
        weapon_id              TEXT,
        action_type            TEXT NOT NULL DEFAULT 'attack',
        called_shot_system     TEXT,
        attack_skill_base      INTEGER,
        attack_modifiers       TEXT,
        attack_total           INTEGER,
        attack_roll            INTEGER,
        attack_hit             BOOLEAN,
        dodge_base             INTEGER,
        dodge_modifiers        TEXT,
        dodge_total            INTEGER,
        dodge_roll             INTEGER,
        dodge_success          BOOLEAN,
        damage_dice            INTEGER,
        damage_mult            INTEGER,
        damage_roll            TEXT,
        damage_raw             INTEGER,
        damage_screen_absorbed INTEGER,
        damage_hull_absorbed   INTEGER,
        damage_net             INTEGER,
        wound_level_before     TEXT,
        wound_level_after      TEXT,
        system_damage_roll     INTEGER,
        system_damaged         TEXT,
        ht_roll_result         INTEGER,
        created_at             DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
]


async def init_combat_schema(db_path: str = "psiwars.db"):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Add columns gracefully (ignore if already exist)
        for table, col, typedef in _ALTER_COLUMNS:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
                await db.commit()
            except Exception:
                pass

        # Create tables
        for sql in _COMBAT_TABLES:
            await db.execute(sql)

        # Migration: ensure combat_declarations has UNIQUE(combat_id, ship_id, round_number)
        async with db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='combat_declarations'"
        ) as cur:
            row = await cur.fetchone()
        if row and "UNIQUE(combat_id, ship_id, round_number)" not in (row["sql"] or ""):
            await db.execute("ALTER TABLE combat_declarations RENAME TO combat_declarations_old")
            await db.execute("""CREATE TABLE combat_declarations (
                declaration_id       TEXT PRIMARY KEY,
                combat_id            TEXT NOT NULL,
                ship_id              TEXT NOT NULL,
                round_number         INTEGER NOT NULL,
                maneuver             TEXT,
                pursuit_target_id    TEXT,
                afterburner_active   INTEGER NOT NULL DEFAULT 0,
                active_config        TEXT,
                chase_roll_result    INTEGER,
                chase_total          INTEGER,
                chase_resolution_choice TEXT,
                submitted            INTEGER NOT NULL DEFAULT 0,
                revealed             INTEGER NOT NULL DEFAULT 0,
                UNIQUE(combat_id, ship_id, round_number)
            )""")
            # Get actual columns from old table to do a safe copy
            async with db.execute("PRAGMA table_info(combat_declarations_old)") as _cur:
                _cols = [r[1] for r in await _cur.fetchall()]
            _safe = [c for c in [
                "declaration_id", "combat_id", "ship_id", "round_number",
                "maneuver", "pursuit_target_id", "afterburner_active", "active_config",
                "submitted", "revealed"
            ] if c in _cols]
            _col_str = ", ".join(_safe)
            await db.execute(
                f"INSERT OR IGNORE INTO combat_declarations ({_col_str}) "
                f"SELECT {_col_str} FROM combat_declarations_old"
            )
            await db.execute("DROP TABLE combat_declarations_old")

        await db.commit()


# ---------------------------------------------------------------------------
# Lookup constants
# ---------------------------------------------------------------------------

RANGE_ORDER = ["close", "short", "medium", "long", "extreme", "distant", "beyond_visual"]

RANGE_PENALTIES = {
    "close":         0,
    "short":        -3,
    "medium":       -7,
    "long":        -11,
    "extreme":     -15,
    "distant":     -19,
    "beyond_visual": -23,
}

STATIC_MANEUVERS = {"attack", "stop", "precision_aim"}

WOUND_ORDER = ["none", "scratch", "minor", "major", "crippling", "mortal", "lethal"]

SYSTEM_DAMAGE_TABLE = {
    3:  ("armor",      "fuel"),
    4:  ("habitat",    "cargo"),
    5:  ("propulsion", "weaponry"),
    6:  ("cargo",      None),
    7:  ("equipment",  "controls"),
    8:  ("power",      "propulsion"),
    9:  ("weaponry",   "equipment"),
    10: ("armor",      "fuel"),
    11: ("fuel",       "power"),
    12: ("habitat",    "cargo"),
    13: ("propulsion", "weaponry"),
    14: ("cargo",      None),
    15: ("equipment",  "controls"),
    16: ("power",      "propulsion"),
    17: ("weaponry",   "equipment"),
    18: ("armor",      "fuel"),
}


# ---------------------------------------------------------------------------
# Internal DB fetch helpers
# ---------------------------------------------------------------------------

async def _fetch_combat_full(db, combat_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM combats WHERE combat_id = ?", (combat_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None

    combat = _row_to_dict(row)
    # No gm_review_rolls — nothing to coerce there

    # Initiative order
    async with db.execute(
        "SELECT * FROM combat_initiative WHERE combat_id = ? ORDER BY turn_order",
        (combat_id,)
    ) as cur:
        rows = await cur.fetchall()
    combat["initiative_order"] = [
        {**_row_to_dict(r), "has_acted": bool(r["has_acted"])}
        for r in rows
    ]

    # Range matrix
    async with db.execute(
        "SELECT * FROM combat_ranges WHERE combat_id = ?",
        (combat_id,)
    ) as cur:
        rows = await cur.fetchall()
    combat["ranges"] = [
        {**_row_to_dict(r), "matched_speed": bool(r["matched_speed"])}
        for r in rows
    ]

    return combat


async def _fetch_range_row(db, range_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM combat_ranges WHERE range_id = ?", (range_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["matched_speed"] = bool(d["matched_speed"])
    return d


async def _fetch_range_for_pair(db, combat_id: str, ship_x: str, ship_y: str) -> dict | None:
    """Fetch range row regardless of which ship is a vs b."""
    a, b = (ship_x, ship_y) if ship_x < ship_y else (ship_y, ship_x)
    async with db.execute(
        "SELECT * FROM combat_ranges WHERE combat_id=? AND ship_a_id=? AND ship_b_id=?",
        (combat_id, a, b)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["matched_speed"] = bool(d["matched_speed"])
    return d


async def _fetch_ship_and_pilot(db, ship_id: str) -> tuple[dict, dict]:
    async with db.execute(
        "SELECT * FROM ships WHERE ship_id = ?", (ship_id,)
    ) as cur:
        ship_row = await cur.fetchone()
    async with db.execute(
        "SELECT * FROM pilots WHERE ship_id = ?", (ship_id,)
    ) as cur:
        pilot_row = await cur.fetchone()

    ship  = _row_to_dict(ship_row)  if ship_row  else {}
    pilot = _row_to_dict(pilot_row) if pilot_row else {}

    for f in ["afterburner_available", "afterburner_active", "is_destroyed",
              "is_uncontrolled", "force_screen_hardened", "has_targeting_computer",
              "sensor_lock_active", "fuel_tracking_enforced"]:
        if f in ship:
            ship[f] = bool(ship[f])

    for f in ["is_ace_pilot", "is_gunslinger"]:
        if f in pilot:
            pilot[f] = bool(pilot[f])

    if "faction" not in pilot or pilot["faction"] is None:
        pilot["faction"] = "player"

    return ship, pilot


async def _fetch_weapon(db, weapon_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM weapons WHERE weapon_id = ?", (weapon_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    w = _row_to_dict(row)
    if isinstance(w.get("facings"), str):
        w["facings"] = json.loads(w["facings"])
    for f in ["is_linked", "is_light_turret", "is_disabled"]:
        if f in w:
            w[f] = bool(w[f])
    return w


async def _fetch_ship_systems(db, ship_id: str) -> dict:
    async with db.execute(
        "SELECT system_name, status FROM ship_systems WHERE ship_id = ?",
        (ship_id,)
    ) as cur:
        rows = await cur.fetchall()
    return {r["system_name"]: r["status"] for r in rows}


async def _get_declaration(db, combat_id: str, ship_id: str, round_number: int) -> dict | None:
    async with db.execute(
        """SELECT * FROM combat_declarations
           WHERE combat_id=? AND ship_id=? AND round_number=?""",
        (combat_id, ship_id, round_number)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["submitted"]         = bool(d["submitted"])
    d["revealed"]          = bool(d["revealed"])
    d["afterburner_active"] = bool(d["afterburner_active"])
    return d


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def _speed_bonus(ship: dict) -> int:
    ship_class = ship.get("ship_class", "fighter")
    move = ship.get("move_space", 0)
    if ship_class == "fighter":
        return min(move // 25, 20)
    elif ship_class == "corvette":
        return min(move // 50, 15)
    return 0  # capital ships get no speed bonus


def calculate_chase_bonus(ship: dict, declaration: dict, range_row: dict) -> int:
    """
    Calculate the full per-round chase bonus for this ship.
    range_row is the combat_ranges row for the relevant pair.
    """
    bonus = ship.get("handling", 0) + ship.get("sr", 0)

    move = ship.get("move_space", 0)
    if declaration.get("afterburner_active") and ship.get("afterburner_available"):
        move += ship.get("afterburner_move_bonus", 0)

    ship_class = ship.get("ship_class", "fighter")
    if ship_class == "fighter":
        bonus += min(move // 25, 20)
    elif ship_class == "corvette":
        bonus += min(move // 50, 15)

    # Advantage bonus
    if range_row.get("advantage_ship_id") == ship.get("ship_id"):
        bonus += 2

    maneuver = declaration.get("maneuver", "")
    if maneuver in ("evade", "move_evade"):
        bonus -= 2
    elif maneuver == "stunt":
        bonus += 2
    elif maneuver == "high_g_stunt":
        bonus += 3

    return bonus


def _speed_penalty(ship: dict) -> int:
    """Speed penalty for attack roll (negative value)."""
    return -_speed_bonus(ship)


def _size_penalty(attacker: dict, target: dict, weapon: dict) -> int:
    ac = attacker.get("ship_class", "fighter")
    tc = target.get("ship_class", "fighter")
    is_light = bool(weapon.get("is_light_turret", False))

    if ac == "corvette"  and tc == "fighter":   pen = -5
    elif ac == "capital" and tc == "corvette":  pen = -5
    elif ac == "capital" and tc == "fighter":   pen = -10
    else:                                        pen = 0

    if is_light and pen != 0:
        pen = -(abs(pen) // 2)
    return pen


def _wound_level(net_damage: int, hp_max: int) -> str:
    if hp_max <= 0:
        return "scratch"
    r = net_damage / hp_max
    if r >= 5.0: return "lethal"
    if r >= 2.0: return "mortal"
    if r >= 1.0: return "crippling"
    if r >= 0.5: return "major"
    if r >= 0.1: return "minor"
    return "scratch"


# ---------------------------------------------------------------------------
# Maneuver legality
# ---------------------------------------------------------------------------

def check_maneuver_legality(
    maneuver: str, ship: dict, systems: dict, has_opponent_advantage: bool
) -> tuple[bool, str]:
    if bool(ship.get("is_destroyed")):
        return False, "Ship is destroyed"
    if bool(ship.get("is_uncontrolled")) or systems.get("controls") == "destroyed":
        return False, "Controls are destroyed — ship is uncontrolled"
    if systems.get("controls") == "disabled" and maneuver not in STATIC_MANEUVERS:
        # Disabled controls: handling -2, but can still maneuver (not forced static)
        pass

    stall = ship.get("stall_speed", 0)
    prop_dead = systems.get("propulsion") == "destroyed"

    if prop_dead and maneuver in ("move_pursue", "move_evade", "evade"):
        return False, "Propulsion is destroyed"

    if stall > 0:
        if maneuver == "attack":
            return False, "Stall-speed ships cannot use Attack maneuver"
        if has_opponent_advantage and maneuver == "move_pursue":
            return False, "Cannot pursue: opponent has Advantage and ship has stall speed"
        if has_opponent_advantage and maneuver == "stunt":
            return False, "Cannot stunt against advantaged opponent with stall speed"

    return True, ""


# ---------------------------------------------------------------------------
# Chase outcome
# ---------------------------------------------------------------------------

def _shift_range(current: str, shifts: int, direction: str) -> str:
    idx = RANGE_ORDER.index(current) if current in RANGE_ORDER else 2
    if direction == "closer":
        idx = max(0, idx - shifts)
    else:
        idx = min(len(RANGE_ORDER) - 1, idx + shifts)
    return RANGE_ORDER[idx]


def _apply_chase_outcome(
    range_row: dict,
    winner_ship_id: str | None,
    margin: int,
    winner_pursuing: bool,
    a_static: bool,
    b_static: bool,
    decl_a: dict,
    decl_b: dict,
) -> dict:
    """
    Pure function: given the current range_row and chase contest result,
    return updated fields dict {range_band, advantage_ship_id, matched_speed}.

    Static maneuver rule (PDF p.5):
      Static ship still rolls chase. Additionally, their opponent gets one
      free 1-band shift regardless of the contest outcome.
      Matched Speed is lost if the advantaged ship took a static maneuver.
    """
    new_band      = range_row["range_band"]
    new_adv       = range_row["advantage_ship_id"]
    new_matched   = False  # matched speed clears each round unless re-earned

    # If the currently-advantaged ship went static, matched speed is lost
    # (handled by new_matched = False above — matched_speed always resets)

    # --- Static ship free shift ---
    # If exactly one ship is static, the non-static ship gets a free 1-band
    # shift in their preferred direction, independent of contest outcome.
    # If both are static: no shifts, no contest effects.
    if a_static and b_static:
        return {"range_band": new_band, "advantage_ship_id": new_adv, "matched_speed": False}

    if a_static:
        # B gets free shift in B's direction
        b_pursuing = decl_b.get("maneuver", "") in ("move_pursue", "move_and_attack")
        new_band = _shift_range(new_band, 1, "closer" if b_pursuing else "farther")
        # Contest still happens — winner_ship_id/margin from the non-static
        # side's roll vs static's roll. But convention: static ship MOS treated
        # as 0, non-static still wins/loses normally for advantage purposes.
        # Since a_static, B effectively always wins the advantage contest
        # (static ships auto-lose advantage per PDF).
        new_adv = range_row["ship_b_id"]  # B wins by default
        return {"range_band": new_band, "advantage_ship_id": new_adv, "matched_speed": False}

    if b_static:
        a_pursuing = decl_a.get("maneuver", "") in ("move_pursue", "move_and_attack")
        new_band = _shift_range(new_band, 1, "closer" if a_pursuing else "farther")
        new_adv = range_row["ship_a_id"]
        return {"range_band": new_band, "advantage_ship_id": new_adv, "matched_speed": False}

    # --- Normal contest ---
    if winner_ship_id is None:
        # Tie — no change to range or advantage
        return {"range_band": new_band, "advantage_ship_id": new_adv, "matched_speed": False}

    already_advantaged = (range_row["advantage_ship_id"] == winner_ship_id)

    if margin <= 4:
        # No range change. Loser loses advantage if they had it.
        if new_adv and new_adv != winner_ship_id:
            new_adv = None

    elif margin <= 9:
        # Winner's choice: Advantage OR 1 range shift.
        # Auto-pick: if already advantaged → Match Speed; else gain Advantage.
        # (Slice 4 will add UI for explicit choice via chase_resolution_choice)
        if already_advantaged:
            new_matched = True
            new_adv = winner_ship_id
        else:
            new_adv = winner_ship_id

    else:  # margin >= 10
        if already_advantaged:
            # Already had it → Match Speed
            new_matched = True
            new_adv = winner_ship_id
        else:
            # Gain Advantage AND shift 1 band
            new_adv = winner_ship_id
            new_band = _shift_range(new_band, 1, "closer" if winner_pursuing else "farther")

    return {"range_band": new_band, "advantage_ship_id": new_adv, "matched_speed": new_matched}


# ---------------------------------------------------------------------------
# Combat lifecycle
# ---------------------------------------------------------------------------

async def start_combat(
    scenario_id: str,
    initiative_roll_style: str = "stat_only",
    db_path: str = "psiwars.db",
) -> dict:
    """
    Create a new active combat for the scenario.
    Calculates initiative order.
    Creates all n*(n-1)/2 range rows (default: medium, neutral, F/F facings).
    """
    combat_id = _new_id()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        await db.execute(
            """INSERT INTO combats
               (combat_id, scenario_id, status, current_round, current_phase, initiative_roll_style)
               VALUES (?, ?, 'active', 1, 'setup', ?)""",
            (combat_id, scenario_id, initiative_roll_style),
        )

        # Fetch all ships in scenario
        async with db.execute(
            "SELECT ship_id FROM ships WHERE scenario_id = ?", (scenario_id,)
        ) as cur:
            ship_rows = await cur.fetchall()

        ship_ids = [r["ship_id"] for r in ship_rows]

        # Calculate initiative
        initiatives = []
        for sid in ship_ids:
            ship, pilot = await _fetch_ship_and_pilot(db, sid)
            basic_speed = pilot.get("basic_speed", 6)
            init_mod    = ship.get("initiative_modifier", 0) + pilot.get("initiative_modifier", 0)
            roll = None
            if initiative_roll_style == "stat_plus_1d6":
                roll = _roll_1d6()
                init_value = basic_speed + init_mod + roll
            else:
                init_value = basic_speed + init_mod
            initiatives.append({
                "ship_id": sid,
                "initiative_value": init_value,
                "initiative_roll": roll,
                "basic_speed": basic_speed,
            })

        # Sort descending; tie-break by basic_speed
        initiatives.sort(
            key=lambda x: (x["initiative_value"], x["basic_speed"]), reverse=True
        )

        for order, init in enumerate(initiatives, start=1):
            await db.execute(
                """INSERT INTO combat_initiative
                   (initiative_id, combat_id, ship_id, initiative_value,
                    initiative_roll, turn_order, has_acted)
                   VALUES (?, ?, ?, ?, ?, ?, 0)""",
                (_new_id(), combat_id, init["ship_id"],
                 init["initiative_value"], init["initiative_roll"], order),
            )

        # Create range matrix rows for all pairs
        for i in range(len(ship_ids)):
            for j in range(i + 1, len(ship_ids)):
                a, b = sorted([ship_ids[i], ship_ids[j]])
                await db.execute(
                    """INSERT INTO combat_ranges
                       (range_id, combat_id, ship_a_id, ship_b_id,
                        range_band, advantage_ship_id, matched_speed,
                        facing_a_to_b, facing_b_to_a)
                       VALUES (?, ?, ?, ?, 'medium', NULL, 0, 'F', 'F')""",
                    (_new_id(), combat_id, a, b),
                )

        await db.commit()
        return await _fetch_combat_full(db, combat_id)


async def get_combat(combat_id: str, db_path: str = "psiwars.db") -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        return await _fetch_combat_full(db, combat_id)


async def get_active_combat(scenario_id: str, db_path: str = "psiwars.db") -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT combat_id FROM combats
               WHERE scenario_id=? AND status='active'
               ORDER BY created_at DESC LIMIT 1""",
            (scenario_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return await _fetch_combat_full(db, row["combat_id"])


# ---------------------------------------------------------------------------
# Range management
# ---------------------------------------------------------------------------

async def get_combat_ranges(combat_id: str, db_path: str = "psiwars.db") -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM combat_ranges WHERE combat_id=?", (combat_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [{**_row_to_dict(r), "matched_speed": bool(r["matched_speed"])} for r in rows]


async def update_range(range_id: str, fields: dict, db_path: str = "psiwars.db") -> dict | None:
    ALLOWED = {
        "range_band", "advantage_ship_id", "matched_speed",
        "facing_a_to_b", "facing_b_to_a"
    }
    safe = {k: v for k, v in fields.items() if k in ALLOWED}
    if not safe:
        return None
    set_clause = ", ".join(f"{k}=?" for k in safe)
    values = list(safe.values()) + [range_id]
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            f"UPDATE combat_ranges SET {set_clause} WHERE range_id=?", values
        )
        await db.commit()
        return await _fetch_range_row(db, range_id)


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------

async def submit_declaration(
    combat_id: str,
    ship_id: str,
    round_number: int,
    maneuver: str,
    pursuit_target_id: str | None,
    afterburner_active: bool,
    active_config: str | None,
    db_path: str = "psiwars.db",
) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        ship, pilot = await _fetch_ship_and_pilot(db, ship_id)
        systems     = await _fetch_ship_systems(db, ship_id)

        # Determine if any opponent has advantage over this ship
        # (for legality check — any range row where adv is NOT this ship)
        async with db.execute(
            """SELECT advantage_ship_id FROM combat_ranges
               WHERE combat_id=? AND (ship_a_id=? OR ship_b_id=?)""",
            (combat_id, ship_id, ship_id)
        ) as cur:
            adv_rows = await cur.fetchall()
        has_opponent_adv = any(
            r["advantage_ship_id"] and r["advantage_ship_id"] != ship_id
            for r in adv_rows
        )

        ok, reason = check_maneuver_legality(maneuver, ship, systems, has_opponent_adv)
        if not ok:
            raise ValueError(f"Illegal maneuver: {reason}")

        # Upsert declaration (UNIQUE on combat_id, ship_id, round_number)
        existing = await _get_declaration(db, combat_id, ship_id, round_number)
        if existing:
            await db.execute(
                """UPDATE combat_declarations
                   SET maneuver=?, pursuit_target_id=?, afterburner_active=?,
                       active_config=?, submitted=1, revealed=0
                   WHERE declaration_id=?""",
                (maneuver, pursuit_target_id, afterburner_active,
                 active_config, existing["declaration_id"]),
            )
            decl_id = existing["declaration_id"]
        else:
            decl_id = _new_id()
            await db.execute(
                """INSERT INTO combat_declarations
                   (declaration_id, combat_id, ship_id, round_number,
                    maneuver, pursuit_target_id, afterburner_active,
                    active_config, submitted, revealed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0)""",
                (decl_id, combat_id, ship_id, round_number,
                 maneuver, pursuit_target_id, afterburner_active, active_config),
            )
        await db.commit()

        # Check if ALL ships have now submitted
        async with db.execute(
            "SELECT COUNT(*) as n FROM combat_initiative WHERE combat_id=?",
            (combat_id,)
        ) as cur:
            total = (await cur.fetchone())["n"]

        async with db.execute(
            """SELECT COUNT(*) as n FROM combat_declarations
               WHERE combat_id=? AND round_number=? AND submitted=1""",
            (combat_id, round_number)
        ) as cur:
            submitted = (await cur.fetchone())["n"]

        all_submitted = (submitted >= total)

        if all_submitted:
            # Auto-reveal all and advance to chase phase
            await db.execute(
                """UPDATE combat_declarations SET revealed=1
                   WHERE combat_id=? AND round_number=?""",
                (combat_id, round_number)
            )
            await db.execute(
                "UPDATE combats SET current_phase='chase' WHERE combat_id=?",
                (combat_id,)
            )
            await db.commit()

        decl = await _get_declaration(db, combat_id, ship_id, round_number)
        decl["all_submitted"] = all_submitted
        return decl


async def reveal_declarations(
    combat_id: str, round_number: int, db_path: str = "psiwars.db"
) -> list[dict]:
    """Manual reveal (GM override). Normally auto-triggered."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE combat_declarations SET revealed=1 WHERE combat_id=? AND round_number=?",
            (combat_id, round_number)
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM combat_declarations WHERE combat_id=? AND round_number=?",
            (combat_id, round_number)
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        d["submitted"]          = bool(d["submitted"])
        d["revealed"]           = bool(d["revealed"])
        d["afterburner_active"] = bool(d["afterburner_active"])
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Chase rolls (per-ship, player-driven)
# ---------------------------------------------------------------------------

async def roll_chase_for_ship(
    combat_id: str,
    ship_id: str,
    roll_value: int,
    db_path: str = "psiwars.db",
) -> dict:
    """
    Record a player's chase roll for their ship.
    roll_value comes from the dice engine (player clicked Roll).

    Returns:
        {
          declaration: dict,
          all_rolled: bool,
          updated_ranges: list[dict]   # populated when all_rolled=True
        }
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get current round
        async with db.execute(
            "SELECT current_round FROM combats WHERE combat_id=?", (combat_id,)
        ) as cur:
            combat_row = await cur.fetchone()
        if not combat_row:
            raise ValueError("Combat not found")
        round_number = combat_row["current_round"]

        decl = await _get_declaration(db, combat_id, ship_id, round_number)
        if not decl:
            raise ValueError("No declaration found for this ship/round")

        ship, pilot = await _fetch_ship_and_pilot(db, ship_id)

        # Find this ship's range rows to compute per-pair bonuses
        # For the chase bonus we use the first relevant range row
        # (bonus is the same regardless of which opponent for the base calc;
        # advantage bonus differs per pair — we'll handle that per-pair below)

        # For now, calculate bonus using an arbitrary range row (advantage will
        # vary per pair; we store the roll on the declaration and compute MOS
        # per-pair during resolution)
        async with db.execute(
            """SELECT * FROM combat_ranges
               WHERE combat_id=? AND (ship_a_id=? OR ship_b_id=?) LIMIT 1""",
            (combat_id, ship_id, ship_id)
        ) as cur:
            first_range_row = await cur.fetchone()

        # Build a minimal range_row for bonus calc if none found
        range_row_for_bonus = (
            {**_row_to_dict(first_range_row), "matched_speed": bool(first_range_row["matched_speed"])}
            if first_range_row else
            {"advantage_ship_id": None}
        )

        bonus = calculate_chase_bonus(ship, decl, range_row_for_bonus)
        mos   = bonus - roll_value

        await db.execute(
            """UPDATE combat_declarations
               SET chase_roll_result=?, chase_mos=?, chase_bonus_used=?
               WHERE declaration_id=?""",
            (roll_value, mos, bonus, decl["declaration_id"])
        )
        await db.commit()

        # Check if ALL ships in this combat have rolled (or are static)
        async with db.execute(
            "SELECT ship_id FROM combat_initiative WHERE combat_id=?", (combat_id,)
        ) as cur:
            all_ship_rows = await cur.fetchall()
        all_ship_ids = [r["ship_id"] for r in all_ship_rows]

        async with db.execute(
            """SELECT ship_id, maneuver, chase_roll_result
               FROM combat_declarations
               WHERE combat_id=? AND round_number=?""",
            (combat_id, round_number)
        ) as cur:
            decl_rows = await cur.fetchall()

        decls_by_ship = {r["ship_id"]: r for r in decl_rows}

        all_rolled = all(
            sid in decls_by_ship and (
                decls_by_ship[sid]["chase_roll_result"] is not None
                or decls_by_ship[sid]["maneuver"] in STATIC_MANEUVERS
            )
            for sid in all_ship_ids
        )

        updated_ranges = []
        if all_rolled:
            updated_ranges = await _resolve_all_chase_outcomes(
                db, combat_id, round_number, all_ship_ids, decls_by_ship
            )
            await db.execute(
                "UPDATE combats SET current_phase='action' WHERE combat_id=?",
                (combat_id,)
            )
            await db.commit()

        decl_out = await _get_declaration(db, combat_id, ship_id, round_number)
        decl_out["all_submitted"] = True  # already in chase phase

    return {
        "declaration": decl_out,
        "all_rolled":  all_rolled,
        "updated_ranges": updated_ranges,
    }


async def _resolve_all_chase_outcomes(
    db, combat_id: str, round_number: int,
    all_ship_ids: list[str], decls_by_ship: dict
) -> list[dict]:
    """
    Resolve chase outcomes for every range matrix row where at least one
    ship declared a pursue/evade relationship with the other.
    Returns the list of updated range dicts.
    """
    # Get all range rows for this combat
    async with db.execute(
        "SELECT * FROM combat_ranges WHERE combat_id=?", (combat_id,)
    ) as cur:
        range_rows = await cur.fetchall()

    # Get full declarations for MOS values
    async with db.execute(
        """SELECT * FROM combat_declarations
           WHERE combat_id=? AND round_number=?""",
        (combat_id, round_number)
    ) as cur:
        full_decl_rows = await cur.fetchall()

    full_decls = {}
    for r in full_decl_rows:
        d = _row_to_dict(r)
        d["submitted"]          = bool(d["submitted"])
        d["revealed"]           = bool(d["revealed"])
        d["afterburner_active"] = bool(d["afterburner_active"])
        full_decls[d["ship_id"]] = d

    updated = []
    for rr in range_rows:
        rr_dict = {**_row_to_dict(rr), "matched_speed": bool(rr["matched_speed"])}
        sid_a = rr_dict["ship_a_id"]
        sid_b = rr_dict["ship_b_id"]

        decl_a = full_decls.get(sid_a)
        decl_b = full_decls.get(sid_b)

        if not decl_a or not decl_b:
            updated.append(rr_dict)
            continue

        a_static = decl_a["maneuver"] in STATIC_MANEUVERS
        b_static = decl_b["maneuver"] in STATIC_MANEUVERS

        # Only run a contest if there's a directional relationship between
        # these two ships (at least one is pursuing/evading the other)
        # OR if one is static (static still grants the free shift).
        a_targets_b = (decl_a.get("pursuit_target_id") == sid_b)
        b_targets_a = (decl_b.get("pursuit_target_id") == sid_a)
        has_relationship = a_targets_b or b_targets_a or a_static or b_static

        if not has_relationship:
            updated.append(rr_dict)
            continue

        # Compute per-pair MOS (advantage bonus may differ per pair)
        mos_a, mos_b = None, None
        winner_ship_id = None
        margin = 0

        if not a_static and decl_a.get("chase_roll_result") is not None:
            # Recompute bonus with this specific range row for accuracy
            async with db.execute(
                "SELECT * FROM ships WHERE ship_id=?", (sid_a,)
            ) as cur:
                ship_a_row = await cur.fetchone()
            ship_a = _row_to_dict(ship_a_row) if ship_a_row else {}
            for f in ["afterburner_available", "afterburner_active"]:
                if f in ship_a:
                    ship_a[f] = bool(ship_a[f])
            bonus_a = calculate_chase_bonus(ship_a, decl_a, rr_dict)
            mos_a = bonus_a - decl_a["chase_roll_result"]

        if not b_static and decl_b.get("chase_roll_result") is not None:
            async with db.execute(
                "SELECT * FROM ships WHERE ship_id=?", (sid_b,)
            ) as cur:
                ship_b_row = await cur.fetchone()
            ship_b = _row_to_dict(ship_b_row) if ship_b_row else {}
            for f in ["afterburner_available", "afterburner_active"]:
                if f in ship_b:
                    ship_b[f] = bool(ship_b[f])
            bonus_b = calculate_chase_bonus(ship_b, decl_b, rr_dict)
            mos_b = bonus_b - decl_b["chase_roll_result"]

        if mos_a is not None and mos_b is not None:
            if mos_a > mos_b:
                winner_ship_id = sid_a
                margin = mos_a - mos_b
            elif mos_b > mos_a:
                winner_ship_id = sid_b
                margin = mos_b - mos_a
            # else tie: winner_ship_id stays None

        winner_pursuing = False
        if winner_ship_id:
            winning_decl = decl_a if winner_ship_id == sid_a else decl_b
            winner_pursuing = winning_decl.get("maneuver", "") in (
                "move_pursue", "move_and_attack"
            )

        outcome = _apply_chase_outcome(
            rr_dict, winner_ship_id, margin, winner_pursuing,
            a_static, b_static, decl_a, decl_b
        )

        await db.execute(
            """UPDATE combat_ranges
               SET range_band=?, advantage_ship_id=?, matched_speed=?
               WHERE range_id=?""",
            (outcome["range_band"], outcome["advantage_ship_id"],
             outcome["matched_speed"], rr_dict["range_id"])
        )

        rr_dict.update(outcome)
        updated.append(rr_dict)

    return updated


# ---------------------------------------------------------------------------
# Attack / Defense / Damage
# ---------------------------------------------------------------------------

async def submit_attack(
    combat_id: str,
    round_number: int,
    acting_ship_id: str,
    target_ship_id: str,
    weapon_id: str,
    attack_roll: int,
    called_shot_system: str | None = None,
    db_path: str = "psiwars.db",
) -> dict:
    """
    Record an attack. attack_roll comes from the dice engine (player clicked Roll).
    Returns the action record with hit/miss result.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        ship_a, pilot_a = await _fetch_ship_and_pilot(db, acting_ship_id)
        ship_b, _       = await _fetch_ship_and_pilot(db, target_ship_id)
        weapon          = await _fetch_weapon(db, weapon_id)
        systems_a       = await _fetch_ship_systems(db, acting_ship_id)

        range_row = await _fetch_range_for_pair(db, combat_id, acting_ship_id, target_ship_id)
        decl      = await _get_declaration(db, combat_id, acting_ship_id, round_number)

        gunner  = pilot_a.get("gunner_skill", 10)
        mods    = {}
        maneuver = decl["maneuver"] if decl else ""
        matched  = bool(range_row.get("matched_speed")) if range_row else False

        # Accuracy: Attack maneuver or matched speed
        if maneuver == "attack" or matched:
            mods["accuracy"] = weapon.get("accuracy", 0) if weapon else 0
        else:
            mods["accuracy"] = 0

        # Sensor lock
        if bool(ship_a.get("sensor_lock_active")):
            mods["sensor_lock"] = 5 if bool(ship_a.get("has_targeting_computer")) else 3
        else:
            mods["sensor_lock"] = 0

        # Range/speed penalty: highest of |range_pen|, attacker speed pen, defender speed pen
        range_band = range_row["range_band"] if range_row else "medium"
        range_pen  = RANGE_PENALTIES.get(range_band, -7)
        spd_a = _speed_penalty(ship_a)
        spd_b = _speed_penalty(ship_b)
        mods["range_speed"] = min(range_pen, spd_a, spd_b)  # all ≤ 0; min = most negative

        # Size penalty
        mods["size"] = _size_penalty(ship_a, ship_b, weapon or {})

        # Called shot
        mods["called_shot"] = -5 if called_shot_system else 0

        if systems_a.get("weaponry") in ("disabled", "destroyed"):
            mods["weapons_offline"] = -999

        total      = gunner + sum(mods.values())
        attack_hit = attack_roll <= total

        action_id = _new_id()
        await db.execute(
            """INSERT INTO combat_actions
               (action_id, combat_id, round_number, acting_ship_id, target_ship_id,
                weapon_id, action_type, called_shot_system,
                attack_skill_base, attack_modifiers, attack_total,
                attack_roll, attack_hit)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action_id, combat_id, round_number, acting_ship_id, target_ship_id,
                weapon_id,
                "called_shot" if called_shot_system else "attack",
                called_shot_system,
                gunner, json.dumps(mods), total,
                attack_roll, attack_hit,
            )
        )
        await db.commit()

        return await _fetch_action(db, action_id)


async def submit_defense(
    action_id: str,
    dodge_roll: int,
    db_path: str = "psiwars.db",
) -> dict:
    """
    Record a dodge roll. dodge_roll comes from the dice engine.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        action = await _fetch_action(db, action_id)
        if not action:
            raise ValueError("Action not found")

        _, pilot = await _fetch_ship_and_pilot(db, action["target_ship_id"])
        decl     = await _get_declaration(
            db, action["combat_id"], action["target_ship_id"], action["round_number"]
        )

        base_dodge = pilot.get("dodge", 8)
        mods = {}
        maneuver = decl["maneuver"] if decl else ""

        # Evade bonus
        if maneuver in ("evade", "move_evade"):
            mods["evade"] = 1

        # Advantage escape bonus (gained Advantage this round via escape)
        # Stored on range row — if defender now has advantage after this round's chase
        range_row = await _fetch_range_for_pair(
            db, action["combat_id"], action["acting_ship_id"], action["target_ship_id"]
        )
        if range_row and range_row.get("advantage_ship_id") == action["target_ship_id"]:
            if maneuver in ("move_evade", "evade"):
                mods["advantage_escape"] = 1

        dodge_total   = base_dodge + sum(mods.values())
        dodge_success = dodge_roll <= dodge_total

        await db.execute(
            """UPDATE combat_actions
               SET dodge_base=?, dodge_modifiers=?, dodge_total=?,
                   dodge_roll=?, dodge_success=?, attack_hit=?
               WHERE action_id=?""",
            (base_dodge, json.dumps(mods), dodge_total,
             dodge_roll, dodge_success,
             not dodge_success,  # attack_hit true only if dodge failed
             action_id)
        )
        await db.commit()
        return await _fetch_action(db, action_id)


async def submit_damage(
    action_id: str,
    db_path: str = "psiwars.db",
) -> dict:
    """
    Roll and record damage. Called by attacker after seeing hit confirmed.
    Server rolls the damage dice (deterministic from weapon stats).
    GM applies the result to ship record via existing PATCH endpoint.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        action = await _fetch_action(db, action_id)
        if not action:
            raise ValueError("Action not found")

        weapon  = await _fetch_weapon(db, action["weapon_id"]) if action.get("weapon_id") else None
        ship, _ = await _fetch_ship_and_pilot(db, action["target_ship_id"])

        if not weapon:
            raise ValueError("Weapon not found on action")

        damage_dice   = weapon.get("damage_dice", 1)
        damage_mult   = weapon.get("damage_mult", 1)
        armor_divisor = float(weapon.get("armor_divisor", 1.0))

        rolls     = [random.randint(1, 6) for _ in range(damage_dice)]
        damage_raw = sum(rolls) * damage_mult

        # Force screen
        fs_current  = ship.get("force_screen_current", 0)
        fs_hardened = bool(ship.get("force_screen_hardened", False))
        dr_hull     = ship.get("dr_hull", 0)

        screen_absorbed = 0
        if fs_current > 0:
            # Hardened screen: ignore armor divisors
            effective_for_screen = damage_raw  # divisors don't apply to screen check
            screen_absorbed = min(damage_raw, fs_current)
            # Note: force_screen_current must be decremented by GM via patch_ship

        remaining = damage_raw - screen_absorbed

        # Hull DR — armor divisor applies here (and is ignored by hardened screen
        # for the underlying hull only while FS has DR)
        if fs_current > 0 and fs_hardened:
            effective_hull_dr = dr_hull  # hardened: hull DR also ignores AD
        elif armor_divisor > 1:
            effective_hull_dr = max(1, int(dr_hull / armor_divisor))
        else:
            effective_hull_dr = dr_hull

        hull_absorbed = min(remaining, effective_hull_dr)
        damage_net    = max(0, remaining - hull_absorbed)

        hp_max         = ship.get("hp_max", 100)
        wound_before   = ship.get("wound_level", "none")
        wound_after    = _wound_level(damage_net, hp_max)

        # System damage (major wound or worse)
        sys_roll      = None
        system_damaged = None
        ht_roll_result = None

        wi = WOUND_ORDER.index(wound_after) if wound_after in WOUND_ORDER else 0
        if wi >= WOUND_ORDER.index("major"):
            sys_roll = _roll_3d6()
            system_damaged, _ = SYSTEM_DAMAGE_TABLE.get(sys_roll, ("equipment", "controls"))

        if wi >= WOUND_ORDER.index("crippling"):
            ht_roll_result = _roll_3d6()

        await db.execute(
            """UPDATE combat_actions
               SET damage_dice=?, damage_mult=?, damage_roll=?, damage_raw=?,
                   damage_screen_absorbed=?, damage_hull_absorbed=?, damage_net=?,
                   wound_level_before=?, wound_level_after=?,
                   system_damage_roll=?, system_damaged=?, ht_roll_result=?
               WHERE action_id=?""",
            (
                damage_dice, damage_mult, json.dumps(rolls), damage_raw,
                screen_absorbed, hull_absorbed, damage_net,
                wound_before, wound_after,
                sys_roll, system_damaged, ht_roll_result,
                action_id,
            )
        )
        await db.commit()
        return await _fetch_action(db, action_id)


async def _fetch_action(db, action_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM combat_actions WHERE action_id=?", (action_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    a = _row_to_dict(row)
    for f in ["attack_hit", "dodge_success"]:
        if a.get(f) is not None:
            a[f] = bool(a[f])
    for f in ["attack_modifiers", "dodge_modifiers"]:
        if a.get(f):
            a[f] = json.loads(a[f])
        else:
            a[f] = {}
    if a.get("damage_roll"):
        a["damage_roll"] = json.loads(a["damage_roll"])
    else:
        a["damage_roll"] = []
    return a


# ---------------------------------------------------------------------------
# Phase / round management
# ---------------------------------------------------------------------------

async def advance_phase(combat_id: str, db_path: str = "psiwars.db") -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT current_phase, current_round FROM combats WHERE combat_id=?",
            (combat_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("Combat not found")

        phase = row["current_phase"]
        rnd   = row["current_round"]

        _PHASES = ["setup", "declaration", "chase", "action", "end_round"]

        if phase == "end_round":
            # Start next round
            await db.execute(
                "UPDATE combat_initiative SET has_acted=0 WHERE combat_id=?",
                (combat_id,)
            )
            await db.execute(
                """UPDATE combats SET current_phase='declaration', current_round=?
                   WHERE combat_id=?""",
                (rnd + 1, combat_id)
            )
        else:
            idx        = _PHASES.index(phase) if phase in _PHASES else 0
            next_phase = _PHASES[idx + 1] if idx + 1 < len(_PHASES) else "end_round"
            await db.execute(
                "UPDATE combats SET current_phase=? WHERE combat_id=?",
                (next_phase, combat_id)
            )

        await db.commit()
        return await _fetch_combat_full(db, combat_id)


async def mark_ship_acted(combat_id: str, ship_id: str, db_path: str = "psiwars.db") -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE combat_initiative SET has_acted=1 WHERE combat_id=? AND ship_id=?",
            (combat_id, ship_id)
        )
        await db.commit()
        return await _fetch_combat_full(db, combat_id)


async def end_combat(combat_id: str, db_path: str = "psiwars.db") -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE combats SET status='ended' WHERE combat_id=?", (combat_id,)
        )
        await db.commit()
        return await _fetch_combat_full(db, combat_id)


# ---------------------------------------------------------------------------
# NPC Autopilot
# ---------------------------------------------------------------------------

def _is_npc(ship: dict) -> bool:
    return ship.get("faction") in ("hostile_npc", "friendly_npc")


def _pick_npc_target(ship_id: str, ship_or_pilot: dict, all_ships: list[dict]) -> str | None:
    """
    Pick the first enemy-faction ship as target.
    hostile_npc targets player + friendly_npc ships.
    friendly_npc targets hostile_npc ships.
    ship_or_pilot: either a ship dict (has 'faction') or entry from all_ships (has 'pilot_faction').
    """
    faction = ship_or_pilot.get("faction") or ship_or_pilot.get("pilot_faction", "hostile_npc")
    if faction == "hostile_npc":
        enemy_factions = ("player", "friendly_npc")
    else:
        enemy_factions = ("hostile_npc",)

    for s in all_ships:
        if s["ship_id"] == ship_id:
            continue
        if s.get("pilot_faction") in enemy_factions:
            return s["ship_id"]
    return None


def _pick_npc_weapon(ship_id: str, weapons: list[dict], facing: str = "F") -> dict | None:
    """Pick first non-disabled weapon whose facings include the given facing."""
    for w in weapons:
        if bool(w.get("is_disabled")):
            continue
        facings = w.get("facings", [])
        if isinstance(facings, str):
            import json as _j
            facings = _j.loads(facings)
        if facing in facings:
            return w
    return None


async def _fetch_all_ships_with_pilots(db, scenario_id: str) -> list[dict]:
    """Fetch all ships in scenario with faction from ship record."""
    async with db.execute(
        "SELECT s.ship_id, s.scenario_id, s.faction "
        "FROM ships s "
        "WHERE s.scenario_id = ?",
        (scenario_id,)
    ) as cur:
        rows = await cur.fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        d["pilot_faction"] = d.pop("faction", "player") or "player"
        result.append(d)
    return result


async def run_npc_declarations(
    combat_id: str,
    db_path: str = "psiwars.db",
) -> list[dict]:
    """
    Auto-submit declarations for all NPC ships.
    Called automatically when declaration phase starts.
    Returns list of declaration dicts that were submitted.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get combat + scenario
        async with db.execute(
            "SELECT scenario_id, current_round FROM combats WHERE combat_id=?",
            (combat_id,)
        ) as cur:
            combat_row = await cur.fetchone()
        if not combat_row:
            return []

        scenario_id  = combat_row["scenario_id"]
        round_number = combat_row["current_round"]

        all_ships = await _fetch_all_ships_with_pilots(db, scenario_id)

        submitted = []
        for s in all_ships:
            ship_id = s["ship_id"]
            faction = s.get("pilot_faction", "player")
            if faction not in ("hostile_npc", "friendly_npc"):
                continue

            # Skip if already declared this round
            existing = await _get_declaration(db, combat_id, ship_id, round_number)
            if existing and existing.get("submitted"):
                continue

            ship, pilot = await _fetch_ship_and_pilot(db, ship_id)
            # Ensure ship faction is set (may differ from pilot faction)
            if not ship.get("faction"):
                ship["faction"] = faction
            systems     = await _fetch_ship_systems(db, ship_id)

            # Pick target
            target_id = _pick_npc_target(ship_id, pilot, all_ships)

            # Check if any opponent has advantage over this ship
            async with db.execute(
                """SELECT advantage_ship_id FROM combat_ranges
                   WHERE combat_id=? AND (ship_a_id=? OR ship_b_id=?)""",
                (combat_id, ship_id, ship_id)
            ) as cur:
                adv_rows = await cur.fetchall()
            has_opponent_adv = any(
                r["advantage_ship_id"] and r["advantage_ship_id"] != ship_id
                for r in adv_rows
            )

            # Pick maneuver — move_and_attack preferred, evade as fallback
            maneuver = "move_and_attack"
            ok, _ = check_maneuver_legality(maneuver, ship, systems, has_opponent_adv)
            if not ok:
                maneuver = "evade"
                ok, _ = check_maneuver_legality(maneuver, ship, systems, has_opponent_adv)
                if not ok:
                    maneuver = "stop"  # last resort — always legal

            # Afterburner ON if available (fuel not enforced for NPC)
            afterburner = bool(ship.get("afterburner_available", False))

            # Upsert declaration directly (bypass submit_declaration to avoid
            # re-checking legality in a loop — we already checked above)
            decl_id = _new_id()
            await db.execute(
                """INSERT INTO combat_declarations
                   (declaration_id, combat_id, ship_id, round_number,
                    maneuver, pursuit_target_id, afterburner_active,
                    active_config, submitted, revealed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, 0)
                   ON CONFLICT(combat_id, ship_id, round_number) DO UPDATE SET
                   maneuver=excluded.maneuver,
                   pursuit_target_id=excluded.pursuit_target_id,
                   afterburner_active=excluded.afterburner_active,
                   submitted=1, revealed=0""",
                (decl_id, combat_id, ship_id, round_number,
                 maneuver, target_id, afterburner),
            )
            submitted.append({
                "ship_id":    ship_id,
                "maneuver":   maneuver,
                "target_id":  target_id,
                "afterburner": afterburner,
            })

        # Check if ALL ships have now submitted — if so reveal + advance
        async with db.execute(
            "SELECT COUNT(*) as n FROM combat_initiative WHERE combat_id=?",
            (combat_id,)
        ) as cur:
            total = (await cur.fetchone())["n"]

        async with db.execute(
            """SELECT COUNT(*) as n FROM combat_declarations
               WHERE combat_id=? AND round_number=? AND submitted=1""",
            (combat_id, round_number)
        ) as cur:
            done = (await cur.fetchone())["n"]

        if done >= total:
            await db.execute(
                "UPDATE combat_declarations SET revealed=1 WHERE combat_id=? AND round_number=?",
                (combat_id, round_number)
            )
            await db.execute(
                "UPDATE combats SET current_phase='chase' WHERE combat_id=?",
                (combat_id,)
            )

        await db.commit()

    return submitted


async def run_npc_chase_rolls(
    combat_id: str,
    db_path: str = "psiwars.db",
) -> list[dict]:
    """
    Auto-roll chase for all NPC ships that haven't rolled yet.
    Called when chase phase starts (after all declarations revealed).
    Each NPC roll feeds into the normal roll_chase_for_ship flow.
    Returns list of roll results.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT scenario_id, current_round FROM combats WHERE combat_id=?",
            (combat_id,)
        ) as cur:
            combat_row = await cur.fetchone()
        if not combat_row:
            return []

        scenario_id  = combat_row["scenario_id"]
        round_number = combat_row["current_round"]
        all_ships    = await _fetch_all_ships_with_pilots(db, scenario_id)

    results = []
    for s in all_ships:
        faction = s.get("pilot_faction", "player")
        if faction not in ("hostile_npc", "friendly_npc"):
            continue

        ship_id = s["ship_id"]

        # Check not already rolled
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            decl = await _get_declaration(db, combat_id, ship_id, round_number)

        if not decl:
            continue
        if decl.get("chase_roll_result") is not None:
            continue
        if decl.get("maneuver") in STATIC_MANEUVERS:
            continue

        # Roll and submit via normal path
        roll = _roll_3d6()
        result = await roll_chase_for_ship(combat_id, ship_id, roll, db_path)
        results.append(result)

    return results


async def run_npc_action(
    combat_id: str,
    ship_id: str,
    db_path: str = "psiwars.db",
) -> dict | None:
    """
    Auto-execute action phase for one NPC ship:
    pick target, pick weapon, roll attack, roll damage if hit.
    Returns the action dict or None if ship can't act.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT scenario_id, current_round FROM combats WHERE combat_id=?",
            (combat_id,)
        ) as cur:
            combat_row = await cur.fetchone()
        if not combat_row:
            return None

        scenario_id  = combat_row["scenario_id"]
        round_number = combat_row["current_round"]

        ship, pilot  = await _fetch_ship_and_pilot(db, ship_id)
        systems      = await _fetch_ship_systems(db, ship_id)

        if bool(ship.get("is_destroyed")) or bool(ship.get("is_uncontrolled")):
            return None
        if systems.get("weaponry") == "destroyed":
            return None

        all_ships = await _fetch_all_ships_with_pilots(db, scenario_id)
        target_id = _pick_npc_target(ship_id, ship, all_ships)
        if not target_id:
            return None

        # Get weapons for this ship
        async with db.execute(
            "SELECT * FROM weapons WHERE ship_id=?", (ship_id,)
        ) as cur:
            weapon_rows = await cur.fetchall()
        weapons = []
        for wr in weapon_rows:
            w = _row_to_dict(wr)
            if isinstance(w.get("facings"), str):
                w["facings"] = json.loads(w["facings"])
            for f in ["is_linked", "is_light_turret", "is_disabled"]:
                if f in w:
                    w[f] = bool(w[f])
            weapons.append(w)

        weapon = _pick_npc_weapon(ship_id, weapons, facing="F")
        if not weapon:
            return None

    # Roll attack via normal path
    attack_roll = _roll_3d6()
    action = await submit_attack(
        combat_id, round_number, ship_id, target_id,
        weapon["weapon_id"], attack_roll, None, db_path,
    )

    # If hit, auto-roll damage
    if action.get("attack_hit"):
        action = await submit_damage(action["action_id"], db_path)

    # Mark ship as acted
    await mark_ship_acted(combat_id, ship_id, db_path)

    return action
