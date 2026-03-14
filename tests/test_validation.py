"""
T-01 through T-07: Ingestion & Validation Tests

Verifies that Pydantic models correctly accept valid JSON and reject
invalid JSON with clear errors.
"""
import json
import re
import pytest


# ---------------------------------------------------------------------------
# Helper: validate HT pattern without constructing a full ShipTemplate
# ---------------------------------------------------------------------------

def _ht_is_valid(ht_value: str) -> bool:
    """
    Test whether a given HT string matches the expected pattern:
    one or more digits (starting with non-zero), optionally followed
    by a recognized suffix: 'f' (fragile) or 'x' (explosive).
    """
    pattern = r"^[1-9]\d*[fx]?$"
    return bool(re.match(pattern, ht_value))


class TestShipTemplateValidation:
    """Tests for ShipTemplate Pydantic model validation."""

    def test_load_valid_template_javelin(self, javelin_path):
        """T-01: A well-formed ship JSON passes Pydantic validation."""
        from m3_data_vault.models.template import ShipTemplate

        data = json.loads(javelin_path.read_text())
        template = ShipTemplate(**data)

        assert template.template_id == "javelin_v1"
        assert template.name == "Javelin Class Fighter"
        assert template.attributes.st_hp == 80
        assert template.attributes.ht == "9f"
        assert template.attributes.hnd == 4
        assert template.attributes.sr == 3
        assert template.mobility.accel == 20
        assert template.mobility.top_speed == 600
        assert template.mobility.stall_speed == 35
        assert template.defense.dr_front == 15
        assert template.defense.fdr_max == 0
        assert template.defense.force_screen_type == "none"
        assert template.afterburner is not None
        assert template.afterburner.top_speed == 750
        assert len(template.weapons) == 1
        assert template.weapons[0].weapon_ref == "imperial_fighter_blaster"
        assert template.module_slots == []

    def test_load_valid_template_hornet(self, hornet_path):
        """T-01b: Hornet with force screen, modes, and multiple weapons validates."""
        from m3_data_vault.models.template import ShipTemplate

        data = json.loads(hornet_path.read_text())
        template = ShipTemplate(**data)

        assert template.template_id == "hornet_v1"
        assert template.defense.fdr_max == 150
        assert template.defense.force_screen_type == "standard"
        assert "High Maneuverability" in template.modes
        assert template.modes["High Maneuverability"]["hnd"] == 7
        assert len(template.weapons) == 2
        assert template.afterburner is None

    def test_load_valid_template_wildcat_modules(self, wildcat_path):
        """T-01c: Wildcat with module slots validates correctly."""
        from m3_data_vault.models.template import ShipTemplate

        data = json.loads(wildcat_path.read_text())
        template = ShipTemplate(**data)

        assert template.template_id == "wildcat_v1"
        assert len(template.module_slots) == 5
        slot_ids = [s.slot_id for s in template.module_slots]
        assert "main_weapon" in slot_ids
        assert "wing_left" in slot_ids
        assert "armor" in slot_ids
        assert "Heavy Module Loaded" in template.modes

    def test_load_valid_template_capital_ship(self, sword_path):
        """T-01d: Capital ship with large numbers and craft complement validates."""
        from m3_data_vault.models.template import ShipTemplate

        data = json.loads(sword_path.read_text())
        template = ShipTemplate(**data)

        assert template.attributes.st_hp == 7000
        assert template.defense.dr_front == 5000
        assert template.defense.dr_rear == 2500
        assert template.defense.fdr_max == 10000
        assert template.defense.force_screen_type == "heavy"
        assert template.attributes.hnd == -4  # Negative handling for capital ships
        assert len(template.craft_complement) == 1
        assert template.craft_complement[0].count == 5

    def test_reject_invalid_template(self, invalid_ship_path):
        """T-02: A JSON with missing/invalid fields raises ValidationError."""
        from m3_data_vault.models.template import ShipTemplate
        from pydantic import ValidationError

        data = json.loads(invalid_ship_path.read_text())

        with pytest.raises(ValidationError) as exc_info:
            ShipTemplate(**data)

        # Should have multiple errors: negative HP, bad HT suffix, missing fields
        errors = exc_info.value.errors()
        assert len(errors) >= 2

    def test_ht_suffix_acceptance(self):
        """T-03: HT values with valid suffixes pass validation."""
        valid_ht_values = ["9f", "8x", "12", "13", "14", "11f"]

        for ht_val in valid_ht_values:
            assert _ht_is_valid(ht_val), f"HT value '{ht_val}' should be valid"

    def test_ht_suffix_rejection(self):
        """T-04: HT values with invalid suffixes fail validation."""
        invalid_ht_values = ["12z", "abc", "f9", "", "12fx", "0"]

        for ht_val in invalid_ht_values:
            assert not _ht_is_valid(ht_val), f"HT value '{ht_val}' should be invalid"


