"""
Controller management for M3 Data-Vault.

Controllers represent players, NPCs, or AI entities that can fly ships.
A ship's apparent faction is always derived from its controller.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from m3_data_vault.db.tables import ControllerRow, ShipInstanceRow
from m3_data_vault.exceptions import InstanceNotFoundError


def create_controller(
    session: Session,
    name: str,
    faction: str,
    is_ace_pilot: bool = False,
    crew_skill: int = 12,
    notes: str = "",
) -> str:
    """
    Create a new controller and return its UUID (as string).

    Args:
        session: Active SQLAlchemy session.
        name: Display name for the controller.
        faction: Faction alignment tag (e.g. "empire", "rebel", "trader").
        is_ace_pilot: Whether this controller has the Ace Pilot advantage.
        crew_skill: Default crew skill level (used for capital ship crews).
        notes: Freeform notes.

    Returns:
        The controller's UUID as a string.
    """
    controller_id = str(uuid.uuid4())
    row = ControllerRow(
        id=controller_id,
        name=name,
        faction=faction,
        is_ace_pilot=is_ace_pilot,
        crew_skill=crew_skill,
        notes=notes,
    )
    session.add(row)
    session.flush()  # Ensure the row is visible within this transaction
    return controller_id


def get_controller(session: Session, controller_id: str) -> Optional[ControllerRow]:
    """
    Retrieve a controller by ID.

    Args:
        session: Active SQLAlchemy session.
        controller_id: The controller's UUID string.

    Returns:
        The ControllerRow, or None if not found.
    """
    return session.query(ControllerRow).filter_by(id=controller_id).first()


def transfer_control(
    session: Session,
    instance_id: str,
    new_controller_id: Optional[str],
) -> None:
    """
    Transfer control of a ship instance to a new controller.

    The ship's apparent faction alignment changes to match the new
    controller's faction. Setting new_controller_id to None makes
    the ship uncontrolled.

    Args:
        session: Active SQLAlchemy session.
        instance_id: The ship instance UUID string.
        new_controller_id: The new controller's UUID, or None for uncontrolled.

    Raises:
        InstanceNotFoundError: If the ship instance doesn't exist.
    """
    row = session.query(ShipInstanceRow).filter_by(
        instance_id=instance_id
    ).first()

    if row is None:
        raise InstanceNotFoundError(
            f"Ship instance '{instance_id}' not found"
        )

    row.controller_id = new_controller_id
    session.flush()
