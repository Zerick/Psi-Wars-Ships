"""
Input handling for the Psi-Wars terminal UI.

ALL menus and prompts go through the ScreenBuffer. Nothing is printed
directly to stdout except through buf.draw(). This guarantees the
status bar stays at the top.

The pattern for every interactive function:
    1. Build the menu/prompt as a list of strings
    2. Call buf.set_action(lines)
    3. Call buf.draw()
    4. Read input
    5. Return result

Hotkeys (H, I, Q) are intercepted at every menu before number parsing.

Modification guide:
    - To add a new hotkey: add a check in menu_choice()
    - To change menu layout: modify the line-building in menu_choice()
    - To change help text: modify HELP_TEXT
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from psi_wars_ui.renderer import ScreenBuffer

from psi_wars_ui.display import Color, bold, dim, colorize, clear_screen


# Hotkey return codes
HOTKEY_HELP = -100
HOTKEY_INSPECT = -101
HOTKEY_QUIT = -102


def get_input(prompt: str = "> ") -> str:
    """Get a line of input. Handles EOF/Ctrl-C gracefully."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def menu_choice(
    title: str,
    options: list[str],
    buf: "ScreenBuffer",
    prompt: str = "Choose",
    allow_cancel: bool = True,
) -> Optional[int]:
    """
    Display a numbered menu inside the screen buffer and get input.

    The menu is rendered in the action area of the buffer. The status
    bar and combat log remain visible above it.

    Args:
        title: Menu title.
        options: List of option strings.
        buf: The ScreenBuffer instance (renders the full screen).
        prompt: Input prompt text.
        allow_cancel: Whether option 0 (Cancel) is shown.

    Returns:
        0-based index, None (cancel), or HOTKEY_* constant.
    """
    while True:
        # Build menu lines
        action_lines = [f" {bold(title)}"]
        for i, opt in enumerate(options):
            action_lines.append(f"   {Color.BRIGHT_CYAN}{i + 1}{Color.RESET}. {opt}")
        if allow_cancel:
            action_lines.append(f"   {dim('0. Cancel')}")
        action_lines.append(f"   {dim('[H]elp  [I]nspect  [Q]uit')}")
        action_lines.append("")  # Blank line before prompt

        # Draw full screen with menu in action area
        buf.set_action(action_lines)
        buf.draw()

        raw = get_input(f" {prompt} [1-{len(options)}]: ")

        # Hotkey interception
        if raw.lower() in ("h", "help"):
            return HOTKEY_HELP
        if raw.lower() in ("i", "inspect"):
            return HOTKEY_INSPECT
        if raw.lower() in ("q", "quit"):
            return HOTKEY_QUIT

        if raw == "0" and allow_cancel:
            return None

        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice - 1
        except ValueError:
            pass

        # Invalid input — show error and loop
        action_lines.append(colorize(f"  Invalid. Enter 1-{len(options)}, or H/I/Q.", Color.RED))
        buf.set_action(action_lines)
        buf.draw()
        get_input(f" {dim('Press Enter...')}")


def menu_choice_simple(
    title: str,
    options: list[str],
    prompt: str = "Choose",
) -> Optional[int]:
    """
    Simple menu for setup phase (no screen buffer needed).

    Returns 0-based index or None.
    """
    print(f"\n {bold(title)}")
    for i, opt in enumerate(options):
        print(f"   {Color.BRIGHT_CYAN}{i + 1}{Color.RESET}. {opt}")

    while True:
        raw = get_input(f" {prompt} [1-{len(options)}]: ")
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice - 1
        except ValueError:
            pass
        print(colorize(f"  Invalid. Enter 1-{len(options)}.", Color.RED))


def yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    suffix = "(Y/n)" if default else "(y/N)"
    raw = get_input(f" {prompt} {suffix}: ")
    if not raw:
        return default
    return raw.lower().startswith("y")


def get_number(prompt: str, min_val: int = 0, max_val: int = 999,
               default: Optional[int] = None) -> int:
    """Get a numeric input within a range."""
    default_str = f" [{default}]" if default is not None else ""
    while True:
        raw = get_input(f" {prompt}{default_str}: ")
        if not raw and default is not None:
            return default
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
        except ValueError:
            pass
        print(colorize(f"  Enter a number from {min_val} to {max_val}.", Color.RED))


def get_text(prompt: str, default: str = "") -> str:
    """Get text input with optional default."""
    default_str = f" [{default}]" if default else ""
    raw = get_input(f" {prompt}{default_str}: ")
    return raw if raw else default


def pause(message: str = "Press Enter to continue...") -> None:
    """Pause and wait for Enter."""
    get_input(f" {dim(message)}")


