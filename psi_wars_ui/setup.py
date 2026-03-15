"""
Game setup flow for the Psi-Wars terminal UI.

Ship catalog is sorted by SM (smallest first), with category headers
displayed as non-selectable visual separators.

IMPORTANT: Category headers are NOT numbered menu items. Only actual
ships get numbers. The menu_choice_with_headers() function handles
this by building a mapping from display position to catalog index.

Modification guide:
    - To change sort order: modify load_ship_catalog()
    - To change category grouping: modify _sm_category()
    - To add setup steps: add to run_setup()
"""
from __future__ import annotations

import json
from pathlib import Path

from m1_psi_core.session import GameSession
from m1_psi_core.testing import MockShipStats, MockPilot
from psi_wars_ui.display import Color, bold, dim, colorize, clear_screen, colored_faction
from psi_wars_ui.input_handler import yes_no, get_text, get_number, pause, get_input


def load_ship_catalog(fixtures_dir: Path) -> list[dict]:
    """
    Load all valid ship JSONs, sorted by SM (smallest first),
    then alphabetically within each SM group.
    """
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

    # Sort by SM first, then by name within each SM
    ships.sort(key=lambda s: (s.get("sm", 99), s.get("name", "")))
    return ships


def ship_to_mock_stats(data: dict) -> MockShipStats:
    """Convert a ship JSON dict into a MockShipStats object."""
    attrs = data.get("attributes", {})
    mobility = data.get("mobility", {})
    defense = data.get("defense", {})
    electronics = data.get("electronics", {})

    return MockShipStats(
        template_id=data.get("template_id", "unknown"),
        instance_id="",
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
        ship_class=data.get("ship_class", ""),
        has_tactical_esm=electronics.get("has_tactical_esm", False),
        has_decoy_launcher=electronics.get("has_decoy_launcher", False),
        traits=data.get("traits", []),
    )


def _sm_category(sm: int) -> str:
    """
    Get a human-readable category label for an SM value.

    Based on Psi-Wars RAW:
    - SM 4-5: Fighters (standard fighters, interceptors)
    - SM 6: Strikers & Small Craft (big fighters, assault boats, shuttles)
    - SM 7-8: Corvettes (patrol craft, light escorts)
    - SM 9-10: Frigates & Heavy Corvettes
    - SM 11-12: Cruisers
    - SM 13+: Capital Ships & Super-Capitals
    """
    if sm <= 5:
        return "FIGHTERS"
    elif sm == 6:
        return "STRIKERS & SMALL CRAFT"
    elif sm <= 8:
        return "CORVETTES"
    elif sm <= 10:
        return "FRIGATES & HEAVY CORVETTES"
    elif sm <= 12:
        return "CRUISERS"
    else:
        return "CAPITAL SHIPS & SUPER-CAPITALS"


def _ship_menu_with_headers(catalog: list[dict]) -> int:
    """
    Display a ship selection menu with non-selectable category headers.

    Category headers are printed as plain text (no number).
    Only actual ships get numbered entries.

    Returns the catalog index of the selected ship.
    """
    # Build display: interleave headers with numbered ship entries
    # number_to_index maps menu number (1-based) -> catalog index
    number_to_index: dict[int, int] = {}
    current_num = 1
    last_category = ""

    print(f"\n {bold('Ships')}")

    for cat_idx, ship in enumerate(catalog):
        sm = ship.get("sm", 99)
        category = _sm_category(sm)

        # Print category header if it changed
        if category != last_category:
            print(f"   {dim(f'── {category} (SM {sm}+) ──')}")
            last_category = category

        # Print numbered ship entry
        name = ship.get("name", "?")
        hp = ship.get("attributes", {}).get("st_hp", "?")
        cls = ship.get("ship_class", "?")
        fdr = ship.get("defense", {}).get("fdr_max", 0)
        fdr_str = f"fDR:{fdr}" if fdr > 0 else ""

        print(f"   {Color.BRIGHT_CYAN}{current_num:3d}{Color.RESET}. "
              f"{name} (SM {sm}, HP {hp}, {cls}) {fdr_str}")

        number_to_index[current_num] = cat_idx
        current_num += 1

    # Get input
    max_num = current_num - 1
    while True:
        raw = get_input(f" Ship # [1-{max_num}]: ")
        try:
            choice = int(raw)
            if choice in number_to_index:
                return number_to_index[choice]
        except ValueError:
            pass
        print(colorize(f"  Invalid. Enter 1-{max_num}.", Color.RED))


