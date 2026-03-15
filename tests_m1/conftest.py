"""
Shared pytest fixtures for M1 Psi-Core test suite.

Mock classes (MockShipStats, MockWeapon, MockPilot, MockDice) live in
m1_psi_core.testing so they can be imported by any test file without
conftest import issues when running multiple test suites together.
"""
import pytest

from m1_psi_core.testing import MockShipStats, MockWeapon, MockPilot, MockDice


# ---------------------------------------------------------------------------
# Dice fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_dice():
    """Factory fixture: create a MockDice with predetermined values."""
    def _make(values: list[int]) -> MockDice:
        return MockDice(values)
    return _make


# ---------------------------------------------------------------------------
# Common ship configurations
# ---------------------------------------------------------------------------

@pytest.fixture
def javelin_stats():
    """A Javelin Class Fighter - simple Imperial fighter, no force screen."""
    return MockShipStats(
        template_id="javelin_v1", display_name="Red Five", faction="empire",
        st_hp=80, ht="9f", hnd=4, sr=3,
        accel=20, top_speed=600, stall_speed=35,
        dr_front=15, dr_rear=15, dr_left=15, dr_right=15, dr_top=15, dr_bottom=15,
        dr_material="carbide_composite",
        fdr_max=0, force_screen_type="none", current_fdr=0,
        ecm_rating=-4, targeting_bonus=5, ultrascanner_range=30,
        current_hp=80, sm=4,
        has_tactical_esm=True, has_decoy_launcher=True,
    )


@pytest.fixture
def hornet_stats():
    """A Hornet-Class Interceptor - Trader fighter with force screen and modes."""
    return MockShipStats(
        template_id="hornet_v1", display_name="Stinger One", faction="trader",
        st_hp=95, ht="13", hnd=6, sr=3,
        accel=15, top_speed=500, stall_speed=0,
        dr_front=10, dr_rear=10, dr_left=10, dr_right=10, dr_top=10, dr_bottom=10,
        dr_material="nanopolymer",
        fdr_max=150, force_screen_type="standard", current_fdr=150,
        ecm_rating=-4, targeting_bonus=5, ultrascanner_range=30,
        current_hp=95, sm=4,
        has_tactical_esm=True, has_decoy_launcher=False,
    )


@pytest.fixture
def sword_stats():
    """A Sword-Pattern Battleship - capital ship with heavy force screen."""
    return MockShipStats(
        template_id="sword_battleship_v1", display_name="ISS Retribution",
        faction="empire",
        st_hp=7000, ht="13", hnd=-4, sr=6,
        accel=3, top_speed=90, stall_speed=0,
        dr_front=5000, dr_rear=2500, dr_left=2500, dr_right=2500,
        dr_top=2500, dr_bottom=2500,
        dr_material="carbide_composite",
        fdr_max=10000, force_screen_type="heavy", current_fdr=10000,
        ecm_rating=-4, targeting_bonus=5, ultrascanner_range=4000,
        current_hp=7000, sm=13,
        has_tactical_esm=False, has_decoy_launcher=False,
    )


@pytest.fixture
def default_pilot():
    """An average pilot with no special abilities."""
    return MockPilot()


@pytest.fixture
def ace_pilot():
    """A skilled ace pilot."""
    return MockPilot(
        name="Ace", piloting_skill=18, gunnery_skill=16,
        basic_speed=7.0, is_ace_pilot=True, has_combat_reflexes=True,
    )


@pytest.fixture
def test_blaster():
    """Imperial Fighter Blaster weapon."""
    return MockWeapon(
        weapon_id="imperial_fighter_blaster", name="Imperial Fighter Blaster",
        damage="6d×5(5) burn", acc=9, rof="3", rcl=2,
        weapon_type="beam", damage_type="burn", armor_divisor="(5)",
        mount="fixed_front", linked_count=2, arc="front",
    )


@pytest.fixture
def test_missile():
    """160mm Plasma Lance Missile."""
    return MockWeapon(
        weapon_id="160mm_plasma_lance_missile", name="160mm Plasma Lance Missile",
        damage="6d×30(10) burn", acc=3, rof="1", rcl=1,
        weapon_type="missile", damage_type="burn", armor_divisor="(10)",
        mount="wing_left", linked_count=1, arc="front",
    )


@pytest.fixture
def test_torpedo():
    """400mm Isomeric Torpedo."""
    return MockWeapon(
        weapon_id="400mm_isomeric_torpedo", name="400mm Isomeric Torpedo",
        damage="5d×200 cr ex", acc=3, rof="1", rcl=1,
        weapon_type="torpedo", damage_type="cr_ex", armor_divisor=None,
        mount="fixed_front", linked_count=1, arc="front",
    )


@pytest.fixture
def plasma_flak():
    """Plasma Flak Turret."""
    return MockWeapon(
        weapon_id="plasma_flak_turret", name="Plasma Flak Turret",
        damage="6d×10 burn ex", acc=0, rof="20", rcl=1,
        weapon_type="flak", damage_type="burn_ex", armor_divisor=None,
        mount="turret", linked_count=1, arc="all",
    )
