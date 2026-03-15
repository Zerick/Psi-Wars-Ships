"""
T-29: Session Snapshot Tests
"""
import json
import pytest


class TestSessionSnapshot:

    def test_session_snapshot_roundtrip(self, seeded_db, make_ship, make_controller):
        """T-29: Full roundtrip - create ships with varied state, export, import, verify."""
        from m3_data_vault.dal.instances import (
            apply_damage, apply_fdr_damage, set_mode, add_custom_weapon,
        )
        from m3_data_vault.dal.snapshots import export_session_snapshot, import_session_snapshot
        from m3_data_vault.db.engine import create_engine_and_tables
        from m3_data_vault.db.session import get_session
        from m3_data_vault.db.tables import ShipInstanceRow, SystemStatusRow
        from m3_data_vault.dal.ingestion import ingest_template, ingest_weapon, ingest_module
        from tests.paths import WEAPONS_DIR, MODULES_DIR, SHIPS_DIR

        session_id = "snapshot_test_session"

        imperial_ctrl = make_controller(name="Imperial Ace", faction="empire", is_ace=True)
        rebel_ctrl = make_controller(name="Rebel Pilot", faction="rebel")

        # Ship 1: Damaged Javelin
        javelin_id = make_ship(
            template_id="javelin_v1", controller_id=imperial_ctrl,
            display_name="Red Five", session_id=session_id,
        )
        apply_damage(seeded_db, javelin_id, 40)
        from m3_data_vault.dal.instances import update_system_status
        update_system_status(seeded_db, javelin_id, "propulsion", "disabled")

        # Ship 2: Hornet in non-standard mode
        hornet_id = make_ship(
            template_id="hornet_v1", controller_id=rebel_ctrl,
            display_name="Stinger One", session_id=session_id,
        )
        set_mode(seeded_db, hornet_id, "High Maneuverability")
        apply_fdr_damage(seeded_db, hornet_id, 120)

        # Ship 3: Wildcat with modules and custom weapon
        wildcat_id = make_ship(
            template_id="wildcat_v1", controller_id=rebel_ctrl,
            display_name="Frankenstein", session_id=session_id,
            module_loadout={"main_weapon": "boom_cannon_module", "armor": "tank_armor"},
        )
        custom_wpn = {
            "weapon_id": "grafted_tractor_beam", "name": "Salvaged Tractor Beam",
            "damage": "0", "acc": 0, "range": "500/2000", "rof": "1", "rcl": 1,
            "shots": "NA", "ewt": "2000", "st_requirement": "M", "bulk": "-10",
            "weapon_type": "tractor", "damage_type": "special", "armor_divisor": None,
            "notes": "Salvaged", "tags": ["custom"], "version": "1.0.0",
        }
        add_custom_weapon(seeded_db, wildcat_id, custom_wpn)
        seeded_db.commit()

        # --- Export ---
        snapshot = export_session_snapshot(seeded_db, session_id)
        snapshot_json = json.dumps(snapshot)
        assert len(snapshot_json) > 0

        # --- Import into fresh database ---
        fresh_engine = create_engine_and_tables("sqlite:///:memory:")
        fresh_session = get_session(fresh_engine)

        try:
            for f in WEAPONS_DIR.glob("*.json"):
                if "invalid" not in f.stem:
                    ingest_weapon(fresh_session, f)
            for f in MODULES_DIR.glob("*.json"):
                if "invalid" not in f.stem:
                    ingest_module(fresh_session, f)
            for f in SHIPS_DIR.glob("*.json"):
                if "invalid" not in f.stem:
                    ingest_template(fresh_session, f)
            fresh_session.commit()

            imported_session_id = import_session_snapshot(fresh_session, snapshot)
            fresh_session.commit()
            assert imported_session_id == session_id

            # Verify Javelin
            javelin_row = fresh_session.query(ShipInstanceRow).filter_by(instance_id=javelin_id).one()
            assert javelin_row.wound_level == "major"
            assert javelin_row.display_name == "Red Five"

            prop_status = fresh_session.query(SystemStatusRow).filter_by(
                instance_id=javelin_id, system_type="propulsion",
            ).one()
            assert prop_status.status == "disabled"

            # Verify Hornet
            hornet_row = fresh_session.query(ShipInstanceRow).filter_by(instance_id=hornet_id).one()
            assert hornet_row.active_mode == "High Maneuverability"
            assert hornet_row.current_fdr == 30

            # Verify Wildcat
            wildcat_row = fresh_session.query(ShipInstanceRow).filter_by(instance_id=wildcat_id).one()
            installed = json.loads(wildcat_row.installed_modules)
            assert installed["main_weapon"] == "boom_cannon_module"
            custom_weapons = json.loads(wildcat_row.custom_weapons)
            assert len(custom_weapons) == 1
            assert custom_weapons[0]["weapon_id"] == "grafted_tractor_beam"
        finally:
            fresh_session.close()
