"""
Game setup flow for the terminal UI.

Walks the player through ship selection, faction assignment,
pilot configuration, and engagement creation. Returns a fully
configured GameSession ready to play.
"""
from __future__ import annotations

import json
from pathlib import Path

from m1_psi_core.session import GameSession
from m1_psi_core.testing import MockShipStats, MockPilot
from psi_wars_ui.display import (
    Color, bold, dim, colorize, clear_screen, colored_faction,
)
from psi_wars_ui.input_handler import (
    menu_choice, yes_no, get_text, get_number, pause,
)


# ---------------------------------------------------------------------------
# Ship catalog loading
# ---------------------------------------------------------------------------

def load_ship_catalog(fixtures_dir: Path) -> list[dict]:
    """Load all valid ship JSONs from the fixtures directory."""
    ships = []
    ships_dir = fixtures_dir / "ships"
    if not ships_dir.exists():
        return ships

    for f in sorted(ships_dir.glob("*.json")):
        if "invalid" in f.stem:
            continue
        try:
            data = json.loads(f.read_text())
            ships.append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    return ships


def ship_to_mock_stats(data: dict) -> MockShipStats:
    """Convert a ship JSON dict into a MockShipStats for the session."""
    attrs = data.get("attributes", {})
    mobility = data.get("mobility", {})
    defense = data.get("defense", {})
    electronics = data.get("electronics", {})
    logistics = data.get("logistics", {})

    return MockShipStats(
        template_id=data.get("template_id", "unknown"),
        instance_id="",  # Will be set during registration
        display_name=data.get("name", "Unknown Ship"),
        faction=data.get("faction_origin", "unknown"),
        st_hp=attrs.get("st_hp", 80),
        ht=attrs.get("ht", "12"),
        hnd=attrs.get("hnd", 0),
        sr=attrs.get("sr", 3),
        accel=mobility.get("accel", 10),
        top_speed=mobility.get("top_speed", 400),
        stall_speed=mobility.get("stall_speed", 0),
        dr_front=defense.get("dr_front", 10),
        dr_rear=defense.get("dr_rear", 10),
        dr_left=defense.get("dr_left", 10),
        dr_right=defense.get("dr_right", 10),
        dr_top=defense.get("dr_top", 10),
        dr_bottom=defense.get("dr_bottom", 10),
        dr_material=defense.get("dr_material"),
        fdr_max=defense.get("fdr_max", 0),
        force_screen_type=defense.get("force_screen_type", "none"),
        current_fdr=defense.get("fdr_max", 0),
        ecm_rating=electronics.get("ecm_rating", 0),
        targeting_bonus=electronics.get("targeting_bonus", 5),
        ultrascanner_range=electronics.get("ultrascanner_range"),
        current_hp=attrs.get("st_hp", 80),
        sm=data.get("sm", 4),
        has_tactical_esm=electronics.get("has_tactical_esm", False),
        has_decoy_launcher=electronics.get("has_decoy_launcher", False),
        traits=data.get("traits", []),
    )


# ---------------------------------------------------------------------------
# Setup flow
# ---------------------------------------------------------------------------

