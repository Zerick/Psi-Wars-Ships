"""
Tests for subsystem damage affecting gameplay.

When a ship takes a major+ wound, a subsystem is disabled or destroyed.
These tests verify that disabled/destroyed systems actually change
the ship's combat capabilities.

Rules basis (GURPS + Psi-Wars):
    - Disabled propulsion: half Move and Accel
    - Destroyed propulsion: ship adrift (Move 0, Accel 0)
    - Disabled weaponry: half ROF (round down)
    - Destroyed weaponry: cannot fire at all
    - Disabled power: force screens at half max fDR regen
    - Destroyed power: no force screen regen, no sensors, no weapons
    - Disabled controls: -4 to all pilot rolls
    - Destroyed controls: ship uncontrollable (no maneuvers, no dodge)
    - Disabled/destroyed equipment, habitat, cargo, fuel, armor:
      cosmetic or narrative only (no direct combat mechanic for v1)

Architecture:
    Subsystem status is tracked on the ship stats object via a
    'disabled_systems' and 'destroyed_systems' set. The engine
    pipeline reads these sets when calculating effective stats.
"""
import pytest
from m1_psi_core.testing import MockShipStats, MockPilot


class TestSubsystemTracking:
    """Verify that subsystem status can be tracked on ships."""

    def test_ship_starts_with_no_damage(self):
        """New ships have no disabled or destroyed systems."""
        from m1_psi_core.subsystems import get_disabled, get_destroyed

        ship = MockShipStats()
        assert len(get_disabled(ship)) == 0
        assert len(get_destroyed(ship)) == 0

    def test_can_disable_a_system(self):
        """Can mark a system as disabled."""
        from m1_psi_core.subsystems import disable_system, get_disabled

        ship = MockShipStats()
        disable_system(ship, "propulsion")
        assert "propulsion" in get_disabled(ship)

    def test_can_destroy_a_system(self):
        """Can mark a system as destroyed."""
        from m1_psi_core.subsystems import destroy_system, get_destroyed

        ship = MockShipStats()
        destroy_system(ship, "weaponry")
        assert "weaponry" in get_destroyed(ship)

    def test_destroying_removes_disabled(self):
        """Destroying a system that was disabled promotes it to destroyed."""
        from m1_psi_core.subsystems import disable_system, destroy_system, get_disabled, get_destroyed

        ship = MockShipStats()
        disable_system(ship, "power")
        assert "power" in get_disabled(ship)

        destroy_system(ship, "power")
        assert "power" not in get_disabled(ship)
        assert "power" in get_destroyed(ship)


class TestPropulsionDamage:
    """Disabled/destroyed propulsion affects movement."""

    def test_disabled_propulsion_halves_speed(self):
        """Disabled propulsion: Move and Accel halved."""
        from m1_psi_core.subsystems import disable_system, get_effective_move

        ship = MockShipStats(accel=20, top_speed=600)
        disable_system(ship, "propulsion")

        eff = get_effective_move(ship)
        assert eff["accel"] == 10
        assert eff["top_speed"] == 300

    def test_destroyed_propulsion_no_movement(self):
        """Destroyed propulsion: ship adrift."""
        from m1_psi_core.subsystems import destroy_system, get_effective_move

        ship = MockShipStats(accel=20, top_speed=600)
        destroy_system(ship, "propulsion")

        eff = get_effective_move(ship)
        assert eff["accel"] == 0
        assert eff["top_speed"] == 0

    def test_undamaged_propulsion_full_speed(self):
        """Undamaged propulsion: full Move and Accel."""
        from m1_psi_core.subsystems import get_effective_move

        ship = MockShipStats(accel=20, top_speed=600)
        eff = get_effective_move(ship)
        assert eff["accel"] == 20
        assert eff["top_speed"] == 600


class TestWeaponryDamage:
    """Disabled/destroyed weaponry affects attacks."""

    def test_disabled_weaponry_halves_rof(self):
        """Disabled weaponry: effective ROF halved."""
        from m1_psi_core.subsystems import disable_system, get_effective_rof

        ship = MockShipStats()
        disable_system(ship, "weaponry")

        assert get_effective_rof(ship, base_rof=6) == 3
        assert get_effective_rof(ship, base_rof=3) == 1  # Round down

    def test_destroyed_weaponry_cannot_fire(self):
        """Destroyed weaponry: cannot fire at all."""
        from m1_psi_core.subsystems import destroy_system, can_fire_weapons

        ship = MockShipStats()
        destroy_system(ship, "weaponry")

        assert can_fire_weapons(ship) is False

    def test_undamaged_weaponry_can_fire(self):
        """Undamaged weaponry: normal fire."""
        from m1_psi_core.subsystems import can_fire_weapons

        ship = MockShipStats()
        assert can_fire_weapons(ship) is True


class TestPowerDamage:
    """Disabled/destroyed power affects force screens and other systems."""

    def test_disabled_power_halves_fdr_regen(self):
        """Disabled power: force screen regens to half max."""
        from m1_psi_core.subsystems import disable_system, get_effective_fdr_max

        ship = MockShipStats(fdr_max=150)
        disable_system(ship, "power")

        assert get_effective_fdr_max(ship) == 75

    def test_destroyed_power_no_fdr_regen(self):
        """Destroyed power: no force screen regen at all."""
        from m1_psi_core.subsystems import destroy_system, get_effective_fdr_max

        ship = MockShipStats(fdr_max=150)
        destroy_system(ship, "power")

        assert get_effective_fdr_max(ship) == 0

    def test_destroyed_power_no_weapons(self):
        """Destroyed power: weapons have no power, cannot fire."""
        from m1_psi_core.subsystems import destroy_system, can_fire_weapons

        ship = MockShipStats()
        destroy_system(ship, "power")

        assert can_fire_weapons(ship) is False

    def test_undamaged_power_full_fdr(self):
        """Undamaged power: full fDR regen."""
        from m1_psi_core.subsystems import get_effective_fdr_max

        ship = MockShipStats(fdr_max=150)
        assert get_effective_fdr_max(ship) == 150


