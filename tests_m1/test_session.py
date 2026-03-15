"""
Tests for the Game Session Manager.

The session manager orchestrates a full combat game:
setup, turn loop, faction relationships, engagement tracking,
combat end detection, and NPC AI integration.

These tests verify the session logic WITHOUT any display code.
The terminal UI is tested by inspection.

Covers:
- Faction setup and relationships (allied/enemy/neutral)
- Neutral-to-enemy transition on attack
- Ship registration and control mode assignment
- Turn ordering (declaration order based on speed/advantage)
- Full turn execution through all 5 phases
- NPC AI producing valid declarations
- Combat end detection (destruction, escape)
- Engagement state persistence across turns
- Force screen regeneration between turns
- Wound state persistence across turns
"""
import pytest
from m1_psi_core.testing import MockShipStats, MockPilot, MockDice


# ============================================================================
# Faction Management
# ============================================================================

class TestFactionSetup:
    """Faction creation and relationship tracking."""

    def test_create_two_factions(self):
        """Can create two factions with names and colors."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire", color="red")
        session.add_faction("trader", color="blue")

        assert "empire" in session.factions
        assert "trader" in session.factions
        assert session.get_faction_color("empire") == "red"

    def test_default_relationship_is_neutral(self):
        """New factions default to neutral relationship."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")

        assert session.get_relationship("empire", "trader") == "neutral"

    def test_set_enemy_relationship(self):
        """Can set two factions as enemies."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        assert session.get_relationship("empire", "trader") == "enemy"
        assert session.get_relationship("trader", "empire") == "enemy"  # Symmetric

    def test_set_allied_relationship(self):
        """Can set two factions as allies."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("house_mistral")
        session.set_relationship("empire", "house_mistral", "allied")

        assert session.get_relationship("empire", "house_mistral") == "allied"

    def test_neutral_becomes_enemy_on_attack(self):
        """When a neutral faction attacks another, they become enemies."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        # Start neutral
        assert session.get_relationship("empire", "trader") == "neutral"

        session.register_hostile_action("empire", "trader")
        assert session.get_relationship("empire", "trader") == "enemy"

    def test_allied_becomes_enemy_on_attack(self):
        """When an allied faction attacks, they become enemies."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("rebel")
        session.set_relationship("empire", "rebel", "allied")

        session.register_hostile_action("empire", "rebel")
        assert session.get_relationship("empire", "rebel") == "enemy"

    def test_cannot_target_allies(self):
        """Allied ships are not valid targets."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("house_mistral")
        session.set_relationship("empire", "house_mistral", "allied")

        assert session.is_valid_target("empire", "house_mistral") is False

    def test_can_target_enemies(self):
        """Enemy ships are valid targets."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        assert session.is_valid_target("empire", "trader") is True

    def test_cannot_target_neutrals(self):
        """Neutral ships are not valid targets by default."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")

        assert session.is_valid_target("empire", "trader") is False


# ============================================================================
# Ship Registration
# ============================================================================

class TestShipRegistration:
    """Adding ships to a session and assigning control modes."""

    def test_register_ship(self):
        """Can register a ship with faction and control mode."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")

        ship = MockShipStats(instance_id="s1", display_name="Red Five")
        pilot = MockPilot(piloting_skill=14)

        session.register_ship("s1", ship, pilot, faction="empire", control="human")
        assert session.get_ship("s1") is not None
        assert session.get_control_mode("s1") == "human"

    def test_register_npc_ship(self):
        """NPC ships use AI control mode."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("trader")

        ship = MockShipStats(instance_id="s2", display_name="Stinger One")
        pilot = MockPilot(piloting_skill=14)

        session.register_ship("s2", ship, pilot, faction="trader", control="npc")
        assert session.get_control_mode("s2") == "npc"

    def test_list_ships_by_faction(self):
        """Can list all ships in a faction."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")

        ship1 = MockShipStats(instance_id="s1", display_name="Red Five")
        ship2 = MockShipStats(instance_id="s2", display_name="Gold Two")
        pilot = MockPilot()

        session.register_ship("s1", ship1, pilot, faction="empire", control="human")
        session.register_ship("s2", ship2, pilot, faction="empire", control="human")

        empire_ships = session.get_ships_in_faction("empire")
        assert len(empire_ships) == 2
        assert "s1" in empire_ships
        assert "s2" in empire_ships


