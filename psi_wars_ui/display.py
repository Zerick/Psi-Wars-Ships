"""
ANSI color and display primitives for the terminal UI.

Provides color constants, text formatting helpers, and the
ScreenBuffer class for full-screen terminal rendering.
"""
from __future__ import annotations

import os
import sys


# ---------------------------------------------------------------------------
# ANSI escape codes
# ---------------------------------------------------------------------------

class Color:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Standard colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    # Screen control
    CLEAR_SCREEN = "\033[2J\033[H"
    CLEAR_LINE = "\033[2K"


# Faction color mapping
FACTION_COLORS = {
    "empire": Color.RED,
    "trader": Color.BLUE,
    "redjack": Color.YELLOW,
    "rath": Color.GREEN,
    "maradonian": Color.MAGENTA,
    "arc": Color.CYAN,
    "rebel": Color.BRIGHT_GREEN,
    "uncontrolled": Color.DIM,
}

# Wound level color mapping
WOUND_COLORS = {
    "none": Color.GREEN,
    "scratch": Color.GREEN,
    "minor": Color.YELLOW,
    "major": Color.BRIGHT_YELLOW,
    "crippling": Color.RED,
    "mortal": Color.BRIGHT_RED,
    "lethal": Color.BRIGHT_RED,
}

# Event type color mapping
EVENT_COLORS = {
    "chase": Color.CYAN,
    "attack": Color.YELLOW,
    "defense": Color.GREEN,
    "damage": Color.RED,
    "system_damage": Color.BRIGHT_RED,
    "force_screen": Color.BLUE,
    "electronic_warfare": Color.MAGENTA,
    "friendly_fire": Color.BRIGHT_YELLOW + Color.BG_RED,
    "critical_success": Color.BRIGHT_GREEN + Color.BOLD,
    "critical_failure": Color.BRIGHT_RED + Color.BOLD,
    "info": Color.WHITE,
    "turn": Color.BRIGHT_WHITE + Color.BOLD,
    "npc_reasoning": Color.DIM,
}


# ---------------------------------------------------------------------------
# Text formatting helpers
# ---------------------------------------------------------------------------

def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Color.RESET}"


def bold(text: str) -> str:
    """Make text bold."""
    return f"{Color.BOLD}{text}{Color.RESET}"


def dim(text: str) -> str:
    """Make text dim."""
    return f"{Color.DIM}{text}{Color.RESET}"


def faction_color(faction: str) -> str:
    """Get the ANSI color code for a faction."""
    return FACTION_COLORS.get(faction.lower(), Color.WHITE)


def wound_color(wound_level: str) -> str:
    """Get the ANSI color code for a wound level."""
    return WOUND_COLORS.get(wound_level, Color.WHITE)


def event_color(event_type: str) -> str:
    """Get the ANSI color code for an event type."""
    return EVENT_COLORS.get(event_type, Color.WHITE)


def colored_faction(faction: str) -> str:
    """Format a faction name with its color."""
    return colorize(faction.upper(), faction_color(faction))


def colored_wound(wound_level: str) -> str:
    """Format a wound level with its color."""
    return colorize(wound_level.capitalize(), wound_color(wound_level))


# ---------------------------------------------------------------------------
# Terminal utilities
# ---------------------------------------------------------------------------

def get_terminal_size() -> tuple[int, int]:
    """
    Get terminal dimensions (columns, lines).
    Falls back to 80x24 if detection fails.
    """
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except (ValueError, OSError):
        return 80, 24


def clear_screen() -> None:
    """Clear the terminal screen."""
    sys.stdout.write(Color.CLEAR_SCREEN)
    sys.stdout.flush()


def move_cursor(row: int, col: int) -> None:
    """Move cursor to a specific position (1-indexed)."""
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Horizontal rule
# ---------------------------------------------------------------------------

def horizontal_rule(width: int, char: str = "─") -> str:
    """Create a horizontal rule of the given width."""
    return char * width


def boxed_header(text: str, width: int) -> str:
    """Create a boxed header line."""
    padding = width - len(text) - 4
    left_pad = padding // 2
    right_pad = padding - left_pad
    return f"┌{'─' * left_pad} {bold(text)} {'─' * right_pad}┐"
