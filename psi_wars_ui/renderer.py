"""
Screen buffer for the Psi-Wars terminal UI.

THIS IS THE SINGLE AUTHORITY ON WHAT APPEARS ON SCREEN.

Architecture:
    The ScreenBuffer owns the entire terminal display. It divides
    the screen into three fixed regions:

    ┌────────────────────────────────┐
    │ STATUS BAR (fixed height)      │  ← Ship status, engagements
    ├────────────────────────────────┤
    │ COMBAT LOG (variable height)   │  ← Scrolling event history
    ├────────────────────────────────┤
    │ ACTION AREA (variable height)  │  ← Menus, prompts, messages
    └────────────────────────────────┘

    The combat log is TRUNCATED to fit whatever space remains after
    the status bar and action area are laid out. This guarantees the
    status bar never scrolls off and the menu is always visible.

Usage:
    buf = ScreenBuffer()
    buf.set_status(session)
    buf.set_log(combat_log)
    buf.set_action(["Choose maneuver:", "1. Attack", "2. Move"])
    buf.draw()  # Clears screen and prints everything

    # Later, to show a new menu:
    buf.set_action(["Choose intent:", "1. Pursue", "2. Evade"])
    buf.draw()  # Status bar and log are preserved

Modification guide:
    - To change the status bar: modify _build_status_lines()
    - To change the log display: modify _build_log_lines()
    - To change layout proportions: modify draw()
"""
from __future__ import annotations

import sys
from typing import Optional

from psi_wars_ui.display import (
    Color, bold, dim, colorize,
    colored_faction, colored_wound,
    horizontal_rule, get_terminal_size,
    faction_color, event_color, clear_screen,
)


class CombatLog:
    """
    Append-only combat log with message history.

    Messages are pre-formatted with ANSI colors based on event type.
    The ScreenBuffer retrieves recent messages to fill available space.
    """

    def __init__(self, max_history: int = 500):
        self._messages: list[str] = []
        self._max_history = max_history

    def add(self, message: str, event_type: str = "info") -> None:
        """Add a color-coded message to the log."""
        color = event_color(event_type)
        self._messages.append(f"{color}{message}{Color.RESET}")
        if len(self._messages) > self._max_history:
            self._messages.pop(0)

    def get_recent(self, count: int) -> list[str]:
        """Get the most recent N messages."""
        return self._messages[-count:]

    @property
    def total(self) -> int:
        return len(self._messages)


