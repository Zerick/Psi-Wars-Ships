"""
Input handling for the terminal UI.

Provides menu display, numbered choice selection, and input
validation. All user interaction flows through these functions.
"""
from __future__ import annotations

import sys
from typing import Optional

from psi_wars_ui.display import Color, bold, dim, colorize, clear_screen


def get_input(prompt: str = "> ") -> str:
    """Get a line of input from the user."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def menu_choice(
    title: str,
    options: list[str],
    prompt: str = "Choose",
    allow_cancel: bool = True,
) -> Optional[int]:
    """
    Display a numbered menu and get the user's choice.

    Returns the 0-based index of the chosen option, or None if cancelled.
    """
    print(f"\n {bold(title)}")
    for i, option in enumerate(options):
        print(f"   {Color.BRIGHT_CYAN}{i + 1}{Color.RESET}. {option}")

    if allow_cancel:
        print(f"   {dim('0. Cancel')}")

    while True:
        raw = get_input(f" {prompt} [1-{len(options)}]: ")

        if raw.lower() in ("q", "quit"):
            return None
        if raw == "0" and allow_cancel:
            return None

        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice - 1
        except ValueError:
            pass

        print(colorize(f"  Invalid choice. Enter 1-{len(options)}.", Color.RED))


def yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    suffix = "(Y/n)" if default else "(y/N)"
    raw = get_input(f" {prompt} {suffix}: ")

    if not raw:
        return default
    return raw.lower().startswith("y")


def get_number(
    prompt: str,
    min_val: int = 0,
    max_val: int = 100,
    default: Optional[int] = None,
) -> int:
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
    """Get a text input with optional default."""
    default_str = f" [{default}]" if default else ""
    raw = get_input(f" {prompt}{default_str}: ")
    return raw if raw else default


def pause(message: str = "Press Enter to continue...") -> None:
    """Pause and wait for Enter."""
    get_input(f" {dim(message)}")


def pass_to_player(player_name: str) -> None:
    """
    Clear screen and prompt for hot-seat player handoff.

    Ensures the previous player's choices are not visible.
    """
    clear_screen()
    print(f"\n\n\n   {bold(f'Pass to: {player_name}')}")
    print(f"\n   {dim('(Previous player should look away)')}")
    pause("Press Enter when ready...")
    clear_screen()


# ---------------------------------------------------------------------------
# Help overlay
# ---------------------------------------------------------------------------

HELP_TEXT = """
┌─────────────────────────── HOTKEYS ───────────────────────────┐
│                                                               │
│   H  — Show/hide this help                                   │
│   I  — Inspect a ship's full stat block                      │
│   L  — View full combat log                                  │
│   U  — Undo last turn                                        │
│   Q  — Quit (with confirmation)                              │
│                                                               │
│   During setup:                                               │
│   G  — Toggle GM mode                                        │
│   M  — Toggle mook status on a ship                          │
│   A  — Add a ship mid-combat                                 │
│   R  — Remove a ship from combat                             │
│                                                               │
│   Formation reminders:                                        │
│   • Any member can intercept attacks on allies                │
│   • Area jammer protection shared with all members            │
│   • Tactical coordination: +2 chase, +2 hit, or +1 dodge     │
│                                                               │
└───────────────────────────────────────────────────────────────┘
"""


def show_help() -> None:
    """Display the help overlay."""
    print(colorize(HELP_TEXT, Color.BRIGHT_CYAN))
    pause()


# ---------------------------------------------------------------------------
# Ship inspection overlay
# ---------------------------------------------------------------------------

def show_ship_inspection(ship_stats, pilot=None) -> None:
    """Display detailed stats for a single ship."""
    s = ship_stats
    name = getattr(s, "display_name", "Unknown")
    template = getattr(s, "template_id", "")

    print(f"\n {bold(f'═══ SHIP INSPECTION: {name} ({template}) ═══')}")
    print(f"   SM: {getattr(s, 'sm', '?')}    Class: {template}")
    print(f"   HP: {getattr(s, 'current_hp', '?')}/{getattr(s, 'st_hp', '?')}    "
          f"HT: {getattr(s, 'ht', '?')}    "
          f"Handling: {getattr(s, 'hnd', '?'):+d}    "
          f"SR: {getattr(s, 'sr', '?')}")
    print(f"   Move: {getattr(s, 'accel', '?')}/{getattr(s, 'top_speed', '?')}    "
          f"Stall: {getattr(s, 'stall_speed', 0) or 'VTOL'}")
    print()

    # Defense
    print(f"   {bold('DEFENSE')}")
    dr_f = getattr(s, "dr_front", 0)
    dr_r = getattr(s, "dr_rear", 0)
    dr_l = getattr(s, "dr_left", 0)
    dr_ri = getattr(s, "dr_right", 0)
    dr_t = getattr(s, "dr_top", 0)
    dr_b = getattr(s, "dr_bottom", 0)
    print(f"   DR: F:{dr_f} R:{dr_r} L:{dr_l} Ri:{dr_ri} T:{dr_t} B:{dr_b}"
          f"  Material: {getattr(s, 'dr_material', 'none') or 'none'}")
    fdr_max = getattr(s, "fdr_max", 0)
    current_fdr = getattr(s, "current_fdr", 0)
    fs_type = getattr(s, "force_screen_type", "none")
    if fdr_max > 0:
        print(f"   fDR: {current_fdr}/{fdr_max} ({fs_type})")
    else:
        print(f"   fDR: None")
    print()

    # Electronics
    print(f"   {bold('ELECTRONICS')}")
    print(f"   ECM: {getattr(s, 'ecm_rating', 0)}    "
          f"Scanner: {getattr(s, 'ultrascanner_range', 'none')}mi    "
          f"Targeting: +{getattr(s, 'targeting_bonus', 0)}")
    print(f"   ESM: {'Yes' if getattr(s, 'has_tactical_esm', False) else 'No'}    "
          f"Decoy: {'Yes' if getattr(s, 'has_decoy_launcher', False) else 'No'}")
    print()

    # Weapons
    weapons = getattr(s, "weapons", [])
    if weapons:
        print(f"   {bold('WEAPONS')}")
        for i, w in enumerate(weapons):
            if hasattr(w, "name"):
                wname = w.name
                wdmg = w.damage
                wacc = w.acc
                wmount = w.mount
            elif isinstance(w, dict):
                wname = w.get("name", "Unknown")
                wdmg = w.get("damage", "?")
                wacc = w.get("acc", "?")
                wmount = w.get("mount", "?")
            else:
                continue
            print(f"   {i + 1}. {wname} [{wmount}]  {wdmg}  Acc {wacc}")
    print()

    # Traits
    traits = getattr(s, "traits", [])
    if traits:
        print(f"   {bold('TRAITS')}: {', '.join(traits)}")
    print()

    # Pilot info
    if pilot:
        print(f"   {bold('PILOT')}: {getattr(pilot, 'name', 'Unknown')}")
        print(f"   Piloting: {getattr(pilot, 'piloting_skill', '?')}    "
              f"Gunnery: {getattr(pilot, 'gunnery_skill', '?')}    "
              f"Speed: {getattr(pilot, 'basic_speed', '?')}")
        ace = getattr(pilot, "is_ace_pilot", False)
        if ace:
            print(f"   {colorize('★ ACE PILOT', Color.BRIGHT_YELLOW)}")

    pause("\nPress Enter to return...")
