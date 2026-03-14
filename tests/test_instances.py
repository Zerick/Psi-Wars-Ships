"""
T-08 through T-11: Instance Lifecycle Tests

Verifies that spawning a ship instance from a template correctly
initializes all state fields and system status rows.
"""
import pytest


SYSTEM_TYPES = [
    "fuel", "habitat", "propulsion", "cargo_hangar", "equipment",
    "power", "weaponry", "armor", "controls",
]


class TestSpawnShip:
    """Tests for spawn_ship() initialization behavior."""

    def test_spawn_initializes_hp(self, seeded_db, make_ship):
        """T-08: spawn_ship() creates an instance with current_hp == template.st_hp."""
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="javelin_v1")

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()

        # Javelin has st_hp = 80
        assert row.current_hp == 80
        assert row.wound_level == "none"
        assert row.is_disabled is False
        assert row.is_destroyed is False

    def test_spawn_initializes_fdr(self, seeded_db, make_ship):
        """T-09: spawn_ship() creates an instance with current_fdr == template.fdr_max."""
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="hornet_v1")

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()

        # Hornet has fdr_max = 150
        assert row.current_fdr == 150

    def test_spawn_initializes_fdr_zero_when_no_screen(self, seeded_db, make_ship):
        """T-09b: A ship with no force screen initializes current_fdr to 0."""
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="javelin_v1")

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()

        assert row.current_fdr == 0

    def test_spawn_creates_system_status(self, seeded_db, make_ship):
        """T-10: spawn_ship() creates one system_status row per type, all operational."""
        from m3_data_vault.db.tables import SystemStatusRow

        instance_id = make_ship(template_id="javelin_v1")

        rows = seeded_db.query(SystemStatusRow).filter_by(
            instance_id=instance_id
        ).all()

        assert len(rows) == len(SYSTEM_TYPES)

        status_map = {r.system_type: r.status for r in rows}
        for system_type in SYSTEM_TYPES:
            assert system_type in status_map, f"Missing system_status for {system_type}"
            assert status_map[system_type] == "operational"

    def test_spawn_with_module_loadout(self, seeded_db, make_ship):
        """T-11: spawn_ship() with a module_loadout dict stores it correctly."""
        from m3_data_vault.db.tables import ShipInstanceRow
        import json

        loadout = {
            "main_weapon": "boom_cannon_module",
            "accessory": "longstrider_fuel",
        }
        instance_id = make_ship(
            template_id="wildcat_v1",
            module_loadout=loadout,
        )

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()

        installed = json.loads(row.installed_modules)
        assert installed["main_weapon"] == "boom_cannon_module"
        assert installed["accessory"] == "longstrider_fuel"

    def test_spawn_with_controller(self, seeded_db, make_ship, make_controller):
        """T-11b: spawn_ship() with a controller correctly links the FK."""
        from m3_data_vault.db.tables import ShipInstanceRow

        ctrl_id = make_controller(name="Ace Kira", faction="rebel", is_ace=True)
        instance_id = make_ship(
            template_id="javelin_v1",
            controller_id=ctrl_id,
        )

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()

        assert row.controller_id == ctrl_id

    def test_spawn_capital_ship(self, seeded_db, make_ship):
        """T-11c: Capital ships spawn correctly with large stat values."""
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="sword_battleship_v1")

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()

        assert row.current_hp == 7000
        assert row.current_fdr == 10000
