"""
T-38 through T-40: Module Catalog Tests
"""
import json
import pytest


class TestModuleCatalog:

    def test_ingest_valid_module(self, db_session, silverback_path):
        """T-38: A well-formed module JSON passes validation and is stored."""
        from m3_data_vault.dal.ingestion import ingest_module
        from m3_data_vault.db.tables import ModuleCatalogRow
        from m3_data_vault.models.module import ModuleDefinition

        module_id = ingest_module(db_session, silverback_path)
        db_session.commit()

        assert module_id == "silverback_force_screen"

        row = db_session.query(ModuleCatalogRow).filter_by(
            module_id="silverback_force_screen",
        ).one()

        assert row.name == "Redjack AM49 'Silverback' Force Screen Module"
        assert row.file_hash is not None

        stored = ModuleDefinition(**json.loads(row.data_json))
        assert stored.slot_type == "accessory"
        assert stored.weight_class == "heavy"
        assert stored.fdr_provided == 300
        assert "force_screen" in stored.grants_traits

    def test_reject_invalid_module(self, invalid_module_path):
        """T-39: A module JSON with invalid fields raises ValidationError."""
        from m3_data_vault.models.module import ModuleDefinition
        from pydantic import ValidationError

        data = json.loads(invalid_module_path.read_text())
        with pytest.raises(ValidationError):
            ModuleDefinition(**data)

    def test_module_with_weapon_ref(self, db_session, boom_cannon_module_path):
        """T-40: A module that provides a weapon has a valid weapon_ref."""
        from m3_data_vault.dal.ingestion import ingest_weapon, ingest_module
        from m3_data_vault.db.tables import ModuleCatalogRow, WeaponCatalogRow
        from m3_data_vault.models.module import ModuleDefinition
        from tests.paths import WEAPONS_DIR

        ingest_weapon(db_session, WEAPONS_DIR / "boom_heavy_plasma_cannon.json")
        ingest_module(db_session, boom_cannon_module_path)
        db_session.commit()

        mod_row = db_session.query(ModuleCatalogRow).filter_by(
            module_id="boom_cannon_module",
        ).one()

        mod_data = ModuleDefinition(**json.loads(mod_row.data_json))
        assert mod_data.weapon_ref == "boom_heavy_plasma_cannon"

        weapon_row = db_session.query(WeaponCatalogRow).filter_by(
            weapon_id=mod_data.weapon_ref,
        ).one_or_none()
        assert weapon_row is not None

    def test_all_fixture_modules_valid(self):
        """T-40b: Every non-invalid module fixture passes validation."""
        from m3_data_vault.models.module import ModuleDefinition
        from tests.paths import MODULES_DIR

        for module_file in MODULES_DIR.glob("*.json"):
            if "invalid" in module_file.stem:
                continue
            data = json.loads(module_file.read_text())
            module = ModuleDefinition(**data)
            assert module.module_id
            assert module.name

    def test_module_stat_effects(self, db_session, tank_armor_path):
        """T-40c: Module with stat_effects stores and deserializes correctly."""
        from m3_data_vault.dal.ingestion import ingest_module
        from m3_data_vault.db.tables import ModuleCatalogRow
        from m3_data_vault.models.module import ModuleDefinition

        ingest_module(db_session, tank_armor_path)
        db_session.commit()

        row = db_session.query(ModuleCatalogRow).filter_by(module_id="tank_armor").one()
        mod_data = ModuleDefinition(**json.loads(row.data_json))
        assert mod_data.stat_effects is not None
        assert mod_data.stat_effects["dr_front"] == 110
        assert mod_data.stat_effects["dr_rear"] == 55
        assert "triple_dr_vs_plasma" in mod_data.grants_traits
