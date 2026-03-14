"""
Shared pytest fixtures for M3 Data-Vault test suite.

Provides:
- In-memory SQLite database sessions
- Paths to test fixture JSON files
- Helper factories for creating controllers and spawning ships

All M3 imports are done lazily inside fixtures so that pytest can
discover and collect tests even when the implementation is stubbed out.
Individual tests will fail with ImportError until the implementation exists.
"""
import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SHIPS_DIR = FIXTURES_DIR / "ships"
WEAPONS_DIR = FIXTURES_DIR / "weapons"
MODULES_DIR = FIXTURES_DIR / "modules"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session(tmp_path):
    """
    Create a fresh in-memory SQLite database with all tables,
    and yield a session. Torn down automatically after each test.
    """
    from m3_data_vault.db.engine import create_engine_and_tables
    from m3_data_vault.db.session import get_session

    engine = create_engine_and_tables("sqlite:///:memory:")
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_db(db_session):
    """
    A database pre-loaded with all valid fixture data:
    all weapons, all modules, and all valid ship templates.

    Returns the session for further use.
    """
    from m3_data_vault.dal.ingestion import (
        ingest_template,
        ingest_weapon,
        ingest_module,
    )

    # Ingest weapons first (ships reference them)
    for weapon_file in WEAPONS_DIR.glob("*.json"):
        if "invalid" not in weapon_file.stem:
            ingest_weapon(db_session, weapon_file)

    # Ingest modules (some reference weapons)
    for module_file in MODULES_DIR.glob("*.json"):
        if "invalid" not in module_file.stem:
            ingest_module(db_session, module_file)

    # Ingest ship templates
    for ship_file in SHIPS_DIR.glob("*.json"):
        if "invalid" not in ship_file.stem:
            ingest_template(db_session, ship_file)

    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def javelin_path():
    return SHIPS_DIR / "javelin_v1.json"


@pytest.fixture
def hornet_path():
    return SHIPS_DIR / "hornet_v1.json"


@pytest.fixture
def wildcat_path():
    return SHIPS_DIR / "wildcat_v1.json"


@pytest.fixture
def sword_path():
    return SHIPS_DIR / "sword_battleship_v1.json"


@pytest.fixture
def invalid_ship_path():
    return SHIPS_DIR / "invalid_ship.json"


@pytest.fixture
def imperial_blaster_path():
    return WEAPONS_DIR / "imperial_fighter_blaster.json"


@pytest.fixture
def invalid_weapon_path():
    return WEAPONS_DIR / "invalid_weapon.json"


@pytest.fixture
def silverback_path():
    return MODULES_DIR / "silverback_force_screen.json"


@pytest.fixture
def boom_cannon_module_path():
    return MODULES_DIR / "boom_cannon_module.json"


@pytest.fixture
def tank_armor_path():
    return MODULES_DIR / "tank_armor.json"


@pytest.fixture
def longstrider_path():
    return MODULES_DIR / "longstrider_fuel.json"


@pytest.fixture
def invalid_module_path():
    return MODULES_DIR / "invalid_module.json"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def make_controller(db_session):
    """Factory fixture: creates a controller and returns its UUID."""
    def _make(name="Test Pilot", faction="empire", is_ace=False, crew_skill=12):
        from m3_data_vault.dal.controllers import create_controller
        return create_controller(
            db_session,
            name=name,
            faction=faction,
            is_ace_pilot=is_ace,
            crew_skill=crew_skill,
        )
    return _make


@pytest.fixture
def make_ship(seeded_db):
    """
    Factory fixture: spawns a ship instance from a template.
    Requires seeded_db so all templates/weapons/modules are available.
    """
    def _make(
        template_id="javelin_v1",
        controller_id=None,
        display_name="Test Ship",
        session_id="test_session",
        module_loadout=None,
    ):
        from m3_data_vault.dal.instances import spawn_ship
        return spawn_ship(
            seeded_db,
            template_id=template_id,
            controller_id=controller_id,
            display_name=display_name,
            session_id=session_id,
            module_loadout=module_loadout,
        )
    return _make
