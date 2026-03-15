"""
Entry point for the Psi-Wars Combat Simulator terminal UI.

Run with: python -m psi_wars_ui

This module:
    1. Displays the title screen
    2. Locates the ship data fixtures directory
    3. Runs the setup flow (ship/faction selection)
    4. Starts the game loop (turn-by-turn combat)

The fixtures directory is located by searching:
    1. ./tests/fixtures (relative to working directory)
    2. One level up from working directory
    3. Relative to this file's location in the package
"""
from __future__ import annotations

import sys
from pathlib import Path

from psi_wars_ui.display import bold, clear_screen, colorize, Color
from psi_wars_ui.setup import run_setup
from psi_wars_ui.game_loop import GameLoop


def find_fixtures_dir() -> Path:
    """
    Locate the test fixtures directory containing ship JSON data.

    Searches multiple locations to handle different working directories.
    Exits with an error message if not found.
    """
    candidates = [
        Path.cwd() / "tests" / "fixtures",
        Path.cwd().parent / "tests" / "fixtures",
        Path(__file__).parent.parent / "tests" / "fixtures",
    ]

    for path in candidates:
        if path.exists() and (path / "ships").exists():
            return path

    print(colorize("ERROR: Cannot find ship data fixtures directory.", Color.RED))
    print("Expected a 'tests/fixtures/ships/' directory.")
    print("Run from the project root: python -m psi_wars_ui")
    sys.exit(1)


def main():
    """Main entry point for the terminal UI."""
    clear_screen()
    print(colorize("""
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
    ║       ★  PSI-WARS COMBAT SIMULATOR  ★            ║
    ║                                                   ║
    ║       GURPS Space Combat — Terminal Edition        ║
    ║                                                   ║
    ╚═══════════════════════════════════════════════════╝
    """, Color.BRIGHT_CYAN))

    print(f"    {bold('Version 0.7.0 — Pipeline Architecture')}")
    print(f"    422 rules tests passing • 40 ships • 48 weapons\n")

    fixtures_dir = find_fixtures_dir()
    print(f"    Ship data: {fixtures_dir / 'ships'}")
    print()

    try:
        session = run_setup(fixtures_dir)
        game = GameLoop(session, fixtures_dir=fixtures_dir)
        game.run()
    except KeyboardInterrupt:
        print(f"\n\n {bold('Interrupted. Goodbye!')}")
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n{colorize(f'ERROR: {e}', Color.RED)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
