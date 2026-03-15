"""
Shared test fixture paths for M3 Data-Vault testing.

These constants can be imported by any test file without going
through conftest, avoiding import issues with importlib mode.
"""
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SHIPS_DIR = FIXTURES_DIR / "ships"
WEAPONS_DIR = FIXTURES_DIR / "weapons"
MODULES_DIR = FIXTURES_DIR / "modules"
