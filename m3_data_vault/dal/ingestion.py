"""
Ingestion pipeline for M3 Data-Vault.

Handles reading JSON files, validating via Pydantic, computing hashes,
and upserting into the database. Provides both single-file ingestion
and directory-level sync with hash-based change detection.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Type

from pydantic import BaseModel
from sqlalchemy.orm import Session

from m3_data_vault.db.tables import (
    ShipTemplateRow,
    WeaponCatalogRow,
    ModuleCatalogRow,
)
from m3_data_vault.models.template import ShipTemplate
from m3_data_vault.models.weapon import WeaponDefinition
from m3_data_vault.models.module import ModuleDefinition

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    """Result of a sync_all_* operation."""
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)


def _compute_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def _file_mtime(filepath: Path) -> datetime:
    """Get file modification time as UTC datetime."""
    return datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)


# ---------------------------------------------------------------------------
# Ship template ingestion
# ---------------------------------------------------------------------------

def ingest_template(session: Session, json_filepath: Path) -> str:
    """
    Read a ship template JSON file, validate it, and upsert into the database.

    Args:
        session: Active SQLAlchemy session.
        json_filepath: Path to the ship template JSON file.

    Returns:
        The template_id of the ingested template.
    """
    filepath = Path(json_filepath)
    file_hash = _compute_file_hash(filepath)

    # Check if unchanged
    existing = session.query(ShipTemplateRow).filter_by(
        template_id=None  # Placeholder — we need to read the file to get the ID
    ).first()

    # Read and validate
    raw_text = filepath.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    template = ShipTemplate(**data)

    # Check if this template already exists with the same hash
    existing = session.query(ShipTemplateRow).filter_by(
        template_id=template.template_id
    ).first()

    if existing is not None:
        if existing.file_hash == file_hash:
            logger.debug(
                "Template '%s' unchanged, skipping.", template.template_id
            )
            return template.template_id

        # Update existing record
        existing.version = template.version
        existing.name = template.name
        existing.data_json = template.model_dump_json()
        existing.file_hash = file_hash
        existing.file_modified_at = _file_mtime(filepath)
        existing.ingested_at = datetime.now(timezone.utc)
        logger.info(
            "Template '%s' updated to v%s (hash %s...)",
            template.template_id, template.version, file_hash[:12]
        )
    else:
        # Insert new record
        row = ShipTemplateRow(
            template_id=template.template_id,
            version=template.version,
            name=template.name,
            data_json=template.model_dump_json(),
            file_hash=file_hash,
            file_modified_at=_file_mtime(filepath),
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(row)
        logger.info(
            "Template '%s' ingested (v%s, hash %s...)",
            template.template_id, template.version, file_hash[:12]
        )

    return template.template_id


def sync_all_templates(session: Session, json_directory: Path) -> SyncReport:
    """
    Sync all ship template JSON files in a directory with the database.

    Only re-ingests files whose SHA-256 hash has changed.

    Args:
        session: Active SQLAlchemy session.
        json_directory: Path to directory containing ship JSON files.

    Returns:
        SyncReport with counts of added, updated, unchanged, errors.
    """
    return _sync_catalog(
        session=session,
        directory=json_directory,
        model_class=ShipTemplate,
        row_class=ShipTemplateRow,
        id_field="template_id",
        ingest_func=ingest_template,
    )


# ---------------------------------------------------------------------------
# Weapon catalog ingestion
# ---------------------------------------------------------------------------

def ingest_weapon(session: Session, json_filepath: Path) -> str:
    """
    Read a weapon JSON file, validate it, and upsert into the weapon catalog.

    Args:
        session: Active SQLAlchemy session.
        json_filepath: Path to the weapon JSON file.

    Returns:
        The weapon_id of the ingested weapon.
    """
    filepath = Path(json_filepath)
    file_hash = _compute_file_hash(filepath)

    raw_text = filepath.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    weapon = WeaponDefinition(**data)

    existing = session.query(WeaponCatalogRow).filter_by(
        weapon_id=weapon.weapon_id
    ).first()

    if existing is not None:
        if existing.file_hash == file_hash:
            return weapon.weapon_id

        existing.name = weapon.name
        existing.data_json = weapon.model_dump_json()
        existing.file_hash = file_hash
        existing.ingested_at = datetime.now(timezone.utc)
        logger.info("Weapon '%s' updated (hash %s...)", weapon.weapon_id, file_hash[:12])
    else:
        row = WeaponCatalogRow(
            weapon_id=weapon.weapon_id,
            name=weapon.name,
            data_json=weapon.model_dump_json(),
            file_hash=file_hash,
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(row)
        logger.info("Weapon '%s' ingested (hash %s...)", weapon.weapon_id, file_hash[:12])

    return weapon.weapon_id


def sync_all_weapons(session: Session, json_directory: Path) -> SyncReport:
    """Sync all weapon JSON files in a directory with the database."""
    return _sync_catalog(
        session=session,
        directory=json_directory,
        model_class=WeaponDefinition,
        row_class=WeaponCatalogRow,
        id_field="weapon_id",
        ingest_func=ingest_weapon,
    )


# ---------------------------------------------------------------------------
# Module catalog ingestion
# ---------------------------------------------------------------------------

def ingest_module(session: Session, json_filepath: Path) -> str:
    """
    Read a module JSON file, validate it, and upsert into the module catalog.

    Args:
        session: Active SQLAlchemy session.
        json_filepath: Path to the module JSON file.

    Returns:
        The module_id of the ingested module.
    """
    filepath = Path(json_filepath)
    file_hash = _compute_file_hash(filepath)

    raw_text = filepath.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    module = ModuleDefinition(**data)

    existing = session.query(ModuleCatalogRow).filter_by(
        module_id=module.module_id
    ).first()

    if existing is not None:
        if existing.file_hash == file_hash:
            return module.module_id

        existing.name = module.name
        existing.data_json = module.model_dump_json()
        existing.file_hash = file_hash
        existing.ingested_at = datetime.now(timezone.utc)
        logger.info("Module '%s' updated (hash %s...)", module.module_id, file_hash[:12])
    else:
        row = ModuleCatalogRow(
            module_id=module.module_id,
            name=module.name,
            data_json=module.model_dump_json(),
            file_hash=file_hash,
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(row)
        logger.info("Module '%s' ingested (hash %s...)", module.module_id, file_hash[:12])

    return module.module_id


def sync_all_modules(session: Session, json_directory: Path) -> SyncReport:
    """Sync all module JSON files in a directory with the database."""
    return _sync_catalog(
        session=session,
        directory=json_directory,
        model_class=ModuleDefinition,
        row_class=ModuleCatalogRow,
        id_field="module_id",
        ingest_func=ingest_module,
    )


# ---------------------------------------------------------------------------
# Generic sync logic
# ---------------------------------------------------------------------------

def _sync_catalog(
    session: Session,
    directory: Path,
    model_class: Type[BaseModel],
    row_class: type,
    id_field: str,
    ingest_func: callable,
) -> SyncReport:
    """
    Generic sync: scan a directory of JSON files and ingest any that changed.

    Uses the file hash to detect changes. Files whose hash matches the
    stored hash are skipped. New files are added, changed files are updated.

    Args:
        session: Active SQLAlchemy session.
        directory: Path to directory containing JSON files.
        model_class: Pydantic model class for validation.
        row_class: SQLAlchemy row class for DB lookups.
        id_field: Name of the primary key field (e.g. "template_id").
        ingest_func: The single-file ingest function to call.

    Returns:
        SyncReport with operation counts.
    """
    report = SyncReport()
    directory = Path(directory)

    # Build a map of existing hashes
    existing_rows = session.query(row_class).all()
    existing_hashes = {
        getattr(row, id_field): row.file_hash
        for row in existing_rows
    }

    for json_file in sorted(directory.glob("*.json")):
        try:
            file_hash = _compute_file_hash(json_file)

            # Read the file to get the ID
            data = json.loads(json_file.read_text(encoding="utf-8"))
            item_id = data.get(id_field)

            if item_id and item_id in existing_hashes:
                if existing_hashes[item_id] == file_hash:
                    report.unchanged += 1
                    continue
                else:
                    ingest_func(session, json_file)
                    report.updated += 1
            else:
                ingest_func(session, json_file)
                report.added += 1

        except Exception as e:
            report.errors += 1
            report.error_details.append(f"{json_file.name}: {e}")
            logger.error("Failed to sync %s: %s", json_file.name, e)

    return report
