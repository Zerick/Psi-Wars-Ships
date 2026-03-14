"""
T-35 through T-37: Weapon Catalog Tests
"""
import json
import pytest


class TestWeaponCatalog:

    def test_ingest_valid_weapon(self, db_session, imperial_blaster_path):
        """T-35: A well-formed weapon JSON passes validation and is stored."""
        from m3_data_vault.dal.ingestion import ingest_weapon
        from m3_data_vault.db.tables import WeaponCatalogRow
        from m3_data_vault.models.weapon import WeaponDefinition

        weapon_id = ingest_weapon(db_session, imperial_blaster_path)
        db_session.commit()

        assert weapon_id == "imperial_fighter_blaster"

        row = db_session.query(WeaponCatalogRow).filter_by(
            weapon_id="imperial_fighter_blaster",
        ).one()

        assert row.name == "Imperial Fighter Blaster"
        assert row.file_hash is not None
        assert len(row.file_hash) == 64

        stored = WeaponDefinition(**json.loads(row.data_json))
        assert stored.damage == "6d×5(5) burn"
        assert stored.acc == 9
        assert stored.weapon_type == "beam"

    def test_reject_invalid_weapon(self, invalid_weapon_path):
        """T-36: A weapon JSON missing required fields raises ValidationError."""
        from m3_data_vault.models.weapon import WeaponDefinition
        from pydantic import ValidationError

        data = json.loads(invalid_weapon_path.read_text())
        with pytest.raises(ValidationError):
            WeaponDefinition(**data)

    def test_ship_weapon_ref_resolves(self, seeded_db, make_ship):
        """T-37: A ship's weapon_ref correctly resolves to a catalog weapon."""
        from m3_data_vault.dal.instances import get_effective_stats

        instance_id = make_ship(template_id="javelin_v1")
        stats = get_effective_stats(seeded_db, instance_id)

        assert len(stats.weapons) >= 1
        blaster = stats.weapons[0]
        assert blaster.name == "Imperial Fighter Blaster"
        assert blaster.damage == "6d×5(5) burn"
        assert blaster.acc == 9

    def test_all_fixture_weapons_valid(self):
        """T-37b: Every non-invalid weapon fixture passes validation."""
        from m3_data_vault.models.weapon import WeaponDefinition
        from conftest import WEAPONS_DIR

        for weapon_file in WEAPONS_DIR.glob("*.json"):
            if "invalid" in weapon_file.stem:
                continue
            data = json.loads(weapon_file.read_text())
            weapon = WeaponDefinition(**data)
            assert weapon.weapon_id
            assert weapon.name
