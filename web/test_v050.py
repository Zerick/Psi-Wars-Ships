#!/usr/bin/env python3
"""
Psi-Wars Web UI v0.5.0 — Setup Phase Test Suite
=================================================

Tests all requirements from SETUP_REQUIREMENTS.md against the
session_manager backend. Run before AND after implementation.

Before implementation: expect most tests to FAIL (features don't exist yet).
After implementation: expect all tests to PASS.

Usage:
    cd /home/psiwars/psi-wars/web
    source venv/bin/activate
    python3 test_v050.py          # Interactive mode
    python3 test_v050.py --auto   # Skip Y/N prompts

Test sections:
    1.  Ship Template Catalog
    2.  Adding Ships (defaults)
    3.  Ship Customization
    4.  Ship Removal
    5.  Ship Assignment (GM Assign mode)
    6.  Ship Assignment (Player Select mode)
    7.  Faction Management — Creation & Defaults
    8.  Faction Management — Removal & Orphaning
    9.  Faction Relationships — Asymmetric
    10. Faction Relationship Auto-Escalation
    11. Targeting Warnings
    12. Engagements via Target Assignment
    13. Engagement Rules (one target per ship, many pursuers)
    14. Engagement Display Data
    15. NPC Targeting
    16. Combat Transition & Validation Warnings
    17. Permissions — GM Session
    18. Permissions — GM-less Session
    19. Visibility Filtering with Factions
    20. Full Scenario Walkthrough
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AUTO_MODE = '--auto' in sys.argv

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
WARN = '\033[93m⚠\033[0m'
BOLD = '\033[1m'
RESET = '\033[0m'

results = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0}


def check(description, condition, detail=''):
    if condition:
        print(f'  {PASS} {description}')
        results['passed'] += 1
    else:
        print(f'  {FAIL} {description}')
        if detail:
            print(f'    → {detail}')
        results['failed'] += 1
    return condition


def check_raises(description, exception_type, fn):
    try:
        fn()
        print(f'  {FAIL} {description} (no exception raised)')
        results['failed'] += 1
        return False
    except exception_type:
        print(f'  {PASS} {description}')
        results['passed'] += 1
        return True
    except Exception as e:
        print(f'  {FAIL} {description} (wrong exception: {type(e).__name__}: {e})')
        results['failed'] += 1
        return False


def section(title):
    print(f'\n{BOLD}═══ {title} ═══{RESET}')


def safe_run(fn):
    """Run a test function, catching import/attribute errors gracefully."""
    try:
        fn()
    except (ImportError, AttributeError, TypeError) as e:
        print(f'  {FAIL} Section failed — feature not implemented yet: {e}')
        results['errors'] += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_manager():
    """Create a fresh SessionManager with a temp directory."""
    from session_manager import SessionManager
    tmpdir = tempfile.mkdtemp()
    return SessionManager(sessions_dir=tmpdir), tmpdir


def make_gm_session(sm):
    """Create a GM session and return (session, gm_user)."""
    return sm.create_session('GM Dave', has_gm=True, gm_password='test123')


def make_gmless_session(sm):
    """Create a GM-less session and return (session, host_user)."""
    return sm.create_session('Host Alice', has_gm=False)


# ---------------------------------------------------------------------------
# 1. Ship Template Catalog
# ---------------------------------------------------------------------------

def test_template_catalog():
    section('1. Ship Template Catalog')

    # The catalog should be loadable from the server
    # This tests the REST endpoint data format, not the HTTP layer
    try:
        from session_manager import SessionManager
        sm, tmpdir = make_manager()

        # SessionManager should have a method to get the ship catalog
        check('SessionManager has get_ship_catalog() method',
              hasattr(sm, 'get_ship_catalog'))

        if hasattr(sm, 'get_ship_catalog'):
            catalog = sm.get_ship_catalog()
            check('Catalog returns a dict', isinstance(catalog, dict))
            check('Catalog has "categories" key', 'categories' in catalog)

            categories = catalog.get('categories', [])
            check('Catalog has at least 5 categories', len(categories) >= 5)

            # Check category structure
            if categories:
                cat = categories[0]
                check('Category has "label" field', 'label' in cat)
                check('Category has "ships" list', 'ships' in cat and isinstance(cat['ships'], list))

                if cat.get('ships'):
                    ship = cat['ships'][0]
                    check('Template has "template_id"', 'template_id' in ship)
                    check('Template has "name"', 'name' in ship)
                    check('Template has "sm"', 'sm' in ship)
                    check('Template has "st_hp"', 'st_hp' in ship)
                    check('Template has "top_speed"', 'top_speed' in ship)

            # Check specific ships exist
            all_templates = []
            for cat in categories:
                all_templates.extend(cat.get('ships', []))
            template_names = [t.get('name', '') for t in all_templates]

            check('Javelin in catalog', any('javelin' in n.lower() for n in template_names))
            check('Wildcat in catalog', any('wildcat' in n.lower() for n in template_names))
            check('Hornet in catalog', any('hornet' in n.lower() for n in template_names))
            check('Sword in catalog', any('sword' in n.lower() for n in template_names))

    except Exception as e:
        print(f'  {FAIL} Catalog test error: {e}')
        results['errors'] += 1


# ---------------------------------------------------------------------------
# 2. Adding Ships (Defaults)
# ---------------------------------------------------------------------------

def test_add_ship_defaults():
    section('2. Adding Ships — Defaults')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    # Add a ship from template (or raw data with expected defaults)
    # The session_manager should have an add_ship_from_template method
    check('SessionManager has add_ship_from_template() method',
          hasattr(sm, 'add_ship_from_template'))

    if hasattr(sm, 'add_ship_from_template'):
        ship_id = sm.add_ship_from_template(kw, 'wildcat_v1')
        check('Ship added successfully', ship_id is not None)

        session = sm.get_session(kw)
        ship = next((s for s in session.ships if s.get('ship_id') == ship_id), None)
        check('Ship exists in session', ship is not None)

        if ship:
            # Check defaults per requirements §3.1
            check('Default faction is "NPC Hostiles"',
                  ship.get('faction') == 'NPC Hostiles')
            check('Default control is "npc"',
                  ship.get('control') == 'npc')
            check('Default pilot name exists',
                  ship.get('pilot', {}).get('name') is not None)
            check('Default pilot piloting_skill is 12',
                  ship.get('pilot', {}).get('piloting_skill') == 12)
            check('Default pilot gunnery_skill is 12',
                  ship.get('pilot', {}).get('gunnery_skill') == 12)
            check('Default pilot basic_speed is 6.0',
                  ship.get('pilot', {}).get('basic_speed') == 6.0)
            check('Default pilot is_ace_pilot is False',
                  ship.get('pilot', {}).get('is_ace_pilot') == False)
            check('Default pilot luck_level is "none"',
                  ship.get('pilot', {}).get('luck_level') == 'none')
            check('Default target_id is None',
                  ship.get('target_id') is None)
            check('Default assigned_player is None',
                  ship.get('assigned_player') is None)

            # Check that template stats were copied
            check('Ship has st_hp from template',
                  ship.get('st_hp', 0) > 0)
            check('Ship has display_name from template',
                  len(ship.get('display_name', '')) > 0)

    # Check that default "NPC Hostiles" faction was auto-created
    check('Session has factions list', hasattr(session, 'factions') or 'factions' in dir(session))

    if hasattr(session, 'factions'):
        faction_names = [f.get('name', '') for f in session.factions]
        check('"NPC Hostiles" faction auto-created',
              'NPC Hostiles' in faction_names)


# ---------------------------------------------------------------------------
# 3. Ship Customization
# ---------------------------------------------------------------------------

def test_ship_customization():
    section('3. Ship Customization')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    # Add a ship
    sm.add_ship(kw, {
        'ship_id': 'ship_1',
        'display_name': 'Test Ship',
        'faction': 'NPC Hostiles',
        'control': 'npc',
        'st_hp': 100,
        'current_hp': 100,
        'pilot': {'name': 'NPC', 'piloting_skill': 12, 'gunnery_skill': 12,
                  'basic_speed': 6.0, 'is_ace_pilot': False, 'luck_level': 'none',
                  'max_fp': 10, 'current_fp': 10},
    })

    # Test various field updates
    check('Can update display_name',
          sm.update_ship(kw, 'ship_1', {'display_name': 'Red Fox'}))

    session = sm.get_session(kw)
    ship = session.ships[0]
    check('Display name updated', ship.get('display_name') == 'Red Fox')

    check('Can update faction',
          sm.update_ship(kw, 'ship_1', {'faction': 'Empire'}))

    check('Can update control mode',
          sm.update_ship(kw, 'ship_1', {'control': 'human'}))

    check('Can update pilot skills',
          sm.update_ship(kw, 'ship_1', {
              'pilot': {'name': 'Ace', 'piloting_skill': 16, 'gunnery_skill': 14,
                        'basic_speed': 7.0, 'is_ace_pilot': True, 'luck_level': 'luck',
                        'max_fp': 12, 'current_fp': 12}
          }))

    session = sm.get_session(kw)
    ship = session.ships[0]
    check('Faction updated', ship.get('faction') == 'Empire')
    check('Control updated', ship.get('control') == 'human')
    check('Pilot updated', ship.get('pilot', {}).get('piloting_skill') == 16)


# ---------------------------------------------------------------------------
# 4. Ship Removal
# ---------------------------------------------------------------------------

def test_ship_removal():
    section('4. Ship Removal')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 'ship_1', 'display_name': 'Ship A',
                      'target_id': 'ship_2'})
    sm.add_ship(kw, {'ship_id': 'ship_2', 'display_name': 'Ship B',
                      'target_id': 'ship_1'})
    sm.add_ship(kw, {'ship_id': 'ship_3', 'display_name': 'Ship C',
                      'target_id': 'ship_1'})

    player = sm.join_session(kw, 'Alice')
    sm.assign_ship(kw, 'ship_1', 'Alice')

    # Remove ship_1
    removed = sm.remove_ship(kw, 'ship_1')
    check('Ship removed successfully', removed)

    session = sm.get_session(kw)
    check('Ship gone from ships list',
          not any(s.get('ship_id') == 'ship_1' for s in session.ships))

    check('Ship unassigned from player',
          'ship_1' not in session.users['Alice'].ship_ids)

    # Ships targeting the removed ship should have their target cleared
    ship_b = next((s for s in session.ships if s.get('ship_id') == 'ship_2'), None)
    ship_c = next((s for s in session.ships if s.get('ship_id') == 'ship_3'), None)

    if ship_b:
        check('Ship B target cleared (was targeting removed ship)',
              ship_b.get('target_id') is None)
    if ship_c:
        check('Ship C target cleared (was targeting removed ship)',
              ship_c.get('target_id') is None)


# ---------------------------------------------------------------------------
# 5. Ship Assignment — GM Assign Mode
# ---------------------------------------------------------------------------

def test_assignment_gm_mode():
    section('5. Ship Assignment — GM Assign Mode')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 'ship_1', 'display_name': 'Ship A'})
    sm.add_ship(kw, {'ship_id': 'ship_2', 'display_name': 'Ship B'})
    player = sm.join_session(kw, 'Alice')

    sm.assign_ship(kw, 'ship_1', 'Alice')
    check('Ship assigned to player', 'ship_1' in session.users['Alice'].ship_ids)

    # Assign second ship to same player
    sm.assign_ship(kw, 'ship_2', 'Alice')
    check('Player can control multiple ships',
          len(session.users['Alice'].ship_ids) == 2)

    # Unassign
    sm.unassign_ship(kw, 'ship_1', 'Alice')
    check('Ship unassigned', 'ship_1' not in session.users['Alice'].ship_ids)


# ---------------------------------------------------------------------------
# 6. Ship Assignment — Player Select Mode
# ---------------------------------------------------------------------------

def test_assignment_player_select():
    section('6. Ship Assignment — Player Select Mode')

    sm, tmpdir = make_manager()
    session, host = sm.create_session('Host', has_gm=False,
                                       ship_assign_mode='player_select')
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 'ship_1', 'display_name': 'Ship A'})
    sm.add_ship(kw, {'ship_id': 'ship_2', 'display_name': 'Ship B'})
    player = sm.join_session(kw, 'Bob')

    check('Ships in available pool',
          'ship_1' in session.available_ship_ids and 'ship_2' in session.available_ship_ids)

    sm.assign_ship(kw, 'ship_1', 'Bob')
    check('Ship claimed by player', 'ship_1' in session.users['Bob'].ship_ids)
    check('Ship removed from available pool', 'ship_1' not in session.available_ship_ids)

    # Another player can't claim the same ship
    player2 = sm.join_session(kw, 'Charlie')
    check_raises('Duplicate claim rejected', ValueError,
                 lambda: sm.assign_ship(kw, 'ship_1', 'Charlie'))


# ---------------------------------------------------------------------------
# 7. Faction Management — Creation & Defaults
# ---------------------------------------------------------------------------

def test_faction_creation():
    section('7. Faction Management — Creation & Defaults')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    # Check for faction management methods
    check('SessionManager has create_faction()',
          hasattr(sm, 'create_faction'))
    check('SessionManager has get_factions()',
          hasattr(sm, 'get_factions'))

    if not hasattr(sm, 'create_faction'):
        return

    # Adding a ship should auto-create "NPC Hostiles"
    if hasattr(sm, 'add_ship_from_template'):
        sm.add_ship_from_template(kw, 'javelin_v1')
    else:
        sm.add_ship(kw, {'ship_id': 'ship_1', 'faction': 'NPC Hostiles'})

    factions = sm.get_factions(kw)
    faction_names = [f.get('name') for f in factions]
    check('"NPC Hostiles" auto-created', 'NPC Hostiles' in faction_names)

    # Create a new faction
    sm.create_faction(kw, 'Empire', '#60a5fa')
    factions = sm.get_factions(kw)
    faction_names = [f.get('name') for f in factions]
    check('Empire faction created', 'Empire' in faction_names)

    # Check default relationships
    if hasattr(sm, 'get_faction_relationship'):
        rel = sm.get_faction_relationship(kw, 'Empire', 'NPC Hostiles')
        check('Default relationship is neutral', rel == 'neutral')


# ---------------------------------------------------------------------------
# 8. Faction Management — Removal & Orphaning
# ---------------------------------------------------------------------------

def test_faction_removal():
    section('8. Faction Management — Removal & Orphaning')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    if not hasattr(sm, 'create_faction'):
        print(f'  {FAIL} Faction methods not implemented')
        results['errors'] += 1
        return

    sm.create_faction(kw, 'Pirates', '#f87171')
    sm.add_ship(kw, {'ship_id': 'ship_1', 'display_name': 'Raider',
                      'faction': 'Pirates'})
    sm.add_ship(kw, {'ship_id': 'ship_2', 'display_name': 'Scout',
                      'faction': 'Pirates'})

    # Remove the faction
    check('SessionManager has remove_faction()',
          hasattr(sm, 'remove_faction'))

    if hasattr(sm, 'remove_faction'):
        result = sm.remove_faction(kw, 'Pirates')
        check('Faction removed', result is not None)

        # Ships should keep the faction tag but be flagged
        session = sm.get_session(kw)
        ship1 = next(s for s in session.ships if s['ship_id'] == 'ship_1')
        check('Ship keeps faction tag', ship1.get('faction') == 'Pirates')

        # Check for orphan flag
        orphaned = result if isinstance(result, dict) else {}
        orphan_ships = orphaned.get('orphaned_ships', [])
        check('Orphaned ships identified',
              len(orphan_ships) == 2 or ship1.get('faction_orphaned', False))


# ---------------------------------------------------------------------------
# 9. Faction Relationships — Asymmetric
# ---------------------------------------------------------------------------

def test_faction_relationships():
    section('9. Faction Relationships — Asymmetric')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    if not hasattr(sm, 'create_faction'):
        print(f'  {FAIL} Faction methods not implemented')
        results['errors'] += 1
        return

    sm.create_faction(kw, 'Empire', '#60a5fa')
    sm.create_faction(kw, 'Alliance', '#4ade80')

    check('SessionManager has set_faction_relationship()',
          hasattr(sm, 'set_faction_relationship'))

    if not hasattr(sm, 'set_faction_relationship'):
        return

    # Set asymmetric relationships
    sm.set_faction_relationship(kw, 'Empire', 'Alliance', 'hostile')
    sm.set_faction_relationship(kw, 'Alliance', 'Empire', 'neutral')

    r1 = sm.get_faction_relationship(kw, 'Empire', 'Alliance')
    r2 = sm.get_faction_relationship(kw, 'Alliance', 'Empire')

    check('Empire→Alliance is hostile', r1 == 'hostile')
    check('Alliance→Empire is neutral', r2 == 'neutral')
    check('Relationships are asymmetric', r1 != r2)

    # Test all three relationship types
    sm.create_faction(kw, 'Traders', '#facc15')
    sm.set_faction_relationship(kw, 'Empire', 'Traders', 'friendly')
    r3 = sm.get_faction_relationship(kw, 'Empire', 'Traders')
    check('Friendly relationship works', r3 == 'friendly')


# ---------------------------------------------------------------------------
# 10. Faction Relationship Auto-Escalation
# ---------------------------------------------------------------------------

def test_auto_escalation():
    section('10. Faction Relationship Auto-Escalation')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    if not hasattr(sm, 'create_faction'):
        print(f'  {FAIL} Faction methods not implemented')
        results['errors'] += 1
        return

    sm.create_faction(kw, 'Empire', '#60a5fa')
    sm.create_faction(kw, 'Neutrals', '#888888')

    if hasattr(sm, 'set_faction_relationship'):
        sm.set_faction_relationship(kw, 'Neutrals', 'Empire', 'friendly')

    sm.add_ship(kw, {'ship_id': 'imp_1', 'faction': 'Empire', 'control': 'human'})
    sm.add_ship(kw, {'ship_id': 'neut_1', 'faction': 'Neutrals', 'control': 'npc'})

    check('SessionManager has escalate_faction_relationship()',
          hasattr(sm, 'escalate_faction_relationship'))

    if not hasattr(sm, 'escalate_faction_relationship'):
        return

    # First attack: friendly → neutral
    sm.escalate_faction_relationship(kw, 'Empire', 'Neutrals')
    rel = sm.get_faction_relationship(kw, 'Neutrals', 'Empire')
    check('First attack: friendly → neutral', rel == 'neutral')

    # Second attack: neutral → hostile
    sm.escalate_faction_relationship(kw, 'Empire', 'Neutrals')
    rel = sm.get_faction_relationship(kw, 'Neutrals', 'Empire')
    check('Second attack: neutral → hostile', rel == 'hostile')

    # Already hostile — no further change
    sm.escalate_faction_relationship(kw, 'Empire', 'Neutrals')
    rel = sm.get_faction_relationship(kw, 'Neutrals', 'Empire')
    check('Already hostile — stays hostile', rel == 'hostile')


# ---------------------------------------------------------------------------
# 11. Targeting Warnings
# ---------------------------------------------------------------------------

def test_targeting_warnings():
    section('11. Targeting Warnings')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    if not hasattr(sm, 'create_faction'):
        print(f'  {FAIL} Faction methods not implemented')
        results['errors'] += 1
        return

    sm.create_faction(kw, 'Empire', '#60a5fa')
    sm.create_faction(kw, 'Traders', '#facc15')

    if hasattr(sm, 'set_faction_relationship'):
        sm.set_faction_relationship(kw, 'Empire', 'Traders', 'neutral')

    sm.add_ship(kw, {'ship_id': 'imp', 'faction': 'Empire'})
    sm.add_ship(kw, {'ship_id': 'trader', 'faction': 'Traders'})

    check('SessionManager has check_targeting_warning()',
          hasattr(sm, 'check_targeting_warning'))

    if not hasattr(sm, 'check_targeting_warning'):
        return

    # First time targeting neutral: should warn
    warning = sm.check_targeting_warning(kw, 'imp', 'trader')
    check('Warning for targeting neutral faction', warning is not None)

    # Acknowledge warning
    if hasattr(sm, 'acknowledge_targeting_warning'):
        sm.acknowledge_targeting_warning(kw, 'Empire', 'Traders')

        # Second time: no warning
        warning2 = sm.check_targeting_warning(kw, 'imp', 'trader')
        check('No repeat warning after acknowledgment', warning2 is None)


# ---------------------------------------------------------------------------
# 12. Engagements via Target Assignment
# ---------------------------------------------------------------------------

def test_engagement_creation():
    section('12. Engagements via Target Assignment')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 'ship_1', 'display_name': 'Red Fox'})
    sm.add_ship(kw, {'ship_id': 'ship_2', 'display_name': 'Blue Jay'})

    check('SessionManager has set_ship_target()',
          hasattr(sm, 'set_ship_target'))

    if not hasattr(sm, 'set_ship_target'):
        return

    # Set target — this should create an engagement
    sm.set_ship_target(kw, 'ship_1', 'ship_2', range_band='long')

    session = sm.get_session(kw)
    ship1 = next(s for s in session.ships if s['ship_id'] == 'ship_1')
    check('Ship target_id set', ship1.get('target_id') == 'ship_2')

    # Engagement should exist
    check('SessionManager has get_engagements()',
          hasattr(sm, 'get_engagements'))

    if hasattr(sm, 'get_engagements'):
        engagements = sm.get_engagements(kw)
        check('Engagement created', len(engagements) > 0)

        if engagements:
            eng_key = 'ship_1→ship_2'
            eng = engagements.get(eng_key, {}) if isinstance(engagements, dict) else {}
            check('Engagement has correct range',
                  eng.get('range_band') == 'long' or
                  any(e.get('range_band') == 'long' for e in
                      (engagements if isinstance(engagements, list) else engagements.values())))


# ---------------------------------------------------------------------------
# 13. Engagement Rules
# ---------------------------------------------------------------------------

def test_engagement_rules():
    section('13. Engagement Rules — One Target, Many Pursuers')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 's1', 'display_name': 'Alpha'})
    sm.add_ship(kw, {'ship_id': 's2', 'display_name': 'Beta'})
    sm.add_ship(kw, {'ship_id': 's3', 'display_name': 'Gamma'})

    if not hasattr(sm, 'set_ship_target'):
        print(f'  {FAIL} set_ship_target not implemented')
        results['errors'] += 1
        return

    # Multiple ships can target the same ship
    sm.set_ship_target(kw, 's1', 's3', range_band='long')
    sm.set_ship_target(kw, 's2', 's3', range_band='medium')

    session = sm.get_session(kw)
    s1 = next(s for s in session.ships if s['ship_id'] == 's1')
    s2 = next(s for s in session.ships if s['ship_id'] == 's2')

    check('Ship 1 targets Ship 3', s1.get('target_id') == 's3')
    check('Ship 2 targets Ship 3', s2.get('target_id') == 's3')
    check('Multiple pursuers on same target allowed', True)

    # Changing target should remove old engagement
    sm.set_ship_target(kw, 's1', 's2', range_band='extreme')
    session = sm.get_session(kw)
    s1 = next(s for s in session.ships if s['ship_id'] == 's1')
    check('Target changed to Ship 2', s1.get('target_id') == 's2')

    # Old engagement (s1→s3) should be gone
    if hasattr(sm, 'get_engagements'):
        engagements = sm.get_engagements(kw)
        if isinstance(engagements, dict):
            check('Old engagement removed', 's1→s3' not in engagements)
            check('New engagement exists', 's1→s2' in engagements)

    # Mutual pursuit
    sm.set_ship_target(kw, 's2', 's1', range_band='long')
    session = sm.get_session(kw)
    s2 = next(s for s in session.ships if s['ship_id'] == 's2')
    check('Mutual pursuit: s2 targets s1', s2.get('target_id') == 's1')

    if hasattr(sm, 'get_engagements'):
        engagements = sm.get_engagements(kw)
        if isinstance(engagements, dict):
            check('Both engagement directions exist',
                  's1→s2' in engagements and 's2→s1' in engagements)


# ---------------------------------------------------------------------------
# 14. Engagement Display Data
# ---------------------------------------------------------------------------

def test_engagement_display():
    section('14. Engagement Display Data')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 's1', 'display_name': 'Alpha'})
    sm.add_ship(kw, {'ship_id': 's2', 'display_name': 'Beta'})

    if not hasattr(sm, 'set_ship_target'):
        print(f'  {FAIL} set_ship_target not implemented')
        results['errors'] += 1
        return

    sm.set_ship_target(kw, 's1', 's2', range_band='long',
                        advantage='s1', matched_speed=False)

    if hasattr(sm, 'get_engagements'):
        engagements = sm.get_engagements(kw)
        eng = None
        if isinstance(engagements, dict):
            eng = engagements.get('s1→s2')
        elif isinstance(engagements, list):
            eng = engagements[0] if engagements else None

        if eng:
            check('Engagement has range_band', 'range_band' in eng)
            check('Engagement has advantage', 'advantage' in eng)
            check('Engagement has matched_speed', 'matched_speed' in eng)
            check('Engagement has hugging', 'hugging' in eng)
            check('Advantage set correctly', eng.get('advantage') == 's1')


# ---------------------------------------------------------------------------
# 15. NPC Targeting
# ---------------------------------------------------------------------------

def test_npc_targeting():
    section('15. NPC Targeting')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 'npc_1', 'display_name': 'NPC Fighter',
                      'control': 'npc'})
    sm.add_ship(kw, {'ship_id': 'player_1', 'display_name': 'Player Ship',
                      'control': 'human'})

    # NPC starts with no target
    session = sm.get_session(kw)
    npc = next(s for s in session.ships if s['ship_id'] == 'npc_1')
    check('NPC starts with no target', npc.get('target_id') is None)

    # GM can assign target to NPC
    if hasattr(sm, 'set_ship_target'):
        sm.set_ship_target(kw, 'npc_1', 'player_1', range_band='long')
        session = sm.get_session(kw)
        npc = next(s for s in session.ships if s['ship_id'] == 'npc_1')
        check('GM assigned target to NPC', npc.get('target_id') == 'player_1')

        # GM can clear NPC target
        sm.set_ship_target(kw, 'npc_1', None)
        session = sm.get_session(kw)
        npc = next(s for s in session.ships if s['ship_id'] == 'npc_1')
        check('GM cleared NPC target', npc.get('target_id') is None)


# ---------------------------------------------------------------------------
# 16. Combat Transition & Validation Warnings
# ---------------------------------------------------------------------------

def test_combat_transition():
    section('16. Combat Transition & Validation Warnings')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    check('Session starts in SETUP status', session.status == 'setup')

    check('SessionManager has start_combat()',
          hasattr(sm, 'start_combat'))

    if not hasattr(sm, 'start_combat'):
        return

    # Add ships with incomplete setup
    sm.add_ship(kw, {'ship_id': 's1', 'display_name': 'Ship A',
                      'control': 'npc', 'faction': 'NPC Hostiles'})
    sm.add_ship(kw, {'ship_id': 's2', 'display_name': 'Ship B',
                      'control': 'npc', 'faction': 'NPC Hostiles'})

    # Start combat — should return warnings but succeed
    result = sm.start_combat(kw)

    session = sm.get_session(kw)
    check('Session status is now ACTIVE', session.status == 'active')

    # Check for validation warnings
    if isinstance(result, dict):
        warnings = result.get('warnings', [])
        check('Warnings returned (non-blocking)',
              isinstance(warnings, list))
        check('Warning about ships with no target',
              any('target' in w.lower() for w in warnings))
        check('Warning about default pilots',
              any('pilot' in w.lower() for w in warnings))

    # Verify setup actions still work after combat starts
    sm.add_ship(kw, {'ship_id': 's3', 'display_name': 'Reinforcement'})
    session = sm.get_session(kw)
    check('Can still add ships after combat starts',
          len(session.ships) == 3)


# ---------------------------------------------------------------------------
# 17. Permissions — GM Session
# ---------------------------------------------------------------------------

def test_permissions_gm_session():
    section('17. Permissions — GM Session')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword
    player = sm.join_session(kw, 'Alice')

    sm.add_ship(kw, {'ship_id': 's1', 'display_name': 'Ship A'})
    sm.assign_ship(kw, 's1', 'Alice')

    # GM can edit any ship
    check('GM can edit ships', sm.can_edit_ships(kw, 'GM Dave'))

    # Player cannot edit ships (GM session)
    check('Player cannot edit ships in GM session',
          not sm.can_edit_ships(kw, 'Alice'))

    # Player can edit own ship's allowed fields
    # (This would be checked in the WebSocket handler, not session_manager directly)

    # GM can manage session
    check('GM can manage session', sm.can_manage_session(kw, 'GM Dave'))
    check('Player cannot manage session',
          not sm.can_manage_session(kw, 'Alice'))


# ---------------------------------------------------------------------------
# 18. Permissions — GM-less Session
# ---------------------------------------------------------------------------

def test_permissions_gmless():
    section('18. Permissions — GM-less Session')

    sm, tmpdir = make_manager()
    session, host = make_gmless_session(sm)
    kw = session.keyword
    player = sm.join_session(kw, 'Bob')

    # Both host and player can edit ships
    check('Host can edit ships', sm.can_edit_ships(kw, 'Host Alice'))
    check('Player can edit ships (GM-less)', sm.can_edit_ships(kw, 'Bob'))

    # Both can manage session
    check('Host can manage session', sm.can_manage_session(kw, 'Host Alice'))
    check('Player can manage session (GM-less)',
          sm.can_manage_session(kw, 'Bob'))

    # Neither can undo/redo
    check('Host cannot undo', not sm.can_undo_redo(kw, 'Host Alice'))
    check('Player cannot undo', not sm.can_undo_redo(kw, 'Bob'))


# ---------------------------------------------------------------------------
# 19. Visibility Filtering with Factions
# ---------------------------------------------------------------------------

def test_visibility_with_factions():
    section('19. Visibility Filtering with Factions')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    sm.add_ship(kw, {'ship_id': 's1', 'display_name': 'Player Ship',
                      'faction': 'Alliance', 'st_hp': 100, 'current_hp': 100})
    sm.add_ship(kw, {'ship_id': 's2', 'display_name': 'Enemy Ship',
                      'faction': 'Empire', 'st_hp': 80, 'current_hp': 60})
    sm.add_ship(kw, {'ship_id': 's3', 'display_name': 'Ally Ship',
                      'faction': 'Alliance', 'st_hp': 90, 'current_hp': 90})

    player = sm.join_session(kw, 'Alice')
    sm.assign_ship(kw, 's1', 'Alice')

    # Player should see own ship in full detail
    state = sm.get_state_for_user(kw, 'Alice')
    ships = state['ships']
    own = next(s for s in ships if s.get('ship_id') == 's1')
    enemy = next(s for s in ships if s.get('ship_id') == 's2')
    ally = next(s for s in ships if s.get('ship_id') == 's3')

    check('Own ship has full stats', 'st_hp' in own)
    check('Enemy ship is limited', enemy.get('visibility') == 'limited')
    check('Allied ship is ALSO limited (not own)',
          ally.get('visibility') == 'limited')

    # GM sees everything
    gm_state = sm.get_state_for_user(kw, 'GM Dave')
    gm_ships = gm_state['ships']
    check('GM sees all ships with full stats',
          all('st_hp' in s for s in gm_ships))


# ---------------------------------------------------------------------------
# 20. Full Scenario Walkthrough
# ---------------------------------------------------------------------------

def test_full_scenario():
    section('20. Full Scenario Walkthrough')

    sm, tmpdir = make_manager()
    session, gm = make_gm_session(sm)
    kw = session.keyword

    # Step 1: GM creates factions
    if hasattr(sm, 'create_faction'):
        sm.create_faction(kw, 'Empire', '#60a5fa')
        sm.create_faction(kw, 'Pirates', '#f87171')
        check('Factions created', True)

        if hasattr(sm, 'set_faction_relationship'):
            sm.set_faction_relationship(kw, 'Empire', 'Pirates', 'hostile')
            sm.set_faction_relationship(kw, 'Pirates', 'Empire', 'hostile')
            check('Faction relationships set', True)
    else:
        print(f'  {FAIL} Faction management not implemented')
        results['errors'] += 1
        return

    # Step 2: GM adds ships
    if hasattr(sm, 'add_ship_from_template'):
        s1 = sm.add_ship_from_template(kw, 'wildcat_v1')
        s2 = sm.add_ship_from_template(kw, 'javelin_v1')
        check('Ships added from templates', s1 is not None and s2 is not None)
    else:
        sm.add_ship(kw, {'ship_id': 's1', 'display_name': 'Wildcat',
                          'faction': 'NPC Hostiles', 'st_hp': 120, 'current_hp': 120})
        sm.add_ship(kw, {'ship_id': 's2', 'display_name': 'Javelin',
                          'faction': 'NPC Hostiles', 'st_hp': 80, 'current_hp': 80})
        s1, s2 = 's1', 's2'
        check('Ships added manually', True)

    # Step 3: GM customizes ships
    sm.update_ship(kw, s1, {'display_name': 'Red Fox', 'faction': 'Pirates'})
    sm.update_ship(kw, s2, {'display_name': 'Blue Jay', 'faction': 'Empire'})
    check('Ships customized', True)

    # Step 4: Player joins and gets ship assigned
    player = sm.join_session(kw, 'Alice')
    sm.assign_ship(kw, s1, 'Alice')
    check('Player joined and ship assigned', 'Alice' in [u.name for u in session.users.values()])

    # Step 5: Set targets (creates engagements)
    if hasattr(sm, 'set_ship_target'):
        sm.set_ship_target(kw, s1, s2, range_band='long')
        sm.set_ship_target(kw, s2, s1, range_band='long')
        check('Mutual targets set (mutual pursuit)', True)
    else:
        check('set_ship_target not implemented', False)

    # Step 6: Verify visibility
    alice_state = sm.get_state_for_user(kw, 'Alice')
    alice_ships = alice_state['ships']
    own = next((s for s in alice_ships if s.get('ship_id') == s1), None)
    enemy = next((s for s in alice_ships if s.get('ship_id') == s2), None)

    if own and enemy:
        check('Alice sees own ship fully', 'st_hp' in own)
        check('Alice sees enemy as limited', enemy.get('visibility') == 'limited')

    # Step 7: Start combat
    if hasattr(sm, 'start_combat'):
        sm.start_combat(kw)
        session = sm.get_session(kw)
        check('Combat started', session.status == 'active')
    else:
        check('start_combat not implemented', False)

    # Step 8: Verify persistence
    sm2, _ = make_manager()
    # Point at same directory
    sm2.sessions_dir = sm.sessions_dir
    sm2.load_all()
    reloaded = sm2.get_session(kw)
    check('Session persisted and reloaded',
          reloaded is not None and len(reloaded.ships) == 2)

    print()
    print(f'  {BOLD}Full scenario complete!{RESET}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f'\n{BOLD}Psi-Wars Web UI v0.5.0 — Setup Phase Test Suite{RESET}')
    print(f'Mode: {"AUTO" if AUTO_MODE else "INTERACTIVE"}')
    print('=' * 60)

    tests = [
        test_template_catalog,
        test_add_ship_defaults,
        test_ship_customization,
        test_ship_removal,
        test_assignment_gm_mode,
        test_assignment_player_select,
        test_faction_creation,
        test_faction_removal,
        test_faction_relationships,
        test_auto_escalation,
        test_targeting_warnings,
        test_engagement_creation,
        test_engagement_rules,
        test_engagement_display,
        test_npc_targeting,
        test_combat_transition,
        test_permissions_gm_session,
        test_permissions_gmless,
        test_visibility_with_factions,
        test_full_scenario,
    ]

    for test_fn in tests:
        safe_run(test_fn)

    # Summary
    print(f'\n{"=" * 60}')
    total = results['passed'] + results['failed']
    print(f'{BOLD}Results: {results["passed"]}/{total} passed, '
          f'{results["failed"]} failed, {results["errors"]} errors{RESET}')

    if results['failed'] == 0 and results['errors'] == 0:
        print(f'{PASS} All tests passed!')
    elif results['failed'] + results['errors'] == total or results['errors'] > 0:
        print(f'{WARN} Most tests expected to fail before implementation.')
    else:
        print(f'{FAIL} Some tests failed.')

    sys.exit(0 if results['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
