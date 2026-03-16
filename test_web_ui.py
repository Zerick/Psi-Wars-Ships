#!/usr/bin/env python3
"""
Psi-Wars Combat Simulator — Interactive Test Script
Web UI v0.2.6

Run this on any machine with Python 3. It walks you through each test
one at a time, collects your answers, and generates a report at the end.

Usage:
    python test_web_ui.py

Output:
    test_results.txt (paste this back to Claude)
"""

import datetime
import sys
import os

# ---------------------------------------------------------------------------
# Test definitions
# Each test: (section, id, instruction, answer_type)
# answer_type: "yn" = Y/N, "ynm" = Y/N/meh, "text" = free text,
#              "rating" = 1-10, "choice" = custom choices shown in prompt
# ---------------------------------------------------------------------------
TESTS = [
    # Section 0: Pre-Flight
    ("Pre-Flight", "0.1",
     "Open https://pwdev.simonious.com/ in your browser.\nDoes the landing page load?",
     "yn"),
    ("Pre-Flight", "0.2",
     "Click the 'Enter Combat' button.\nDoes it take you to the combat page?",
     "yn"),
    ("Pre-Flight", "0.3",
     "Look at the bottom-right corner of the page.\nDoes the version stamp show v0.2.6?",
     "yn"),
    ("Pre-Flight", "0.4",
     "Look at the page fonts — the title, card text, and log text.\nDo they look styled (NOT plain Arial/default browser font)?",
     "yn"),

    # Section 1: Ship Cards — Display
    ("Ship Cards — Display", "1.1",
     "Look at the top strip.\nCan you see 4 ship cards? (Red Fox, Blue Jay, Iron Maw, Wraith)",
     "yn"),
    ("Ship Cards — Display", "1.2",
     "Red Fox should have a blue/cyan glowing top border (it's the active ship).\nDo you see it?",
     "yn"),
    ("Ship Cards — Display", "1.3",
     "Blue Jay should have a red glowing top border (it's being targeted).\nDo you see it?",
     "yn"),
    ("Ship Cards — Display", "1.4",
     "Iron Maw and Wraith should be narrow/compact cards (just name, HP bar, dots).\nAre they noticeably smaller than Red Fox and Blue Jay?",
     "yn"),
    ("Ship Cards — Display", "1.5",
     "Wraith is destroyed. Its card should be faded/dimmed.\nDoes it look faded compared to the others?",
     "yn"),
    ("Ship Cards — Display", "1.6",
     "Red Fox's card should show 2 weapons listed.\nDo you see weapon names and damage values?",
     "yn"),
    ("Ship Cards — Display", "1.7",
     "Do you like the overall look of the ship cards?",
     "ynm"),
    ("Ship Cards — Display", "1.8",
     "Is the card text readable at your screen size?\n(Not too small, not cramped)",
     "yn"),
    ("Ship Cards — Display", "1.9",
     "Any info you'd want to see on the default (non-expanded) card that isn't there?\nType what's missing, or 'none' if it looks good.",
     "text"),

    # Section 2: Expand/Collapse
    ("Ship Cards — Expand", "2.1",
     "Click on Red Fox's card body (NOT on a stat number or subsystem dot).\nDoes the card expand to show more details?",
     "yn"),
    ("Ship Cards — Expand", "2.2",
     "In the expanded view, do you see:\n- Armor DR for all 6 faces (Front/Rear/Left/Right/Top/Bottom)\n- Performance stats (Accel, Top Speed, Stall, Handling)\n- Electronics (ECM, Target Bonus, Tac ESM, Decoys)\n- Full weapon details\n- Pilot details\nAll present?",
     "yn"),
    ("Ship Cards — Expand", "2.3",
     "Red Fox should show a '→ Source Page' link at the bottom of the expanded view.\nDo you see it?",
     "yn"),
    ("Ship Cards — Expand", "2.4",
     "Click the card again to collapse it.\nDoes it collapse back to the compact view?",
     "yn"),

    # Section 3: Subsystem Dots
    ("Subsystem Dots", "3.1",
     "Look at Red Fox's subsystem dots (PROP, WEAP, SENS, RCTR, COMM, LIFE).\nAre all 6 dots showing green?",
     "yn"),
    ("Subsystem Dots", "3.2",
     "Blue Jay should have its SENS dot in yellow (sensors disabled).\nDo you see a yellow dot for SENS?",
     "yn"),
    ("Subsystem Dots", "3.3",
     "Click Red Fox's PROP dot once.\nDid it turn YELLOW (disabled)?",
     "yn"),
    ("Subsystem Dots", "3.4",
     "Click the same PROP dot again.\nDid it turn RED (destroyed)?",
     "yn"),
    ("Subsystem Dots", "3.5",
     "Click it one more time.\nDid it turn back to GREEN (OK)?",
     "yn"),
    ("Subsystem Dots", "3.6",
     "Check the combat log at the bottom.\nDid cycling the subsystem dot create any log entry? (It should NOT)",
     "yn"),
    ("Subsystem Dots", "3.7",
     "Try clicking a subsystem dot on Iron Maw (the compact card).\nDoes it cycle there too?",
     "yn"),
    ("Subsystem Dots", "3.8",
     "Do the dots feel easy to click? Good visual feedback?",
     "ynm"),

    # Section 4: Click-to-Edit
    ("Click-to-Edit", "4.1",
     "Hover your mouse over Red Fox's HP number (the current HP value next to the HP bar).\nDoes it show a dotted underline and change color?",
     "yn"),
    ("Click-to-Edit", "4.2",
     "Click the HP number.\nDoes it turn into a small editable text input?",
     "yn"),
    ("Click-to-Edit", "4.3",
     "Type 30 and press Enter.\nDoes the HP bar shrink and the number update to 30?",
     "yn"),
    ("Click-to-Edit", "4.4",
     "Click the HP number again. Type 0 and press Enter.\nDoes the card go faded/destroyed?",
     "yn"),
    ("Click-to-Edit", "4.5",
     "Click the HP number, type 120, Enter.\nDoes it recover to full health?",
     "yn"),
    ("Click-to-Edit", "4.6",
     "Click the HND value in the stat grid. Change it. Press Enter.\nDid it update?",
     "yn"),
    ("Click-to-Edit", "4.7",
     "Click the DR/F value in the stat grid. Change it. Press Enter.\nDid it update?",
     "yn"),
    ("Click-to-Edit", "4.8",
     "Check the combat log.\nDid ANY of your edits show up in the log? (They should NOT)",
     "yn"),
    ("Click-to-Edit", "4.9",
     "Click 'Hide GM' to hide the GM panel.\nCan you still click-to-edit stat values on cards?",
     "yn"),
    ("Click-to-Edit", "4.10",
     "Click 'Show GM' to bring the panel back.\nAre the edit inputs free of up/down spinner arrows?",
     "yn"),
    ("Click-to-Edit", "4.11",
     "Expand Red Fox and try editing a value in the expanded detail section\n(like a specific DR face, or Pilot skill).\nDoes it work there too?",
     "yn"),
    ("Click-to-Edit", "4.12",
     "Is click-to-edit intuitive? Does it feel natural?",
     "ynm"),
    ("Click-to-Edit", "4.13",
     "Any stats you wish were editable that aren't?\nType what's missing, or 'none'.",
     "text"),

    # Section 5: Engagement Display
    ("Engagements", "5.1",
     "Look between the ship cards and the combat log.\nCan you see the engagement strip?",
     "yn"),
    ("Engagements", "5.2",
     "First engagement should show:\n  Red Fox — MED — Blue Jay\nDo you see this?",
     "yn"),
    ("Engagements", "5.3",
     "The 'MED' range label should be in yellow/amber.\nIs it?",
     "yn"),
    ("Engagements", "5.4",
     "It should show '◀ ADV' indicating Red Fox has advantage.\nDo you see the advantage indicator?",
     "yn"),
    ("Engagements", "5.5",
     "It should show a green 'MATCHED' tag (matched speed).\nDo you see it?",
     "yn"),
    ("Engagements", "5.6",
     "Second engagement: Iron Maw — LONG — Blue Jay\nWith 'LONG' in blue and 'NO ADV'.\nPresent?",
     "yn"),
    ("Engagements", "5.7",
     "Are ship names in the engagement strip colored by faction?\n(Red for Empire, blue for Alliance)",
     "yn"),
    ("Engagements", "5.8",
     "Is the engagement display useful at a glance?",
     "ynm"),
    ("Engagements", "5.9",
     "Would you want to click/edit engagement values (range, advantage) directly?",
     "yn"),

    # Section 6: Combat Log
    ("Combat Log", "6.1",
     "The combat log should have pre-loaded mock entries.\nCan you see turn headers, attacks, damage, etc?",
     "yn"),
    ("Combat Log", "6.2",
     "Turn headers ('TURN 1', 'TURN 2') should be gold/yellow with a line under them.\nCorrect?",
     "yn"),
    ("Combat Log", "6.3",
     "Look at the different entry colors:\n- Chase = cyan/teal\n- Attack = white/bright\n- Defense fail = red\n- Damage = orange\n- System damage = red bold\n- NPC reasoning = purple italic\n- Force screen = blue\nAre these visually distinct?",
     "yn"),
    ("Combat Log", "6.4",
     "Can you scroll up through the log history?",
     "yn"),
    ("Combat Log", "6.5",
     "Type 'hello world' in the input box and press Enter.\nDoes it appear in the log?",
     "yn"),
    ("Combat Log", "6.6",
     "Select some text in the log and try to copy it (Ctrl+C).\nCan you copy/paste log text?",
     "yn"),
    ("Combat Log", "6.7",
     "Is the log font size readable?",
     "yn"),
    ("Combat Log", "6.8",
     "Is the color coding helpful or is it too much?",
     "text"),

    # Section 7: Dice Roller — Basic
    ("Dice — Basic", "7.1",
     "Type [[3d6]] in the chat input and press Enter.\nDo you get a result between 3-18 with a breakdown?",
     "yn"),
    ("Dice — Basic", "7.2",
     "Type [[1d20]] — result 1-20?",
     "yn"),
    ("Dice — Basic", "7.3",
     "Type [[2d6+5]] — result 7-17?",
     "yn"),
    ("Dice — Basic", "7.4",
     "Type [[1d20-3]] — result -2 to 17?",
     "yn"),
    ("Dice — Basic", "7.5",
     "Do dice results show in cyan/accent color?",
     "yn"),

    # Section 8: Dice Roller — Advanced
    ("Dice — Advanced", "8.1",
     "Type [[1d20a]] — advantage roll.\nDoes it return a result?",
     "yn"),
    ("Dice — Advanced", "8.2",
     "Type [[1d20d]] — disadvantage roll.\nDoes it return a result?",
     "yn"),
    ("Dice — Advanced", "8.3",
     "Type [[4d6kh3]] — keep highest 3.\nResult between 3-18?",
     "yn"),
    ("Dice — Advanced", "8.4",
     "Type [[6d8dl2]] — drop lowest 2.\nDoes it return a result?",
     "yn"),
    ("Dice — Advanced", "8.5",
     "Type [[5d6kh3v]] — verbose mode.\nDoes it show the full breakdown with individual dice?",
     "yn"),
    ("Dice — Advanced", "8.6",
     "Type [[10x3d6]] — batch sum.\nShows a grand total (should be 30-180)?",
     "yn"),
    ("Dice — Advanced", "8.7",
     "Type [[4t3d6]] — individual batch.\nShows 4 separate results?",
     "yn"),
    ("Dice — Advanced", "8.8",
     "Type [[4#1d6]] — same as t.\nShows 4 separate results?",
     "yn"),

    # Section 9: Dice — Commands
    ("Dice — Commands", "9.1",
     "Type [[help]]\nDoes the full help text appear in the log?",
     "yn"),
    ("Dice — Commands", "9.2",
     "Is the help text readable? (proper line breaks, not garbled)",
     "yn"),
    ("Dice — Commands", "9.3",
     "Type [[about]]\nDoes the SBDB attribution text appear?",
     "yn"),
    ("Dice — Commands", "9.4",
     "Type [[stats 3d6]]\nDoes it show min, max, mean, median, std dev?",
     "yn"),
    ("Dice — Commands", "9.5",
     "Do the stats look reasonable? (3d6: min ~3, max ~18, mean ~10.5)",
     "yn"),
    ("Dice — Commands", "9.6",
     "Type [[stats 4d6kh3]]\nDoes it work with keep/drop syntax?",
     "yn"),
    ("Dice — Commands", "9.7",
     "Type [[garbage]]\nDoes it show an error message (not crash)?",
     "yn"),

    # Section 10: Inline Rolls
    ("Dice — Inline", "10.1",
     "Type: I attack with [[3d6+4]] damage\nDoes it show your text, then the roll result below?",
     "yn"),
    ("Dice — Inline", "10.2",
     "Type: Rolling [[1d20]] to hit and [[2d6+3]] damage\nDoes it show the text, then BOTH roll results?",
     "yn"),
    ("Dice — Inline", "10.3",
     "Does inline rolling feel natural?",
     "ynm"),

    # Section 11: GM Panel
    ("GM Panel", "11.1",
     "Is the GM panel visible on the right side?",
     "yn"),
    ("GM Panel", "11.2",
     "Click 'Hide GM' — does the panel disappear and the log expand?",
     "yn"),
    ("GM Panel", "11.3",
     "Click 'Show GM' — does it come back?",
     "yn"),
    ("GM Panel", "11.4",
     "Dice Review section — click 'None' filter.\nDoes the dice log go empty?",
     "yn"),
    ("GM Panel", "11.5",
     "Click 'NPC Only' — shows only NPC rolls?",
     "yn"),
    ("GM Panel", "11.6",
     "Click 'All' — shows everything again?",
     "yn"),
    ("GM Panel", "11.7",
     "What's missing from the GM panel? What would make it more useful?\nType your thoughts, or 'looks good'.",
     "text"),

    # Section 12: Overall
    ("Overall", "12.1",
     "Rate the overall visual design on a scale of 1-10.\n(1 = ugly, 10 = perfect)",
     "rating"),
    ("Overall", "12.2",
     "Does it feel like a tactical combat tool, or a generic web app?",
     "text"),
    ("Overall", "12.3",
     "Is the dark theme comfortable? Could you use this for a long session?",
     "yn"),
    ("Overall", "12.4",
     "Any colors that are hard to read or that clash?",
     "text"),
    ("Overall", "12.5",
     "Is the layout intuitive?\n(Cards top, engagements middle, log bottom-left, GM bottom-right)",
     "yn"),
    ("Overall", "12.6",
     "What's the SINGLE thing you'd most want changed right now?",
     "text"),
    ("Overall", "12.7",
     "What's working best? What do you like most?",
     "text"),
    ("Overall", "12.8",
     "Any features from the terminal UI that you miss in the web version?",
     "text"),
    ("Overall", "12.9",
     "Ready to move on to session instances & login?\nOr more UI polish needed first?",
     "text"),
]


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_answer(answer_type):
    while True:
        if answer_type == "yn":
            raw = input("\n  → [Y/N]: ").strip().lower()
            if raw in ('y', 'yes'): return 'Y'
            if raw in ('n', 'no'): return 'N'
            print("    Please enter Y or N.")

        elif answer_type == "ynm":
            raw = input("\n  → [Y/N/meh]: ").strip().lower()
            if raw in ('y', 'yes'): return 'Y'
            if raw in ('n', 'no'): return 'N'
            if raw in ('m', 'meh'): return 'meh'
            print("    Please enter Y, N, or meh.")

        elif answer_type == "text":
            raw = input("\n  → ").strip()
            if raw: return raw
            print("    Please type something.")

        elif answer_type == "rating":
            raw = input("\n  → [1-10]: ").strip()
            try:
                val = int(raw)
                if 1 <= val <= 10: return str(val)
            except ValueError:
                pass
            print("    Please enter a number 1-10.")


