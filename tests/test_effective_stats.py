"""
T-12 through T-18: Effective Stats Resolution Tests

Verifies the get_effective_stats() pipeline: base template -> modules ->
modes -> system damage penalties -> weapon assembly.
"""
import pytest


class TestBaseStats:
    """Stats resolution with no modes or damage applied."""

    def test_base_stats_no_mode(self, seeded_db, make_ship):
        """T-12: get_effective_stats() on a fresh Javelin returns base template values."""
        from m3_data_vault.dal.instances import get_effective_stats

        instance_id = make_ship(template_id="javelin_v1")
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.st_hp == 80
        assert stats.ht == "9f"
        assert stats.hnd == 4
        assert stats.sr == 3
        assert stats.accel == 20
        assert stats.top_speed == 600
        assert stats.stall_speed == 35
        assert stats.dr_front == 15
        assert stats.dr_rear == 15
        assert stats.fdr_max == 0
        assert stats.ecm_rating == -4

    def test_base_stats_hornet(self, seeded_db, make_ship):
        """T-12b: Hornet base stats in standard mode."""
        from m3_data_vault.dal.instances import get_effective_stats

        instance_id = make_ship(template_id="hornet_v1")
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.hnd == 6
        assert stats.accel == 15
        assert stats.top_speed == 500
        assert stats.fdr_max == 150

    def test_base_stats_capital_ship(self, seeded_db, make_ship):
        """T-12c: Capital ship effective stats with directional DR."""
        from m3_data_vault.dal.instances import get_effective_stats

        instance_id = make_ship(template_id="sword_battleship_v1")
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.st_hp == 7000
        assert stats.dr_front == 5000
        assert stats.dr_rear == 2500
        assert stats.dr_left == 2500
        assert stats.fdr_max == 10000
        assert stats.hnd == -4


class TestModeOverrides:
    """Stats resolution with mode switching."""

    def test_mode_override(self, seeded_db, make_ship):
        """T-13: Switching Hornet to 'High Maneuverability' overrides stats."""
        from m3_data_vault.dal.instances import get_effective_stats, set_mode

        instance_id = make_ship(template_id="hornet_v1")
        set_mode(seeded_db, instance_id, "High Maneuverability")
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.hnd == 7      # overridden from 6
        assert stats.accel == 3     # overridden from 15
        assert stats.top_speed == 250  # overridden from 500
        # SR should be unchanged (not mentioned in mode)
        assert stats.sr == 3

    def test_mode_standard_reset(self, seeded_db, make_ship):
        """T-14: Setting mode back to 'standard' restores base stats."""
        from m3_data_vault.dal.instances import get_effective_stats, set_mode

        instance_id = make_ship(template_id="hornet_v1")

        set_mode(seeded_db, instance_id, "High Maneuverability")
        stats_hm = get_effective_stats(seeded_db, instance_id)
        assert stats_hm.hnd == 7

        set_mode(seeded_db, instance_id, "standard")
        stats_std = get_effective_stats(seeded_db, instance_id)
        assert stats_std.hnd == 6
        assert stats_std.accel == 15
        assert stats_std.top_speed == 500

    def test_invalid_mode_raises(self, seeded_db, make_ship):
        """T-14b: Setting a nonexistent mode raises ValueError."""
        from m3_data_vault.dal.instances import set_mode

        instance_id = make_ship(template_id="javelin_v1")

        with pytest.raises(ValueError, match="[Ii]nvalid mode"):
            set_mode(seeded_db, instance_id, "Nonexistent Mode")


class TestSystemDamagePenalties:
    """Stats resolution with disabled/destroyed systems."""

    def test_disabled_propulsion_halves_speed(self, seeded_db, make_ship):
        """T-15: Disabling propulsion halves top_speed in effective stats."""
        from m3_data_vault.dal.instances import get_effective_stats, update_system_status

        instance_id = make_ship(template_id="javelin_v1")
        update_system_status(seeded_db, instance_id, "propulsion", "disabled")
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.top_speed == 300  # 600 / 2

    def test_destroyed_propulsion_zeroes_speed(self, seeded_db, make_ship):
        """T-16: Destroying propulsion sets top_speed and accel to 0."""
        from m3_data_vault.dal.instances import get_effective_stats, update_system_status

        instance_id = make_ship(template_id="javelin_v1")
        update_system_status(seeded_db, instance_id, "propulsion", "destroyed")
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.top_speed == 0
        assert stats.accel == 0

    def test_disabled_controls_reduces_handling(self, seeded_db, make_ship):
        """T-17: Disabling controls reduces hnd by 2."""
        from m3_data_vault.dal.instances import get_effective_stats, update_system_status

        instance_id = make_ship(template_id="hornet_v1")
        update_system_status(seeded_db, instance_id, "controls", "disabled")
        stats = get_effective_stats(seeded_db, instance_id)

        # Hornet base hnd = 6, disabled controls = 6 - 2 = 4
        assert stats.hnd == 4

    def test_mode_and_damage_stack(self, seeded_db, make_ship):
        """T-17b: Mode overrides apply BEFORE system damage penalties."""
        from m3_data_vault.dal.instances import get_effective_stats, set_mode, update_system_status

        instance_id = make_ship(template_id="hornet_v1")
        set_mode(seeded_db, instance_id, "High Maneuverability")
        update_system_status(seeded_db, instance_id, "propulsion", "disabled")
        stats = get_effective_stats(seeded_db, instance_id)

        # Mode sets top_speed to 250, then propulsion disabled halves it to 125
        assert stats.top_speed == 125
        assert stats.hnd == 7


class TestModuleEffects:
    """Stats resolution with installed modules."""

    def test_module_affects_stats(self, seeded_db, make_ship):
        """T-18: Installing an armor module that changes DR is reflected in stats."""
        from m3_data_vault.dal.instances import get_effective_stats

        loadout = {"armor": "tank_armor"}
        instance_id = make_ship(
            template_id="wildcat_v1",
            module_loadout=loadout,
        )
        stats = get_effective_stats(seeded_db, instance_id)

        # Tank armor overrides DR to 110 front, 55 everywhere else
        assert stats.dr_front == 110
        assert stats.dr_rear == 55
        assert stats.dr_left == 55

    def test_force_screen_module(self, seeded_db, make_ship):
        """T-18b: Installing a force screen module sets fdr_max on effective stats."""
        from m3_data_vault.dal.instances import get_effective_stats
        from m3_data_vault.db.tables import ShipInstanceRow

        loadout = {"accessory": "silverback_force_screen"}
        instance_id = make_ship(
            template_id="wildcat_v1",
            module_loadout=loadout,
        )
        stats = get_effective_stats(seeded_db, instance_id)

        # Silverback provides 300 fDR
        assert stats.fdr_max == 300

        row = seeded_db.query(ShipInstanceRow).filter_by(
            instance_id=instance_id
        ).one()
        assert row.current_fdr == 300
