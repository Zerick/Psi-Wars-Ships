"""
Turn State Machine for Psi-Wars Combat.

This module decouples combat resolution from the UI. Instead of the
terminal game loop blocking on input(), the state machine advances
through discrete states, pausing whenever a player decision is needed.

Architecture:
    The TurnResolver holds the current combat state and a queue of
    pending decisions. The UI (terminal, web, or test harness) calls:

        1. resolver.begin_turn() → first state + prompt (if any)
        2. resolver.submit_decision(decision) → next state + prompt
        3. Repeat until state == TURN_COMPLETE

    Each state is a dict with:
        - "phase": which phase we're in
        - "status": what just happened (for display)
        - "prompt": what decision is needed (None if auto-advancing)
        - "prompt_type": "maneuver_choice", "chase_choice", "high_g", "luck", etc.
        - "options": list of valid choices
        - "context": any data the UI needs to render the current state

    The UI never calls engine functions directly. The state machine
    is the ONLY orchestrator of combat resolution.

States:
    AWAITING_DECLARATIONS   - Waiting for each ship's maneuver + intent
    RESOLVING_CHASE         - Chase contest being resolved (auto)
    CHASE_CHOICE_NEEDED     - Winner must choose advantage/range/match
    APPLYING_EMERGENCY_POWER - EP skill rolls being resolved (auto)
    RESOLVING_ATTACK        - Attack roll for current ship (auto)
    LUCK_ATTACK_OFFERED     - Attacker missed, Luck available
    LUCK_CRITICAL_OFFERED   - Opponent crit, defender's Luck available
    HIGH_G_OFFERED          - Defender can attempt High-G dodge
    RESOLVING_DEFENSE       - Defense roll (auto)
    LUCK_DEFENSE_OFFERED    - Dodge failed, Luck available
    RESOLVING_DAMAGE        - Damage pipeline (auto)
    FLESH_WOUND_OFFERED     - Major+ wound, Impulse available
    NEXT_ATTACKER           - Move to next ship's attack
    TURN_COMPLETE           - All phases done, cleanup applied

Usage:
    resolver = TurnResolver(session, dice)
    state = resolver.begin_turn()

    while state["phase"] != "TURN_COMPLETE":
        if state["prompt"]:
            # Show prompt to player, get their choice
            decision = get_player_input(state)
            state = resolver.submit_decision(decision)
        else:
            # Auto-advance (NPC decisions, dice rolls)
            state = resolver.advance()
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Any


@dataclass
class TurnState:
    """
    Immutable snapshot of the current turn resolution state.

    This is what gets sent to the UI. The UI renders based on this
    and sends back a decision when prompt is not None.
    """
    phase: str
    status: str = ""                    # What just happened (for combat log)
    prompt: Optional[str] = None        # Question for the player (None = auto)
    prompt_type: Optional[str] = None   # Type of decision needed
    options: list[str] = field(default_factory=list)  # Valid choices
    context: dict[str, Any] = field(default_factory=dict)  # Extra data for UI
    ship_id: Optional[str] = None       # Which ship this state is about
    combat_log_entries: list[dict] = field(default_factory=list)  # New log entries

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON transport."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Decision types (what the UI sends back)
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    """A player's response to a TurnState prompt."""
    decision_type: str      # Matches the prompt_type
    value: Any              # The chosen option
    ship_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> Decision:
        return cls(
            decision_type=d["decision_type"],
            value=d["value"],
            ship_id=d.get("ship_id"),
        )


# ---------------------------------------------------------------------------
# All valid phases
# ---------------------------------------------------------------------------

PHASES = [
    "AWAITING_DECLARATIONS",
    "RESOLVING_EMERGENCY_POWER",
    "RESOLVING_CHASE",
    "CHASE_CHOICE_NEEDED",
    "RESOLVING_ATTACK",
    "WEAPON_CHOICE_NEEDED",
    "DECEPTIVE_CHOICE_NEEDED",
    "LUCK_ATTACK_OFFERED",
    "LUCK_CRITICAL_OFFERED",
    "HIGH_G_OFFERED",
    "RESOLVING_DEFENSE",
    "LUCK_DEFENSE_OFFERED",
    "RESOLVING_DAMAGE",
    "FLESH_WOUND_OFFERED",
    "NEXT_ATTACKER",
    "TURN_COMPLETE",
]

PROMPT_TYPES = [
    "maneuver_choice",      # Choose maneuver + intent
    "emergency_power",      # Choose EP option + skill target
    "chase_choice",         # Choose advantage/range/match speed
    "weapon_choice",        # Choose which weapon to fire
    "deceptive_choice",     # Choose deceptive attack level
    "high_g_choice",        # Attempt High-G dodge? y/n
    "luck_reroll",          # Use Luck to reroll? y/n
    "flesh_wound",          # Use Impulse for Flesh Wound? y/n
]
