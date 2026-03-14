"""
T-22 through T-26: Damage & State Tests
"""
import pytest


class TestWoundLevels:

    def test_wound_level_thresholds(self, seeded_db, make_ship):
        """T-22: Damage at each threshold produces the correct wound level."""
        from m3_data_vault.dal.instances import apply_damage
        from m3_data_vault.db.tables import ShipInstanceRow

        # Javelin has st_hp = 80
        test_cases = [
            (7, "scratch"),      # 8.75% < 10%
            (8, "minor"),        # 10%
            (39, "minor"),       # 48.75%
            (40, "major"),       # 50%
            (79, "major"),       # 98.75%
            (80, "crippling"),   # 100%
            (159, "crippling"),  # 198.75%
            (160, "mortal"),     # 200%
            (399, "mortal"),     # 498.75%
            (400, "lethal"),     # 500%
        ]

        for damage, expected_level in test_cases:
            instance_id = make_ship(
                template_id="javelin_v1",
                display_name=f"Wound Test ({damage} dmg)",
            )
            apply_damage(seeded_db, instance_id, damage)

            row = seeded_db.query(ShipInstanceRow).filter_by(
                instance_id=instance_id
            ).one()

            assert row.wound_level == expected_level, (
                f"Damage {damage} on 80 HP ship: expected '{expected_level}', "
                f"got '{row.wound_level}'"
            )

    def test_wound_level_capital_ship(self, seeded_db, make_ship):
        """T-22b: Wound thresholds work correctly with large HP values."""
        from m3_data_vault.dal.instances import apply_damage
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="sword_battleship_v1")
        apply_damage(seeded_db, instance_id, 700)  # 10% of 7000

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()
        assert row.wound_level == "minor"


class TestForceScreen:

    def test_fdr_absorbs_damage(self, seeded_db, make_ship):
        """T-23: fDR absorbs damage fully when sufficient."""
        from m3_data_vault.dal.instances import apply_fdr_damage
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="hornet_v1")
        penetrating = apply_fdr_damage(seeded_db, instance_id, 100)

        assert penetrating == 0

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()
        assert row.current_fdr == 50  # 150 - 100

    def test_fdr_penetration(self, seeded_db, make_ship):
        """T-24: Damage exceeding fDR penetrates with correct remainder."""
        from m3_data_vault.dal.instances import apply_fdr_damage
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="hornet_v1")
        penetrating = apply_fdr_damage(seeded_db, instance_id, 200)

        assert penetrating == 50  # 200 - 150

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()
        assert row.current_fdr == 0

    def test_fdr_already_depleted(self, seeded_db, make_ship):
        """T-24b: If fDR is already 0, all damage penetrates."""
        from m3_data_vault.dal.instances import apply_fdr_damage

        instance_id = make_ship(template_id="hornet_v1")
        apply_fdr_damage(seeded_db, instance_id, 150)
        penetrating = apply_fdr_damage(seeded_db, instance_id, 50)
        assert penetrating == 50

    def test_fdr_reset(self, seeded_db, make_ship):
        """T-25: reset_fdr() restores current_fdr to fdr_max."""
        from m3_data_vault.dal.instances import apply_fdr_damage, reset_fdr
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="hornet_v1")
        apply_fdr_damage(seeded_db, instance_id, 100)

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()
        assert row.current_fdr == 50

        reset_fdr(seeded_db, instance_id)
        seeded_db.refresh(row)
        assert row.current_fdr == 150


class TestSystemStatus:

    def test_system_status_update(self, seeded_db, make_ship):
        """T-26: update_system_status() correctly sets the status."""
        from m3_data_vault.dal.instances import update_system_status
        from m3_data_vault.db.tables import SystemStatusRow

        instance_id = make_ship(template_id="javelin_v1")
        update_system_status(seeded_db, instance_id, "propulsion", "disabled")

        row = seeded_db.query(SystemStatusRow).filter_by(
            instance_id=instance_id, system_type="propulsion",
        ).one()
        assert row.status == "disabled"

    def test_system_status_to_destroyed(self, seeded_db, make_ship):
        """T-26b: Systems can progress from disabled to destroyed."""
        from m3_data_vault.dal.instances import update_system_status
        from m3_data_vault.db.tables import SystemStatusRow

        instance_id = make_ship(template_id="javelin_v1")
        update_system_status(seeded_db, instance_id, "weaponry", "disabled")
        update_system_status(seeded_db, instance_id, "weaponry", "destroyed")

        row = seeded_db.query(SystemStatusRow).filter_by(
            instance_id=instance_id, system_type="weaponry",
        ).one()
        assert row.status == "destroyed"

    def test_invalid_system_type_raises(self, seeded_db, make_ship):
        """T-26c: Invalid system type raises ValueError."""
        from m3_data_vault.dal.instances import update_system_status

        instance_id = make_ship(template_id="javelin_v1")
        with pytest.raises(ValueError):
            update_system_status(seeded_db, instance_id, "warp_core", "disabled")

    def test_invalid_status_raises(self, seeded_db, make_ship):
        """T-26d: Invalid status value raises ValueError."""
        from m3_data_vault.dal.instances import update_system_status

        instance_id = make_ship(template_id="javelin_v1")
        with pytest.raises(ValueError):
            update_system_status(seeded_db, instance_id, "propulsion", "on_fire")