def pause_with_buffer(buf: "ScreenBuffer", message: str = "Press Enter to continue...") -> None:
    """Pause with the screen buffer visible."""
    buf.set_action([f" {dim(message)}"])
    buf.draw()
    get_input(f" {dim('')}")


def pass_to_player(player_name: str) -> None:
    """Hot-seat handoff: clear screen, prompt for next player."""
    clear_screen()
    print(f"\n\n\n   {bold(f'Pass to: {player_name}')}")
    print(f"\n   {dim('(Previous player should look away)')}")
    pause("Press Enter when ready...")
    clear_screen()


# ---------------------------------------------------------------------------
# Help overlay
# ---------------------------------------------------------------------------

HELP_TEXT = """
┌──────────────────────────── HOTKEYS ─────────────────────────────┐
│                                                                  │
│   H  — Show this help                                           │
│   I  — Inspect a ship's full stat block                         │
│   Q  — Quit (with confirmation)                                 │
│                                                                  │
│   Type a letter at any numbered menu to use a hotkey.            │
│                                                                  │
│  ┌─ ADVANTAGE explained ─────────────────────────────────────┐  │
│  │ Winning a chase by 5+ lets you "gain advantage."          │  │
│  │ Advantage means superior position:                        │  │
│  │   • Your fixed weapons can fire (you choose facing)       │  │
│  │   • Next chase win: match speed (grants full accuracy!)   │  │
│  │   • Opponent must beat you in a chase to escape           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ FORMATION benefits ──────────────────────────────────────┐  │
│  │   • Any member can intercept attacks on allies            │  │
│  │   • Area jammer protection shared with all members        │  │
│  │   • Tactical coordination: +2 chase, +2 hit, or +1 dodge │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
"""


def show_help() -> None:
    """Display the help overlay."""
    clear_screen()
    print(colorize(HELP_TEXT, Color.BRIGHT_CYAN))
    pause()


def show_ship_inspection(ship_stats, pilot=None) -> None:
    """Display detailed stats for a single ship."""
    clear_screen()
    s = ship_stats
    name = getattr(s, "display_name", "Unknown")
    template = getattr(s, "template_id", "")

    print(f"\n {bold(f'═══ SHIP INSPECTION: {name} ({template}) ═══')}")
    print(f"   SM: {getattr(s, 'sm', '?')}    "
          f"HP: {getattr(s, 'current_hp', '?')}/{getattr(s, 'st_hp', '?')}    "
          f"HT: {getattr(s, 'ht', '?')}    "
          f"Hnd: {getattr(s, 'hnd', '?'):+d}    "
          f"SR: {getattr(s, 'sr', '?')}")
    print(f"   Move: {getattr(s, 'accel', '?')}/{getattr(s, 'top_speed', '?')}    "
          f"Stall: {getattr(s, 'stall_speed', 0) or 'VTOL'}")

    print(f"\n   {bold('DEFENSE')}")
    print(f"   DR — F:{getattr(s, 'dr_front', 0)} R:{getattr(s, 'dr_rear', 0)} "
          f"L:{getattr(s, 'dr_left', 0)} Ri:{getattr(s, 'dr_right', 0)} "
          f"T:{getattr(s, 'dr_top', 0)} B:{getattr(s, 'dr_bottom', 0)}")
    fdr = getattr(s, "fdr_max", 0)
    if fdr > 0:
        print(f"   fDR: {getattr(s, 'current_fdr', 0)}/{fdr} "
              f"({getattr(s, 'force_screen_type', 'none')})")

    print(f"\n   {bold('ELECTRONICS')}")
    print(f"   ECM: {getattr(s, 'ecm_rating', 0)}  "
          f"Scanner: {getattr(s, 'ultrascanner_range', 'none')}mi  "
          f"Targeting: +{getattr(s, 'targeting_bonus', 0)}  "
          f"ESM: {'Yes' if getattr(s, 'has_tactical_esm', False) else 'No'}  "
          f"Decoy: {'Yes' if getattr(s, 'has_decoy_launcher', False) else 'No'}")

    if pilot:
        print(f"\n   {bold('PILOT')}: {getattr(pilot, 'name', 'Unknown')}")
        print(f"   Piloting: {getattr(pilot, 'piloting_skill', '?')}  "
              f"Gunnery: {getattr(pilot, 'gunnery_skill', '?')}  "
              f"Speed: {getattr(pilot, 'basic_speed', '?')}")
        if getattr(pilot, "is_ace_pilot", False):
            print(f"   {colorize('★ ACE PILOT', Color.BRIGHT_YELLOW)}")

    traits = getattr(s, "traits", [])
    if traits:
        print(f"\n   {bold('TRAITS')}: {', '.join(traits)}")

    pause("\nPress Enter to return...")