class ScreenBuffer:
    """
    Single-authority screen buffer. Owns the entire terminal display.

    All output goes through this buffer. Call draw() to render.
    Between draws, update the status, log, or action area independently.
    """

    def __init__(self):
        self.combat_log = CombatLog()
        self._status_lines: list[str] = []
        self._action_lines: list[str] = []

    # -------------------------------------------------------------------
    # Region setters
    # -------------------------------------------------------------------

    def set_status(self, session) -> None:
        """
        Rebuild the status bar from the current session state.

        This captures: turn counter, title, ship status table,
        and engagement map.
        """
        cols, _ = get_terminal_size()
        width = min(cols, 140)
        lines: list[str] = []

        # Header
        turn_text = f" TURN {session.current_turn}"
        title = "PSI-WARS COMBAT SIMULATOR"
        padding = max(1, width - len(turn_text) - len(title) - 2)
        lines.append(f"{bold(turn_text)}{' ' * padding}{bold(title)}")
        lines.append(colorize(horizontal_rule(width), Color.DIM))

        # Ship status
        for ship_id in session.get_all_ship_ids():
            line = self._render_ship_line(session, ship_id)
            if line:
                lines.append(line)

        lines.append(colorize(horizontal_rule(width), Color.DIM))

        # Engagements
        eng_lines = self._render_engagements(session)
        lines.extend(eng_lines)
        lines.append(colorize(horizontal_rule(width), Color.DIM))

        self._status_lines = lines

    def set_action(self, lines: list[str]) -> None:
        """
        Set the action area content (menus, prompts, etc).

        Pass an empty list to clear the action area.
        """
        self._action_lines = list(lines)

    def clear_action(self) -> None:
        """Clear the action area."""
        self._action_lines = []

    # -------------------------------------------------------------------
    # Drawing
    # -------------------------------------------------------------------

    def draw(self) -> None:
        """
        Render the entire screen buffer to the terminal.

        Layout calculation:
        1. Status bar: fixed height (self._status_lines)
        2. Action area: fixed height (self._action_lines)
        3. Combat log: fills ALL remaining space between them

        The combat log is truncated (most recent messages) to fit.
        """
        cols, total_lines = get_terminal_size()
        width = min(cols, 140)

        status_height = len(self._status_lines)
        action_height = len(self._action_lines)

        # Reserve lines: status + separator + log header + separator + action
        # The log fills everything in between
        overhead = status_height + action_height + 3  # +3 for log header + 2 separators
        log_height = max(2, total_lines - overhead)

        # Build the complete frame
        frame: list[str] = []

        # 1. Status bar
        frame.extend(self._status_lines)

        # 2. Combat log
        frame.append(
            bold(" COMBAT LOG")
            + dim(f"  [{self.combat_log.total} entries]")
        )
        log_msgs = self.combat_log.get_recent(log_height)
        for msg in log_msgs:
            frame.append(f" {msg}")
        # Pad remaining log space so action area stays at bottom
        for _ in range(log_height - len(log_msgs)):
            frame.append("")

        frame.append(colorize(horizontal_rule(width), Color.DIM))

        # 3. Action area
        frame.extend(self._action_lines)

        # Render
        clear_screen()
        sys.stdout.write("\n".join(frame))
        sys.stdout.write("\n")
        sys.stdout.flush()

    # -------------------------------------------------------------------
    # Ship status rendering
    # -------------------------------------------------------------------

    def _render_ship_line(self, session, ship_id: str) -> Optional[str]:
        """
        Render one ship's status line.

        Format: [FACTION] [CTRL] Name  HP:cur/max  fDR:cur/max  Wound
        """
        ship = session.get_ship(ship_id)
        if ship is None:
            return None

        faction_name = session.get_faction_for_ship(ship_id) or "?"
        control = session.get_control_mode(ship_id) or "?"
        fc = faction_color(faction_name)

        ftag = colorize(f"[{faction_name.upper()[:6]:6s}]", fc)

        if control == "npc":
            ctrl = colorize("[NPC]", Color.MAGENTA)
        elif control == "gm":
            ctrl = colorize(" [GM]", Color.YELLOW)
        else:
            ctrl = colorize("[YOU]", Color.BRIGHT_GREEN)

        name = getattr(ship, "display_name", ship_id)

        # HP with color
        cur_hp = getattr(ship, "current_hp", 0)
        max_hp = getattr(ship, "st_hp", 1)
        hp_pct = cur_hp / max(max_hp, 1)
        hp_color = Color.GREEN if hp_pct > 0.7 else (Color.YELLOW if hp_pct > 0.3 else Color.RED)
        hp_str = colorize(f"HP:{cur_hp}/{max_hp}", hp_color)

        # fDR
        fdr_max = getattr(ship, "fdr_max", 0)
        cur_fdr = getattr(ship, "current_fdr", 0)
        if fdr_max > 0:
            fdr_pct = cur_fdr / max(fdr_max, 1)
            fdr_color = Color.BLUE if fdr_pct > 0.5 else (Color.YELLOW if fdr_pct > 0 else Color.RED)
            fdr_str = colorize(f"fDR:{cur_fdr}/{fdr_max}", fdr_color)
        else:
            fdr_str = dim("fDR:--")

        # Wound
        wound = getattr(ship, "wound_level", "none")
        wound_str = colored_wound(wound)

        # Destroyed override
        if getattr(ship, "is_destroyed", False):
            name = colorize(f"✘ {name}", Color.DIM)
            wound_str = colorize("DESTROYED", Color.BRIGHT_RED + Color.BOLD)

        return f" {ftag} {ctrl} {name:20s} {hp_str:22s} {fdr_str:22s} {wound_str}"

    def _render_engagements(self, session) -> list[str]:
        """Render all active engagements."""
        lines = []
        seen: set[tuple[str, str]] = set()

        for ship_id in session.get_all_ship_ids():
            for eng in session.get_engagements_for_ship(ship_id):
                key = (min(eng.ship_a_id, eng.ship_b_id),
                       max(eng.ship_a_id, eng.ship_b_id))
                if key in seen:
                    continue
                seen.add(key)

                ship_a = session.get_ship(eng.ship_a_id)
                ship_b = session.get_ship(eng.ship_b_id)
                na = getattr(ship_a, "display_name", eng.ship_a_id) if ship_a else eng.ship_a_id
                nb = getattr(ship_b, "display_name", eng.ship_b_id) if ship_b else eng.ship_b_id

                rng = colorize(eng.range_band.upper(), Color.BRIGHT_CYAN)

                if eng.matched_speed and eng.advantage:
                    an = na if eng.advantage == eng.ship_a_id else nb
                    adv = colorize(f"{an} MATCHED SPEED", Color.BRIGHT_GREEN + Color.BOLD)
                elif eng.advantage:
                    an = na if eng.advantage == eng.ship_a_id else nb
                    adv = colorize(f"{an} has ADVANTAGE", Color.BRIGHT_YELLOW)
                else:
                    adv = dim("No advantage")

                lines.append(f" {na} ←[{rng}]→ {nb}  │ {adv}")

        return lines if lines else [dim("  No engagements.")]
