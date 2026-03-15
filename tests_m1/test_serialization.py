"""
Tests for game state serialization.

Every object that crosses the engine/UI boundary must serialize
to plain JSON-compatible dicts with no Python-specific types.
"""
import json
import pytest
from m1_psi_core.testing import MockShipStats, MockPilot


class TestShipSerialization:
    """Ship + pilot serialize to a complete, JSON-safe dict."""

    def test_basic_ship_serializes(self):
        from m1_psi_core.serialization import serialize_ship

        ship = MockShipStats(display_name="Test Fighter", sm=4, st_hp=80)
        pilot = MockPilot(name="Test Pilot", piloting_skill=14)

        result = serialize_ship(ship, pilot, "s1", "empire", "human")

        # Must be JSON-serializable
        json_str = json.dumps(result)
        assert len(json_str) > 100

        # Core fields present
        assert result["display_name"] == "Test Fighter"
        assert result["sm"] == 4
        assert result["st_hp"] == 80
        assert result["pilot"]["name"] == "Test Pilot"
        assert result["pilot"]["piloting_skill"] == 14

    def test_ship_without_pilot(self):
        from m1_psi_core.serialization import serialize_ship

        ship = MockShipStats(display_name="Drone")
        result = serialize_ship(ship)
        assert result["pilot"] is None

    def test_all_dr_facings_present(self):
        from m1_psi_core.serialization import serialize_ship

        ship = MockShipStats(dr_front=500, dr_rear=100)
        result = serialize_ship(ship)
        assert "dr_front" in result
        assert "dr_rear" in result
        assert "dr_left" in result
        assert "dr_top" in result
        assert result["dr_front"] == 500
        assert result["dr_rear"] == 100

    def test_weapons_included(self):
        from m1_psi_core.serialization import serialize_ship

        ship = MockShipStats(weapons=[
            {"weapon_ref": "imperial_fighter_blaster", "mount": "fixed_front",
             "linked_count": 2, "arc": "front"},
        ])
        result = serialize_ship(ship)
        assert len(result["weapons"]) >= 1
        assert result["weapons"][0]["name"] == "Imperial Fighter Blaster"

    def test_subsystem_damage_included(self):
        from m1_psi_core.serialization import serialize_ship
        from m1_psi_core.subsystems import disable_system

        ship = MockShipStats()
        disable_system(ship, "propulsion")
        result = serialize_ship(ship)
        assert "propulsion" in result["disabled_systems"]

    def test_luck_level_in_pilot(self):
        from m1_psi_core.serialization import serialize_ship

        ship = MockShipStats()
        pilot = MockPilot(luck_level="extraordinary")
        result = serialize_ship(ship, pilot)
        assert result["pilot"]["luck_level"] == "extraordinary"


class TestEngagementSerialization:
    """Engagement state serializes cleanly."""

    def test_basic_engagement(self):
        from m1_psi_core.serialization import serialize_engagement
        from m1_psi_core.combat_state import EngagementState

        eng = EngagementState(ship_a_id="s1", ship_b_id="s2", range_band="long")
        eng.set_advantage("s1")

        result = serialize_engagement(eng)
        json_str = json.dumps(result)
        assert len(json_str) > 50

        assert result["range_band"] == "long"
        assert result["advantage"] == "s1"
        assert result["matched_speed"] is False


class TestSessionSerialization:
    """Full session serializes with all ships, engagements, factions."""

    def test_full_session(self):
        from m1_psi_core.serialization import serialize_session
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire", "red")
        session.add_faction("trader", "blue")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1", display_name="Alpha")
        ship_b = MockShipStats(instance_id="s2", display_name="Bravo")
        pilot_a = MockPilot(name="Pilot A")
        pilot_b = MockPilot(name="Pilot B")

        session.register_ship("s1", ship_a, pilot_a, "empire", "human")
        session.register_ship("s2", ship_b, pilot_b, "trader", "npc")
        session.create_engagement("s1", "s2", "long")

        result = serialize_session(session)
        json_str = json.dumps(result)

        assert result["current_turn"] == 1
        assert "s1" in result["ships"]
        assert "s2" in result["ships"]
        assert len(result["engagements"]) == 1
        assert "empire" in result["factions"]
        assert result["combat_ended"] is False


class TestResultSerialization:
    """Attack, defense, and damage results serialize cleanly."""

    def test_attack_result(self):
        from m1_psi_core.serialization import serialize_attack_result
        from m1_psi_core.engine import resolve_attack, WeaponInfo
        from m1_psi_core.combat_state import EngagementState
        from m1_psi_core.dice import DiceRoller

        a = MockShipStats(instance_id="a1", display_name="Alpha")
        t = MockShipStats(instance_id="b1", display_name="Bravo")
        p = MockPilot()
        eng = EngagementState(ship_a_id="a1", ship_b_id="b1", range_band="long")
        w = WeaponInfo(name="Blaster", damage_str="6d×5(5) burn", acc=9, rof=3,
                       weapon_type="beam", armor_divisor=5.0, mount="fixed_front",
                       linked_count=1, is_explosive=False)

        atk = resolve_attack("a1", a, p, "b1", t, eng,
                             {"maneuver": "move_and_attack", "intent": "pursue"},
                             w, DiceRoller(seed=42))

        result = serialize_attack_result(atk)
        json_str = json.dumps(result)
        assert "attacker_name" in result
        assert "modifiers" in result
        assert isinstance(result["roll"], int)

    def test_damage_result(self):
        from m1_psi_core.serialization import serialize_damage_result
        from m1_psi_core.engine import resolve_damage, WeaponInfo
        from m1_psi_core.testing import MockDice

        t = MockShipStats(instance_id="t1", display_name="Target",
                          st_hp=100, current_hp=100, dr_front=10,
                          fdr_max=0, force_screen_type="none", current_fdr=0)
        w = WeaponInfo(name="Blaster", damage_str="6d×5(5) burn", acc=9, rof=3,
                       weapon_type="beam", armor_divisor=5.0, mount="fixed_front",
                       linked_count=1, is_explosive=False)

        dmg = resolve_damage("t1", t, w, MockDice([20, 10, 10, 10]), facing="front")
        result = serialize_damage_result(dmg)
        json_str = json.dumps(result)
        assert "raw_damage" in result
        assert "steps" in result
        assert isinstance(result["steps"], list)