class TestIngestionToDatabase:
    """Tests for the ingest pipeline writing to the database."""

    def test_ingest_writes_to_db(self, db_session, javelin_path, imperial_blaster_path):
        """T-05: After ingest_template(), a matching row exists with correct hash."""
        from m3_data_vault.dal.ingestion import ingest_weapon, ingest_template
        from m3_data_vault.db.tables import ShipTemplateRow

        # Must ingest weapon first since Javelin references it
        ingest_weapon(db_session, imperial_blaster_path)
        template_id = ingest_template(db_session, javelin_path)
        db_session.commit()

        assert template_id == "javelin_v1"

        row = db_session.query(ShipTemplateRow).filter_by(
            template_id="javelin_v1"
        ).one()

        assert row.version == "1.0.0"
        assert row.name == "Javelin Class Fighter"
        assert row.file_hash is not None
        assert len(row.file_hash) == 64  # SHA-256 hex digest length
        assert row.ingested_at is not None

    def test_ingest_upsert_on_change(self, db_session, tmp_path, imperial_blaster_path):
        """T-06: Modifying a JSON file and re-ingesting updates the record."""
        from m3_data_vault.dal.ingestion import ingest_weapon, ingest_template
        from m3_data_vault.db.tables import ShipTemplateRow
        from conftest import SHIPS_DIR

        ingest_weapon(db_session, imperial_blaster_path)

        # Create a temp copy of javelin, ingest it
        original = (SHIPS_DIR / "javelin_v1.json").read_text()
        temp_file = tmp_path / "javelin_v1.json"
        temp_file.write_text(original)
        ingest_template(db_session, temp_file)
        db_session.commit()

        row1 = db_session.query(ShipTemplateRow).filter_by(
            template_id="javelin_v1"
        ).one()
        original_hash = row1.file_hash
        original_time = row1.ingested_at

        # Modify the file (change the version)
        data = json.loads(original)
        data["version"] = "1.1.0"
        temp_file.write_text(json.dumps(data))

        ingest_template(db_session, temp_file)
        db_session.commit()

        row2 = db_session.query(ShipTemplateRow).filter_by(
            template_id="javelin_v1"
        ).one()

        assert row2.file_hash != original_hash
        assert row2.version == "1.1.0"
        assert row2.ingested_at >= original_time

    def test_ingest_skip_unchanged(self, db_session, javelin_path, imperial_blaster_path):
        """T-07: Re-ingesting an unchanged file is a no-op."""
        from m3_data_vault.dal.ingestion import ingest_weapon, ingest_template
        from m3_data_vault.db.tables import ShipTemplateRow

        ingest_weapon(db_session, imperial_blaster_path)
        ingest_template(db_session, javelin_path)
        db_session.commit()

        row1 = db_session.query(ShipTemplateRow).filter_by(
            template_id="javelin_v1"
        ).one()
        first_hash = row1.file_hash
        first_time = row1.ingested_at

        # Ingest again — same file, no changes
        ingest_template(db_session, javelin_path)
        db_session.commit()

        row2 = db_session.query(ShipTemplateRow).filter_by(
            template_id="javelin_v1"
        ).one()

        assert row2.file_hash == first_hash
        assert row2.ingested_at == first_time
