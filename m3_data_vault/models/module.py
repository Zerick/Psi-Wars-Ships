"""
ModuleDefinition: Pydantic model for the shared module catalog.

Modules are installable components (weapons, armor, accessories, engines, etc.)
that can be mounted in a ship's module slots to modify its stats.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# Valid slot types that a module can declare compatibility with
VALID_SLOT_TYPES = {
    "weapon", "engine", "armor", "accessory", "cargo",
    "fuel", "hardpoint", "electronics",
}

# Valid weight classes
VALID_WEIGHT_CLASSES = {"light", "heavy"}


class ModuleDefinition(BaseModel):
    """
    A module definition from the shared module catalog.

    Modules modify ship stats when installed in compatible slots.
    Some modules provide weapons (via weapon_ref to the weapon catalog),
    some provide force screens (via fdr_provided), and some grant
    special traits.
    """
    module_id: str = Field(..., min_length=1, description="Unique module identifier")
    name: str = Field(..., min_length=1, description="Display name")
    slot_type: str = Field(..., description="Compatible slot type")
    weight_class: str = Field(..., description="'light' or 'heavy'")
    weight_lbs: float = Field(..., ge=0, description="Module weight in pounds")
    cost: str = Field(..., description="Cost string, e.g. '$400,000'")
    stat_effects: Optional[dict] = Field(None, description="Stat overrides when installed")
    weapon_ref: Optional[str] = Field(None, description="Weapon catalog ID if module provides a weapon")
    grants_traits: list[str] = Field(default_factory=list, description="Traits granted when installed")
    fdr_provided: Optional[int] = Field(None, ge=0, description="Force screen DR provided, if any")
    notes: str = Field("", description="Freeform rules text")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    version: str = Field("1.0.0", description="Semver version string")

    @field_validator("slot_type")
    @classmethod
    def validate_slot_type(cls, v: str) -> str:
        if v not in VALID_SLOT_TYPES:
            raise ValueError(
                f"Invalid slot_type '{v}'. Must be one of: {sorted(VALID_SLOT_TYPES)}"
            )
        return v

    @field_validator("weight_class")
    @classmethod
    def validate_weight_class(cls, v: str) -> str:
        if v not in VALID_WEIGHT_CLASSES:
            raise ValueError(
                f"Invalid weight_class '{v}'. Must be one of: {sorted(VALID_WEIGHT_CLASSES)}"
            )
        return v

    model_config = {"extra": "forbid"}
