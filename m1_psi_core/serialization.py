"""
JSON Serialization for Psi-Wars game state.

Every object that crosses the engine/UI boundary must be serializable
to plain JSON dicts. This module provides to_dict() and from_dict()
for all stateful objects.

Design principle: the JSON format IS the API contract. If the web UI
receives a ship dict, it should contain exactly the fields the UI
needs to render that ship — no more, no less.

Usage:
    from m1_psi_core.serialization import serialize_session, serialize_ship

    # Send to web UI:
    state_json = serialize_session(session)
    ship_json = serialize_ship(ship_stats, pilot)

    # Receive from web UI:
    decision = deserialize_decision(request_json)
"""
from __future__ import annotations

from typing import Any, Optional
from dataclasses import asdict


# ---------------------------------------------------------------------------
# Ship serialization
# ---------------------------------------------------------------------------

def serialize_ship(ship_stats, pilot=None, ship_id: str = "",
                   faction: str = "", control: str = "human") -> dict:
    """
    Serialize a ship + pilot into a flat dict for the UI.

    Returns all fields the UI needs to render the ship status bar,
    inspection panel, and weapon selection menu.
    """
    s = ship_stats

    # Core identity
    result = {
        "ship_id": ship_id or getattr(s, "instance_id", ""),
        "template_id": getattr(s, "template_id", ""),
        "display_name": getattr(s, "display_name", "Unknown"),
        "faction": faction,
        "control": control,
        "sm": getattr(s, "sm", 4),
        "ship_class": getattr(s, "ship_class", "fighter"),
    }

    # HP and wound
    result["st_hp"] = getattr(s, "st_hp", 80)
    result["current_hp"] = getattr(s, "current_hp", result["st_hp"])
    result["wound_level"] = getattr(s, "wound_level", "none")
    result["is_destroyed"] = getattr(s, "is_destroyed", False)
    result["ht"] = str(getattr(s, "ht", 12))

    # Mobility
    result["hnd"] = getattr(s, "hnd", 0)
    result["sr"] = getattr(s, "sr", 3)
    result["accel"] = getattr(s, "accel", 10)
    result["top_speed"] = getattr(s, "top_speed", 400)
    result["stall_speed"] = getattr(s, "stall_speed", 0)

    # Armor (all 6 facings)
    for facing in ("front", "rear", "left", "right", "top", "bottom"):
        result[f"dr_{facing}"] = getattr(s, f"dr_{facing}", 10)

    # Force screen
    result["fdr_max"] = getattr(s, "fdr_max", 0)
    result["current_fdr"] = getattr(s, "current_fdr", 0)
    result["force_screen_type"] = getattr(s, "force_screen_type", "none")

    # Electronics
    result["ecm_rating"] = getattr(s, "ecm_rating", -4)
    result["targeting_bonus"] = getattr(s, "targeting_bonus", 5)
    result["has_tactical_esm"] = getattr(s, "has_tactical_esm", False)
    result["has_decoy_launcher"] = getattr(s, "has_decoy_launcher", False)

    # Subsystem damage
    from m1_psi_core.subsystems import get_disabled, get_destroyed
    result["disabled_systems"] = list(get_disabled(s))
    result["destroyed_systems"] = list(get_destroyed(s))

    # Emergency power
    result["emergency_power_reserves"] = getattr(s, "emergency_power_reserves", 0)

    # Weapons (resolved from JSON)
    from m1_psi_core.engine import resolve_all_weapons
    try:
        weapons = resolve_all_weapons(s)
        result["weapons"] = [
            {
                "name": w.name,
                "damage_str": w.damage_str,
                "acc": w.acc,
                "rof": w.rof,
                "weapon_type": w.weapon_type,
                "armor_divisor": w.armor_divisor,
                "mount": w.mount,
                "range_str": w.range_str,
                "is_explosive": w.is_explosive,
            }
            for w in weapons
        ]
    except Exception:
        result["weapons"] = []

    # Pilot info
    if pilot:
        result["pilot"] = {
            "name": getattr(pilot, "name", "Unknown"),
            "piloting_skill": getattr(pilot, "piloting_skill", 12),
            "gunnery_skill": getattr(pilot, "gunnery_skill", 12),
            "basic_speed": getattr(pilot, "basic_speed", 6.0),
            "is_ace_pilot": getattr(pilot, "is_ace_pilot", False),
            "luck_level": getattr(pilot, "luck_level", "none"),
            "current_fp": getattr(pilot, "current_fp", 10),
            "max_fp": getattr(pilot, "max_fp", 10),
        }
    else:
        result["pilot"] = None

    return result


# ---------------------------------------------------------------------------
# Engagement serialization
# ---------------------------------------------------------------------------

def serialize_engagement(eng) -> dict:
    """Serialize an EngagementState for the UI."""
    return {
        "ship_a_id": eng.ship_a_id,
        "ship_b_id": eng.ship_b_id,
        "range_band": eng.range_band,
        "advantage": eng.advantage,
        "matched_speed": eng.matched_speed,
        "hugging": eng.hugging,
    }


# ---------------------------------------------------------------------------
# Full session serialization
# ---------------------------------------------------------------------------

