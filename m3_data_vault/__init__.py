"""
M3 Data-Vault: Persistence & Validation Layer

The Data-Vault manages read-only ship blueprints (Templates) and live,
session-specific ship state (Instances) for a GURPS Psi-Wars space
combat simulator.

M3 is strictly a data layer. It does not resolve game rules.
It validates, stores, retrieves, and calculates effective stat blocks.
"""

__version__ = "0.1.0"
