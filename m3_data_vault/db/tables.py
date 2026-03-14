"""
SQLAlchemy table definitions for M3 Data-Vault.

Tables:
- ship_templates: Validated ship blueprints (JSON blob storage)
- weapon_catalog: Shared weapon definitions
- module_catalog: Shared module definitions
- controllers: Players/NPCs who control ships
- ship_instances: Live ship state in combat sessions
- system_status: Per-instance subsystem damage tracking
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all M3 SQLAlchemy models."""
    pass


def _uuid_str() -> str:
    """Generate a UUID4 as a string for use as primary key."""
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Catalog tables (read-only blueprints)
# ---------------------------------------------------------------------------

class ShipTemplateRow(Base):
    """
    Stores validated ship template data.
    The full JSON is stored as a blob for flexible deserialization.
    """
    __tablename__ = "ship_templates"

    template_id = Column(String, primary_key=True)
    version = Column(String, nullable=False)
    name = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_modified_at = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, nullable=False, default=_now_utc)

    def __repr__(self) -> str:
        return f"<ShipTemplate {self.template_id} v{self.version}>"


class WeaponCatalogRow(Base):
    """Stores validated weapon definitions from the shared catalog."""
    __tablename__ = "weapon_catalog"

    weapon_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)
    ingested_at = Column(DateTime, nullable=False, default=_now_utc)

    def __repr__(self) -> str:
        return f"<WeaponCatalog {self.weapon_id}>"


class ModuleCatalogRow(Base):
    """Stores validated module definitions from the shared catalog."""
    __tablename__ = "module_catalog"

    module_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)
    ingested_at = Column(DateTime, nullable=False, default=_now_utc)

    def __repr__(self) -> str:
        return f"<ModuleCatalog {self.module_id}>"


# ---------------------------------------------------------------------------
# Controller table
# ---------------------------------------------------------------------------

class ControllerRow(Base):
    """
    Represents a player, NPC, or AI entity that can control ships.
    Lightweight stub — full character stats belong to a future module.
    """
    __tablename__ = "controllers"

    id = Column(String, primary_key=True, default=_uuid_str)
    name = Column(String, nullable=False)
    faction = Column(String, nullable=False)
    is_ace_pilot = Column(Boolean, nullable=False, default=False)
    crew_skill = Column(Integer, nullable=False, default=12)
    notes = Column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<Controller {self.name} ({self.faction})>"


# ---------------------------------------------------------------------------
# Instance tables (live session state)
# ---------------------------------------------------------------------------

class ShipInstanceRow(Base):
    """
    Live state of a ship in a combat session.
    Created by spawning from a template.
    """
    __tablename__ = "ship_instances"

    instance_id = Column(String, primary_key=True, default=_uuid_str)
    template_id = Column(String, ForeignKey("ship_templates.template_id"), nullable=False)
    controller_id = Column(String, ForeignKey("controllers.id"), nullable=True)
    display_name = Column(String, nullable=False)
    session_id = Column(String, nullable=False, index=True)

    # State fields
    current_hp = Column(Integer, nullable=False)
    wound_level = Column(String, nullable=False, default="none")
    current_fdr = Column(Integer, nullable=False, default=0)
    active_mode = Column(String, nullable=False, default="standard")
    is_disabled = Column(Boolean, nullable=False, default=False)
    is_destroyed = Column(Boolean, nullable=False, default=False)

    # Module loadout and custom weapons (JSON blobs)
    installed_modules = Column(Text, nullable=False, default="{}")
    custom_weapons = Column(Text, nullable=False, default="[]")

    # Relationships
    system_statuses = relationship("SystemStatusRow", back_populates="ship_instance",
                                   cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ShipInstance {self.display_name} ({self.template_id})>"


class SystemStatusRow(Base):
    """
    Tracks damage to individual ship subsystems.
    One row per system type per ship instance.
    """
    __tablename__ = "system_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String, ForeignKey("ship_instances.instance_id"), nullable=False)
    system_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="operational")

    # Relationship back to parent
    ship_instance = relationship("ShipInstanceRow", back_populates="system_statuses")

    __table_args__ = (
        UniqueConstraint("instance_id", "system_type", name="uq_instance_system"),
    )

    def __repr__(self) -> str:
        return f"<SystemStatus {self.system_type}={self.status}>"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All valid system types for system_status rows
SYSTEM_TYPES = frozenset({
    "fuel", "habitat", "propulsion", "cargo_hangar", "equipment",
    "power", "weaponry", "armor", "controls",
})

# All valid system statuses
SYSTEM_STATUSES = frozenset({"operational", "disabled", "destroyed"})

# Wound level thresholds (percentage of max HP)
WOUND_THRESHOLDS = [
    (5.0, "lethal"),      # >= 500%
    (2.0, "mortal"),      # >= 200%
    (1.0, "crippling"),   # >= 100%
    (0.5, "major"),       # >= 50%
    (0.1, "minor"),       # >= 10%
    (0.0, "scratch"),     # > 0% (any damage below 10%)
]
