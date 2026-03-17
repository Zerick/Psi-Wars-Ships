"""
Ship Template Catalog — Psi-Wars Web UI
========================================

Loads ship templates from JSON fixture files and provides:
  - Categorized catalog for the ship picker UI
  - Template-to-instance conversion with sensible defaults
  - Template lookup by template_id

This module is stateless — it loads templates on init and serves
them on request. It has no dependency on SessionManager or any
other module.

Usage:
    catalog = ShipCatalog(templates_dir=Path("ship_templates"))
    catalog.load()

    # Get the full categorized catalog for the UI picker
    picker_data = catalog.get_catalog()

    # Create a ship instance from a template
    ship = catalog.create_ship_from_template("wildcat_v1")

Modification guide:
    - To change categories: edit CATEGORY_DEFINITIONS
    - To change default pilot: edit DEFAULT_PILOT
    - To change what fields appear in the picker summary: edit _summarize_template()
    - To add a new template source: add to load()
    - To change ship_id generation: edit create_ship_from_template()

Dependencies: json (stdlib), pathlib (stdlib), logging (stdlib)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default pilot stats applied to every newly created ship instance.
# These represent a generic NPC crewmember with all skills at 12.
DEFAULT_PILOT = {
    "name": "NPC Pilot",
    "piloting_skill": 12,
    "gunnery_skill": 12,
    "basic_speed": 6.0,
    "is_ace_pilot": False,
    "luck_level": "none",
    "current_fp": 10,
    "max_fp": 10,
}

# Default faction for newly created ships.
DEFAULT_FACTION = "NPC Hostiles"

# Ship categories for the picker UI.
# Each category has a label and a filter function that tests
# whether a template belongs to that category.
#
# Order matters — templates are assigned to the first matching
# category. The final "Specialty/Civilian" category catches
# everything else.
#
# To add a new category, insert it before the catch-all.
CATEGORY_DEFINITIONS = [
    {
        "label": "FIGHTERS",
        "description": "Small, fast combat craft (SM +4 to +5)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("fighter",)
            and t.get("sm", 0) <= 5
        ),
    },
    {
        "label": "INTERCEPTORS",
        "description": "High-speed pursuit craft (SM +4 to +5)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("interceptor",)
            and t.get("sm", 0) <= 5
        ),
    },
    {
        "label": "STRIKERS",
        "description": "Heavy fighters and ground attack craft (SM +5 to +6)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("striker",)
        ),
    },
    {
        "label": "ASSAULT BOATS",
        "description": "Boarding and close assault craft",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("assault_boat", "assault boat")
        ),
    },
    {
        "label": "CORVETTES",
        "description": "Light warships (SM +7 to +8)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("corvette",)
        ),
    },
    {
        "label": "FRIGATES",
        "description": "Medium warships (SM +8 to +9)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("frigate",)
        ),
    },
    {
        "label": "CRUISERS",
        "description": "Heavy warships (SM +9 to +10)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("cruiser", "heavy_cruiser",
                                                  "light_cruiser", "artillery_cruiser")
        ),
    },
    {
        "label": "CAPITAL SHIPS",
        "description": "Battleships and dreadnoughts (SM +10+)",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("battleship", "dreadnought",
                                                  "mobile_fortress")
        ),
    },
    {
        "label": "CARRIERS",
        "description": "Ships with hangar bays for fighters",
        "match": lambda t: (
            t.get("ship_class", "").lower() in ("carrier", "super_carrier",
                                                  "assault_carrier", "battle_carrier")
        ),
    },
    {
        "label": "SPECIALTY / CIVILIAN",
        "description": "Non-combat and specialty vessels",
        "match": lambda t: True,  # Catch-all — must be last
    },
]


# ---------------------------------------------------------------------------
# Ship Catalog
# ---------------------------------------------------------------------------

class ShipCatalog:
    """
    Manages the ship template library.

    Loads templates from a directory of JSON files at startup.
    Provides categorized access for the UI picker and conversion
    from template to ship instance with default values.

    Thread safety: Read-only after load(). Safe for concurrent access.
    """

    def __init__(self, templates_dir: Path | str | None = None):
        """
        Args:
            templates_dir: Directory containing ship template JSON files.
                           If None, templates must be loaded via load_from_list().
        """
        self.templates_dir = Path(templates_dir) if templates_dir else None
        self._templates: dict[str, dict] = {}  # template_id -> full template data
        self._catalog_cache: Optional[dict] = None  # Cached categorized catalog

    def load(self) -> int:
        """
        Load all templates from the templates directory.

        Scans for *.json files, parses each one, and indexes by
        template_id. Files with "invalid" in the name are skipped
        (test fixtures). Files that fail to parse are logged and skipped.

        Returns:
            Number of templates successfully loaded.
        """
        if not self.templates_dir or not self.templates_dir.exists():
            logger.warning("Templates directory not found: %s", self.templates_dir)
            return 0

        loaded = 0
        for filepath in sorted(self.templates_dir.glob("*.json")):
            if "invalid" in filepath.stem:
                continue

            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                template_id = data.get("template_id", filepath.stem)

                # Ensure template_id is set in the data
                data["template_id"] = template_id

                self._templates[template_id] = data
                loaded += 1

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load template %s: %s", filepath.name, e)

        self._catalog_cache = None  # Invalidate cache
        logger.info("Loaded %d ship templates from %s", loaded, self.templates_dir)
        return loaded

    def load_from_list(self, templates: list[dict]) -> int:
        """
        Load templates from an in-memory list (for testing).

        Args:
            templates: List of template dicts, each with a "template_id" key.

        Returns:
            Number of templates loaded.
        """
        for data in templates:
            tid = data.get("template_id")
            if tid:
                self._templates[tid] = data

        self._catalog_cache = None
        return len(templates)

    def get_template(self, template_id: str) -> Optional[dict]:
        """
        Get a single template by ID.

        Returns a copy so callers can't mutate the catalog.
        """
        template = self._templates.get(template_id)
        if template:
            return json.loads(json.dumps(template))  # Deep copy via JSON round-trip
        return None

    def get_all_template_ids(self) -> list[str]:
        """Get a sorted list of all template IDs."""
        return sorted(self._templates.keys())

    def get_catalog(self) -> dict:
        """
        Get the full categorized catalog for the UI picker.

        Returns a dict with:
            {
                "categories": [
                    {
                        "label": "FIGHTERS",
                        "description": "Small, fast combat craft",
                        "ships": [
                            { "template_id": "javelin_v1", "name": "Javelin Class Fighter",
                              "sm": 4, "ship_class": "fighter", "st_hp": 80, ... }
                        ]
                    },
                    ...
                ]
            }

        Categories with no matching ships are omitted.
        Templates are assigned to the first matching category.
        """
        if self._catalog_cache is not None:
            return self._catalog_cache

        # Assign each template to a category
        assigned: set[str] = set()
        categories = []

        for cat_def in CATEGORY_DEFINITIONS:
            ships = []
            for tid, template in sorted(self._templates.items()):
                if tid in assigned:
                    continue
                if cat_def["match"](template):
                    ships.append(self._summarize_template(template))
                    assigned.add(tid)

            if ships:
                categories.append({
                    "label": cat_def["label"],
                    "description": cat_def.get("description", ""),
                    "ships": ships,
                })

        self._catalog_cache = {"categories": categories}
        return self._catalog_cache

    def create_ship_from_template(
        self,
        template_id: str,
        ship_id: str = "",
    ) -> Optional[dict]:
        """
        Create a new ship instance from a template.

        Copies all template stats and applies default values for
        runtime fields (pilot, faction, control, target, assignment).

        Args:
            template_id: The template to instantiate.
            ship_id:     Optional ship_id. Auto-generated if empty.

        Returns:
            A complete ship data dict ready for the session, or None
            if the template_id is not found.
        """
        template = self.get_template(template_id)
        if not template:
            return None

        # Start with the full template data
        ship = template

        # Set/override runtime fields
        if ship_id:
            ship["ship_id"] = ship_id
        elif not ship.get("ship_id"):
            ship["ship_id"] = f"ship_{template_id}_{id(ship)}"

        # Display name defaults to the template name
        if not ship.get("display_name"):
            ship["display_name"] = ship.get("name", template_id)

        # Apply defaults for fields that aren't in the template
        ship.setdefault("faction", DEFAULT_FACTION)
        ship.setdefault("control", "npc")
        ship.setdefault("target_id", None)
        ship.setdefault("assigned_player", None)
        ship.setdefault("wound_level", "none")
        ship.setdefault("is_destroyed", False)

        # Set current_hp to max if not already set
        if "current_hp" not in ship:
            ship["current_hp"] = ship.get("st_hp", 0)

        # Set current_fdr to max if not already set
        if "current_fdr" not in ship:
            ship["current_fdr"] = ship.get("fdr_max", 0)

        # Apply default pilot
        ship["pilot"] = dict(DEFAULT_PILOT)

        # Initialize system status
        ship.setdefault("disabled_systems", [])
        ship.setdefault("destroyed_systems", [])
        ship.setdefault("emergency_power_reserves", 0)

        return ship

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_template(template: dict) -> dict:
        """
        Create a summary dict for the UI picker.

        Includes only the fields needed to display a template in the
        ship selection dropdown/grid. Keeps the payload small.
        """
        weapons = template.get("weapons", [])
        # Handle weapons that might be nested in the template format
        if not isinstance(weapons, list):
            weapons = []

        return {
            "template_id": template.get("template_id", ""),
            "name": template.get("name", template.get("display_name", "Unknown")),
            "sm": template.get("sm", 0),
            "ship_class": template.get("ship_class", "unknown"),
            "st_hp": template.get("st_hp", template.get("attributes", {}).get("st_hp", 0)),
            "top_speed": template.get("top_speed", template.get("mobility", {}).get("top_speed", 0)),
            "dr_front": template.get("dr_front", template.get("defense", {}).get("dr_front", 0)),
            "fdr_max": template.get("fdr_max", template.get("defense", {}).get("fdr_max", 0)),
            "weapon_count": len(weapons),
            "description": template.get("description", ""),
        }
