"""
EffectiveStatBlock: The resolved stat block returned by get_effective_stats().

This dataclass represents the current truth about a specific ship instance
after applying all template stats, module effects, mode overrides, and
system damage penalties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResolvedWeapon:
    """A fully resolved weapon with stats from the weapon catalog."""
    weapon_id: str
    name: str
    damage: str
    acc: int
    range: str
    rof: str
    rcl: int
    shots: str
    ewt: str
    weapon_type: str
    damage_type: str
    armor_divisor: Optional[str]
    mount: str
    linked_count: int
    arc: str
    notes: str


@dataclass
class EffectiveStatBlock:
    """
    The fully resolved stat block for a ship instance.

    Computed by get_effective_stats() through the pipeline:
    base template -> installed modules -> active mode -> system damage penalties
    """
    # Identity
    template_id: str
    instance_id: str  # UUID as string
    display_name: str
    faction: str  # From controller, not template

    # Attributes
    st_hp: int
    ht: str
    hnd: int
    sr: int

    # Mobility
    accel: int
    top_speed: int
    stall_speed: int

    # Defense
    dr_front: int
    dr_rear: int
    dr_left: int
    dr_right: int
    dr_top: int
    dr_bottom: int
    dr_material: Optional[str]
    fdr_max: int
    force_screen_type: str
    current_fdr: int

    # Electronics
    ecm_rating: int
    targeting_bonus: int
    ultrascanner_range: Optional[int]

    # State
    current_hp: int
    wound_level: str
    active_mode: str
    is_disabled: bool
    is_destroyed: bool

    # System status flags (computed from system_status rows)
    half_power: bool = False
    no_power: bool = False

    # Traits (merged from template + installed modules)
    traits: list[str] = field(default_factory=list)

    # Resolved weapons (from template mounts + module weapons + custom weapons)
    weapons: list[ResolvedWeapon] = field(default_factory=list)
