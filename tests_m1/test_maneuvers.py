"""
Tests for the maneuver catalog and validation subsystem.

Covers:
- All maneuvers defined in the catalog
- Facing requirements per maneuver
- Attack permission levels per maneuver
- Stall speed restrictions
- Static maneuver identification
- Collision range requirements
- Ace Pilot and Gunslinger attack permission overrides
"""
import pytest


class TestManeuverCatalog:
    """Verify all maneuvers are defined with correct properties."""

    def test_all_maneuvers_exist(self):
        """All 15 maneuvers are defined in the catalog."""
        from m1_psi_core.maneuvers import MANEUVER_CATALOG
        expected = {
            "attack", "move", "move_and_attack", "evade",
            "mobility_pursuit", "mobility_escape",
            "stunt", "stunt_escape", "force", "ram",
            "hide", "stop", "precision_aiming",
            "embark_disembark", "emergency_action",
        }
        assert set(MANEUVER_CATALOG.keys()) == expected

    def test_attack_maneuver_properties(self):
        """Attack maneuver has correct facing and full accuracy."""
        from m1_psi_core.maneuvers import MANEUVER_CATALOG
        m = MANEUVER_CATALOG["attack"]
        assert m.facing == "front"
        assert m.allows_attack == "full_accuracy"
        assert m.is_static is False

    def test_evade_maneuver_properties(self):
        """Evade has rear facing, -2 chase mod, +2 dodge."""
        from m1_psi_core.maneuvers import MANEUVER_CATALOG
        m = MANEUVER_CATALOG["evade"]
        assert m.facing == "rear"
        assert m.chase_modifier == -2
        assert m.dodge_bonus == 2
        assert m.allows_attack == "none"

    def test_precision_aiming_is_static(self):
        """Precision Aiming is a static maneuver."""
        from m1_psi_core.maneuvers import MANEUVER_CATALOG
        m = MANEUVER_CATALOG["precision_aiming"]
        assert m.is_static is True
        assert m.facing == "front"

    def test_ram_requires_collision(self):
        """Ram requires collision range."""
        from m1_psi_core.maneuvers import MANEUVER_CATALOG
        m = MANEUVER_CATALOG["ram"]
        assert m.requires_collision is True


class TestManeuverValidation:
    """Validation of maneuver choices against ship state."""

    def test_stall_cannot_attack(self):
        """Ships with stall speed cannot use the Attack maneuver."""
        from m1_psi_core.maneuvers import validate_maneuver
        errors = validate_maneuver(
            maneuver="attack",
            stall_speed=35,
            opponent_has_advantage=False,
            at_collision_range=False,
            is_stopped=False,
        )
        assert len(errors) > 0
        assert any("stall" in e.lower() for e in errors)

    def test_no_stall_can_attack(self):
        """Ships without stall speed can use Attack."""
        from m1_psi_core.maneuvers import validate_maneuver
        errors = validate_maneuver(
            maneuver="attack",
            stall_speed=0,
            opponent_has_advantage=False,
            at_collision_range=False,
            is_stopped=False,
        )
        assert len(errors) == 0

    def test_stall_cannot_stunt_against_advantaged(self):
        """Stall-speed ships cannot Stunt against an advantaged opponent."""
        from m1_psi_core.maneuvers import validate_maneuver
        errors = validate_maneuver(
            maneuver="stunt",
            stall_speed=35,
            opponent_has_advantage=True,
            at_collision_range=False,
            is_stopped=False,
        )
        assert len(errors) > 0

    def test_stall_can_stunt_escape(self):
        """Stall-speed ships CAN use Stunt Escape even against advantaged."""
        from m1_psi_core.maneuvers import validate_maneuver
        errors = validate_maneuver(
            maneuver="stunt_escape",
            stall_speed=35,
            opponent_has_advantage=True,
            at_collision_range=False,
            is_stopped=False,
        )
        assert len(errors) == 0

    def test_ram_needs_collision_range(self):
        """Ram fails validation if not at collision range."""
        from m1_psi_core.maneuvers import validate_maneuver
        errors = validate_maneuver(
            maneuver="ram",
            stall_speed=0,
            opponent_has_advantage=False,
            at_collision_range=False,
            is_stopped=False,
        )
        assert len(errors) > 0
        assert any("collision" in e.lower() for e in errors)

    def test_static_with_stall_needs_stopped(self):
        """Static maneuvers require stall-speed ships to be stopped first."""
        from m1_psi_core.maneuvers import validate_maneuver
        errors = validate_maneuver(
            maneuver="stop",
            stall_speed=35,
            opponent_has_advantage=False,
            at_collision_range=False,
            is_stopped=False,
        )
        # Stop itself is the way to become stopped, so it should be allowed
        # But Hide (also static) with stall and not stopped should fail
        errors_hide = validate_maneuver(
            maneuver="hide",
            stall_speed=35,
            opponent_has_advantage=False,
            at_collision_range=False,
            is_stopped=False,
        )
        assert len(errors_hide) > 0


class TestAcePilotAttackPermissions:
    """Ace Pilots get expanded attack permissions."""

    def test_ace_can_attack_during_move(self):
        """Ace Pilots may attack (without accuracy) during Move maneuver."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("move", is_ace_pilot=True, is_gunslinger=False)
        assert perm == "no_accuracy"

    def test_ace_can_attack_during_stunt(self):
        """Ace Pilots may attack (without accuracy) during Stunt."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("stunt", is_ace_pilot=True, is_gunslinger=False)
        assert perm == "no_accuracy"

    def test_ace_half_accuracy_during_move_and_attack(self):
        """Ace Pilots get half accuracy on Move and Attack."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("move_and_attack", is_ace_pilot=True, is_gunslinger=False)
        assert perm == "half_accuracy"

    def test_ace_full_accuracy_on_attack(self):
        """Ace Pilots get full accuracy on Attack maneuver."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("attack", is_ace_pilot=True, is_gunslinger=False)
        assert perm == "full_accuracy"

    def test_non_ace_cannot_attack_during_move(self):
        """Non-Ace pilots cannot attack during Move maneuver."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("move", is_ace_pilot=False, is_gunslinger=False)
        assert perm == "none"

    def test_ace_cannot_attack_during_hide(self):
        """Even Ace Pilots cannot attack during Hide."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("hide", is_ace_pilot=True, is_gunslinger=False)
        assert perm == "none"

    def test_ace_embark_no_attack(self):
        """Ace Pilots get 'no attack' on Embark/Disembark (not gunslinger)."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("embark_disembark", is_ace_pilot=True, is_gunslinger=False)
        assert perm == "none"

    def test_gunslinger_embark_half_accuracy(self):
        """Gunslingers get half accuracy on Embark/Disembark."""
        from m1_psi_core.maneuvers import get_attack_permission
        perm = get_attack_permission("embark_disembark", is_ace_pilot=False, is_gunslinger=True)
        assert perm == "half_accuracy"


class TestSoarLikeLeaf:
    """The 'Soar like a Leaf' perk for corvettes."""

    def test_soar_imposes_stall_restriction(self):
        """Soar like a Leaf imposes stall restrictions even on VTOL corvettes."""
        from m1_psi_core.maneuvers import validate_maneuver
        # A corvette with stall 0 but soar_like_leaf = True should have stall restrictions
        errors = validate_maneuver(
            maneuver="attack",
            stall_speed=0,
            opponent_has_advantage=False,
            at_collision_range=False,
            is_stopped=False,
            soar_like_leaf=True,
        )
        assert len(errors) > 0
        assert any("stall" in e.lower() or "soar" in e.lower() for e in errors)
