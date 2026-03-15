"""
Event system for M1 Psi-Core.

All combat outcomes are expressed as structured event objects.
The terminal UI and future web UI consume these events to display
what happened and why.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CombatEvent:
    """Base class for all combat events."""
    turn: int = 0
    description: str = ""


@dataclass
class TurnStartEvent(CombatEvent):
    """Turn begins. Force screens regenerate."""
    ships_regenerated: list[str] = field(default_factory=list)


@dataclass
class ManeuverEvent(CombatEvent):
    """A ship declared a maneuver."""
    ship_id: str = ""
    maneuver: str = ""
    intent: str = ""


@dataclass
class ChaseRollEvent(CombatEvent):
    """Result of a chase roll contest."""
    ship_a_id: str = ""
    ship_b_id: str = ""
    winner: Optional[str] = None
    margin: int = 0
    range_shift: int = 0
    advantage_changed: bool = False


@dataclass
class AttackRollEvent(CombatEvent):
    """An attack roll with all modifiers."""
    attacker_id: str = ""
    target_id: str = ""
    weapon_name: str = ""
    effective_skill: int = 0
    roll: int = 0
    hit: bool = False
    critical: bool = False


@dataclass
class DefenseRollEvent(CombatEvent):
    """A defense roll with all modifiers."""
    defender_id: str = ""
    defense_type: str = ""
    effective_defense: int = 0
    roll: int = 0
    success: bool = False


@dataclass
class DamageEvent(CombatEvent):
    """Damage dealt to a ship."""
    target_id: str = ""
    raw_damage: int = 0
    fdr_absorbed: int = 0
    dr_absorbed: int = 0
    penetrating: int = 0
    wound_level: str = ""


@dataclass
class SystemDamageEvent(CombatEvent):
    """A subsystem was disabled or destroyed."""
    ship_id: str = ""
    system: str = ""
    new_status: str = ""
    cascaded_from: Optional[str] = None


@dataclass
class ForceScreenEvent(CombatEvent):
    """Force screen status change."""
    ship_id: str = ""
    previous_fdr: int = 0
    current_fdr: int = 0
    regenerated: bool = False


@dataclass
class DestructionEvent(CombatEvent):
    """A ship was destroyed."""
    ship_id: str = ""
    cause: str = ""


@dataclass
class EscapeEvent(CombatEvent):
    """A ship escaped combat."""
    ship_id: str = ""
    method: str = ""


@dataclass
class TurnEndEvent(CombatEvent):
    """Turn ends, cleanup performed."""
    pass
