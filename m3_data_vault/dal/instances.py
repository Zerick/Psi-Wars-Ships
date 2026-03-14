"""
Ship instance management for M3 Data-Vault.

This module handles the full lifecycle of ship instances:
spawning from templates, calculating effective stats, applying
damage, managing modes, installing modules, and grafting custom weapons.

The get_effective_stats() function is the primary consumer-facing method.
It resolves the complete stat block through the pipeline:
    base template -> installed modules -> active mode -> system damage penalties
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from m3_data_vault.db.tables import (
    ShipTemplateRow,
    ShipInstanceRow,
    SystemStatusRow,
    WeaponCatalogRow,
    ModuleCatalogRow,
    ControllerRow,
    SYSTEM_TYPES,
    SYSTEM_STATUSES,
    WOUND_THRESHOLDS,
)
from m3_data_vault.models.template import ShipTemplate
from m3_data_vault.models.weapon import WeaponDefinition
from m3_data_vault.models.module import ModuleDefinition
from m3_data_vault.models.effective_stats import EffectiveStatBlock, ResolvedWeapon
from m3_data_vault.exceptions import (
    TemplateNotFoundError,
    InstanceNotFoundError,
    InvalidModeError,
    InvalidSystemTypeError,
    InvalidStatusError,
    SlotMismatchError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_template(session: Session, template_id: str) -> ShipTemplate:
    """Fetch and deserialize a ship template from the database."""
    row = session.query(ShipTemplateRow).filter_by(
        template_id=template_id
    ).first()
    if row is None:
        raise TemplateNotFoundError(f"Template '{template_id}' not found")
    return ShipTemplate.model_validate_json(row.data_json)


def _get_instance(session: Session, instance_id: str) -> ShipInstanceRow:
    """Fetch a ship instance row, raising if not found."""
    row = session.query(ShipInstanceRow).filter_by(
        instance_id=instance_id
    ).first()
    if row is None:
        raise InstanceNotFoundError(f"Ship instance '{instance_id}' not found")
    return row


def _get_weapon_from_catalog(session: Session, weapon_id: str) -> WeaponDefinition:
    """Fetch and deserialize a weapon from the catalog."""
    row = session.query(WeaponCatalogRow).filter_by(weapon_id=weapon_id).first()
    if row is None:
        # Return a placeholder rather than crashing — allows graceful degradation
        logger.warning("Weapon '%s' not found in catalog", weapon_id)
        return WeaponDefinition(
            weapon_id=weapon_id, name=f"[MISSING: {weapon_id}]",
            damage="0", acc=0, range="0", rof="0", rcl=0, shots="0",
            ewt="0", st_requirement="M", bulk="0",
            weapon_type="unknown", damage_type="unknown",
            notes="This weapon was not found in the catalog.",
        )
    return WeaponDefinition.model_validate_json(row.data_json)


def _get_module_from_catalog(session: Session, module_id: str) -> ModuleDefinition:
    """Fetch and deserialize a module from the catalog."""
    row = session.query(ModuleCatalogRow).filter_by(module_id=module_id).first()
    if row is None:
        logger.warning("Module '%s' not found in catalog", module_id)
        return None
    return ModuleDefinition.model_validate_json(row.data_json)


def _compute_wound_level(damage: int, max_hp: int) -> str:
    """
    Determine wound level from a single hit's damage relative to max HP.

    The wound level is determined by the ratio of damage to max HP:
        scratch:   < 10%
        minor:     10% - 49%
        major:     50% - 99%
        crippling: 100% - 199%
        mortal:    200% - 499%
        lethal:    >= 500%
    """
    if damage <= 0 or max_hp <= 0:
        return "none"

    ratio = damage / max_hp

    # WOUND_THRESHOLDS is ordered from highest to lowest
    for threshold, level in WOUND_THRESHOLDS:
        if ratio >= threshold:
            return level

    return "none"


# ---------------------------------------------------------------------------
# Spawn
# ---------------------------------------------------------------------------

def spawn_ship(
    session: Session,
    template_id: str,
    controller_id: Optional[str] = None,
    display_name: str = "Unnamed Ship",
    session_id: str = "default",
    module_loadout: Optional[dict] = None,
) -> str:
    """
    Create a new ship instance from a template.

    Initializes all state fields and creates system_status rows for
    every system type. If a module_loadout is provided, it's stored
    on the instance. If any module provides a force screen (fdr_provided),
    the instance's current_fdr is initialized to that value.

    Args:
        session: Active SQLAlchemy session.
        template_id: Which ship template to spawn from.
        controller_id: UUID of the controller, or None for uncontrolled.
        display_name: Instance-specific name (e.g. "Red Five").
        session_id: Combat session identifier.
        module_loadout: Dict mapping slot_id -> module_id.

    Returns:
        The instance_id (UUID string) of the new ship.

    Raises:
        TemplateNotFoundError: If the template doesn't exist.
    """
    template = _get_template(session, template_id)

    # Determine initial fDR — from template, or from installed force screen module
    initial_fdr = template.defense.fdr_max

    if module_loadout:
        for slot_id, mod_id in module_loadout.items():
            mod_def = _get_module_from_catalog(session, mod_id)
            if mod_def and mod_def.fdr_provided is not None:
                initial_fdr = max(initial_fdr, mod_def.fdr_provided)

    instance_id = str(uuid.uuid4())
    instance = ShipInstanceRow(
        instance_id=instance_id,
        template_id=template_id,
        controller_id=controller_id,
        display_name=display_name,
        session_id=session_id,
        current_hp=template.attributes.st_hp,
        wound_level="none",
        current_fdr=initial_fdr,
        active_mode="standard",
        is_disabled=False,
        is_destroyed=False,
        installed_modules=json.dumps(module_loadout or {}),
        custom_weapons=json.dumps([]),
    )
    session.add(instance)

    # Create system_status rows for all system types
    for sys_type in SYSTEM_TYPES:
        status_row = SystemStatusRow(
            instance_id=instance_id,
            system_type=sys_type,
            status="operational",
        )
        session.add(status_row)

    session.flush()
    return instance_id


# ---------------------------------------------------------------------------
# Effective stats resolution
# ---------------------------------------------------------------------------

def get_effective_stats(session: Session, instance_id: str) -> EffectiveStatBlock:
    """
    Calculate and return the current effective stat block for a ship instance.

    Resolution pipeline:
    1. Load base template stats
    2. Apply installed module effects (stat overrides, force screen, weapons)
    3. Apply active mode overrides
    4. Apply system damage penalties
    5. Resolve all weapons (template + module + custom)
    6. Determine faction from controller

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.

    Returns:
        A fully resolved EffectiveStatBlock.

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
        TemplateNotFoundError: If the instance's template doesn't exist.
    """
    instance = _get_instance(session, instance_id)
    template = _get_template(session, instance.template_id)

    # --- Step 1: Start with base template stats ---
    stats = {
        "st_hp": template.attributes.st_hp,
        "ht": template.attributes.ht,
        "hnd": template.attributes.hnd,
        "sr": template.attributes.sr,
        "accel": template.mobility.accel,
        "top_speed": template.mobility.top_speed,
        "stall_speed": template.mobility.stall_speed,
        "dr_front": template.defense.dr_front,
        "dr_rear": template.defense.dr_rear,
        "dr_left": template.defense.dr_left,
        "dr_right": template.defense.dr_right,
        "dr_top": template.defense.dr_top,
        "dr_bottom": template.defense.dr_bottom,
        "dr_material": template.defense.dr_material,
        "fdr_max": template.defense.fdr_max,
        "force_screen_type": template.defense.force_screen_type,
        "ecm_rating": template.electronics.ecm_rating,
        "targeting_bonus": template.electronics.targeting_bonus,
        "ultrascanner_range": template.electronics.ultrascanner_range,
    }

    # Collect traits from template
    traits = list(template.traits)

    # Collect weapons from template mounts
    weapons: list[ResolvedWeapon] = []

    # --- Step 2: Apply installed module effects ---
    installed = json.loads(instance.installed_modules)
    for slot_id, mod_id in installed.items():
        mod_def = _get_module_from_catalog(session, mod_id)
        if mod_def is None:
            continue

        # Apply stat overrides from the module
        if mod_def.stat_effects:
            for stat_key, stat_value in mod_def.stat_effects.items():
                if stat_key in stats:
                    stats[stat_key] = stat_value

        # Apply force screen from module
        if mod_def.fdr_provided is not None:
            stats["fdr_max"] = max(stats["fdr_max"], mod_def.fdr_provided)
            if stats["force_screen_type"] == "none":
                stats["force_screen_type"] = "standard"

        # Add traits from module
        traits.extend(mod_def.grants_traits)

        # Add weapon from module (if it provides one)
        if mod_def.weapon_ref:
            wpn_def = _get_weapon_from_catalog(session, mod_def.weapon_ref)
            weapons.append(ResolvedWeapon(
                weapon_id=wpn_def.weapon_id,
                name=wpn_def.name,
                damage=wpn_def.damage,
                acc=wpn_def.acc,
                range=wpn_def.range,
                rof=wpn_def.rof,
                rcl=wpn_def.rcl,
                shots=wpn_def.shots,
                ewt=wpn_def.ewt,
                weapon_type=wpn_def.weapon_type,
                damage_type=wpn_def.damage_type,
                armor_divisor=wpn_def.armor_divisor,
                mount=slot_id,  # Use the slot as mount info
                linked_count=1,
                arc="all",  # Modules are typically turreted
                notes=f"From module: {mod_def.name}",
            ))

    # --- Step 3: Apply active mode overrides ---
    if instance.active_mode != "standard" and instance.active_mode in template.modes:
        mode_overrides = template.modes[instance.active_mode]
        for stat_key, stat_value in mode_overrides.items():
            if stat_key in stats:
                stats[stat_key] = stat_value

    # --- Step 4: Apply system damage penalties ---
    system_statuses = {
        row.system_type: row.status
        for row in session.query(SystemStatusRow).filter_by(
            instance_id=instance_id
        ).all()
    }

    # Propulsion
    prop_status = system_statuses.get("propulsion", "operational")
    if prop_status == "disabled":
        stats["top_speed"] = stats["top_speed"] // 2
    elif prop_status == "destroyed":
        stats["top_speed"] = 0
        stats["accel"] = 0

    # Controls
    ctrl_status = system_statuses.get("controls", "operational")
    if ctrl_status == "disabled":
        stats["hnd"] -= 2

    # Power
    power_status = system_statuses.get("power", "operational")
    half_power = power_status == "disabled"
    no_power = power_status == "destroyed"

    # --- Step 5: Resolve weapons from template mounts ---
    for mount in template.weapons:
        wpn_def = _get_weapon_from_catalog(session, mount.weapon_ref)
        weapons.append(ResolvedWeapon(
            weapon_id=wpn_def.weapon_id,
            name=wpn_def.name,
            damage=wpn_def.damage,
            acc=wpn_def.acc,
            range=wpn_def.range,
            rof=wpn_def.rof,
            rcl=wpn_def.rcl,
            shots=wpn_def.shots,
            ewt=wpn_def.ewt,
            weapon_type=wpn_def.weapon_type,
            damage_type=wpn_def.damage_type,
            armor_divisor=wpn_def.armor_divisor,
            mount=mount.mount,
            linked_count=mount.linked_count,
            arc=mount.arc,
            notes=mount.notes,
        ))

    # Add custom weapons
    custom_weapons_json = json.loads(instance.custom_weapons)
    for cwpn in custom_weapons_json:
        weapons.append(ResolvedWeapon(
            weapon_id=cwpn["weapon_id"],
            name=cwpn["name"],
            damage=cwpn["damage"],
            acc=cwpn["acc"],
            range=cwpn["range"],
            rof=cwpn["rof"],
            rcl=cwpn["rcl"],
            shots=cwpn["shots"],
            ewt=cwpn["ewt"],
            weapon_type=cwpn["weapon_type"],
            damage_type=cwpn["damage_type"],
            armor_divisor=cwpn.get("armor_divisor"),
            mount="custom",
            linked_count=1,
            arc="all",
            notes=cwpn.get("notes", ""),
        ))

    # --- Step 6: Determine faction from controller ---
    faction = "uncontrolled"
    if instance.controller_id:
        controller = session.query(ControllerRow).filter_by(
            id=instance.controller_id
        ).first()
        if controller:
            faction = controller.faction

    return EffectiveStatBlock(
        template_id=template.template_id,
        instance_id=str(instance.instance_id),
        display_name=instance.display_name,
        faction=faction,
        st_hp=stats["st_hp"],
        ht=stats["ht"],
        hnd=stats["hnd"],
        sr=stats["sr"],
        accel=stats["accel"],
        top_speed=stats["top_speed"],
        stall_speed=stats["stall_speed"],
        dr_front=stats["dr_front"],
        dr_rear=stats["dr_rear"],
        dr_left=stats["dr_left"],
        dr_right=stats["dr_right"],
        dr_top=stats["dr_top"],
        dr_bottom=stats["dr_bottom"],
        dr_material=stats["dr_material"],
        fdr_max=stats["fdr_max"],
        force_screen_type=stats["force_screen_type"],
        current_fdr=instance.current_fdr,
        ecm_rating=stats["ecm_rating"],
        targeting_bonus=stats["targeting_bonus"],
        ultrascanner_range=stats["ultrascanner_range"],
        current_hp=instance.current_hp,
        wound_level=instance.wound_level,
        active_mode=instance.active_mode,
        is_disabled=instance.is_disabled,
        is_destroyed=instance.is_destroyed,
        half_power=half_power,
        no_power=no_power,
        traits=traits,
        weapons=weapons,
    )


# ---------------------------------------------------------------------------
# Mode management
# ---------------------------------------------------------------------------

def set_mode(session: Session, instance_id: str, mode_name: str) -> None:
    """
    Set the active mode on a ship instance.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        mode_name: Mode name, or "standard" for default.

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
        InvalidModeError: If the mode name isn't valid for this template.
    """
    instance = _get_instance(session, instance_id)
    template = _get_template(session, instance.template_id)

    if mode_name != "standard" and mode_name not in template.modes:
        valid_modes = ["standard"] + list(template.modes.keys())
        raise InvalidModeError(
            f"Invalid mode '{mode_name}' for {template.template_id}. "
            f"Valid modes: {valid_modes}"
        )

    instance.active_mode = mode_name
    session.flush()


# ---------------------------------------------------------------------------
# Damage
# ---------------------------------------------------------------------------

def apply_damage(session: Session, instance_id: str, hp_damage: int) -> None:
    """
    Apply damage to a ship instance.

    Updates current_hp and determines wound_level based on the damage
    amount relative to the template's max HP. Wound level is per-hit,
    not cumulative.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        hp_damage: Amount of HP damage from this hit.

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
    """
    instance = _get_instance(session, instance_id)
    template = _get_template(session, instance.template_id)

    # Reduce HP
    instance.current_hp = max(0, instance.current_hp - hp_damage)

    # Determine wound level from this single hit
    wound_level = _compute_wound_level(hp_damage, template.attributes.st_hp)

    # Wound level only escalates, never downgrades from accumulation
    # (But since each test spawns fresh, this mainly matters for real gameplay)
    wound_severity = {
        "none": 0, "scratch": 1, "minor": 2, "major": 3,
        "crippling": 4, "mortal": 5, "lethal": 6,
    }
    current_severity = wound_severity.get(instance.wound_level, 0)
    new_severity = wound_severity.get(wound_level, 0)

    if new_severity > current_severity:
        instance.wound_level = wound_level

    if wound_level == "lethal":
        instance.is_destroyed = True

    session.flush()


def apply_fdr_damage(session: Session, instance_id: str, damage: int) -> int:
    """
    Apply damage to a ship's force screen.

    Reduces current_fdr by the damage amount. If damage exceeds
    remaining fdr, the excess penetrates through.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        damage: Amount of damage hitting the force screen.

    Returns:
        The amount of damage that penetrated through (excess beyond fdr).

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
    """
    instance = _get_instance(session, instance_id)

    absorbed = min(damage, instance.current_fdr)
    penetrating = damage - absorbed
    instance.current_fdr = instance.current_fdr - absorbed

    session.flush()
    return penetrating


def reset_fdr(session: Session, instance_id: str) -> None:
    """
    Reset force screen DR to maximum.

    Called by M1 at the start of each turn per force screen regen rules.
    Restores current_fdr to the template's fdr_max (or module-provided max).

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
    """
    instance = _get_instance(session, instance_id)
    template = _get_template(session, instance.template_id)

    # Determine max fDR (template base or module-provided)
    fdr_max = template.defense.fdr_max

    installed = json.loads(instance.installed_modules)
    for slot_id, mod_id in installed.items():
        mod_def = _get_module_from_catalog(session, mod_id)
        if mod_def and mod_def.fdr_provided is not None:
            fdr_max = max(fdr_max, mod_def.fdr_provided)

    instance.current_fdr = fdr_max
    session.flush()


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

def update_system_status(
    session: Session,
    instance_id: str,
    system_type: str,
    new_status: str,
) -> None:
    """
    Update the status of a specific subsystem on a ship instance.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        system_type: One of the valid system types (e.g. "propulsion").
        new_status: "operational", "disabled", or "destroyed".

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
        InvalidSystemTypeError: If system_type is not valid.
        InvalidStatusError: If new_status is not valid.
    """
    if system_type not in SYSTEM_TYPES:
        raise InvalidSystemTypeError(
            f"Invalid system type '{system_type}'. "
            f"Valid types: {sorted(SYSTEM_TYPES)}"
        )
    if new_status not in SYSTEM_STATUSES:
        raise InvalidStatusError(
            f"Invalid status '{new_status}'. "
            f"Valid statuses: {sorted(SYSTEM_STATUSES)}"
        )

    # Ensure instance exists
    _get_instance(session, instance_id)

    row = session.query(SystemStatusRow).filter_by(
        instance_id=instance_id,
        system_type=system_type,
    ).first()

    if row is None:
        # Shouldn't happen if spawn_ship was called correctly, but be safe
        row = SystemStatusRow(
            instance_id=instance_id,
            system_type=system_type,
            status=new_status,
        )
        session.add(row)
    else:
        row.status = new_status

    session.flush()


# ---------------------------------------------------------------------------
# Module installation
# ---------------------------------------------------------------------------

def install_module(
    session: Session,
    instance_id: str,
    slot_id: str,
    module_id: str,
) -> None:
    """
    Install a module into a specific slot on a ship instance.

    Validates that the slot exists on the template and that the module's
    slot_type matches. Replaces any previously installed module in that slot.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        slot_id: The target slot ID (e.g. "main_weapon", "armor").
        module_id: The module to install (from the module catalog).

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
        SlotMismatchError: If the slot doesn't exist or types don't match.
    """
    instance = _get_instance(session, instance_id)
    template = _get_template(session, instance.template_id)

    # Find the slot in the template
    slot = None
    for s in template.module_slots:
        if s.slot_id == slot_id:
            slot = s
            break

    if slot is None:
        raise SlotMismatchError(
            f"Slot '{slot_id}' does not exist on template '{template.template_id}'. "
            f"Available slots: {[s.slot_id for s in template.module_slots]}"
        )

    # Validate module compatibility
    mod_def = _get_module_from_catalog(session, module_id)
    if mod_def is None:
        raise SlotMismatchError(f"Module '{module_id}' not found in catalog")

    if slot.slot_type != "any" and mod_def.slot_type != slot.slot_type:
        raise SlotMismatchError(
            f"Slot type mismatch: slot '{slot_id}' accepts '{slot.slot_type}' "
            f"but module '{module_id}' is type '{mod_def.slot_type}'"
        )

    # Update the installed_modules JSON
    installed = json.loads(instance.installed_modules)
    installed[slot_id] = module_id
    instance.installed_modules = json.dumps(installed)

    session.flush()


# ---------------------------------------------------------------------------
# Custom weapons
# ---------------------------------------------------------------------------

def add_custom_weapon(
    session: Session,
    instance_id: str,
    weapon_data: dict,
) -> None:
    """
    Graft a custom weapon onto a ship instance.

    The weapon is stored as a full inline definition on the instance,
    not in the shared weapon catalog. This supports one-off modifications
    without polluting the catalog.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        weapon_data: Dict with full weapon definition fields.

    Raises:
        InstanceNotFoundError: If the instance doesn't exist.
    """
    instance = _get_instance(session, instance_id)

    custom_list = json.loads(instance.custom_weapons)
    custom_list.append(weapon_data)
    instance.custom_weapons = json.dumps(custom_list)

    session.flush()