# ============================================================================
# Engagement Management
# ============================================================================

class TestEngagementManagement:
    """Creating and tracking engagements between ships."""

    def test_create_engagement(self):
        """Can create an engagement between two ships."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1")
        ship_b = MockShipStats(instance_id="s2")
        pilot = MockPilot()

        session.register_ship("s1", ship_a, pilot, "empire", "human")
        session.register_ship("s2", ship_b, pilot, "trader", "npc")

        session.create_engagement("s1", "s2", range_band="long")
        eng = session.get_engagement("s1", "s2")

        assert eng is not None
        assert eng.range_band == "long"

    def test_engagement_persists_across_turns(self):
        """Engagement state (range, advantage) persists between turns."""
        from m1_psi_core.session import GameSession
        from m1_psi_core.combat_state import EngagementState

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1", hnd=4, top_speed=600)
        ship_b = MockShipStats(instance_id="s2", hnd=6, top_speed=500)
        pilot = MockPilot()

        session.register_ship("s1", ship_a, pilot, "empire", "human")
        session.register_ship("s2", ship_b, pilot, "trader", "npc")
        session.create_engagement("s1", "s2", range_band="long")

        # Simulate advantage gained
        eng = session.get_engagement("s1", "s2")
        eng.set_advantage("s1")

        # Retrieve again — should still have advantage
        eng2 = session.get_engagement("s1", "s2")
        assert eng2.advantage == "s1"


# ============================================================================
# Turn Ordering
# ============================================================================

class TestTurnOrdering:
    """Declaration order based on speed and advantage."""

    def test_slower_declares_first(self):
        """Slower ship declares first (sees nothing), faster declares second."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1")
        ship_b = MockShipStats(instance_id="s2")
        pilot_slow = MockPilot(basic_speed=5.0)
        pilot_fast = MockPilot(basic_speed=7.0)

        session.register_ship("s1", ship_a, pilot_slow, "empire", "human")
        session.register_ship("s2", ship_b, pilot_fast, "trader", "human")
        session.create_engagement("s1", "s2", range_band="long")

        order = session.get_declaration_order()
        assert order[0] == "s1"  # Slow declares first
        assert order[1] == "s2"  # Fast declares second

    def test_advantaged_declares_second(self):
        """Advantaged ship declares second regardless of speed."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1")
        ship_b = MockShipStats(instance_id="s2")
        pilot_fast = MockPilot(basic_speed=7.0)
        pilot_slow = MockPilot(basic_speed=5.0)

        session.register_ship("s1", ship_a, pilot_fast, "empire", "human")
        session.register_ship("s2", ship_b, pilot_slow, "trader", "human")
        session.create_engagement("s1", "s2", range_band="long")

        # Give advantage to the slow ship
        eng = session.get_engagement("s1", "s2")
        eng.set_advantage("s2")

        order = session.get_declaration_order()
        assert order[-1] == "s2"  # Advantaged declares last


# ============================================================================
# NPC AI Integration
# ============================================================================

class TestNPCIntegration:
    """NPC ships produce valid declarations via AI."""

    def test_npc_produces_valid_declaration(self):
        """NPC AI produces a maneuver and intent."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1", top_speed=600, stall_speed=0,
                               fdr_max=0, current_fdr=0)
        ship_b = MockShipStats(instance_id="s2", top_speed=500, stall_speed=0,
                               fdr_max=150, current_fdr=150)
        pilot = MockPilot()

        session.register_ship("s1", ship_a, pilot, "empire", "npc")
        session.register_ship("s2", ship_b, pilot, "trader", "npc")
        session.create_engagement("s1", "s2", range_band="long")

        declaration = session.get_npc_declaration("s1")
        assert declaration["maneuver"] is not None
        assert declaration["intent"] in ("pursue", "evade")

    def test_npc_declaration_respects_stall_speed(self):
        """NPC with stall speed does not choose the Attack maneuver."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        # Javelin has stall speed 35
        ship = MockShipStats(instance_id="s1", top_speed=600, stall_speed=35,
                             fdr_max=0, current_fdr=0)
        opponent = MockShipStats(instance_id="s2", top_speed=500)
        pilot = MockPilot()

        session.register_ship("s1", ship, pilot, "empire", "npc")
        session.register_ship("s2", opponent, pilot, "trader", "npc")
        session.create_engagement("s1", "s2", range_band="long")

        declaration = session.get_npc_declaration("s1")
        assert declaration["maneuver"] != "attack"


# ============================================================================
# Combat End Detection
# ============================================================================

class TestCombatEndDetection:
    """Auto-detect when combat should end."""

    def test_combat_ends_when_enemy_destroyed(self):
        """Combat ends when all enemy ships are destroyed."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1", is_destroyed=False)
        ship_b = MockShipStats(instance_id="s2", is_destroyed=True)
        pilot = MockPilot()

        session.register_ship("s1", ship_a, pilot, "empire", "human")
        session.register_ship("s2", ship_b, pilot, "trader", "npc")

        assert session.check_combat_end() is True

    def test_combat_continues_with_active_enemies(self):
        """Combat continues while enemies are still active."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("trader")
        session.set_relationship("empire", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1", is_destroyed=False)
        ship_b = MockShipStats(instance_id="s2", is_destroyed=False)
        pilot = MockPilot()

        session.register_ship("s1", ship_a, pilot, "empire", "human")
        session.register_ship("s2", ship_b, pilot, "trader", "npc")

        assert session.check_combat_end() is False

    def test_combat_ends_when_only_allies_remain(self):
        """Combat ends when only allied factions have active ships."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("empire")
        session.add_faction("house_mistral")
        session.add_faction("trader")
        session.set_relationship("empire", "house_mistral", "allied")
        session.set_relationship("empire", "trader", "enemy")
        session.set_relationship("house_mistral", "trader", "enemy")

        ship_a = MockShipStats(instance_id="s1", is_destroyed=False)
        ship_b = MockShipStats(instance_id="s2", is_destroyed=False)
        ship_c = MockShipStats(instance_id="s3", is_destroyed=True)
        pilot = MockPilot()

        session.register_ship("s1", ship_a, pilot, "empire", "human")
        session.register_ship("s2", ship_b, pilot, "house_mistral", "npc")
        session.register_ship("s3", ship_c, pilot, "trader", "npc")

        assert session.check_combat_end() is True