def main():
    clear_screen()
    print("=" * 60)
    print("  PSI-WARS COMBAT SIMULATOR — WEB UI TEST SCRIPT")
    print("  Version: v0.2.6")
    print("=" * 60)
    print()
    print("  This script walks you through testing every component.")
    print("  Answer each prompt, and a report will be generated")
    print("  at the end that you can paste back to Claude.")
    print()
    print("  Before starting:")
    print("  1. Deploy v0.2.6 to the Pi")
    print("  2. Run: cd /home/psiwars/psi-wars/web && venv/bin/pip install d20")
    print("  3. Run: sudo systemctl restart psiwars-web")
    print("  4. Open https://pwdev.simonious.com/combat in your browser")
    print()
    input("  Press Enter to begin...")

    results = []
    current_section = None
    total = len(TESTS)
    passes = 0
    fails = 0
    skipped = 0

    for i, (section, test_id, instruction, answer_type) in enumerate(TESTS):
        clear_screen()

        if section != current_section:
            current_section = section
            print(f"\n{'─' * 60}")
            print(f"  SECTION: {section}")
            print(f"{'─' * 60}")

        print(f"\n  Test {test_id}  ({i+1}/{total})")
        print(f"  {'─' * 40}")
        # Print instruction with indent
        for line in instruction.split('\n'):
            print(f"  {line}")

        answer = get_answer(answer_type)
        results.append((section, test_id, instruction.split('\n')[0], answer))

        if answer == 'Y':
            passes += 1
        elif answer == 'N':
            fails += 1
            # Ask for notes on failures
            note = input("  Notes on what went wrong (or Enter to skip): ").strip()
            if note:
                results[-1] = (section, test_id, instruction.split('\n')[0], f"N — {note}")

    # Generate report
    clear_screen()
    print("\n  Test complete! Generating report...\n")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("PSI-WARS WEB UI TEST RESULTS — v0.2.6")
    report_lines.append(f"Date: {timestamp}")
    report_lines.append(f"Total: {total}  Pass: {passes}  Fail: {fails}")
    report_lines.append("=" * 60)
    report_lines.append("")

    current_section = None
    for section, test_id, summary, answer in results:
        if section != current_section:
            current_section = section
            report_lines.append(f"\n--- {section} ---")
        report_lines.append(f"  [{test_id}] {answer:8s}  {summary}")

    report_lines.append("")
    report_lines.append("=" * 60)
    report_lines.append("END OF REPORT — Paste this to Claude")
    report_lines.append("=" * 60)

    report = "\n".join(report_lines)

    # Save to file
    report_path = "test_results.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\n  Report saved to: {report_path}")
    print(f"  Paste the contents of that file back to Claude.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Test interrupted. No report generated.")
        sys.exit(1)
