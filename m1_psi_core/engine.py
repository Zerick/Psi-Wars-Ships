"""
Top-level combat engine for M1 Psi-Core.

Orchestrates all subsystems to run a complete combat encounter
turn by turn. This is the primary entry point for the terminal UI
and future web interface.

This module will be built incrementally as the subsystems mature.
"""
from __future__ import annotations


class CombatEngine:
    """
    Orchestrates a full combat encounter.

    Manages the turn loop, delegates to subsystems, and emits events.
    """

    def __init__(self):
        pass  # Will be implemented after all subsystems are tested
