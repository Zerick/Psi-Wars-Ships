"""
Session snapshot export/import for M3 Data-Vault.

Snapshots capture the complete state of a combat session — all ship
instances, their system statuses, and associated controllers — as a
single JSON-serializable dict that can be saved and restored.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from m3_data_vault.db.tables import (
    ShipInstanceRow,
    SystemStatusRow,
    ControllerRow,
)

logger = logging.getLogger(__name__)


def export_session_snapshot(session: Session, session_id: str) -> dict:
    """
    Export all state for a combat session as a JSON-serializable dict.

    Captures:
    - All ship instances in the session
    - All system_status rows for those instances
    - All controllers referenced by those instances

    Args:
        session: Active SQLAlchemy session.
        session_id: The combat session identifier.

    Returns:
        A dict containing the full session state, suitable for
        json.dumps() and later import via import_session_snapshot().
    """
    # Fetch all instances in this session
    instances = session.query(ShipInstanceRow).filter_by(
        session_id=session_id
    ).all()

    # Collect all referenced controller IDs
    controller_ids = set()
    for inst in instances:
        if inst.controller_id:
            controller_ids.add(inst.controller_id)

    # Fetch controllers
    controllers = []
    for ctrl_id in controller_ids:
        ctrl = session.query(ControllerRow).filter_by(id=ctrl_id).first()
        if ctrl:
            controllers.append({
                "id": ctrl.id,
                "name": ctrl.name,
                "faction": ctrl.faction,
                "is_ace_pilot": ctrl.is_ace_pilot,
                "crew_skill": ctrl.crew_skill,
                "notes": ctrl.notes,
            })

    # Serialize instances and their system statuses
    instance_data = []
    for inst in instances:
        # Fetch system statuses for this instance
        statuses = session.query(SystemStatusRow).filter_by(
            instance_id=inst.instance_id
        ).all()

        status_list = [
            {
                "system_type": s.system_type,
                "status": s.status,
            }
            for s in statuses
        ]

        instance_data.append({
            "instance_id": inst.instance_id,
            "template_id": inst.template_id,
            "controller_id": inst.controller_id,
            "display_name": inst.display_name,
            "session_id": inst.session_id,
            "current_hp": inst.current_hp,
            "wound_level": inst.wound_level,
            "current_fdr": inst.current_fdr,
            "active_mode": inst.active_mode,
            "is_disabled": inst.is_disabled,
            "is_destroyed": inst.is_destroyed,
            "installed_modules": inst.installed_modules,  # Already JSON string
            "custom_weapons": inst.custom_weapons,        # Already JSON string
            "system_statuses": status_list,
        })

    snapshot = {
        "session_id": session_id,
        "controllers": controllers,
        "instances": instance_data,
    }

    logger.info(
        "Exported session '%s': %d instances, %d controllers",
        session_id, len(instance_data), len(controllers),
    )

    return snapshot


def import_session_snapshot(session: Session, snapshot: dict) -> str:
    """
    Import a previously exported session snapshot into the database.

    Recreates all controllers, ship instances, and system statuses
    from the snapshot data. Templates, weapons, and modules must
    already exist in the database.

    Args:
        session: Active SQLAlchemy session.
        snapshot: Dict from a previous export_session_snapshot() call.

    Returns:
        The session_id of the imported session.
    """
    session_id = snapshot["session_id"]

    # Import controllers (skip if they already exist)
    for ctrl_data in snapshot.get("controllers", []):
        existing = session.query(ControllerRow).filter_by(
            id=ctrl_data["id"]
        ).first()

        if existing is None:
            ctrl = ControllerRow(
                id=ctrl_data["id"],
                name=ctrl_data["name"],
                faction=ctrl_data["faction"],
                is_ace_pilot=ctrl_data.get("is_ace_pilot", False),
                crew_skill=ctrl_data.get("crew_skill", 12),
                notes=ctrl_data.get("notes", ""),
            )
            session.add(ctrl)

    session.flush()

    # Import ship instances and their system statuses
    for inst_data in snapshot.get("instances", []):
        instance = ShipInstanceRow(
            instance_id=inst_data["instance_id"],
            template_id=inst_data["template_id"],
            controller_id=inst_data.get("controller_id"),
            display_name=inst_data["display_name"],
            session_id=inst_data["session_id"],
            current_hp=inst_data["current_hp"],
            wound_level=inst_data.get("wound_level", "none"),
            current_fdr=inst_data.get("current_fdr", 0),
            active_mode=inst_data.get("active_mode", "standard"),
            is_disabled=inst_data.get("is_disabled", False),
            is_destroyed=inst_data.get("is_destroyed", False),
            installed_modules=inst_data.get("installed_modules", "{}"),
            custom_weapons=inst_data.get("custom_weapons", "[]"),
        )
        session.add(instance)
        session.flush()

        # Import system statuses
        for status_data in inst_data.get("system_statuses", []):
            status = SystemStatusRow(
                instance_id=inst_data["instance_id"],
                system_type=status_data["system_type"],
                status=status_data["status"],
            )
            session.add(status)

    session.flush()

    logger.info(
        "Imported session '%s': %d instances, %d controllers",
        session_id,
        len(snapshot.get("instances", [])),
        len(snapshot.get("controllers", [])),
    )

    return session_id
