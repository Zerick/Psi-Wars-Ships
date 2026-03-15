"""
Shared mock objects for M1 Psi-Core testing.

These are test-support classes that can be imported by any test file
without going through conftest. They mirror the fields that M1 reads
from M3's EffectiveStatBlock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MockShipStats:
    """Simplified ship stats for M1 testing."""
    template_id: str = "test_ship"
    instance_id: str = "test_instance_1"
    display_name: str = "Test Ship"
    faction: str = "empire"

    st_hp: int = 80
    ht: str = "12"
    hnd: int = 4
    sr: int = 3

    accel: int = 20
    top_speed: int = 600
    stall_speed: int = 0

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

    ecm_rating: int = -4
    targeting_bonus: int = 5
    ultrascanner_range: Optional[int] = 30

    current_hp: int = 80
    wound_level: str = "none"
    active_mode: str = "standard"
    is_disabled: bool = False
    is_destroyed: bool = False
    half_power: bool = False
    no_power: bool = False

    sm: int = 4
    has_tactical_esm: bool = True
    has_decoy_launcher: bool = True
    has_g_chair: bool = False
    is_mook: bool = False

    traits: list = field(default_factory=list)
    weapons: list = field(default_factory=list)


@dataclass
class MockWeapon:
    """Simplified weapon for testing."""
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

    # Luck advantage (GURPS B66)
    # "none", "luck" (1/hr), "extraordinary" (1/30min), "ridiculous" (1/10min)
    luck_level: str = "none"

    # Current FP tracking
    current_fp: int = 10
    max_fp: int = 10


class MockDice:
    """A mock dice roller that returns predetermined values."""
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