def run_setup(fixtures_dir: Path) -> GameSession:
    """
    Run the complete game setup flow.

    Returns a configured GameSession ready to play.
    """
    clear_screen()
    print(f"\n {bold('═══ PSI-WARS COMBAT SIMULATOR — SETUP ═══')}\n")

    session = GameSession()

    # Load ship catalog
    catalog = load_ship_catalog(fixtures_dir)
    if not catalog:
        print(colorize(" ERROR: No ship data found!", Color.RED))
        print(f" Expected ship JSONs in: {fixtures_dir / 'ships'}")
        raise SystemExit(1)

    print(f" {len(catalog)} ships available.\n")

    # --- Faction setup ---
    print(bold(" FACTION SETUP"))
    print(dim(" Setting up a 2-faction battle.\n"))

    faction1_name = get_text("Faction 1 name", default="Empire")
    faction1_color = _pick_faction_color(faction1_name)
    session.add_faction(faction1_name.lower(), color=faction1_color)

    faction2_name = get_text("Faction 2 name", default="Trader")
    faction2_color = _pick_faction_color(faction2_name)
    session.add_faction(faction2_name.lower(), color=faction2_color)

    session.set_relationship(faction1_name.lower(), faction2_name.lower(), "enemy")
    print(f"\n {colored_faction(faction1_name.lower())} vs "
          f"{colored_faction(faction2_name.lower())} — {colorize('ENEMIES', Color.RED)}\n")

    # --- Ship selection ---
    ships_data = []  # [(ship_json, faction, control, display_name, pilot)]

    for faction_idx, (faction_name, faction_lower) in enumerate([
        (faction1_name, faction1_name.lower()),
        (faction2_name, faction2_name.lower()),
    ]):
        print(f"\n {bold(f'SELECT SHIP FOR {faction_name.upper()}')}")

        # Build menu organized by class
        ship_options = []
        for s in catalog:
            cls = s.get("ship_class", "?")
            name = s.get("name", "Unknown")
            sm = s.get("sm", "?")
            hp = s.get("attributes", {}).get("st_hp", "?")
            ship_options.append(f"{name} (SM {sm}, HP {hp}, {cls})")

        choice = menu_choice("Ships", ship_options, allow_cancel=False)
        if choice is None:
            choice = 0

        ship_data = catalog[choice]
        display_name = get_text("Display name", default=ship_data["name"])

        # Control mode
        control_options = ["Human player", "NPC (AI controlled)"]
        ctrl_choice = menu_choice("Control mode", control_options, allow_cancel=False)
        control = "human" if ctrl_choice == 0 else "npc"

        # Pilot skills
        print(f"\n {bold('Pilot Configuration')}")
        if yes_no("Use default pilot skills?", default=True):
            pilot = MockPilot(name=f"{display_name} Pilot")
        else:
            p_name = get_text("Pilot name", default=f"{display_name} Pilot")
            p_skill = get_number("Piloting skill", 8, 20, default=14)
            g_skill = get_number("Gunnery skill", 8, 20, default=14)
            speed = get_number("Basic Speed (x10)", 40, 80, default=60) / 10.0
            is_ace = yes_no("Ace Pilot?", default=False)
            pilot = MockPilot(
                name=p_name,
                piloting_skill=p_skill,
                gunnery_skill=g_skill,
                basic_speed=speed,
                is_ace_pilot=is_ace,
            )

        ships_data.append((ship_data, faction_lower, control, display_name, pilot))

    # --- Register ships ---
    for i, (ship_data, faction, control, display_name, pilot) in enumerate(ships_data):
        ship_id = f"ship_{i + 1}"
        stats = ship_to_mock_stats(ship_data)
        stats.instance_id = ship_id
        stats.display_name = display_name
        session.register_ship(ship_id, stats, pilot, faction, control)

    # --- Engagement setup ---
    print(f"\n {bold('ENGAGEMENT SETUP')}")

    range_options = ["Close", "Short", "Medium", "Long", "Extreme", "Distant"]
    range_values = ["close", "short", "medium", "long", "extreme", "distant"]
    range_choice = menu_choice(
        "Starting range band", range_options, allow_cancel=False,
    )
    starting_range = range_values[range_choice if range_choice is not None else 3]

    # Create engagement between the two ships
    all_ids = session.get_all_ship_ids()
    if len(all_ids) >= 2:
        session.create_engagement(all_ids[0], all_ids[1], range_band=starting_range)

    print(f"\n {bold('Setup complete!')} Starting combat...\n")
    pause()

    return session


def _pick_faction_color(faction_name: str) -> str:
    """Pick a color name based on faction name."""
    name_lower = faction_name.lower()
    color_map = {
        "empire": "red",
        "imperial": "red",
        "trader": "blue",
        "redjack": "yellow",
        "rath": "green",
        "maradonian": "magenta",
        "arc": "cyan",
        "rebel": "green",
    }
    return color_map.get(name_lower, "white")
