"""
T-19 through T-21: Controller & Faction Tests
"""
import pytest


class TestControllerFaction:

    def test_controller_assignment(self, seeded_db, make_ship, make_controller):
        """T-19: Ship inherits apparent faction from controller, not template."""
        from m3_data_vault.dal.instances import get_effective_stats

        ctrl_id = make_controller(name="Rebel Pilot", faction="rebel")
        instance_id = make_ship(template_id="javelin_v1", controller_id=ctrl_id)
        stats = get_effective_stats(seeded_db, instance_id)

        assert stats.faction == "rebel"

    def test_transfer_control(self, seeded_db, make_ship, make_controller):
        """T-20: transfer_control() changes the controller and thus faction."""
        from m3_data_vault.dal.instances import get_effective_stats
        from m3_data_vault.dal.controllers import transfer_control

        imperial_ctrl = make_controller(name="Imperial Ace", faction="empire")
        rebel_ctrl = make_controller(name="Rebel Defector", faction="rebel")
        instance_id = make_ship(template_id="javelin_v1", controller_id=imperial_ctrl)

        stats1 = get_effective_stats(seeded_db, instance_id)
        assert stats1.faction == "empire"

        transfer_control(seeded_db, instance_id, rebel_ctrl)
        stats2 = get_effective_stats(seeded_db, instance_id)
        assert stats2.faction == "rebel"

    def test_uncontrolled_ship(self, seeded_db, make_ship):
        """T-21: A ship with controller_id=None returns faction 'uncontrolled'."""
        from m3_data_vault.dal.instances import get_effective_stats

        instance_id = make_ship(template_id="javelin_v1", controller_id=None)
        stats = get_effective_stats(seeded_db, instance_id)
        assert stats.faction == "uncontrolled"

    def test_transfer_to_none(self, seeded_db, make_ship, make_controller):
        """T-21b: Transferring control to None makes the ship uncontrolled."""
        from m3_data_vault.dal.instances import get_effective_stats
        from m3_data_vault.dal.controllers import transfer_control

        ctrl_id = make_controller(name="Pilot", faction="trader")
        instance_id = make_ship(template_id="hornet_v1", controller_id=ctrl_id)

        stats1 = get_effective_stats(seeded_db, instance_id)
        assert stats1.faction == "trader"

        transfer_control(seeded_db, instance_id, None)
        stats2 = get_effective_stats(seeded_db, instance_id)
        assert stats2.faction == "uncontrolled"
