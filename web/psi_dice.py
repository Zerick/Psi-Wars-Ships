"""
Psi-Wars Dice Engine — Server-side port of SquareBracketDiceBot
Handles: basic rolls, keep/drop, advantage/disadvantage, batch (x/t/b/#),
math modifiers, verbose flag, stats command, help, about.
Uses the d20 library for parsing and rolling.
"""

import re
import statistics
try:
    import d20
    HAS_D20 = True
except ImportError:
    HAS_D20 = False


# ---------------------------------------------------------------------------
# Help / About text (adapted from SBDB for web context)
# ---------------------------------------------------------------------------
HELP_TEXT = """🎲 Psi-Wars Dice Roller Help 🎲

Basic Rolls:
  [[2d6]]         Roll two 6-sided dice
  [[1d20]]        Roll one 20-sided die

Advanced Modifiers:
  [[1d20a]]       Advantage (roll twice, keep highest)
  [[1d20d]]       Disadvantage (roll twice, keep lowest)
  [[5d6kh3]]      Keep Highest 3
  [[4d20kl2]]     Keep Lowest 2
  [[6d8dh2]]      Drop Highest 2
  [[7d10dl3]]     Drop Lowest 3

Multiple Rolls:
  [[10x3d6]]      Roll 3d6 ten times and sum results
  [[5x2d20kh1]]   Roll 2d20kh1 five times, sum results
  [[10t3d6]]      Roll 3d6 ten times, show each result
  use t, b, or # for individual results

Combining with Math:
  [[5d6kh3+2]]    Keep highest 3, then add 2
  [[4*2d20kl1]]   Keep lowest 1, then multiply by 4

Verbose Mode:
  Add v to any roll for full breakdown:
  [[1d20v]]  [[5d6kh3v]]  [[10x3d6v]]

Dice Statistics:
  [[stats 1d20]]      Show min, max, mean, median, std dev
  [[stats 5d6kh3+2]]  Works with any valid expression

Type [[help]] to see this again.
Dice engine: SquareBracketDiceBot by Zerick/Simonious"""

ABOUT_TEXT = """SquareBracketDiceBot (SBDB)
Bringing inline dice-rolling to the Psi-Wars Combat Simulator.

Born from the idea that dice rolling shouldn't interrupt the flow of play.
Roll naturally using [[square brackets]] mid-sentence.

Author: Simonious A.K.A. Zerick
GitHub: https://github.com/Zerick/SquareBracketDiceBot
License: MIT"""


# ---------------------------------------------------------------------------
# Translation layer (from SBDB dice_engine.py)
# ---------------------------------------------------------------------------
def translate_query(query):
    clean_q = query.replace(" ", "").lower()

    # Advantage: 1dXa -> 2dXkh1
    adv_match = re.match(r'^1d(\d+)a$', clean_q)
    if adv_match:
        return f"2d{adv_match.group(1)}kh1"

    # Disadvantage: 1dXd -> 2dXkl1
    dis_match = re.match(r'^1d(\d+)d$', clean_q)
    if dis_match:
        return f"2d{dis_match.group(1)}kl1"

    # Drop high/low -> keep low/high
    drop_match = re.search(r'(\d+)d(\d+)(d[hl])(\d+)', clean_q)
    if drop_match:
        count, size, type_code, amount = drop_match.groups()
        keep_count = max(0, int(count) - int(amount))
        new_type = "kl" if "h" in type_code else "kh"
        return f"{count}d{size}{new_type}{keep_count}"

    return clean_q


def force_deterministic(query, mode):
    def replace_dice(match):
        count = int(match.group(1))
        size = int(match.group(2))
        if mode == "min":
            die_str = "1d1"
        else:
            die_str = f"(1d1+{size-1})"
        return "(" + ",".join([die_str] * count) + ")"
    return re.sub(r'(\d+)d(\d+)', replace_dice, query)


def format_breakdown(res):
    raw_str = str(res)
    inner_match = re.search(r'[\({](.*?)[\)}]', raw_str)
    if inner_match:
        dice_part = inner_match.group(1)
        dice_part = re.sub(r'~~(.*?)~~', r'(\1)', dice_part)
        dice_part = dice_part.replace('*', '')
        total = getattr(res, 'total', res)
        if dice_part.strip() == str(total):
            return str(total)
        return f"{dice_part} = {total}"
    return str(getattr(res, 'total', res))


def parse_verbose_flag(query):
    stripped = query.strip()
    if stripped.endswith('v') and len(stripped) > 1:
        preceding = stripped[-2]
        if preceding.isdigit() or preceding in ('a', 'd'):
            return stripped[:-1], True
    return stripped, False


