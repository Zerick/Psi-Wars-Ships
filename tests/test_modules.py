"""
T-32 through T-34: Module Installation Tests
"""
import json
import pytest


class TestModuleInstallation:

    def test_install_module_valid_slot(self, seeded_db, make_ship):
        """T-32: Installing a weapon module in a weapon slot succeeds."""
        from m3_data_vault.dal.instances import install_module
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="wildcat_v1")
        install_module(seeded_db, instance_id, "main_weapon", "boom_cannon_module")
        seeded_db.commit()

        row = seeded_db.query(ShipInstanceRow).filter_by(instance_id=instance_id).one()
        installed = json.loads(row.installed_modules)
        assert installed["main_weapon"] == "boom_cannon_module"

    def test_install_module_invalid_slot_type(self, seeded_db, make_ship):
        """T-33: Installing a weapon module in an armor slot raises ValueError."""
        from m3_data_vault.dal.instances import install_module

        instance_id = make_ship(template_id="wildcat_v1")
        with pytest.raises(ValueError, match="[Ss]lot.*type"):
            install_module(seeded_db, instance_id, "armor", "boom_cannon_module")

    def test_install_module_nonexistent_slot(self, seeded_db, make_ship):
        """T-33b: Installing into a slot that doesn't exist raises ValueError."""
        from m3_data_vault.dal.instances import install_module

        instance_id = make_ship(template_id="javelin_v1")
        with pytest.raises(ValueError, match="[Ss]lot"):
            install_module(seeded_db, instance_id, "main_weapon", "boom_cannon_module")

    def test_module_weapon_in_effective_stats(self, seeded_db, make_ship):
        """T-34: A weapon module's weapon appears in the effective stat block."""
        from m3_data_vault.dal.instances import get_effective_stats

        loadout = {"main_weapon": "boom_cannon_module"}
        instance_id = make_ship(template_id="wildcat_v1", module_loadout=loadout)
        stats = get_effective_stats(seeded_db, instance_id)

        weapon_names = [w.name for w in stats.weapons]
        assert any("Plasma Cannon" in name or "B00-M" in name for name in weapon_names), (
            f"Expected B00-M weapon in stats, got: {weapon_names}"
        )

    def test_module_replacement(self, seeded_db, make_ship):
        """T-34b: Installing a new module in an occupied slot replaces the old one."""
        from m3_data_vault.dal.instances import install_module
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(
            template_id="wildcat_v1",
            module_loadout={"accessory": "longstrider_fuel"},
        )
        install_module(seeded_db, instance_id, "accessory", "silverback_force_screen")
        seeded_db.commit()

        row = seeded_db.query(ShipInstanceRow).filter_by(instance_id=instance_id).one()
        installed = json.loads(row.installed_modules)
        assert installed["accessory"] == "silverback_force_screen"

    def test_accessory_module_in_accessory_slot(self, seeded_db, make_ship):
        """T-34c: Accessory module installs in accessory slot correctly."""
        from m3_data_vault.dal.instances import install_module
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="wildcat_v1")
        install_module(seeded_db, instance_id, "accessory", "longstrider_fuel")
        seeded_db.commit()

        row = seeded_db.query(ShipInstanceRow).filter_by(instance_id=instance_id).one()
        installed = json.loads(row.installed_modules)
        assert installed["accessory"] == "longstrider_fuel"
