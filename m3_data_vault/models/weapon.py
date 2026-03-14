"""
WeaponDefinition: Pydantic model for the shared weapon catalog.

Each weapon is defined once in the catalog and referenced by weapon_id
from ship templates and module definitions.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class WeaponDefinition(BaseModel):
    """
    A weapon definition from the shared weapon catalog.

    Weapons are defined as individual JSON files and referenced by ID
    from ship templates (via ShipWeaponMount.weapon_ref) and modules
    (via ModuleDefinition.weapon_ref).
    """
    weapon_id: str = Field(..., min_length=1, description="Unique weapon identifier")
    name: str = Field(..., min_length=1, description="Display name")
    damage: str = Field(..., min_length=1, description="GURPS damage string, e.g. '6d×5(5) burn'")
    acc: int = Field(..., description="Accuracy")
    range: str = Field(..., description="Range string, e.g. '2700/8000' or '1 mi/3 mi'")
    rof: str = Field(..., description="Rate of fire as string, e.g. '3', '1/3', '20'")
    rcl: int = Field(..., description="Recoil")
    shots: str = Field(..., description="Ammo string, e.g. '200/Fp', 'NA', '15/2F'")
    ewt: str = Field(..., description="Emplacement weight, e.g. '1000', '500t'")
    st_requirement: str = Field(..., description="ST requirement, e.g. '75M', 'M'")
    bulk: str = Field(..., description="Bulk value, e.g. '-10'")
    weapon_type: str = Field(..., description="Category: beam, plasma, missile, torpedo, flak, tractor, etc.")
    damage_type: str = Field(..., description="Damage type: burn, burn_ex, cut_inc, cr_ex, etc.")
    armor_divisor: Optional[str] = Field(None, description="Armor divisor, e.g. '(5)', '(10)'. None = no divisor.")
    notes: str = Field("", description="Freeform rules text")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    version: str = Field("1.0.0", description="Semver version string")

    model_config = {"extra": "forbid"}