def run_setup(fixtures_dir: Path) -> GameSession:
    """Run the complete game setup flow."""
    clear_screen()
    print(f"\n {bold('═══ PSI-WARS COMBAT SIMULATOR — SETUP ═══')}\n")

    session = GameSession()
    catalog = load_ship_catalog(fixtures_dir)

    if not catalog:
        print(colorize(" ERROR: No ship data found!", Color.RED))
        raise SystemExit(1)

    print(f" {len(catalog)} ships available.\n")

    # Factions
    print(bold(" FACTION SETUP"))
    faction1 = get_text("Faction 1 name", default="Empire").lower()
    faction2 = get_text("Faction 2 name", default="Trader").lower()
    session.add_faction(faction1, color=_pick_color(faction1))
    session.add_faction(faction2, color=_pick_color(faction2))
    session.set_relationship(faction1, faction2, "enemy")
    print(f"\n {colored_faction(faction1)} vs {colored_faction(faction2)}"
          f" — {colorize('ENEMIES', Color.RED)}\n")

    # Ship selection
    from psi_wars_ui.input_handler import menu_choice_simple

    ships_config = []
    for faction in [faction1, faction2]:
        print(f"\n {bold(f'SELECT SHIP FOR {faction.upper()}')}")
        cat_idx = _ship_menu_with_headers(catalog)
        ship_data = catalog[cat_idx]

        print(f"\n Selected: {bold(ship_data.get('name', '?'))}")
        display_name = get_text("Display name", default=ship_data.get("name", "Ship"))

        ctrl_choice = menu_choice_simple(
            "Control mode",
            ["Human player", "NPC (AI controlled)"],
        )
        control = "human" if ctrl_choice == 0 else "npc"

        pilot = _configure_pilot(display_name)
        ships_config.append((ship_data, faction, control, display_name, pilot))

    # Register
    for i, (ship_data, faction, control, display_name, pilot) in enumerate(ships_config):
        ship_id = f"ship_{i + 1}"
        stats = ship_to_mock_stats(ship_data)
        stats.instance_id = ship_id
        stats.display_name = display_name
        session.register_ship(ship_id, stats, pilot, faction, control)

    # Engagement
    print(f"\n {bold('ENGAGEMENT SETUP')}")
    range_options = ["Close", "Short", "Medium", "Long", "Extreme", "Distant"]
    range_values = ["close", "short", "medium", "long", "extreme", "distant"]
    range_choice = menu_choice_simple("Starting range band", range_options)
    if range_choice is None:
        range_choice = 3
    starting_range = range_values[range_choice]

    all_ids = session.get_all_ship_ids()
    if len(all_ids) >= 2:
        session.create_engagement(all_ids[0], all_ids[1], range_band=starting_range)

    print(f"\n {bold('Setup complete!')}\n")
    pause()
    return session


def _configure_pilot(ship_name: str) -> MockPilot:
    """Configure a pilot (default or custom skills)."""
    from psi_wars_ui.input_handler import menu_choice_simple

    print(f"\n {bold('Pilot Configuration')}")
    if yes_no("Use default pilot skills?", default=True):
        return MockPilot(name=f"{ship_name} Pilot")

    p_name = get_text("Pilot name", default=f"{ship_name} Pilot")
    p_skill = get_number("Piloting skill", 6, 30, default=14)
    g_skill = get_number("Gunnery skill", 6, 30, default=14)
    speed = get_number("Basic Speed (x10)", 40, 100, default=60) / 10.0
    is_ace = yes_no("Ace Pilot?", default=False)

    # Luck advantage
    luck_choice = menu_choice_simple(
        "Luck advantage",
        ["None", "Luck (reroll 1/hour, 15pts)",
         "Extraordinary Luck (1/30min, 30pts)",
         "Ridiculous Luck (1/10min, 60pts)"],
    )
    luck_levels = ["none", "luck", "extraordinary", "ridiculous"]
    luck_level = luck_levels[luck_choice] if luck_choice is not None else "none"

    return MockPilot(
        name=p_name, piloting_skill=p_skill, gunnery_skill=g_skill,
        basic_speed=speed, is_ace_pilot=is_ace, luck_level=luck_level,
    )


def _pick_color(name: str) -> str:
    colors = {
        "empire": "red", "imperial": "red", "trader": "blue",
        "redjack": "yellow", "rath": "green", "maradonian": "magenta",
        "arc": "cyan", "rebel": "green",
    }
    return colors.get(name, "white")