def serialize_session(session) -> dict:
    """
    Serialize the entire game session for the UI.

    This is the complete snapshot the web UI needs to render
    the battlefield — all ships, engagements, factions, and turn state.
    """
    ships = {}
    for sid in session.get_all_ship_ids():
        ship = session.get_ship(sid)
        pilot = session.get_pilot(sid)
        faction = session.get_faction_for_ship(sid) or ""
        control = session.get_control_mode(sid) or "human"
        ships[sid] = serialize_ship(ship, pilot, sid, faction, control)

    engagements = []
    seen = set()
    for sid in session.get_all_ship_ids():
        for eng in session.get_engagements_for_ship(sid):
            key = (min(eng.ship_a_id, eng.ship_b_id),
                   max(eng.ship_a_id, eng.ship_b_id))
            if key not in seen:
                seen.add(key)
                engagements.append(serialize_engagement(eng))

    factions = {}
    for fname, fobj in session.factions.items():
        factions[fname] = {"name": fobj.name, "color": fobj.color}

    return {
        "current_turn": session.current_turn,
        "ships": ships,
        "engagements": engagements,
        "factions": factions,
        "combat_ended": session.check_combat_end(),
    }


# ---------------------------------------------------------------------------
# Combat log entry serialization
# ---------------------------------------------------------------------------

def serialize_log_entry(message: str, event_type: str = "info",
                        turn: int = 0) -> dict:
    """Serialize a single combat log entry."""
    return {
        "message": message,
        "event_type": event_type,
        "turn": turn,
    }


# ---------------------------------------------------------------------------
# Attack/Defense/Damage result serialization
# ---------------------------------------------------------------------------

def serialize_attack_result(atk) -> dict:
    """Serialize an AttackResult for the UI."""
    return {
        "attacker_id": atk.attacker_id,
        "attacker_name": atk.attacker_name,
        "target_id": atk.target_id,
        "target_name": atk.target_name,
        "weapon_name": atk.weapon.name if atk.weapon else "",
        "can_attack": atk.can_attack,
        "reason_cannot_attack": getattr(atk, "reason_cannot_attack", ""),
        "hit": atk.hit,
        "critical": atk.critical,
        "roll": atk.roll,
        "margin": atk.margin,
        "modifiers": {
            "base_skill": atk.modifiers.base_skill,
            "range_penalty": atk.modifiers.range_penalty,
            "sm_bonus": atk.modifiers.sm_bonus,
            "sensor_lock_bonus": atk.modifiers.sensor_lock_bonus,
            "accuracy": atk.modifiers.accuracy,
            "rof_bonus": atk.modifiers.rof_bonus,
            "relative_size_penalty": atk.modifiers.relative_size_penalty,
            "deceptive_penalty": atk.modifiers.deceptive_penalty,
            "effective_skill": atk.modifiers.effective_skill,
        },
    }


def serialize_defense_result(defense) -> dict:
    """Serialize a DefenseResult for the UI."""
    return {
        "defender_id": defense.defender_id,
        "defender_name": defense.defender_name,
        "defense_type": defense.defense_type,
        "success": defense.success,
        "roll": defense.roll,
        "margin": defense.margin,
        "modifiers": {
            "base_dodge": defense.modifiers.base_dodge,
            "effective_dodge": defense.modifiers.effective_dodge,
            "evade_bonus": defense.modifiers.evade_bonus,
            "high_g_bonus": defense.modifiers.high_g_bonus,
            "deceptive_penalty": defense.modifiers.deceptive_penalty,
        },
        "high_g": {
            "attempted": defense.high_g.attempted,
            "ht_roll": defense.high_g.ht_roll,
            "ht_target": defense.high_g.ht_target,
            "ht_succeeded": defense.high_g.ht_succeeded,
            "fp_lost": defense.high_g.fp_lost,
        } if defense.high_g else None,
    }


def serialize_damage_result(dmg) -> dict:
    """Serialize a DamageResult for the UI."""
    return {
        "target_id": dmg.target_id,
        "target_name": dmg.target_name,
        "raw_damage": dmg.raw_damage,
        "has_force_screen": dmg.has_force_screen,
        "fdr_absorbed": dmg.fdr_absorbed,
        "fdr_remaining": dmg.fdr_remaining,
        "hull_dr": dmg.hull_dr,
        "effective_dr": dmg.effective_dr,
        "penetrating_damage": dmg.penetrating_damage,
        "wound_level": dmg.wound_level,
        "new_wound_level": getattr(dmg, "new_wound_level", dmg.wound_level),
        "new_hp": dmg.new_hp,
        "max_hp": dmg.max_hp,
        "is_destroyed": dmg.is_destroyed,
        "subsystem_hit": getattr(dmg, "subsystem_hit", ""),
        "subsystem_status": getattr(dmg, "subsystem_status", ""),
        "steps": [
            {"label": s.label, "value": s.value}
            for s in dmg.steps
        ],
    }


def serialize_chase_result(chase) -> dict:
    """Serialize a ChaseResult for the UI."""
    return {
        "skill_a": chase.skill_a,
        "skill_b": chase.skill_b,
        "roll_a": chase.roll_a,
        "roll_b": chase.roll_b,
        "margin_a": chase.margin_a,
        "margin_b": chase.margin_b,
        "winner_id": chase.winner_id,
        "winner_name": chase.winner_name,
        "margin_of_victory": chase.margin_of_victory,
        "can_gain_advantage": getattr(chase, "can_gain_advantage", False),
        "can_match_speed": getattr(chase, "can_match_speed", False),
        "can_shift_range": getattr(chase, "can_shift_range", 0),
    }
