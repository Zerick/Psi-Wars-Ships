"""
scenario_manager.py
Scenario CRUD, ship add/edit/delete, pilot CRUD.
Slice 2 — no rules logic, no combat calculations.
"""

import json
import uuid
from datetime import datetime
from typing import Any

import aiosqlite

from ship_library import SHIP_LIBRARY, SYSTEM_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row: aiosqlite.Row) -> dict:
    return dict(row)


async def _get_db(db_path: str = "psiwars.db") -> aiosqlite.Connection:
    """Open a connection with row_factory set."""
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation (called once at startup from main.py)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'setup',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ships (
    ship_id                      TEXT PRIMARY KEY,
    scenario_id                  TEXT NOT NULL REFERENCES scenarios(scenario_id),
    library_key                  TEXT,
    name                         TEXT NOT NULL,
    faction                      TEXT NOT NULL DEFAULT 'neutral',
    assigned_user_id             TEXT,
    hp_max                       INTEGER NOT NULL,
    hp_current                   INTEGER NOT NULL,
    ht                           INTEGER NOT NULL,
    sm                           INTEGER NOT NULL,
    ship_class                   TEXT NOT NULL,
    handling                     INTEGER NOT NULL,
    sr                           INTEGER NOT NULL,
    move_ground                  INTEGER NOT NULL,
    move_space                   INTEGER NOT NULL,
    stall_speed                  INTEGER NOT NULL DEFAULT 0,
    afterburner_available        BOOLEAN NOT NULL DEFAULT 0,
    afterburner_active           BOOLEAN NOT NULL DEFAULT 0,
    afterburner_move_bonus       INTEGER NOT NULL DEFAULT 0,
    afterburner_chase_bonus      INTEGER NOT NULL DEFAULT 0,
    fuel_max                     INTEGER NOT NULL DEFAULT 0,
    fuel_current                 INTEGER NOT NULL DEFAULT 0,
    fuel_consumption_normal      INTEGER NOT NULL DEFAULT 0,
    fuel_consumption_afterburner INTEGER NOT NULL DEFAULT 0,
    fuel_tracking_enforced       BOOLEAN NOT NULL DEFAULT 1,
    dr_hull                      INTEGER NOT NULL,
    force_screen_max             INTEGER NOT NULL DEFAULT 0,
    force_screen_current         INTEGER NOT NULL DEFAULT 0,
    force_screen_hardened        BOOLEAN NOT NULL DEFAULT 0,
    ecm_rating                   INTEGER NOT NULL DEFAULT 0,
    has_targeting_computer       BOOLEAN NOT NULL DEFAULT 0,
    has_tactical_esm             BOOLEAN NOT NULL DEFAULT 0,
    has_decoy_launcher           BOOLEAN NOT NULL DEFAULT 0,
    has_ultrascanner             BOOLEAN NOT NULL DEFAULT 0,
    sensor_lock_active           BOOLEAN NOT NULL DEFAULT 0,
    wound_level                  TEXT NOT NULL DEFAULT 'none',
    is_destroyed                 BOOLEAN NOT NULL DEFAULT 0,
    is_uncontrolled              BOOLEAN NOT NULL DEFAULT 0,
    config_modes                 TEXT NOT NULL DEFAULT '[]',
    active_config                TEXT,
    notes                        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ship_systems (
    system_id   TEXT PRIMARY KEY,
    ship_id     TEXT NOT NULL REFERENCES ships(ship_id),
    system_name TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'operational'
);

CREATE TABLE IF NOT EXISTS weapons (
    weapon_id      TEXT PRIMARY KEY,
    ship_id        TEXT NOT NULL REFERENCES ships(ship_id),
    name           TEXT NOT NULL,
    weapon_type    TEXT NOT NULL,
    mount_type     TEXT NOT NULL,
    facings        TEXT NOT NULL,
    damage_dice    INTEGER NOT NULL,
    damage_mult    INTEGER NOT NULL DEFAULT 1,
    damage_type    TEXT NOT NULL,
    armor_divisor  REAL NOT NULL DEFAULT 1.0,
    accuracy       INTEGER NOT NULL DEFAULT 0,
    rof            INTEGER NOT NULL DEFAULT 1,
    shots_max      INTEGER NOT NULL DEFAULT 0,
    shots_current  INTEGER NOT NULL DEFAULT 0,
    is_linked      BOOLEAN NOT NULL DEFAULT 0,
    is_light_turret BOOLEAN NOT NULL DEFAULT 0,
    is_disabled    BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pilots (
    pilot_id       TEXT PRIMARY KEY,
    ship_id        TEXT NOT NULL REFERENCES ships(ship_id),
    name           TEXT NOT NULL,
    piloting_skill INTEGER NOT NULL,
    gunner_skill   INTEGER NOT NULL,
    dodge          INTEGER NOT NULL,
    is_ace_pilot   BOOLEAN NOT NULL DEFAULT 0,
    is_gunslinger  BOOLEAN NOT NULL DEFAULT 0
);
"""


async def init_schema(db_path: str = "psiwars.db"):
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


# ---------------------------------------------------------------------------
# Internal DB helpers
# ---------------------------------------------------------------------------

async def _fetch_ship_full(db: aiosqlite.Connection, ship_id: str) -> dict | None:
    """Return a complete ship dict including pilot, weapons, systems."""
    async with db.execute("SELECT * FROM ships WHERE ship_id = ?", (ship_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        return None
    ship = _row_to_dict(row)
    ship["config_modes"] = json.loads(ship["config_modes"])
    # Coerce SQLite 0/1 to Python bool
    ship["afterburner_available"] = bool(ship["afterburner_available"])
    ship["afterburner_active"] = bool(ship["afterburner_active"])
    ship["fuel_tracking_enforced"] = bool(ship["fuel_tracking_enforced"])
    ship["force_screen_hardened"] = bool(ship["force_screen_hardened"])
    ship["has_targeting_computer"] = bool(ship["has_targeting_computer"])
    ship["has_tactical_esm"] = bool(ship["has_tactical_esm"])
    ship["has_decoy_launcher"] = bool(ship["has_decoy_launcher"])
    ship["has_ultrascanner"] = bool(ship["has_ultrascanner"])
    ship["sensor_lock_active"] = bool(ship["sensor_lock_active"])
    ship["is_destroyed"] = bool(ship["is_destroyed"])
    ship["is_uncontrolled"] = bool(ship["is_uncontrolled"])

    # Pilot
    async with db.execute("SELECT * FROM pilots WHERE ship_id = ?", (ship_id,)) as cur:
        pilot_row = await cur.fetchone()
    if pilot_row:
        pilot = _row_to_dict(pilot_row)
        pilot["is_ace_pilot"] = bool(pilot["is_ace_pilot"])
        pilot["is_gunslinger"] = bool(pilot["is_gunslinger"])
        ship["pilot"] = pilot
    else:
        ship["pilot"] = None

    # Weapons
    async with db.execute("SELECT * FROM weapons WHERE ship_id = ?", (ship_id,)) as cur:
        weapon_rows = await cur.fetchall()
    ship["weapons"] = []
    for w in weapon_rows:
        wd = _row_to_dict(w)
        wd["facings"] = json.loads(wd["facings"])
        # Coerce weapon booleans
        wd["is_linked"] = bool(wd["is_linked"])
        wd["is_light_turret"] = bool(wd["is_light_turret"])
        wd["is_disabled"] = bool(wd["is_disabled"])
        ship["weapons"].append(wd)

    # Systems
    async with db.execute(
        "SELECT * FROM ship_systems WHERE ship_id = ? ORDER BY system_name", (ship_id,)
    ) as cur:
        sys_rows = await cur.fetchall()
    ship["systems"] = {r["system_name"]: r["status"] for r in sys_rows}

    return ship


def _filter_ship_for_player(ship: dict, viewer_user_id: str) -> dict:
    """
    Return a filtered version of ship appropriate for a player who does NOT own this ship.
    Pilot stats remain fully public per design decision.
    """
    filtered = {
        "ship_id": ship["ship_id"],
        "scenario_id": ship["scenario_id"],
        "name": ship["name"],
        "ship_class": ship["ship_class"],
        "faction": ship["faction"],
        "assigned_user_id": ship["assigned_user_id"],
        "hp_max": ship["hp_max"],
        "hp_current": ship["hp_current"],
        "wound_level": ship["wound_level"],
        "is_destroyed": ship["is_destroyed"],
        # Pilot stats are intentionally public
        "pilot": ship["pilot"],
        # Weapons: name and type only
        "weapons": [
            {"weapon_id": w["weapon_id"], "name": w["name"], "weapon_type": w["weapon_type"], "mount_type": w["mount_type"]}
            for w in (ship.get("weapons") or [])
        ],
        # Everything else hidden
        "_restricted": True,
    }
    return filtered


async def _fetch_scenario_ships(
    db: aiosqlite.Connection,
    scenario_id: str,
    viewer_user_id: str,
    is_gm: bool,
) -> list[dict]:
    async with db.execute(
        "SELECT ship_id FROM ships WHERE scenario_id = ?", (scenario_id,)
    ) as cur:
        rows = await cur.fetchall()

    ships = []
    for row in rows:
        full = await _fetch_ship_full(db, row["ship_id"])
        if full is None:
            continue
        if is_gm or full.get("assigned_user_id") == viewer_user_id:
            ships.append(full)
        else:
            ships.append(_filter_ship_for_player(full, viewer_user_id))
    return ships


# ---------------------------------------------------------------------------
# Scenario operations
# ---------------------------------------------------------------------------

async def create_scenario(session_id: str, name: str, db_path: str = "psiwars.db") -> dict:
    scenario_id = _new_id()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO scenarios (scenario_id, session_id, name, status) VALUES (?, ?, ?, 'setup')",
            (scenario_id, session_id, name),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM scenarios WHERE scenario_id = ?", (scenario_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_dict(row)


async def get_scenario(
    scenario_id: str,
    viewer_user_id: str,
    is_gm: bool,
    db_path: str = "psiwars.db",
) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM scenarios WHERE scenario_id = ?", (scenario_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        scenario = _row_to_dict(row)
        scenario["ships"] = await _fetch_scenario_ships(db, scenario_id, viewer_user_id, is_gm)
        return scenario


async def get_scenario_by_session(
    session_id: str,
    viewer_user_id: str,
    is_gm: bool,
    db_path: str = "psiwars.db",
) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM scenarios WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        scenario = _row_to_dict(row)
        scenario["ships"] = await _fetch_scenario_ships(
            db, scenario["scenario_id"], viewer_user_id, is_gm
        )
        return scenario


# ---------------------------------------------------------------------------
# Ship operations
# ---------------------------------------------------------------------------

async def add_ship(
    scenario_id: str,
    library_key: str | None,
    custom_ship: dict | None,
    db_path: str = "psiwars.db",
) -> dict:
    """
    Add a ship to a scenario.
    If library_key is provided, pre-fill from SHIP_LIBRARY then apply any overrides from custom_ship.
    If library_key is None, use custom_ship directly.
    Returns the full ship dict.
    """
    if library_key and library_key in SHIP_LIBRARY:
        template = dict(SHIP_LIBRARY[library_key])
        # Deep copy weapons list
        template["weapons"] = [dict(w) for w in template.get("weapons", [])]
        if custom_ship:
            # Apply overrides (but not weapons — those are managed separately)
            overrides = {k: v for k, v in custom_ship.items() if k != "weapons"}
            template.update(overrides)
        data = template
    elif custom_ship:
        data = custom_ship
    else:
        raise ValueError("Must supply either library_key or custom_ship")

    ship_id = _new_id()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        await db.execute(
            """INSERT INTO ships (
                ship_id, scenario_id, library_key, name, faction, assigned_user_id,
                hp_max, hp_current, ht, sm, ship_class,
                handling, sr, move_ground, move_space, stall_speed,
                afterburner_available, afterburner_active, afterburner_move_bonus, afterburner_chase_bonus,
                fuel_max, fuel_current, fuel_consumption_normal, fuel_consumption_afterburner, fuel_tracking_enforced,
                dr_hull, force_screen_max, force_screen_current, force_screen_hardened,
                ecm_rating, has_targeting_computer, has_tactical_esm, has_decoy_launcher,
                has_ultrascanner, sensor_lock_active,
                wound_level, is_destroyed, is_uncontrolled,
                config_modes, active_config, notes
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )""",
            (
                ship_id,
                scenario_id,
                data.get("library_key"),
                data.get("name", "Unknown Ship"),
                data.get("faction", "neutral"),
                data.get("assigned_user_id"),
                data.get("hp_max", 100),
                data.get("hp_current", 100),
                data.get("ht", 10),
                data.get("sm", 4),
                data.get("ship_class", "fighter"),
                data.get("handling", 0),
                data.get("sr", 3),
                data.get("move_ground", 0),
                data.get("move_space", 0),
                data.get("stall_speed", 0),
                data.get("afterburner_available", False),
                data.get("afterburner_active", False),
                data.get("afterburner_move_bonus", 0),
                data.get("afterburner_chase_bonus", 0),
                data.get("fuel_max", 0),
                data.get("fuel_current", 0),
                data.get("fuel_consumption_normal", 0),
                data.get("fuel_consumption_afterburner", 0),
                data.get("fuel_tracking_enforced", True),
                data.get("dr_hull", 10),
                data.get("force_screen_max", 0),
                data.get("force_screen_current", 0),
                data.get("force_screen_hardened", False),
                data.get("ecm_rating", 0),
                data.get("has_targeting_computer", False),
                data.get("has_tactical_esm", False),
                data.get("has_decoy_launcher", False),
                data.get("has_ultrascanner", False),
                data.get("sensor_lock_active", False),
                data.get("wound_level", "none"),
                data.get("is_destroyed", False),
                data.get("is_uncontrolled", False),
                json.dumps(data.get("config_modes", [])),
                data.get("active_config"),
                data.get("notes", ""),
            ),
        )

        # Systems
        for sysname in SYSTEM_NAMES:
            await db.execute(
                "INSERT INTO ship_systems (system_id, ship_id, system_name, status) VALUES (?, ?, ?, 'operational')",
                (_new_id(), ship_id, sysname),
            )

        # Weapons
        for w in data.get("weapons", []):
            await db.execute(
                """INSERT INTO weapons (
                    weapon_id, ship_id, name, weapon_type, mount_type, facings,
                    damage_dice, damage_mult, damage_type, armor_divisor,
                    accuracy, rof, shots_max, shots_current,
                    is_linked, is_light_turret, is_disabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _new_id(),
                    ship_id,
                    w.get("name", "Weapon"),
                    w.get("weapon_type", "gun"),
                    w.get("mount_type", "fixed"),
                    json.dumps(w.get("facings", ["F"])),
                    w.get("damage_dice", 1),
                    w.get("damage_mult", 1),
                    w.get("damage_type", "burn"),
                    w.get("armor_divisor", 1.0),
                    w.get("accuracy", 0),
                    w.get("rof", 1),
                    w.get("shots_max", 0),
                    w.get("shots_current", w.get("shots_max", 0)),
                    w.get("is_linked", False),
                    w.get("is_light_turret", False),
                    w.get("is_disabled", False),
                ),
            )

        # Pilot (placeholder — GM updates after creation)
        pilot_data = data.get("pilot", {})
        await db.execute(
            """INSERT INTO pilots (pilot_id, ship_id, name, piloting_skill, gunner_skill, dodge, is_ace_pilot, is_gunslinger)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _new_id(),
                ship_id,
                pilot_data.get("name", "Unknown Pilot"),
                pilot_data.get("piloting_skill", 10),
                pilot_data.get("gunner_skill", 10),
                pilot_data.get("dodge", 8),
                pilot_data.get("is_ace_pilot", False),
                pilot_data.get("is_gunslinger", False),
            ),
        )

        await db.commit()
        return await _fetch_ship_full(db, ship_id)


async def patch_ship(
    ship_id: str,
    fields: dict,
    db_path: str = "psiwars.db",
) -> dict | None:
    """Update top-level ship fields. Returns updated full ship dict."""
    ALLOWED = {
        "name", "faction", "assigned_user_id",
        "hp_max", "hp_current", "ht", "sm", "ship_class",
        "handling", "sr", "move_ground", "move_space", "stall_speed",
        "afterburner_available", "afterburner_active", "afterburner_move_bonus", "afterburner_chase_bonus",
        "fuel_max", "fuel_current", "fuel_consumption_normal", "fuel_consumption_afterburner", "fuel_tracking_enforced",
        "dr_hull", "force_screen_max", "force_screen_current", "force_screen_hardened",
        "ecm_rating", "has_targeting_computer", "has_tactical_esm", "has_decoy_launcher",
        "has_ultrascanner", "sensor_lock_active",
        "wound_level", "is_destroyed", "is_uncontrolled",
        "config_modes", "active_config", "notes",
    }
    safe = {k: v for k, v in fields.items() if k in ALLOWED}
    if not safe:
        return None

    # Serialise config_modes if present
    if "config_modes" in safe:
        safe["config_modes"] = json.dumps(safe["config_modes"])

    set_clause = ", ".join(f"{k} = ?" for k in safe)
    values = list(safe.values()) + [ship_id]

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE ships SET {set_clause} WHERE ship_id = ?", values)
        await db.commit()
        return await _fetch_ship_full(db, ship_id)


async def patch_pilot(
    ship_id: str,
    fields: dict,
    db_path: str = "psiwars.db",
) -> dict | None:
    ALLOWED = {"name", "piloting_skill", "gunner_skill", "dodge", "is_ace_pilot", "is_gunslinger"}
    safe = {k: v for k, v in fields.items() if k in ALLOWED}
    if not safe:
        return None

    set_clause = ", ".join(f"{k} = ?" for k in safe)
    values = list(safe.values()) + [ship_id]

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE pilots SET {set_clause} WHERE ship_id = ?", values)
        await db.commit()
        return await _fetch_ship_full(db, ship_id)


async def patch_system(
    ship_id: str,
    system_name: str,
    status: str,
    db_path: str = "psiwars.db",
) -> dict | None:
    if status not in ("operational", "disabled", "destroyed"):
        raise ValueError(f"Invalid system status: {status}")

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE ship_systems SET status = ? WHERE ship_id = ? AND system_name = ?",
            (status, ship_id, system_name),
        )
        # Mirror controls-destroyed to is_uncontrolled flag
        if system_name == "controls":
            await db.execute(
                "UPDATE ships SET is_uncontrolled = ? WHERE ship_id = ?",
                (status == "destroyed", ship_id),
            )
        await db.commit()
        return await _fetch_ship_full(db, ship_id)


async def patch_weapon(
    ship_id: str,
    weapon_id: str,
    fields: dict,
    db_path: str = "psiwars.db",
) -> dict | None:
    ALLOWED = {
        "name", "weapon_type", "mount_type", "facings",
        "damage_dice", "damage_mult", "damage_type", "armor_divisor",
        "accuracy", "rof", "shots_max", "shots_current",
        "is_linked", "is_light_turret", "is_disabled",
    }
    safe = {k: v for k, v in fields.items() if k in ALLOWED}
    if "facings" in safe:
        safe["facings"] = json.dumps(safe["facings"])
    if not safe:
        return None

    set_clause = ", ".join(f"{k} = ?" for k in safe)
    values = list(safe.values()) + [weapon_id, ship_id]

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            f"UPDATE weapons SET {set_clause} WHERE weapon_id = ? AND ship_id = ?", values
        )
        await db.commit()
        return await _fetch_ship_full(db, ship_id)


async def assign_ship(
    ship_id: str,
    user_id: str,
    db_path: str = "psiwars.db",
) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE ships SET assigned_user_id = ? WHERE ship_id = ?", (user_id, ship_id)
        )
        await db.commit()
        return await _fetch_ship_full(db, ship_id)


async def delete_ship(ship_id: str, db_path: str = "psiwars.db") -> bool:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM weapons WHERE ship_id = ?", (ship_id,))
        await db.execute("DELETE FROM ship_systems WHERE ship_id = ?", (ship_id,))
        await db.execute("DELETE FROM pilots WHERE ship_id = ?", (ship_id,))
        await db.execute("DELETE FROM ships WHERE ship_id = ?", (ship_id,))
        await db.commit()
    return True
