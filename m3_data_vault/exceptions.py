"""
Custom exceptions for M3 Data-Vault.

These provide clear, specific error types rather than generic
ValueError/KeyError for callers to catch.
"""


class M3Error(Exception):
    """Base exception for all M3 errors."""
    pass


class TemplateNotFoundError(M3Error):
    """Raised when a ship template_id is not found in the database."""
    pass


class WeaponNotFoundError(M3Error):
    """Raised when a weapon_id is not found in the weapon catalog."""
    pass


class ModuleNotFoundError(M3Error):
    """Raised when a module_id is not found in the module catalog."""
    pass


class InstanceNotFoundError(M3Error):
    """Raised when a ship instance_id is not found."""
    pass


class InvalidModeError(ValueError):
    """Raised when an invalid mode name is set on a ship instance."""
    pass


class SlotMismatchError(ValueError):
    """Raised when a module's slot_type doesn't match the target slot."""
    pass


class InvalidSystemTypeError(ValueError):
    """Raised when an invalid system type is specified."""
    pass


class InvalidStatusError(ValueError):
    """Raised when an invalid system status is specified."""
    pass
