"""
ANSI color and display primitives for the Psi-Wars terminal UI.

This is the foundation layer. All other UI modules import from here.
No game logic lives in this file — only terminal rendering utilities.

Architecture note:
    display.py (this file) — colors, formatting, terminal control
    renderer.py — builds screen layout from game state
    input_handler.py — menus, prompts, hotkeys
    setup.py — game configuration flow
    game_loop.py — turn-by-turn combat execution
    __main__.py — entry point

Modification guide:
    - To add a new faction color: add to FACTION_COLORS dict
    - To change wound level colors: modify WOUND_COLORS dict
    - To add a new event color: add to EVENT_COLORS dict
    - Terminal size detection is in get_terminal_size()
"""
from __future__ import annotations

import os
import sys


# ---------------------------------------------------------------------------
# ANSI escape codes
# ---------------------------------------------------------------------------

class Color:
    """
    ANSI terminal color and formatting codes.

    Usage:
        print(f"{Color.RED}Error!{Color.RESET}")
        print(f"{Color.BOLD}{Color.GREEN}Success{Color.RESET}")
    """
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Standard foreground colors (dark)
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors (for alerts/warnings)
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    # Screen control sequences
    CLEAR_SCREEN = "\033[2J\033[H"  # Clear screen and move cursor to top-left
    CLEAR_LINE = "\033[2K"           # Clear current line


# ---------------------------------------------------------------------------
# Color mappings for game elements
# ---------------------------------------------------------------------------

# Maps faction name (lowercase) -> ANSI color code
# To add a new faction: add an entry here
FACTION_COLORS: dict[str, str] = {
    "empire": Color.RED,
    "imperial": Color.RED,
    "trader": Color.BLUE,
    "redjack": Color.YELLOW,
    "rath": Color.GREEN,
    "maradonian": Color.MAGENTA,
    "arc": Color.CYAN,
    "rebel": Color.BRIGHT_GREEN,
    "uncontrolled": Color.DIM,
}

# Maps wound level -> ANSI color code
# Severity increases from green to red
WOUND_COLORS: dict[str, str] = {
    "none": Color.GREEN,
    "scratch": Color.GREEN,
    "minor": Color.YELLOW,
    "major": Color.BRIGHT_YELLOW,
    "crippling": Color.RED,
    "mortal": Color.BRIGHT_RED,
    "lethal": Color.BRIGHT_RED,
}

# Maps combat event type -> ANSI color code
# Used by the combat log to color-code entries
EVENT_COLORS: dict[str, str] = {
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
    """Wrap text in ANSI color codes. Resets color after text."""
    return f"{color}{text}{Color.RESET}"


def bold(text: str) -> str:
    """Make text bold."""
    return f"{Color.BOLD}{text}{Color.RESET}"


def dim(text: str) -> str:
    """Make text dim/faded."""
    return f"{Color.DIM}{text}{Color.RESET}"


def faction_color(faction: str) -> str:
    """Look up the ANSI color code for a faction name."""
    return FACTION_COLORS.get(faction.lower(), Color.WHITE)


def wound_color(wound_level: str) -> str:
    """Look up the ANSI color code for a wound level."""
    return WOUND_COLORS.get(wound_level, Color.WHITE)


def event_color(event_type: str) -> str:
    """Look up the ANSI color code for a combat event type."""
    return EVENT_COLORS.get(event_type, Color.WHITE)


def colored_faction(faction: str) -> str:
    """Format a faction name in its faction color, uppercased."""
    return colorize(faction.upper(), faction_color(faction))


def colored_wound(wound_level: str) -> str:
    """Format a wound level in its severity color, capitalized."""
    return colorize(wound_level.capitalize(), wound_color(wound_level))


# ---------------------------------------------------------------------------
# Terminal utilities
# ---------------------------------------------------------------------------

def get_terminal_size() -> tuple[int, int]:
    """
    Get terminal dimensions as (columns, lines).

    Falls back to 80x24 if detection fails (e.g., piped output).
    """
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except (ValueError, OSError):
        return 80, 24


def clear_screen() -> None:
    """Clear the terminal screen and move cursor to top-left."""
    sys.stdout.write(Color.CLEAR_SCREEN)
    sys.stdout.flush()


def horizontal_rule(width: int, char: str = "─") -> str:
    """Create a horizontal rule string of the given width."""
    return char * width
