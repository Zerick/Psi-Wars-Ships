"""
T-27 through T-28: Sync & Hash-Check Tests
"""
import json
import shutil
import pytest


class TestHashSync:

    def test_hash_sync_detects_change(self, db_session, tmp_path):
        """T-27: Changing a JSON file's content triggers re-ingestion."""
        from m3_data_vault.dal.ingestion import sync_all_weapons

        weapons_dir = tmp_path / "weapons"
        weapons_dir.mkdir()
        weapon_data = {
            "weapon_id": "test_weapon", "name": "Test Blaster",
            "damage": "6d burn", "acc": 9, "range": "100/300", "rof": "3",
            "rcl": 2, "shots": "100", "ewt": "500", "st_requirement": "M",
            "bulk": "-10", "weapon_type": "beam", "damage_type": "burn",
            "armor_divisor": None, "notes": "", "tags": ["test"], "version": "1.0.0",
        }
        (weapons_dir / "test_weapon.json").write_text(json.dumps(weapon_data))

        report1 = sync_all_weapons(db_session, weapons_dir)
        db_session.commit()
        assert report1.added == 1
        assert report1.updated == 0

        weapon_data["name"] = "Modified Test Blaster"
        weapon_data["version"] = "1.1.0"
        (weapons_dir / "test_weapon.json").write_text(json.dumps(weapon_data))

        report2 = sync_all_weapons(db_session, weapons_dir)
        db_session.commit()
        assert report2.added == 0
        assert report2.updated == 1

    def test_hash_sync_skips_unchanged(self, db_session, tmp_path):
        """T-28: Syncing unchanged files reports 0 updated."""
        from m3_data_vault.dal.ingestion import sync_all_weapons, sync_all_templates
        from tests.paths import WEAPONS_DIR, SHIPS_DIR

        weapons_dir = tmp_path / "weapons"
        weapons_dir.mkdir()
        ships_dir = tmp_path / "ships"
        ships_dir.mkdir()

        shutil.copy(WEAPONS_DIR / "imperial_fighter_blaster.json", weapons_dir)
        shutil.copy(SHIPS_DIR / "javelin_v1.json", ships_dir)

        sync_all_weapons(db_session, weapons_dir)
        db_session.commit()

        report1 = sync_all_templates(db_session, ships_dir)
        db_session.commit()
        assert report1.added == 1

        report2 = sync_all_templates(db_session, ships_dir)
        db_session.commit()
        assert report2.added == 0
        assert report2.updated == 0
        assert report2.unchanged == 1

    def test_sync_mixed_states(self, db_session, tmp_path):
        """T-28b: Sync handles a mix of new, changed, and unchanged files."""
        from m3_data_vault.dal.ingestion import sync_all_weapons

        weapons_dir = tmp_path / "weapons"
        weapons_dir.mkdir()

        base = {
            "damage": "1d burn", "acc": 1, "range": "10/30", "rof": "1",
            "rcl": 1, "shots": "10", "ewt": "100", "st_requirement": "M",
            "bulk": "-5", "weapon_type": "beam", "damage_type": "burn",
            "armor_divisor": None, "notes": "", "tags": [], "version": "1.0.0",
        }

        for name in ["alpha", "beta"]:
            data = {**base, "weapon_id": name, "name": f"Weapon {name}"}
            (weapons_dir / f"{name}.json").write_text(json.dumps(data))

        report1 = sync_all_weapons(db_session, weapons_dir)
        db_session.commit()
        assert report1.added == 2

        alpha_data = {**base, "weapon_id": "alpha", "name": "Modified Alpha", "version": "2.0.0"}
        (weapons_dir / "alpha.json").write_text(json.dumps(alpha_data))
        gamma_data = {**base, "weapon_id": "gamma", "name": "Weapon gamma"}
        (weapons_dir / "gamma.json").write_text(json.dumps(gamma_data))

        report2 = sync_all_weapons(db_session, weapons_dir)
        db_session.commit()
        assert report2.added == 1      # gamma
        assert report2.updated == 1    # alpha
        assert report2.unchanged == 1  # beta
