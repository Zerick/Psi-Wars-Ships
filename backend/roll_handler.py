# =============================================================================
# Psi-Wars Space Combat Simulator — roll_handler.py
# =============================================================================
# Wraps dice_engine.py. Parses [[XdY+Z]] expressions from message text,
# executes the roll, and returns structured result dicts.
# Does NOT broadcast — broadcasting is the caller's responsibility after
# GM review.
# =============================================================================
import re
import json
import logging
from dice_engine import roll_dice

log = logging.getLogger(__name__)

# Matches one or more [[...]] expressions in a message.
ROLL_PATTERN = re.compile(r'\[\[([^\]]+)\]\]')


def extract_rolls(text: str) -> list[str]:
    """Return a list of raw expressions found inside [[ ]] in text."""
    return ROLL_PATTERN.findall(text)


def process_roll(expression: str, rolled_by: str, author_id: str) -> dict:
    """
    Parse and execute a single dice expression (without [[ ]]).

    dice_engine.roll_dice() returns: (total, breakdown_str, is_verbose)

    breakdown_str looks like:  "2, 5, 1 = 8"   or   "14"   for a single die.
    We parse out the individual die values from the left-hand side of ' = '.

    Returns a dict ready to be stored as a log_entry (minus DB IDs / timestamps).
    """
    try:
        total, breakdown_str, _is_verbose = roll_dice(expression)

        if total == "Error":
            log.warning(f"Dice engine error for expression '{expression}': {breakdown_str}")
            return None

        # Parse individual die values from breakdown string.
        # Format examples:
        #   "2, 5, 1 = 8"   -> dice_results = [2, 5, 1]
        #   "14"             -> dice_results = [14]   (single die, no ' = ')
        #   "(3, 5) = 8"     -> dice_results = [3, 5]
        dice_results = _parse_dice_results(breakdown_str, total)

        return {
            "expression": expression,
            "breakdown": breakdown_str,
            "dice_results": json.dumps(dice_results),
            "total": int(total),
            "rolled_by": rolled_by,
            "author_id": author_id,
            "entry_type": "roll",
        }

    except Exception as e:
        log.exception(f"Unexpected error processing roll '{expression}': {e}")
        return None


def _parse_dice_results(breakdown_str: str, total) -> list:
    """
    Extract individual die values from the breakdown string produced by
    dice_engine.format_breakdown().

    The engine produces strings like:
        "2, 5, 1 = 8"
        "14"
        "(3, 5) = 8"
        "(2) = 2"
    """
    try:
        if ' = ' in breakdown_str:
            left = breakdown_str.split(' = ')[0]
            # Strip surrounding parens/braces
            left = left.strip('(){}')
            # Each token separated by ', '
            parts = [p.strip().strip('*').strip() for p in left.split(',')]
            # Filter to numeric-looking tokens (ignore struck-through dropped dice)
            nums = []
            for p in parts:
                # Dropped dice appear as (N) in the engine output
                clean = p.strip('()')
                try:
                    nums.append(int(clean))
                except ValueError:
                    pass
            return nums if nums else [int(total)]
        else:
            return [int(total)]
    except Exception:
        return [int(total)]