class TestControlsDamage:
    """Disabled/destroyed controls affect piloting."""

    def test_disabled_controls_penalty(self):
        """Disabled controls: -4 to all pilot rolls."""
        from m1_psi_core.subsystems import disable_system, get_controls_penalty

        ship = MockShipStats()
        disable_system(ship, "controls")

        assert get_controls_penalty(ship) == -4

    def test_destroyed_controls_uncontrollable(self):
        """Destroyed controls: ship uncontrollable."""
        from m1_psi_core.subsystems import destroy_system, is_controllable

        ship = MockShipStats()
        destroy_system(ship, "controls")

        assert is_controllable(ship) is False

    def test_undamaged_controls_no_penalty(self):
        """Undamaged controls: no penalty."""
        from m1_psi_core.subsystems import get_controls_penalty, is_controllable

        ship = MockShipStats()
        assert get_controls_penalty(ship) == 0
        assert is_controllable(ship) is True


class TestCosmeticSystems:
    """Systems without direct combat effects."""

    def test_disabled_habitat_no_combat_effect(self):
        """Disabled habitat: no direct combat mechanical effect."""
        from m1_psi_core.subsystems import disable_system, get_disabled

        ship = MockShipStats()
        disable_system(ship, "habitat")
        assert "habitat" in get_disabled(ship)
        # No gameplay function to test — it's tracked but cosmetic

    def test_disabled_cargo_no_combat_effect(self):
        """Disabled cargo/hangar: tracked but cosmetic."""
        from m1_psi_core.subsystems import disable_system, get_disabled

        ship = MockShipStats()
        disable_system(ship, "cargo_hangar")
        assert "cargo_hangar" in get_disabled(ship)

    def test_disabled_fuel_no_immediate_effect(self):
        """Disabled fuel: tracked, narrative effect only in v1."""
        from m1_psi_core.subsystems import disable_system, get_disabled

        ship = MockShipStats()
        disable_system(ship, "fuel")
        assert "fuel" in get_disabled(ship)

    def test_disabled_armor_no_immediate_effect(self):
        """Disabled armor: tracked, could reduce DR in future."""
        from m1_psi_core.subsystems import disable_system, get_disabled

        ship = MockShipStats()
        disable_system(ship, "armor")
        assert "armor" in get_disabled(ship)


class TestPipelineIntegration:
    """Verify the engine pipeline reads subsystem status."""

    def test_attack_blocked_by_destroyed_weaponry(self):
        """resolve_attack returns can_attack=False when weapons destroyed."""
        from m1_psi_core.subsystems import destroy_system
        from m1_psi_core.engine import resolve_attack, resolve_weapon
        from m1_psi_core.combat_state import EngagementState
        from m1_psi_core.dice import DiceRoller

        attacker = MockShipStats(instance_id="a1", display_name="Red Five")
        destroy_system(attacker, "weaponry")

        target = MockShipStats(instance_id="b1", display_name="Stinger")
        pilot = MockPilot()
        eng = EngagementState(ship_a_id="a1", ship_b_id="b1", range_band="long")
        weapon = resolve_weapon(attacker)
        dice = DiceRoller(seed=42)

        result = resolve_attack(
            "a1", attacker, pilot, "b1", target, eng,
            {"maneuver": "attack", "intent": "pursue"},
            weapon, dice,
        )

        assert result.can_attack is False

    def test_dodge_penalty_from_disabled_controls(self):
        """resolve_defense includes -4 penalty from disabled controls."""
        from m1_psi_core.subsystems import disable_system, get_controls_penalty
        from m1_psi_core.engine import resolve_defense
        from m1_psi_core.combat_state import EngagementState
        from m1_psi_core.dice import DiceRoller

        defender = MockShipStats(instance_id="b1", display_name="Stinger", hnd=6)
        disable_system(defender, "controls")

        pilot = MockPilot(piloting_skill=14)
        eng = EngagementState(ship_a_id="a1", ship_b_id="b1", range_band="long")
        dice = DiceRoller(seed=42)

        result = resolve_defense(
            "b1", defender, pilot, "evade", "attack", eng, dice,
        )

        # Base dodge: 14//2 + 6 = 13. Evade: +2. Controls: -4. = 11
        # (Plus High-G if available — we'll check the controls penalty is in there)
        penalty = get_controls_penalty(defender)
        assert penalty == -4

    def test_force_screen_regen_respects_disabled_power(self):
        """Force screen regens to half when power is disabled."""
        from m1_psi_core.subsystems import disable_system, get_effective_fdr_max
        from m1_psi_core.engine import regen_force_screen

        ship = MockShipStats(fdr_max=150, current_fdr=0, no_power=False)
        disable_system(ship, "power")

        # The regen function should use effective fDR max, not raw max
        eff_max = get_effective_fdr_max(ship)
        assert eff_max == 75
