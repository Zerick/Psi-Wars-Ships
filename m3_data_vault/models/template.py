"""
ShipTemplate: Pydantic model for ship blueprint validation.

This is the primary validation model for ship JSON files.
It validates all fields, enforces constraints, and provides
typed access to the full ship data hierarchy.
"""
from __future__ import annotations

import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional


# Pattern for valid HT values: digits optionally followed by
# a single recognized suffix letter (f=fragile, x=explosive)
HT_PATTERN = re.compile(r"^[1-9]\d*[fx]?$")


class AttributesBlock(BaseModel):
    """Core ship attributes: HP, HT, handling, stability."""
    st_hp: int = Field(..., gt=0, description="Total Hit Points")
    ht: str = Field(..., description="Health value with optional suffix (e.g. '9f', '12', '8x')")
    hnd: int = Field(..., description="Handling modifier (may be negative for capital ships)")
    sr: int = Field(..., gt=0, description="Stability Rating")

    @field_validator("ht")
    @classmethod
    def validate_ht(cls, v: str) -> str:
        if not HT_PATTERN.match(v):
            raise ValueError(
                f"Invalid HT value '{v}'. Must be digits optionally followed by "
                f"'f' (fragile) or 'x' (explosive). Examples: '9f', '12', '8x'"
            )
        return v


class MobilityBlock(BaseModel):
    """Ship movement characteristics."""
    accel: int = Field(..., ge=0, description="Acceleration in Gs")
    top_speed: int = Field(..., ge=0, description="Top speed in mph")
    stall_speed: int = Field(0, ge=0, description="Stall speed. 0 = VTOL / no stall.")


class AfterburnerBlock(BaseModel):
    """Optional afterburner configuration."""
    accel: int = Field(..., ge=0, description="Afterburner acceleration")
    top_speed: int = Field(..., ge=0, description="Afterburner top speed")
    hnd_mod: int = Field(0, description="Handling modifier delta when afterburner active")
    fuel_multiplier: float = Field(4.0, gt=0, description="Fuel consumption multiplier")
    range_override: Optional[int] = Field(None, description="Reduced range in miles")
    is_high_g: bool = Field(False, description="If true, afterburner always counts as High-G")


class DefenseBlock(BaseModel):
    """Hull armor and force screen configuration."""
    dr_front: int = Field(..., ge=0, description="Hull DR from the front")
    dr_rear: int = Field(..., ge=0, description="Hull DR from the rear")
    dr_left: int = Field(..., ge=0, description="Hull DR from the left")
    dr_right: int = Field(..., ge=0, description="Hull DR from the right")
    dr_top: int = Field(..., ge=0, description="Hull DR from above")
    dr_bottom: int = Field(..., ge=0, description="Hull DR from below")
    dr_material: Optional[str] = Field(None, description="Material tag for special interactions")
    fdr_max: int = Field(0, ge=0, description="Maximum Force Screen DR. 0 = no screen.")
    force_screen_type: str = Field("none", description="'none', 'standard', or 'heavy'")

    @field_validator("force_screen_type")
    @classmethod
    def validate_force_screen_type(cls, v: str) -> str:
        valid = {"none", "standard", "heavy"}
        if v not in valid:
            raise ValueError(f"force_screen_type must be one of: {sorted(valid)}")
        return v


class ElectronicsBlock(BaseModel):
    """Ship electronics and sensor suite."""
    ultrascanner_range: Optional[int] = Field(None, ge=0, description="Scan range in miles")
    targeting_bonus: int = Field(0, description="Bonus from targeting computer with scan-lock")
    ecm_rating: int = Field(0, le=0, description="ECM penalty (negative number, e.g. -4)")
    night_vision: int = Field(0, ge=0, description="Night vision bonus")
    comm_range: Optional[int] = Field(None, ge=0, description="Radio range in miles")
    ftl_comm_range: Optional[int] = Field(None, ge=0, description="FTL comm range in parsecs")
    has_decoy_launcher: bool = Field(False)
    has_tactical_esm: bool = Field(False)
    has_distortion_scrambler: bool = Field(False)
    has_neural_interface: bool = Field(False)
    sensor_notes: str = Field("", description="Freeform notes for unusual electronics")


