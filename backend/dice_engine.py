#!/usr/bin/env python3
# =============================================================================
# SquareBracketDiceBot (SBDB) — dice_engine.py
# =============================================================================
# Author:   Simonious A.K.A. Zerick
# Contact:  simonious@gmail.com
# GitHub:   https://github.com/Zerick/SquareBracketDiceBot
# License:  MIT
# -----------------------------------------------------------------------------
# Core dice rolling engine. Handles query translation, batch rolling,
# deterministic min/max modes for testing, verbose flag parsing, and
# result formatting.
# =============================================================================
import re
import d20

def translate_query(query):
    """
    Translates shorthand.
    Converts both 'dh' and 'dl' into 'kl' and 'kh' respectively.
    Converts 'adv' and 'dis' suffixes to keep-highest/lowest notation.
    Note: 'x' is intentionally NOT converted here — it is handled as a
    summing batch operator in roll_dice() before this function is called.
    """
    clean_q = query.replace(" ", "").lower()

    # Advantage/Disadvantage shorthand
    # 1dXa -> 2dXkh1 (advantage: roll twice, keep highest)
    # 1dXd -> 2dXkl1 (disadvantage: roll twice, keep lowest)
    adv_match = re.match(r'^1d(\d+)a$', clean_q)
    if adv_match:
        return f"2d{adv_match.group(1)}kh1"

    dis_match = re.match(r'^1d(\d+)d$', clean_q)
    if dis_match:
        return f"2d{dis_match.group(1)}kl1"

    # regex to find: (Count)d(Size)(dh or dl)(Number)
    # Example: 6d8dl2
    drop_match = re.search(r'(\d+)d(\d+)(d[hl])(\d+)', clean_q)

    if drop_match:
        count, size, type_code, amount = drop_match.groups()

        # Calculate how many to keep
        # If you have 6 dice and drop 2, you keep 4.
        keep_count = max(0, int(count) - int(amount))

        # Invert the logic:
        # 'dh' (Drop High) becomes 'kl' (Keep Low)
        # 'dl' (Drop Low) becomes 'kh' (Keep High)
        new_type = "kl" if "h" in type_code else "kh"

        return f"{count}d{size}{new_type}{keep_count}"

    return clean_q


def force_deterministic(query, mode):
    """
    Replaces dice with fixed dice that d20 treats as individual rolls.
    '5d6kh3' -> '(1d1+5,1d1+5,1d1+5,1d1+5,1d1+5)kh3'
    """
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
        # If the dice part is just the total on its own (single die, no pool),
        # don't repeat it as "9 = 9" — just return the total alone.
        if dice_part.strip() == str(total):
            return str(total)
        return f"{dice_part} = {total}"
    return str(getattr(res, 'total', res))

def parse_verbose_flag(query):
    """
    Strips a trailing 'v' from a roll query and returns (clean_query, is_verbose).
    Handles three cases:
      - Preceded by a digit:  '1d20v'   -> ('1d20', True)
      - Advantage verbose:    '1d20av'  -> ('1d20a', True)
      - Disadvantage verbose: '1d20dv'  -> ('1d20d', True)
    Examples:
        '1d20v'   -> ('1d20', True)
        '5d6kh3v' -> ('5d6kh3', True)
        '10x3d6v' -> ('10x3d6', True)
        '1d20av'  -> ('1d20a', True)
        '1d20dv'  -> ('1d20d', True)
        '1d20'    -> ('1d20', False)
    """
    stripped = query.strip()
    if stripped.endswith('v') and len(stripped) > 1:
        preceding = stripped[-2]
        if preceding.isdigit() or preceding in ('a', 'd'):
            return stripped[:-1], True
    return stripped, False

def roll_dice(query, mode=None):
    query = query.lower().replace(' ', '')

    # Detect and strip the verbose flag before any other processing
    query, is_verbose = parse_verbose_flag(query)

    try:
        # 1a. SUMMING BATCH: Nx (e.g. 10x3d6)
        # Rolls the expression N times and returns the GRAND TOTAL.
        # Must be checked before translate_query so 'x' isn't consumed.
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

        # 1b. INDIVIDUAL BATCH: Nt / Nb / N# (e.g. 10t3d6)
        # Rolls the expression N times and returns EACH RESULT separately.
        batch_match = re.split(r'[#tb]', query, maxsplit=1)
        if len(batch_match) == 2:
            times_str, expr = batch_match
            count = max(1, min(int(times_str), 20))
            expr = translate_query(expr)
            if mode:
                expr = force_deterministic(expr, mode)
            rolls = [d20.roll(expr) for _ in range(count)]
            totals = [str(getattr(r, 'total', r)) for r in rolls]
            return ", ".join(totals), " | ".join([format_breakdown(r) for r in rolls]), is_verbose

        # 2. STANDARD ROLLS
        processed_q = translate_query(query)
        if mode:
            processed_q = force_deterministic(processed_q, mode)
        result = d20.roll(processed_q)
        return getattr(result, 'total', result), format_breakdown(result), is_verbose

    except Exception as e:
        return "Error", f"{e}", is_verbose
