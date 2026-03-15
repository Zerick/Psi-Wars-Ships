"""
Combat Resolution Pipeline for M1 Psi-Core.

THIS IS THE SINGLE ENTRY POINT FOR ALL COMBAT RESOLUTION.
The terminal UI (and future web UI) calls these functions and
displays the results. No UI code lives here — only rules logic
and structured result objects.

Architecture:
    resolve_chase()   — Quick contest of piloting, returns ChaseResult
    resolve_attack()  — Hit roll pipeline, returns AttackResult
    resolve_defense() — Dodge/defense roll, returns DefenseResult
    resolve_damage()  — Force screen → armor → wound → subsystem, returns DamageResult
    regen_force_screens() — End-of-turn cleanup

Each function returns a dataclass with ALL intermediate values exposed,
so the UI can display every modifier, every roll, every calculation step.

Adding new modifiers:
    1. Add the modifier calculation to the appropriate M1 subsystem module
    2. Add a field to the corresponding result dataclass below
    3. Add the calculation call to the appropriate resolve_*() function
    4. The UI will automatically see the new field and can display it

The pipeline NEVER mutates ship state directly. It returns results that
describe what SHOULD happen. The caller (session manager or game loop)
applies the state changes. This makes the pipeline pure and testable.

Exception: resolve_damage() returns the new state values (new HP, new fDR,
new wound level, is_destroyed) but does NOT write them to the ship object.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from m1_psi_core.dice import DiceRoller, check_success, resolve_quick_contest, parse_damage_string
from m1_psi_core.combat_state import (
    EngagementState, get_range_penalty, RANGE_BAND_ORDER,
)
from m1_psi_core.maneuvers import MANEUVER_CATALOG, get_attack_permission
from m1_psi_core.attack import (
    get_sensor_lock_bonus, apply_accuracy,
    get_relative_size_penalty, can_ship_attack, get_sm_bonus,
    get_rof_bonus, calculate_flak_hit_number,
)
from m1_psi_core.defense import (
    calculate_base_dodge, get_dodge_modifiers,
    is_high_g_available, HIGH_G_DODGE_BONUS,
    get_high_g_ht_modifier, calculate_high_g_fp_loss,
    get_missile_defense_modifiers,
)
from m1_psi_core.damage import (
    apply_force_screen, apply_armor_divisor, calculate_penetrating_damage,
    determine_wound_level, get_subsystem_hit, resolve_subsystem_cascade,
    check_wound_accumulation, apply_mook_rules,
    WOUND_SEVERITY, TARGETED_SYSTEM_PENALTY,
)
from m1_psi_core.special import classify_ship


# ============================================================================
# Result Dataclasses
# ============================================================================

@dataclass
class ChaseResult:
    """Complete result of a chase contest between two ships."""
    skill_a: int
    skill_b: int
    roll_a: int
    roll_b: int
    margin_a: int
    margin_b: int
    winner_id: Optional[str]    # Ship ID or None for tie
    winner_name: str
    margin_of_victory: int
    # Chase outcome options (for winner to choose)
    can_gain_advantage: bool = False
    can_match_speed: bool = False
    can_shift_range: int = 0
    opponent_loses_advantage: bool = False


@dataclass
class WeaponInfo:
    """Resolved weapon data for an attack."""
    name: str
    damage_str: str
    acc: int
    rof: int
    weapon_type: str        # "beam", "missile", "torpedo", "flak"
    armor_divisor: Optional[float]
    mount: str
    linked_count: int
    is_explosive: bool
    range_str: str = ""     # e.g., "2700/8000" or "4 mi/12 mi"


@dataclass
class AttackModifiers:
    """Every modifier that went into the hit roll, individually named."""
    base_skill: int
    range_penalty: int
    sm_bonus: int
    sensor_lock_bonus: int
    accuracy: int
    rof_bonus: int
    relative_size_penalty: int
    deceptive_penalty: int = 0
    targeted_system_penalty: int = 0
    tactical_offensive: int = 0
    # Total
    effective_skill: int = 0


@dataclass
class AttackResult:
    """Complete result of an attack roll."""
    attacker_id: str
    attacker_name: str
    target_id: str
    target_name: str
    weapon: WeaponInfo
    modifiers: AttackModifiers
    roll: int
    margin: int
    hit: bool
    critical: bool
    critical_type: Optional[str]  # "success" or "failure"
    can_attack: bool = True       # False if ship can't attack at all
    reason_cannot_attack: str = ""


@dataclass
class DefenseModifiers:
    """Every modifier that went into the defense roll."""
    base_dodge: int
    piloting_skill: int
    handling: int
    evade_bonus: int = 0
    advantage_escaping_bonus: int = 0
    ace_stunt_bonus: int = 0
    precision_aim_awareness: int = 0
    tactical_defense: int = 0
    high_g_bonus: int = 0
    deceptive_penalty: int = 0
    controls_penalty: int = 0
    effective_dodge: int = 0


@dataclass
class HighGResult:
    """Result of a High-G dodge attempt."""
    attempted: bool = False
    available: bool = False
    ht_target: int = 0
    ht_modifier: int = 0
    ht_roll: int = 0
    ht_succeeded: bool = False
    fp_lost: int = 0


@dataclass
class DefenseResult:
    """Complete result of a defense roll."""
    defender_id: str
    defender_name: str
    defense_type: str           # "dodge", "high_g_dodge"
    modifiers: DefenseModifiers
    roll: int
    margin: int
    success: bool
    critical: bool
    high_g: HighGResult = field(default_factory=HighGResult)
    offered_high_g: bool = False  # True if High-G was available


@dataclass
class DamageStep:
    """One step in the damage pipeline, for display purposes."""
    label: str
    value: str


@dataclass
class DamageResult:
    """Complete result of the damage pipeline."""
    target_id: str
    target_name: str
    raw_damage: int
    # Force screen
    has_force_screen: bool
    fdr_absorbed: int
    fdr_remaining: int
    damage_past_screen: int
    # Armor
    hull_dr: int
    effective_dr: int
    armor_divisor: float
    penetrating_damage: int
    # Wound
    wound_level: str
    wound_pct: float           # Penetrating as % of max HP
    max_hp: int
    new_hp: int
    # Subsystem
    subsystem_roll: int = 0
    subsystem_hit: str = ""
    subsystem_status: str = ""  # "disabled" or "destroyed"
    subsystem_cascade: Optional[str] = None
    # Final state
    is_destroyed: bool = False
    is_mook_removed: bool = False
    wound_escalated: bool = False
    new_wound_level: str = ""
    # All steps for display
    steps: list[DamageStep] = field(default_factory=list)


# ============================================================================
# Weapon Resolution
# ============================================================================

# Cache for loaded weapon data
_weapon_cache: dict[str, dict] = {}


def load_weapon_data(weapon_ref: str, fixtures_dir: Optional[Path] = None) -> Optional[dict]:
    """
    Load weapon data from JSON fixtures by weapon_ref ID.

    Searches common fixture locations. Caches results.
    Returns None if not found.
    """
    if weapon_ref in _weapon_cache:
        return _weapon_cache[weapon_ref]

    search_dirs = []
    if fixtures_dir:
        search_dirs.append(fixtures_dir / "weapons")
    # Common locations
    for base in [Path.cwd(), Path.cwd().parent, Path(__file__).parent.parent]:
        search_dirs.append(base / "tests" / "fixtures" / "weapons")

    for d in search_dirs:
        path = d / f"{weapon_ref}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                _weapon_cache[weapon_ref] = data
                return data
            except (json.JSONDecodeError, KeyError):
                continue

    return None


def resolve_weapon(ship_stats, fixtures_dir: Optional[Path] = None) -> Optional[WeaponInfo]:
    """
    Resolve the primary weapon for a ship.

    Reads the ship's weapon references, loads the weapon JSON,
    and returns a WeaponInfo with all resolved data.

    Falls back to a default 6d×5(5) burn blaster if weapon data
    can't be loaded (ensures combat always works).
    """
    weapons_list = getattr(ship_stats, "weapons", [])

    # Try to load from ship's weapon_ref entries
    if weapons_list:
        for w in weapons_list:
            # Handle both dict (from JSON) and object weapon refs
            if isinstance(w, dict):
                ref = w.get("weapon_ref", "")
                mount = w.get("mount", "fixed_front")
                linked = w.get("linked_count", 1)
                arc = w.get("arc", "front")
            else:
                ref = getattr(w, "weapon_id", "")
                mount = getattr(w, "mount", "fixed_front")
                linked = getattr(w, "linked_count", 1)
                arc = getattr(w, "arc", "front")

            if ref:
                data = load_weapon_data(ref, fixtures_dir)
                if data:
                    parsed = parse_damage_string(data.get("damage", "6d×5(5) burn"))
                    rof_str = data.get("rof", "3")
                    try:
                        rof = int(rof_str.split("/")[0]) * linked
                    except (ValueError, IndexError):
                        rof = 3

                    return WeaponInfo(
                        name=data.get("name", ref),
                        damage_str=data.get("damage", "6d×5(5) burn"),
                        acc=data.get("acc", 9),
                        rof=rof,
                        weapon_type=data.get("weapon_type", "beam"),
                        armor_divisor=parsed.armor_divisor,
                        mount=mount,
                        linked_count=linked,
                        is_explosive=parsed.explosive,
                    )

    # Fallback: generic fighter blaster
    return WeaponInfo(
        name="Fighter Blaster",
        damage_str="6d×5(5) burn",
        acc=9, rof=3,
        weapon_type="beam",
        armor_divisor=5.0,
        mount="fixed_front",
        linked_count=1,
        is_explosive=False,
    )


# ============================================================================
# Facing Helpers
# ============================================================================

def can_weapon_fire_facing(mount: str, ship_facing: str) -> bool:
    """
    Check if a weapon mount can fire given the ship's current facing.

    Fixed front weapons require front or "any" facing.
    Fixed rear weapons require rear or "any" facing.
    Turret weapons fire at any facing.

    Args:
        mount: Weapon mount type ("fixed_front", "fixed_rear", "turret", etc.)
        ship_facing: Ship's facing toward opponent ("front", "rear", "any")
    """
    if "turret" in mount:
        return True
    if mount == "fixed_front":
        return ship_facing in ("front", "any")
    if mount == "fixed_rear":
        return ship_facing in ("rear", "any")
    # Unknown mount types default to allowing fire
    return True


def get_attacker_facing(maneuver: str, intent: str) -> str:
    """
    Determine the attacker's facing from their maneuver and intent.

    RAW:
    - Maneuvers with facing "front" (Attack, Move and Attack, etc.) = front
    - Maneuvers with facing "rear" (Evade, Mobility Escape) = rear
    - Maneuvers with facing "any" (Stunt, Stunt Escape, Hide, Stop) = any
    - Move maneuver: pursue=front, evade=rear (RAW: "You must note if
      you are pursuing or escaping")
    """
    # Move is special: facing depends on intent
    if maneuver == "move":
        return "front" if intent == "pursue" else "rear"

    m = MANEUVER_CATALOG.get(maneuver)
    if m is None:
        return "front"

    if m.facing == "front":
        return "front"
    elif m.facing == "rear":
        return "rear"
    elif m.facing in ("any", "any_opponent_choice"):
        return "any"
    else:
        return "front" if intent == "pursue" else "rear"


def get_target_facing_hit(
    attacker_has_advantage: bool,
    target_maneuver: str,
    target_intent: str,
    attacker_choice: Optional[str] = None,
) -> str:
    """
    Determine which facing of the target gets hit.

    RAW:
    - Non-advantaged: hit the facing the target declared
      (target pursuing = their front faces you, target evading = their rear)
    - Advantaged: attacker chooses which facing to attack
      (defaults to "rear" for maximum damage if no explicit choice)

    Args:
        attacker_has_advantage: Whether the attacker has advantage.
        target_maneuver: Target's declared maneuver.
        target_intent: Target's declared intent.
        attacker_choice: Explicit facing choice (for advantaged attackers).
    """
    if attacker_has_advantage:
        if attacker_choice:
            return attacker_choice
        # Default: attack the rear (weakest armor on most ships)
        return "rear"

    # Non-advantaged: hit the facing target is presenting
    # Target pursuing = their front faces us
    # Target evading = their rear faces us
    target_facing = get_attacker_facing(target_maneuver, target_intent)
    if target_facing == "front":
        return "front"
    elif target_facing == "rear":
        return "rear"
    else:
        return "front"  # "any" defaults to front


def get_dr_for_facing(ship, facing: str) -> int:
    """
    Get the hull DR value for a specific facing.

    Args:
        ship: Ship stats object with dr_front, dr_rear, etc.
        facing: "front", "rear", "left", "right", "top", "bottom"
    """
    dr_map = {
        "front": "dr_front",
        "rear": "dr_rear",
        "left": "dr_left",
        "right": "dr_right",
        "top": "dr_top",
        "bottom": "dr_bottom",
    }
    attr = dr_map.get(facing, "dr_front")
    return getattr(ship, attr, getattr(ship, "dr_front", 10))


# ============================================================================
# Stall Speed Chase Attack Restriction
# ============================================================================

def check_stall_attack_restriction(
    has_stall_speed: bool,
    won_chase: bool,
    weapon_mount: str,
) -> bool:
    """
    Check if a ship with stall speed can fire after a chase roll.

    RAW: "A pursuing craft with a stall speed must succeed by 0 or more
    to attack with fixed weapons."

    Turret weapons are not restricted.

    Returns True if the ship can fire, False if blocked.
    """
    if not has_stall_speed:
        return True
    if "turret" in weapon_mount:
        return True
    return won_chase


# ============================================================================
# Weapon Range Enforcement
# ============================================================================

# Minimum distance (yards) for each range band (the LOW end / start)
_RANGE_BAND_MIN_YARDS = {
    "close": 0,
    "short": 6,
    "medium": 21,
    "long": 101,
    "extreme": 501,
    "distant": 2001,
    "beyond_visual": 10001,
    "remote": 50001,
    "beyond_remote": 200001,
}


def _parse_range_yards(range_part: str) -> Optional[int]:
    """Parse a range value to yards. Handles '8000', '25 mi', '10mi', etc."""
    import re
    s = str(range_part).strip().lower()
    # Check for mile notation
    mi_match = re.match(r"([\d.]+)\s*mi", s)
    if mi_match:
        miles = float(mi_match.group(1))
        return int(miles * 1760)  # 1 mile = 1760 yards
    # Plain number = yards
    digits = re.sub(r"[^0-9]", "", s)
    if digits:
        return int(digits)
    return None


def is_weapon_in_range(weapon_range_str: Optional[str], range_band: str) -> bool:
    """
    Check if a weapon can reach the current range band.

    Weapon range format: "half_range/max_range" (e.g., "2700/8000" or "4 mi/12 mi").
    The weapon must be able to reach at least the START of the range band.

    Gracefully returns True for missing/unparseable range data.
    """
    if not weapon_range_str:
        return True

    try:
        parts = str(weapon_range_str).split("/")
        max_range = _parse_range_yards(parts[-1])
        if max_range is None:
            return True
    except (ValueError, IndexError):
        return True

    band_min = _RANGE_BAND_MIN_YARDS.get(range_band, 0)
    return max_range >= band_min


# ============================================================================
# Multiple Weapons Resolution
# ============================================================================

def resolve_all_weapons(
    ship_stats,
    fixtures_dir: Optional[Path] = None,
) -> list[WeaponInfo]:
    """
    Resolve ALL weapons available on a ship.

    Returns a list of WeaponInfo objects, one per weapon mount.
    Falls back to a single default weapon if no weapon data found.
    """
    weapons_list = getattr(ship_stats, "weapons", [])
    resolved = []

    for w in weapons_list:
        if isinstance(w, dict):
            ref = w.get("weapon_ref", "")
            mount = w.get("mount", "fixed_front")
            linked = w.get("linked_count", 1)
        else:
            ref = getattr(w, "weapon_id", "")
            mount = getattr(w, "mount", "fixed_front")
            linked = getattr(w, "linked_count", 1)

        if ref:
            data = load_weapon_data(ref, fixtures_dir)
            if data:
                parsed = parse_damage_string(data.get("damage", "6d×5(5) burn"))
                rof_str = data.get("rof", "3")
                try:
                    rof = int(rof_str.split("/")[0]) * linked
                except (ValueError, IndexError):
                    rof = 3

                resolved.append(WeaponInfo(
                    name=data.get("name", ref),
                    damage_str=data.get("damage", "6d×5(5) burn"),
                    acc=data.get("acc", 9),
                    rof=rof,
                    weapon_type=data.get("weapon_type", "beam"),
                    armor_divisor=parsed.armor_divisor,
                    mount=mount,
                    linked_count=linked,
                    is_explosive=parsed.explosive,
                    range_str=data.get("range", ""),
                ))

    if not resolved:
        resolved.append(WeaponInfo(
            name="Fighter Blaster", damage_str="6d×5(5) burn",
            acc=9, rof=3, weapon_type="beam", armor_divisor=5.0,
            mount="fixed_front", linked_count=1, is_explosive=False,
        ))

    return resolved


def resolve_chase(
    ship_a_id: str, ship_a, pilot_a,
    ship_b_id: str, ship_b, pilot_b,
    decl_a: dict, decl_b: dict,
    engagement: EngagementState,
    dice: DiceRoller,
) -> ChaseResult:
    """
    Resolve a chase contest between two ships.

    Calculates effective chase skills (Piloting + Handling + maneuver mod),
    rolls the quick contest, and determines available outcomes.

    Does NOT apply outcomes — returns options for the winner to choose.
    """
    # Calculate chase skills
    skill_a = getattr(pilot_a, "piloting_skill", 12) + getattr(ship_a, "hnd", 0)
    skill_b = getattr(pilot_b, "piloting_skill", 12) + getattr(ship_b, "hnd", 0)

    # Apply maneuver modifiers
    m_a = MANEUVER_CATALOG.get(decl_a.get("maneuver", "move"))
    m_b = MANEUVER_CATALOG.get(decl_b.get("maneuver", "move"))
    if m_a:
        skill_a += m_a.chase_modifier
    if m_b:
        skill_b += m_b.chase_modifier

    # Roll
    roll_a = dice.roll_3d6()
    roll_b = dice.roll_3d6()
    margin_a = skill_a - roll_a
    margin_b = skill_b - roll_b

    contest = resolve_quick_contest(skill_a, roll_a, skill_b, roll_b)

    # Determine winner
    if contest.winner == "a":
        winner_id = ship_a_id
        winner_name = getattr(ship_a, "display_name", ship_a_id)
        winner_intent = decl_a.get("intent", "pursue")
        winner_had_adv = engagement.advantage == ship_a_id
        loser_had_adv = engagement.advantage == ship_b_id
    elif contest.winner == "b":
        winner_id = ship_b_id
        winner_name = getattr(ship_b, "display_name", ship_b_id)
        winner_intent = decl_b.get("intent", "pursue")
        winner_had_adv = engagement.advantage == ship_b_id
        loser_had_adv = engagement.advantage == ship_a_id
    else:
        return ChaseResult(
            skill_a=skill_a, skill_b=skill_b,
            roll_a=roll_a, roll_b=roll_b,
            margin_a=margin_a, margin_b=margin_b,
            winner_id=None, winner_name="",
            margin_of_victory=0,
        )

    # Resolve outcome options
    from m1_psi_core.chase import resolve_chase_outcome
    outcome = resolve_chase_outcome(
        margin=contest.margin_of_victory,
        winner_intent=winner_intent,
        winner_had_advantage=winner_had_adv,
        loser_had_advantage=loser_had_adv,
    )

    return ChaseResult(
        skill_a=skill_a, skill_b=skill_b,
        roll_a=roll_a, roll_b=roll_b,
        margin_a=margin_a, margin_b=margin_b,
        winner_id=winner_id, winner_name=winner_name,
        margin_of_victory=contest.margin_of_victory,
        can_gain_advantage=outcome.can_gain_advantage,
        can_match_speed=outcome.can_match_speed,
        can_shift_range=outcome.can_shift_range,
        opponent_loses_advantage=outcome.opponent_loses_advantage and loser_had_adv,
    )


# ============================================================================
# Attack Resolution
# ============================================================================

def resolve_attack(
    attacker_id: str, attacker, pilot,
    target_id: str, target,
    engagement: EngagementState,
    declaration: dict,
    weapon: WeaponInfo,
    dice: DiceRoller,
    deceptive_levels: int = 0,
    targeted_system: bool = False,
) -> AttackResult:
    """
    Resolve a complete attack roll with ALL modifiers.

    Automatically includes: range, SM, sensor lock, accuracy,
    ROF bonus, relative size penalty, deceptive attack, targeted system.

    Returns the result WITHOUT applying any state changes.
    """
    a_name = getattr(attacker, "display_name", attacker_id)
    t_name = getattr(target, "display_name", target_id)

    maneuver = declaration.get("maneuver", "move")

    # Check if attack is allowed
    perm = get_attack_permission(
        maneuver,
        is_ace_pilot=getattr(pilot, "is_ace_pilot", False),
        is_gunslinger=getattr(pilot, "is_gunslinger", False),
    )
    if perm == "none":
        return AttackResult(
            attacker_id=attacker_id, attacker_name=a_name,
            target_id=target_id, target_name=t_name,
            weapon=weapon, modifiers=AttackModifiers(base_skill=0, range_penalty=0,
                sm_bonus=0, sensor_lock_bonus=0, accuracy=0, rof_bonus=0,
                relative_size_penalty=0),
            roll=0, margin=0, hit=False, critical=False, critical_type=None,
            can_attack=False, reason_cannot_attack=f"Maneuver '{maneuver}' does not allow attacks",
        )

    if not can_ship_attack(no_power=getattr(attacker, "no_power", False)):
        return AttackResult(
            attacker_id=attacker_id, attacker_name=a_name,
            target_id=target_id, target_name=t_name,
            weapon=weapon, modifiers=AttackModifiers(base_skill=0, range_penalty=0,
                sm_bonus=0, sensor_lock_bonus=0, accuracy=0, rof_bonus=0,
                relative_size_penalty=0),
            roll=0, margin=0, hit=False, critical=False, critical_type=None,
            can_attack=False, reason_cannot_attack="Ship has no power",
        )

    # Check subsystem damage: destroyed weaponry or destroyed power prevents firing
    from m1_psi_core.subsystems import can_fire_weapons
    if not can_fire_weapons(attacker):
        return AttackResult(
            attacker_id=attacker_id, attacker_name=a_name,
            target_id=target_id, target_name=t_name,
            weapon=weapon, modifiers=AttackModifiers(base_skill=0, range_penalty=0,
                sm_bonus=0, sensor_lock_bonus=0, accuracy=0, rof_bonus=0,
                relative_size_penalty=0),
            roll=0, margin=0, hit=False, critical=False, critical_type=None,
            can_attack=False, reason_cannot_attack="Weapons or power destroyed",
        )

    # Check weapon facing: fixed weapons must have correct facing to fire
    attacker_facing = get_attacker_facing(maneuver, declaration.get("intent", "pursue"))
    if not can_weapon_fire_facing(weapon.mount, attacker_facing):
        return AttackResult(
            attacker_id=attacker_id, attacker_name=a_name,
            target_id=target_id, target_name=t_name,
            weapon=weapon, modifiers=AttackModifiers(base_skill=0, range_penalty=0,
                sm_bonus=0, sensor_lock_bonus=0, accuracy=0, rof_bonus=0,
                relative_size_penalty=0),
            roll=0, margin=0, hit=False, critical=False, critical_type=None,
            can_attack=False,
            reason_cannot_attack=f"Fixed weapon cannot fire while facing {attacker_facing}",
        )

    # Calculate all modifiers
    base_skill = getattr(pilot, "gunnery_skill", 12)

    # Range penalty: use effective range with speed penalties
    own_speed = getattr(attacker, "top_speed", 0)
    opp_speed = getattr(target, "top_speed", 0)
    is_matched = engagement.matched_speed and engagement.advantage == attacker_id

    if is_matched:
        # Matched Speed: use max(|range|, stall_speed_penalty)
        from m1_psi_core.combat_state import get_matched_speed_range_penalty
        stall = getattr(attacker, "stall_speed", 0)
        range_pen = get_matched_speed_range_penalty(engagement.range_band, stall)
    else:
        # Normal: use max(|range|, own_speed, opponent_speed)
        from m1_psi_core.combat_state import get_effective_range_penalty
        range_pen = get_effective_range_penalty(engagement.range_band, own_speed, opp_speed)

    sm_bonus = get_sm_bonus(getattr(target, "sm", 4))
    sensor_lock = get_sensor_lock_bonus(True, getattr(attacker, "targeting_bonus", 5))

    # Accuracy: matched speed grants full accuracy on any maneuver
    if is_matched:
        acc = apply_accuracy(weapon.acc, "full")
    else:
        acc = apply_accuracy(weapon.acc, perm)

    rof_bonus = get_rof_bonus(weapon.rof)

    a_class = classify_ship(getattr(attacker, "sm", 4), 15)
    t_class = classify_ship(getattr(target, "sm", 4), 15)
    rel_size = get_relative_size_penalty(a_class, t_class)

    deceptive_pen = -2 * deceptive_levels
    targeted_pen = TARGETED_SYSTEM_PENALTY if targeted_system else 0

    effective = (base_skill + range_pen + sm_bonus + sensor_lock + acc
                 + rof_bonus + rel_size + deceptive_pen + targeted_pen)

    mods = AttackModifiers(
        base_skill=base_skill,
        range_penalty=range_pen,
        sm_bonus=sm_bonus,
        sensor_lock_bonus=sensor_lock,
        accuracy=acc,
        rof_bonus=rof_bonus,
        relative_size_penalty=rel_size,
        deceptive_penalty=deceptive_pen,
        targeted_system_penalty=targeted_pen,
        effective_skill=effective,
    )

    # Roll
    roll = dice.roll_3d6()
    result = check_success(effective, roll)

    return AttackResult(
        attacker_id=attacker_id, attacker_name=a_name,
        target_id=target_id, target_name=t_name,
        weapon=weapon, modifiers=mods,
        roll=roll, margin=result.margin,
        hit=result.success,
        critical=result.critical,
        critical_type=result.critical_type,
    )


# ============================================================================
# Defense Resolution
# ============================================================================

def resolve_defense(
    defender_id: str, defender, defender_pilot,
    defender_maneuver: str,
    attacker_maneuver: str,
    engagement: EngagementState,
    dice: DiceRoller,
    deceptive_penalty: int = 0,
    attacker_id: str = "",
    offer_high_g: bool = True,
    player_chose_high_g: Optional[bool] = None,
) -> DefenseResult:
    """
    Resolve a defense roll with ALL modifiers.

    Automatically includes: base dodge, maneuver bonuses, advantage
    escaping, ace pilot stunt, precision aim awareness, tactical
    coordination, High-G dodge, and deceptive attack penalty.

    For High-G dodge:
    - If the ship qualifies, sets offered_high_g=True in the result.
    - If player_chose_high_g is True, applies the High-G bonus and
      rolls the HT check for FP loss.
    - NPC ships: the AI decides (for now, always attempt if available).
    """
    d_name = getattr(defender, "display_name", defender_id)

    # Base dodge
    piloting = getattr(defender_pilot, "piloting_skill", 12)
    handling = getattr(defender, "hnd", 0)
    base = calculate_base_dodge(piloting, handling)

    # Situational modifiers
    has_adv_escaping = (
        engagement.advantage == defender_id
        and defender_maneuver in ("evade", "stunt_escape", "mobility_escape")
    )
    ace_stunt = (
        getattr(defender_pilot, "is_ace_pilot", False)
        and defender_maneuver in ("stunt", "stunt_escape")
    )

    mods = get_dodge_modifiers(
        maneuver=defender_maneuver,
        has_advantage_escaping=has_adv_escaping,
        ace_pilot_stunt=ace_stunt,
    )

    # Build our modifier tracking
    dm = DefenseModifiers(
        base_dodge=base,
        piloting_skill=piloting,
        handling=handling,
        evade_bonus=mods.evade_bonus,
        advantage_escaping_bonus=mods.advantage_escaping_bonus,
        ace_stunt_bonus=mods.ace_stunt_bonus,
        deceptive_penalty=deceptive_penalty,
    )

    # High-G dodge check
    accel = getattr(defender, "accel", 0)
    top_speed = getattr(defender, "top_speed", 0)
    high_g_avail = is_high_g_available(accel, top_speed)

    hg = HighGResult(available=high_g_avail)
    offered = high_g_avail and offer_high_g

    # Determine if High-G should be attempted
    attempt_high_g = False
    if high_g_avail:
        if player_chose_high_g is True:
            attempt_high_g = True
        elif player_chose_high_g is None:
            # NPC default: attempt if available
            attempt_high_g = True

    if attempt_high_g:
        dm.high_g_bonus = HIGH_G_DODGE_BONUS
        hg.attempted = True

        # HT roll for FP cost
        ht = getattr(defender_pilot, "ht", 12)
        has_g_chair = getattr(defender, "has_g_chair", False)
        ht_mod = get_high_g_ht_modifier(has_g_chair)
        ht_target = ht + ht_mod
        ht_roll = dice.roll_3d6()
        ht_result = check_success(ht_target, ht_roll)

        hg.ht_target = ht_target
        hg.ht_modifier = ht_mod
        hg.ht_roll = ht_roll
        hg.ht_succeeded = ht_result.success
        hg.fp_lost = calculate_high_g_fp_loss(ht_target, ht_roll)

    # Controls damage penalty
    from m1_psi_core.subsystems import get_controls_penalty
    ctrl_pen = get_controls_penalty(defender)
    dm.controls_penalty = ctrl_pen

    # Calculate effective dodge
    effective = (base + dm.evade_bonus + dm.advantage_escaping_bonus
                 + dm.ace_stunt_bonus + dm.precision_aim_awareness
                 + dm.tactical_defense + dm.high_g_bonus + dm.deceptive_penalty
                 + dm.controls_penalty)
    dm.effective_dodge = effective

    # Roll
    roll = dice.roll_3d6()
    result = check_success(effective, roll, is_defense=True)

    return DefenseResult(
        defender_id=defender_id,
        defender_name=d_name,
        defense_type="high_g_dodge" if attempt_high_g else "dodge",
        modifiers=dm,
        roll=roll,
        margin=result.margin,
        success=result.success,
        critical=result.critical,
        high_g=hg,
        offered_high_g=offered,
    )


# ============================================================================
# Damage Resolution
# ============================================================================

def resolve_damage(
    target_id: str, target,
    weapon: WeaponInfo,
    dice: DiceRoller,
    facing: str = "front",
) -> DamageResult:
    """
    Resolve the complete damage pipeline.

    Steps:
    1. Roll raw damage from the weapon's damage string
    2. Force screen absorption (if ship has one)
    3. Hull armor with armor divisor
    4. Penetrating damage calculation
    5. Wound level determination
    6. Subsystem damage (on major+ wounds)
    7. Destruction check (lethal wound or HP <= 0)
    8. Mook removal check

    Returns all state changes as values — does NOT mutate the target.
    """
    t_name = getattr(target, "display_name", target_id)
    steps: list[DamageStep] = []

    # Step 1: Roll raw damage
    parsed = parse_damage_string(weapon.damage_str)
    if parsed.dice == 0:
        return DamageResult(
            target_id=target_id, target_name=t_name,
            raw_damage=0, has_force_screen=False,
            fdr_absorbed=0, fdr_remaining=0, damage_past_screen=0,
            hull_dr=0, effective_dr=0, armor_divisor=1.0,
            penetrating_damage=0, wound_level="none", wound_pct=0,
            max_hp=0, new_hp=0, steps=steps,
        )

    dice_total = dice.roll_nd6(parsed.dice)
    raw_damage = dice_total * parsed.multiplier + parsed.adds
    ad = weapon.armor_divisor if weapon.armor_divisor else 1.0

    steps.append(DamageStep("Raw damage", f"{parsed.dice}d6={dice_total} × {parsed.multiplier} = {raw_damage}"))

    # Step 2: Force screen
    has_screen = getattr(target, "fdr_max", 0) > 0
    current_fdr = getattr(target, "current_fdr", 0)
    fs_type = getattr(target, "force_screen_type", "none")

    screen = apply_force_screen(
        incoming_damage=raw_damage,
        current_fdr=current_fdr,
        armor_divisor=ad,
        force_screen_type=fs_type,
        damage_type=parsed.damage_type,
    )

    if has_screen:
        steps.append(DamageStep("Force screen",
            f"Absorbs {screen.absorbed} (fDR: {current_fdr} → {screen.remaining_fdr})"))

    if has_screen and screen.penetrating <= 0:
        steps.append(DamageStep("Result", "Blocked by force screen"))
        return DamageResult(
            target_id=target_id, target_name=t_name,
            raw_damage=raw_damage, has_force_screen=True,
            fdr_absorbed=screen.absorbed, fdr_remaining=screen.remaining_fdr,
            damage_past_screen=0,
            hull_dr=0, effective_dr=0, armor_divisor=ad,
            penetrating_damage=0, wound_level="none", wound_pct=0,
            max_hp=getattr(target, "st_hp", 80),
            new_hp=getattr(target, "current_hp", 80),
            new_wound_level=getattr(target, "wound_level", "none"),
            steps=steps,
        )

    # Step 3: Hull armor (uses facing to select correct DR)
    hull_dr = get_dr_for_facing(target, facing)

    # If force screen negated AD (plasma/heavy screen), hull ignores AD too
    hull_ad = 1.0 if screen.hull_ad_negated else ad
    effective_dr = apply_armor_divisor(hull_dr, hull_ad)
    penetrating = max(0, screen.penetrating - effective_dr)

    steps.append(DamageStep("Hull armor",
        f"{screen.penetrating} vs DR {hull_dr} (eff {effective_dr} w/ AD {ad}) → {penetrating} penetrating"))

    if penetrating <= 0:
        steps.append(DamageStep("Result", "Stopped by armor"))
        return DamageResult(
            target_id=target_id, target_name=t_name,
            raw_damage=raw_damage, has_force_screen=has_screen,
            fdr_absorbed=screen.absorbed, fdr_remaining=screen.remaining_fdr,
            damage_past_screen=screen.penetrating,
            hull_dr=hull_dr, effective_dr=effective_dr, armor_divisor=ad,
            penetrating_damage=0, wound_level="none", wound_pct=0,
            max_hp=getattr(target, "st_hp", 80),
            new_hp=getattr(target, "current_hp", 80),
            new_wound_level=getattr(target, "wound_level", "none"),
            steps=steps,
        )

    # Step 4: Wound level
    max_hp = getattr(target, "st_hp", 80)
    current_hp = getattr(target, "current_hp", max_hp)
    wound = determine_wound_level(penetrating, max_hp)
    pct = (penetrating / max(max_hp, 1)) * 100
    new_hp = max(0, current_hp - penetrating)

    steps.append(DamageStep("Wound",
        f"{wound.upper()} ({penetrating}hp = {pct:.0f}% of {max_hp} HP)"))

    # Step 5: Update wound level (only escalate)
    cur_wound = getattr(target, "wound_level", "none")
    cur_sev = WOUND_SEVERITY.get(cur_wound, 0)
    new_sev = WOUND_SEVERITY.get(wound, 0)
    final_wound = wound if new_sev > cur_sev else cur_wound

    # Step 6: Destruction check
    destroyed = (wound == "lethal" or new_hp <= 0)
    if destroyed:
        steps.append(DamageStep("Result", "DESTROYED"))

    # Step 7: Subsystem damage
    sys_roll = 0
    sys_hit = ""
    sys_status = ""
    sys_cascade = None

    if not destroyed and wound in ("major", "crippling", "mortal"):
        sys_roll = dice.roll_3d6()
        sys_hit, cascade_target = get_subsystem_hit(sys_roll)
        sys_status = "disabled" if wound == "major" else "destroyed"
        sys_cascade = cascade_target
        steps.append(DamageStep("Subsystem",
            f"Roll {sys_roll}: {sys_hit} {sys_status}"))

    # Step 8: Mook check
    mook_removed = False
    if getattr(target, "is_mook", False) and new_sev >= WOUND_SEVERITY.get("major", 3):
        mook_removed = True
        destroyed = True
        steps.append(DamageStep("Mook", "Removed from combat"))

    return DamageResult(
        target_id=target_id, target_name=t_name,
        raw_damage=raw_damage, has_force_screen=has_screen,
        fdr_absorbed=screen.absorbed, fdr_remaining=screen.remaining_fdr,
        damage_past_screen=screen.penetrating,
        hull_dr=hull_dr, effective_dr=effective_dr, armor_divisor=ad,
        penetrating_damage=penetrating,
        wound_level=wound, wound_pct=pct, max_hp=max_hp, new_hp=new_hp,
        subsystem_roll=sys_roll, subsystem_hit=sys_hit,
        subsystem_status=sys_status, subsystem_cascade=sys_cascade,
        is_destroyed=destroyed, is_mook_removed=mook_removed,
        new_wound_level=final_wound,
        steps=steps,
    )


# ============================================================================
# Force Screen Regeneration (cleanup phase)
# ============================================================================

def regen_force_screen(ship) -> int:
    """
    Calculate regenerated fDR for end-of-turn cleanup.

    Respects subsystem damage:
    - Destroyed power: no regen (returns current fDR)
    - Disabled power: regen to half max fDR
    - Normal: regen to full max fDR

    Does NOT mutate the ship.
    """
    if getattr(ship, "no_power", False):
        return getattr(ship, "current_fdr", 0)

    from m1_psi_core.subsystems import get_effective_fdr_max
    return get_effective_fdr_max(ship)