class LogisticsBlock(BaseModel):
    """Logistics, cost, and support data."""
    lwt: float = Field(0, ge=0, description="Loaded weight in tons")
    load: float = Field(0, ge=0, description="Cargo capacity in tons")
    range_miles: Optional[int] = Field(None, description="Range in miles. None = reactor-powered.")
    cost: str = Field("", description="Cost as string, e.g. '$2M'")
    hyperdrive_rating: Optional[int] = Field(None, ge=0)
    jump_capacity: Optional[int] = Field(None, ge=0)
    endurance: Optional[str] = Field(None, description="Freeform endurance string")
    signature_cost: Optional[int] = Field(None, ge=0, description="Character point cost")


class ShipWeaponMount(BaseModel):
    """A weapon mount on a ship, referencing the weapon catalog."""
    weapon_ref: str = Field(..., min_length=1, description="References weapon_id in weapon catalog")
    mount: str = Field(..., min_length=1, description="Mount type: fixed_front, turret, etc.")
    linked_count: int = Field(1, ge=1, description="Number of linked weapons")
    arc: str = Field("front", description="Firing arc: front, rear, all, etc.")
    notes: str = Field("", description="Ship-specific weapon notes")


class ModuleSlot(BaseModel):
    """A modular slot on a ship where modules can be installed."""
    slot_id: str = Field(..., min_length=1, description="Unique slot identifier within template")
    slot_type: str = Field(..., min_length=1, description="weapon, engine, armor, accessory, etc.")
    weight_class: str = Field("any", description="'light', 'heavy', or 'any'")
    max_weight: Optional[float] = Field(None, ge=0, description="Max module weight in lbs")
    notes: str = Field("", description="Freeform notes")


class CraftEntry(BaseModel):
    """An onboard craft carried by a capital ship or carrier."""
    template_ref: str = Field(..., min_length=1, description="References another ShipTemplate")
    count: int = Field(..., gt=0, description="Number carried")
    notes: str = Field("", description="Freeform notes")


class ShipTemplate(BaseModel):
    """
    The top-level ship blueprint model.

    Validates a complete ship JSON file. One JSON file per ship class.
    Ships reference weapons from the shared weapon catalog via weapon_ref,
    and define module slots for installable modules.
    """
    template_id: str = Field(..., min_length=1, description="Unique slug identifier")
    version: str = Field(..., min_length=1, description="Semver version string")
    name: str = Field(..., min_length=1, description="Display name")
    faction_origin: str = Field(..., min_length=1, description="Originating faction tag")
    sm: int = Field(..., description="Size Modifier")
    ship_class: str = Field(..., min_length=1, description="Classification tag")

    attributes: AttributesBlock
    mobility: MobilityBlock
    afterburner: Optional[AfterburnerBlock] = None
    defense: DefenseBlock
    electronics: ElectronicsBlock = Field(default_factory=ElectronicsBlock)

    occ_raw: str = Field("", description="Raw occupancy string")
    loc_raw: str = Field("", description="Raw location code string")

    logistics: LogisticsBlock = Field(default_factory=LogisticsBlock)
    traits: list[str] = Field(default_factory=list)

    # Modes: key = mode name, value = dict of stat overrides
    modes: dict[str, dict] = Field(default_factory=dict)

    # Weapon mounts referencing the shared weapon catalog
    weapons: list[ShipWeaponMount] = Field(default_factory=list)

    # Module slots for installable components
    module_slots: list[ModuleSlot] = Field(default_factory=list)

    # Onboard craft (carriers/capital ships)
    craft_complement: list[CraftEntry] = Field(default_factory=list)

    description: str = Field("", description="Freeform look-and-feel text")
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = Field(None)

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(
                f"template_id must be lowercase alphanumeric with underscores, got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def validate_module_slot_ids_unique(self) -> "ShipTemplate":
        """Ensure all module slot IDs are unique within the template."""
        slot_ids = [s.slot_id for s in self.module_slots]
        if len(slot_ids) != len(set(slot_ids)):
            dupes = [sid for sid in slot_ids if slot_ids.count(sid) > 1]
            raise ValueError(f"Duplicate module slot IDs: {set(dupes)}")
        return self

    model_config = {"extra": "ignore"}
