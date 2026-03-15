"""
Screen renderer for the terminal UI.

Builds the complete screen display from game state. The screen is
composed of regions: header, ship status, engagements, combat log,
and input prompt. The renderer produces a list of lines that are
printed as a full-screen redraw.
"""
from __future__ import annotations

from typing import Optional

from psi_wars_ui.display import (
    Color, bold, dim, colorize,
    colored_faction, colored_wound,
    horizontal_rule, get_terminal_size,
    faction_color, event_color,
)


class CombatLog:
    """
    Scrolling combat log that stores formatted event messages.

    Maintains a history of all messages and provides a windowed
    view for display.
    """

    def __init__(self, max_history: int = 500):
        self._messages: list[str] = []
        self._max_history = max_history

    def add(self, message: str, event_type: str = "info") -> None:
        """Add a message to the log with color coding."""
        color = event_color(event_type)
        self._messages.append(f"{color}{message}{Color.RESET}")
        if len(self._messages) > self._max_history:
            self._messages.pop(0)

    def add_raw(self, message: str) -> None:
        """Add a pre-formatted message."""
        self._messages.append(message)

    def get_recent(self, count: int) -> list[str]:
        """Get the most recent N messages."""
        return self._messages[-count:]

    def clear(self) -> None:
        """Clear the log."""
        self._messages.clear()

    @property
    def total_messages(self) -> int:
        return len(self._messages)


class ScreenRenderer:
    """
    Builds the full-screen display from game state.

    Call render() to get a list of lines to print. The renderer
    handles layout calculation, truncation, and padding to fill
    the terminal.
    """

    def __init__(self):
        self.combat_log = CombatLog()

    def render(
        self,
        session,
        active_ship_id: Optional[str] = None,
        prompt_text: str = "",
        extra_info: str = "",
    ) -> str:
        """
        Render the complete screen.

        Returns a single string with ANSI codes, ready to print.
        """
        cols, lines = get_terminal_size()
        width = min(cols, 120)  # Cap width for readability
        output_lines = []

        # --- Header ---
        output_lines.append(self._render_header(session, width))
        output_lines.append(horizontal_rule(width, "─"))

        # --- Ship Status ---
        output_lines.append(bold(" SHIP STATUS"))
        status_lines = self._render_ship_status(session, width)
        output_lines.extend(status_lines)
        output_lines.append(horizontal_rule(width, "─"))

        # --- Engagements ---
        output_lines.append(bold(" ENGAGEMENTS"))
        eng_lines = self._render_engagements(session, width)
        output_lines.extend(eng_lines)
        output_lines.append(horizontal_rule(width, "─"))

        # --- Combat Log ---
        # Calculate remaining space for log
        used_lines = len(output_lines) + 3  # +3 for log header, prompt, and padding
        log_height = max(5, lines - used_lines - 2)

        output_lines.append(
            bold(" COMBAT LOG")
            + dim(f"  [{self.combat_log.total_messages} messages]")
        )

        log_messages = self.combat_log.get_recent(log_height)
        for msg in log_messages:
            output_lines.append(f" {msg}")

        # Pad remaining log space
        for _ in range(log_height - len(log_messages)):
            output_lines.append("")

        output_lines.append(horizontal_rule(width, "─"))

        # --- Extra info (if any) ---
        if extra_info:
            output_lines.append(f" {extra_info}")

        # --- Input Prompt ---
        if prompt_text:
            output_lines.append(f" {prompt_text}")

        return "\n".join(output_lines)

    def _render_header(self, session, width: int) -> str:
        """Render the turn counter and title bar."""
        turn_text = f" TURN {session.current_turn}"
        title = "PSI-WARS COMBAT SIMULATOR"
        padding = width - len(turn_text) - len(title) - 2
        if padding < 1:
            padding = 1
        return f"{bold(turn_text)}{' ' * padding}{bold(title)}"

    def _render_ship_status(self, session, width: int) -> list[str]:
        """Render the ship status table."""
        lines = []
        for ship_id in session.get_all_ship_ids():
            ship = session.get_ship(ship_id)
            if ship is None:
                continue

            faction_name = session.get_faction_for_ship(ship_id) or "unknown"
            control = session.get_control_mode(ship_id) or "?"
            fc = faction_color(faction_name)

            # Faction tag
            faction_tag = colorize(f"[{faction_name.upper()[:8]:8s}]", fc)

            # Ship name
            display_name = getattr(ship, "display_name", ship_id)
            template = getattr(ship, "template_id", "")
            name_str = f"{display_name}"
            if template:
                name_str += dim(f" ({template})")

            # HP
            current_hp = getattr(ship, "current_hp", 0)
            max_hp = getattr(ship, "st_hp", 0)
            hp_str = f"HP:{current_hp}/{max_hp}"

            # fDR
            fdr_max = getattr(ship, "fdr_max", 0)
            current_fdr = getattr(ship, "current_fdr", 0)
            if fdr_max > 0:
                fdr_str = f"fDR:{current_fdr}/{fdr_max}"
            else:
                fdr_str = "fDR:--"

            # Wound level
            wound = getattr(ship, "wound_level", "none")
            wound_str = colored_wound(wound)

            # Control indicator
            if control == "npc":
                ctrl_str = dim("[NPC]")
            elif control == "gm":
                ctrl_str = dim("[GM]")
            else:
                ctrl_str = ""

            # Destroyed indicator
            if getattr(ship, "is_destroyed", False):
                name_str = colorize(f"✘ {display_name}", Color.DIM)
                wound_str = colorize("DESTROYED", Color.BRIGHT_RED + Color.BOLD)

            line = f" {faction_tag} {name_str:30s} {hp_str:12s} {fdr_str:12s} {wound_str} {ctrl_str}"
            lines.append(line)

        if not lines:
            lines.append(dim("  No ships registered."))

        return lines

    def _render_engagements(self, session, width: int) -> list[str]:
        """Render the engagement map."""
        lines = []
        seen = set()

        for ship_id in session.get_all_ship_ids():
            for eng in session.get_engagements_for_ship(ship_id):
                key = (min(eng.ship_a_id, eng.ship_b_id),
                       max(eng.ship_a_id, eng.ship_b_id))
                if key in seen:
                    continue
                seen.add(key)

                ship_a = session.get_ship(eng.ship_a_id)
                ship_b = session.get_ship(eng.ship_b_id)
                name_a = getattr(ship_a, "display_name", eng.ship_a_id) if ship_a else eng.ship_a_id
                name_b = getattr(ship_b, "display_name", eng.ship_b_id) if ship_b else eng.ship_b_id

                range_str = colorize(eng.range_band.upper(), Color.BRIGHT_CYAN)

                # Advantage indicator
                if eng.matched_speed:
                    adv_str = colorize(
                        f"{name_a if eng.advantage == eng.ship_a_id else name_b} MATCHED SPEED",
                        Color.BRIGHT_GREEN + Color.BOLD,
                    )
                elif eng.advantage:
                    adv_name = name_a if eng.advantage == eng.ship_a_id else name_b
                    adv_str = colorize(f"{adv_name} has ADVANTAGE", Color.BRIGHT_YELLOW)
                else:
                    adv_str = dim("No advantage")

                line = f" {name_a} ←[{range_str}]→ {name_b}  │ {adv_str}"
                lines.append(line)

        if not lines:
            lines.append(dim("  No active engagements."))

        return lines