# ---------------------------------------------------------------------------
# Main roll function
# ---------------------------------------------------------------------------
def roll_dice(query, mode=None):
    """
    Roll dice using SBDB syntax.
    Returns: (total, breakdown_str, is_verbose)
    total can be int, str of comma-separated ints, or "Error"
    """
    if not HAS_D20:
        return _roll_dice_fallback(query)

    query = query.lower().replace(' ', '')
    query, is_verbose = parse_verbose_flag(query)

    try:
        # Summing batch: Nx
        x_match = re.split(r'x', query, maxsplit=1)
        if len(x_match) == 2 and x_match[0].isdigit():
            times_str, expr = x_match
            count = max(1, min(int(times_str), 20))
            expr = translate_query(expr)
            if mode:
                expr = force_deterministic(expr, mode)
            rolls = [d20.roll(expr) for _ in range(count)]
            grand_total = sum(getattr(r, 'total', r) for r in rolls)
            breakdown_str = " | ".join([format_breakdown(r) for r in rolls]) + f" | = {grand_total}"
            return grand_total, breakdown_str, is_verbose

        # Individual batch: Nt / Nb / N#
        batch_match = re.split(r'[#tb]', query, maxsplit=1)
        if len(batch_match) == 2 and batch_match[0].isdigit():
            times_str, expr = batch_match
            count = max(1, min(int(times_str), 20))
            expr = translate_query(expr)
            if mode:
                expr = force_deterministic(expr, mode)
            rolls = [d20.roll(expr) for _ in range(count)]
            totals = [str(getattr(r, 'total', r)) for r in rolls]
            return ", ".join(totals), " | ".join([format_breakdown(r) for r in rolls]), is_verbose

        # Standard roll
        processed_q = translate_query(query)
        if mode:
            processed_q = force_deterministic(processed_q, mode)
        result = d20.roll(processed_q)
        return getattr(result, 'total', result), format_breakdown(result), is_verbose

    except Exception as e:
        return "Error", str(e), is_verbose


def _roll_dice_fallback(query):
    """Fallback roller when d20 library is not available. Handles NdX+M only."""
    import random
    query = query.lower().replace(' ', '')
    query, is_verbose = parse_verbose_flag(query)

    match = re.match(r'^(\d+)d(\d+)([+-]\d+)?$', query)
    if not match:
        return "Error", f"Cannot parse: {query} (d20 library not installed)", is_verbose

    count = min(int(match.group(1)), 100)
    sides = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    mod_str = f"+{modifier}" if modifier > 0 else str(modifier) if modifier < 0 else ""
    breakdown = f"[{', '.join(str(r) for r in rolls)}]{mod_str} = {total}"
    return total, breakdown, is_verbose


# ---------------------------------------------------------------------------
# Stats command
# ---------------------------------------------------------------------------
def get_stats(expression, iterations=10000):
    """Run an expression many times and return statistical summary."""
    results = []
    for _ in range(iterations):
        total, _, _ = roll_dice(expression)
        if total == "Error":
            return None
        if isinstance(total, str):
            # batch results like "3, 5, 2" — take first
            try:
                total = int(total.split(",")[0].strip())
            except ValueError:
                return None
        results.append(int(total))

    return {
        "expression": expression,
        "iterations": iterations,
        "min": min(results),
        "max": max(results),
        "mean": round(statistics.mean(results), 2),
        "median": round(statistics.median(results), 2),
        "std_dev": round(statistics.stdev(results), 2) if len(results) > 1 else 0,
    }


# ---------------------------------------------------------------------------
# Command dispatcher — processes a single [[...]] expression
# ---------------------------------------------------------------------------
def process_command(expression):
    """
    Process a [[...]] command.
    Returns dict: { "type": "roll"|"help"|"about"|"stats"|"error", ... }
    """
    expr = expression.strip()
    expr_lower = expr.lower()

    if expr_lower == "help":
        return {"type": "help", "text": HELP_TEXT}

    if expr_lower == "about":
        return {"type": "about", "text": ABOUT_TEXT}

    if expr_lower.startswith("stats "):
        stat_expr = expr[6:].strip()
        stats = get_stats(stat_expr, iterations=5000)
        if stats is None:
            return {"type": "error", "text": f"Cannot compute stats for: {stat_expr}"}
        return {
            "type": "stats",
            "expression": stat_expr,
            "min": stats["min"],
            "max": stats["max"],
            "mean": stats["mean"],
            "median": stats["median"],
            "std_dev": stats["std_dev"],
            "iterations": stats["iterations"],
            "text": (
                f"Stats for {stat_expr} ({stats['iterations']} iterations):\n"
                f"  Min: {stats['min']}  Max: {stats['max']}\n"
                f"  Mean: {stats['mean']}  Median: {stats['median']}\n"
                f"  Std Dev: {stats['std_dev']}"
            ),
        }

    # It's a dice roll
    total, breakdown, is_verbose = roll_dice(expr)
    if total == "Error":
        return {"type": "error", "text": f"Dice error: {breakdown}"}

    return {
        "type": "roll",
        "expression": expr,
        "total": total,
        "breakdown": breakdown,
        "verbose": is_verbose,
    }
