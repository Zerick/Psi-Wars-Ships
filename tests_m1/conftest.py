"""
Shared pytest fixtures for M1 Psi-Core test suite.

Provides:
- Deterministic DiceRoller for reproducible tests
- Mock dice that return predetermined sequences
- Common ship stat blocks for testing
- Combat state factories

All M1 imports are lazy (inside fixtures/tests) so pytest can
discover tests even with stub implementation.
"""
import pytest
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Mock dice for deterministic testing
# ---------------------------------------------------------------------------

class MockDice:
    """
    A mock dice roller that returns predetermined values.
    
    Usage:
        dice = MockDice([10, 8, 15, 3])  # Will return these values in order
        dice.roll_3d6()  # Returns 10
        dice.roll_3d6()  # Returns 8
    """
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0
    
    def roll_3d6(self) -> int:
        return self._next()
    
    def roll_nd6(self, n: int) -> int:
        return self._next()
    
    def roll_1d6(self) -> int:
        return self._next()
    
    def _next(self) -> int:
        if self._index >= len(self._values):
            raise RuntimeError(
                f"MockDice exhausted: requested roll #{self._index + 1} "
                f"but only {len(self._values)} values were provided"
            )
        val = self._values[self._index]
        self._index += 1
        return val


@pytest.fixture
def mock_dice():
    """Factory fixture: create a MockDice with predetermined values."""
    def _make(values: list[int]) -> MockDice:
        return MockDice(values)
    return _make


# ---------------------------------------------------------------------------
# Simplified stat blocks for testing (avoid needing full M3 database)
# ---------------------------------------------------------------------------

@dataclass
class MockShipStats:
    """
    Simplified ship stats for M1 testing.
    Mirrors the fields that M1 reads from M3's EffectiveStatBlock,
    without requiring a live database.
    """
    template_id: str = "test_ship"
    instance_id: str = "test_instance_1"
    display_name: str = "Test Ship"
    faction: str = "empire"
    
    # Attributes
    st_hp: int = 80
    ht: str = "12"
    hnd: int = 4
    sr: int = 3
    
    # Mobility
    accel: int = 20
    top_speed: int = 600
    stall_speed: int = 0
    
    # Defense
    dr_front: int = 15
    dr_rear: int = 15
    dr_left: int = 15
    dr_right: int = 15
    dr_top: int = 15
    dr_bottom: int = 15
    dr_material: Optional[str] = None
    fdr_max: int = 0
    force_screen_type: str = "none"
    current_fdr: int = 0
    
    # Electronics
    ecm_rating: int = -4
    targeting_bonus: int = 5
    ultrascanner_range: Optional[int] = 30
    
    # State
    current_hp: int = 80
    wound_level: str = "none"
    active_mode: str = "standard"
    is_disabled: bool = False
    is_destroyed: bool = False
    half_power: bool = False
    no_power: bool = False
    
    # Flags
    sm: int = 4
    has_tactical_esm: bool = True
    has_decoy_launcher: bool = True
    has_g_chair: bool = False
    is_mook: bool = False
    
    traits: list = field(default_factory=list)
    weapons: list = field(default_factory=list)


@dataclass
class MockWeapon:
    """Simplified weapon for testing attack/damage calculations."""
    weapon_id: str = "test_blaster"
    name: str = "Test Blaster"
    damage: str = "6d×5(5) burn"
    acc: int = 9
    rof: str = "3"
    rcl: int = 2
    weapon_type: str = "beam"
    damage_type: str = "burn"
    armor_divisor: Optional[str] = "(5)"
    mount: str = "fixed_front"
    linked_count: int = 1
    arc: str = "front"


@dataclass 
class MockPilot:
    """Simplified pilot/controller for testing."""
    name: str = "Test Pilot"
    piloting_skill: int = 14
    gunnery_skill: int = 14
    electronics_ops_skill: int = 12
    tactics_skill: int = 12
    navigation_skill: int = 12
    mechanic_skill: int = 12
    leadership_skill: int = 12
    iq: int = 12
    ht: int = 12
    will: int = 12
    basic_speed: float = 6.0
    is_ace_pilot: bool = False
    is_gunslinger: bool = False
    has_combat_reflexes: bool = False
    has_danger_sense: bool = False
    has_soar_like_leaf: bool = False


# ---------------------------------------------------------------------------
# Common ship configurations for testing
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