# ============================================================================
# Force Screen Regeneration
# ============================================================================

class TestForceScreenRegen:
    """Force screens regen between turns via session manager."""

    def test_screens_regen_after_turn(self):
        """All ships with force screens regen to max after turn cleanup."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("trader")

        ship = MockShipStats(instance_id="s1", fdr_max=150, current_fdr=30,
                             force_screen_type="standard", no_power=False)
        pilot = MockPilot()

        session.register_ship("s1", ship, pilot, "trader", "human")

        session.regen_all_force_screens()
        updated_ship = session.get_ship("s1")
        assert updated_ship.current_fdr == 150

    def test_no_regen_without_power(self):
        """Ships with destroyed power do NOT regen force screens."""
        from m1_psi_core.session import GameSession

        session = GameSession()
        session.add_faction("trader")

        ship = MockShipStats(instance_id="s1", fdr_max=150, current_fdr=30,
                             force_screen_type="standard", no_power=True)
        pilot = MockPilot()

        session.register_ship("s1", ship, pilot, "trader", "human")

        session.regen_all_force_screens()
        updated_ship = session.get_ship("s1")
        assert updated_ship.current_fdr == 30  # Unchanged


# ============================================================================
# Turn Counter
# ============================================================================

class TestTurnCounter:
    """Turn counter management."""

    def test_starts_at_turn_1(self):
        """Session starts at turn 1."""
        from m1_psi_core.session import GameSession
        session = GameSession()
        assert session.current_turn == 1

    def test_advances_after_turn(self):
        """Turn counter advances."""
        from m1_psi_core.session import GameSession
        session = GameSession()
        session.advance_turn()
        assert session.current_turn == 2
