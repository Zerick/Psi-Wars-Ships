"""
T-30 through T-31: Custom Weapon Tests
"""
import json
import pytest

CUSTOM_TRACTOR_BEAM = {
    "weapon_id": "salvaged_tractor_beam", "name": "Salvaged Tractor Beam",
    "damage": "0", "acc": 0, "range": "500/2000", "rof": "1", "rcl": 1,
    "shots": "NA", "ewt": "2000", "st_requirement": "M", "bulk": "-10",
    "weapon_type": "tractor", "damage_type": "special", "armor_divisor": None,
    "notes": "Salvaged from a captured corvette.", "tags": ["custom"], "version": "1.0.0",
}


class TestCustomWeapons:

    def test_add_custom_weapon(self, seeded_db, make_ship):
        """T-30: add_custom_weapon() makes the weapon visible in effective stats."""
        from m3_data_vault.dal.instances import get_effective_stats, add_custom_weapon

        instance_id = make_ship(template_id="javelin_v1")
        stats_before = get_effective_stats(seeded_db, instance_id)
        weapon_count_before = len(stats_before.weapons)

        add_custom_weapon(seeded_db, instance_id, CUSTOM_TRACTOR_BEAM)
        seeded_db.commit()

        stats_after = get_effective_stats(seeded_db, instance_id)
        assert len(stats_after.weapons) == weapon_count_before + 1
        custom_names = [w.name for w in stats_after.weapons]
        assert "Salvaged Tractor Beam" in custom_names

    def test_custom_weapon_persists_in_db(self, seeded_db, make_ship):
        """T-31: Custom weapons are stored in the instance row and survive re-reads."""
        from m3_data_vault.dal.instances import add_custom_weapon
        from m3_data_vault.db.tables import ShipInstanceRow

        instance_id = make_ship(template_id="javelin_v1")
        add_custom_weapon(seeded_db, instance_id, CUSTOM_TRACTOR_BEAM)
        seeded_db.commit()

        row = seeded_db.query(ShipInstanceRow).filter_by(instance_id=instance_id).one()
        custom_list = json.loads(row.custom_weapons)
        assert len(custom_list) == 1
        assert custom_list[0]["weapon_id"] == "salvaged_tractor_beam"

    def test_multiple_custom_weapons(self, seeded_db, make_ship):
        """T-31b: Multiple custom weapons can be added to the same instance."""
        from m3_data_vault.dal.instances import get_effective_stats, add_custom_weapon

        instance_id = make_ship(template_id="wildcat_v1")
        weapon_a = {**CUSTOM_TRACTOR_BEAM, "weapon_id": "custom_a", "name": "Custom A"}
        weapon_b = {**CUSTOM_TRACTOR_BEAM, "weapon_id": "custom_b", "name": "Custom B"}

        add_custom_weapon(seeded_db, instance_id, weapon_a)
        add_custom_weapon(seeded_db, instance_id, weapon_b)
        seeded_db.commit()

        stats = get_effective_stats(seeded_db, instance_id)
        custom_names = [w.name for w in stats.weapons if w.weapon_id.startswith("custom_")]
        assert "Custom A" in custom_names
        assert "Custom B" in custom_names
