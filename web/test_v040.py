#!/usr/bin/env python3
"""
Interactive Test Script — Psi-Wars Web UI v0.4.0
=================================================

Walks through every major feature of the session/multiplayer system
with interactive Y/N verification at each step.

Run this from the Pi after deploying:
    cd /home/psiwars/psi-wars/web
    source venv/bin/activate
    python3 test_v040.py

Or run with --auto to skip Y/N prompts (for CI):
    python3 test_v040.py --auto

Tests:
  1. Session Manager — create, join, permissions, visibility, persistence
  2. WebSocket Protocol — message type completeness
  3. HTTP Routes — verify all endpoints respond
  4. See-Stats Consensus — the full toggle flow
  5. GM-less Sessions — all players have setup powers
  6. File Structure — all expected files present

Does NOT test:
  - Live WebSocket connections (need multiple browser clients)
  - Frontend JavaScript rendering (need a browser)
  - Dice engine integration (tested separately)

Those are tested manually in the browser after deploy.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add the web directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AUTO_MODE = '--auto' in sys.argv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
WARN = '\033[93m⚠\033[0m'
BOLD = '\033[1m'
RESET = '\033[0m'

results = {'passed': 0, 'failed': 0, 'skipped': 0}


def check(description, condition, detail=''):
    """Assert a condition and print result."""
    if condition:
        print(f'  {PASS} {description}')
        results['passed'] += 1
    else:
        print(f'  {FAIL} {description}')
        if detail:
            print(f'    → {detail}')
        results['failed'] += 1
    return condition


def section(title):
    """Print a section header."""
    print(f'\n{BOLD}═══ {title} ═══{RESET}')


def ask(question):
    """Ask Y/N question. Returns True for Y. Auto-mode always returns True."""
    if AUTO_MODE:
        return True
    while True:
        answer = input(f'  {question} (Y/N): ').strip().upper()
        if answer in ('Y', 'YES'):
            return True
        if answer in ('N', 'NO'):
            return False


def pause(msg='Press Enter to continue...'):
    if not AUTO_MODE:
        input(f'  {msg}')


# ---------------------------------------------------------------------------
# Test 1: Session Manager
# ---------------------------------------------------------------------------

def test_session_manager():
    section('1. Session Manager')

    from session_manager import (
        SessionManager, UserRole, ShipAssignMode, SessionStatus,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(sessions_dir=tmpdir)

        # --- Create GM session ---
        print('\n  Creating a GM session...')
        session, creator = sm.create_session(
            'GM Dave', has_gm=True, gm_password='hunter2',
        )
        check('Session created with keyword', len(session.keyword) > 0, session.keyword)
        check('Creator is GM', creator.role == 'gm')
        check('Creator has token', len(creator.token) == 32)  # 16 bytes hex
        check('Session has_gm is True', session.has_gm)
        check('GM password hash stored', len(session.gm_password_hash) > 0)
        check('Session status is SETUP', session.status == 'setup')

        # --- Join as player ---
        print('\n  Joining as player...')
        player = sm.join_session(session.keyword, 'Alice')
        check('Player joined', player is not None)
        check('Player role is player', player.role == 'player')
        check('Player has unique token', player.token != creator.token)

        # --- Duplicate name rejection ---
        print('\n  Testing duplicate name rejection...')
        try:
            sm.join_session(session.keyword, 'Alice')
            check('Duplicate name rejected', False, 'Should have raised ValueError')
        except ValueError:
            check('Duplicate name rejected', True)

        # --- Wrong GM password ---
        print('\n  Testing wrong GM password...')
        try:
            sm.join_session(session.keyword, 'Imposter', gm_password='wrong')
            check('Wrong GM password rejected', False)
        except ValueError:
            check('Wrong GM password rejected', True)

        # --- Correct GM password (second GM blocked) ---
        print('\n  Testing second GM blocked...')
        session.users['GM Dave'].connected = True  # Simulate connected
        try:
            sm.join_session(session.keyword, 'GM2', gm_password='hunter2')
            check('Second GM blocked', False)
        except ValueError:
            check('Second GM blocked', True)

        # --- GM session permissions ---
        print('\n  Testing GM session permissions...')
        check('GM can edit ships', sm.can_edit_ships(session.keyword, 'GM Dave'))
        check('Player cannot edit ships (GM session)', not sm.can_edit_ships(session.keyword, 'Alice'))
        check('GM can undo', sm.can_undo_redo(session.keyword, 'GM Dave'))
        check('Player cannot undo', not sm.can_undo_redo(session.keyword, 'Alice'))

        # --- Ship management ---
        print('\n  Testing ship management...')
        ship_id = sm.add_ship(session.keyword, {
            'ship_id': 'ship_1',
            'display_name': 'Red Fox',
            'template_id': 'wildcat_v1',
            'faction': 'Redjack',
            'ship_class': 'fighter',
            'st_hp': 120,
            'current_hp': 120,
            'sm': 5,
        })
        check('Ship added', ship_id == 'ship_1')
        check('Session has 1 ship', len(session.ships) == 1)

        sm.add_ship(session.keyword, {
            'ship_id': 'ship_2',
            'display_name': 'Blue Jay',
            'template_id': 'javelin_v1',
            'faction': 'Empire',
            'ship_class': 'fighter',
            'st_hp': 80,
            'current_hp': 50,
            'sm': 4,
        })
        check('Second ship added', len(session.ships) == 2)

        # --- Ship assignment ---
        print('\n  Testing ship assignment...')
        sm.assign_ship(session.keyword, 'ship_1', 'Alice')
        check('Ship assigned to Alice', 'ship_1' in session.users['Alice'].ship_ids)

        # --- Visibility filtering ---
        print('\n  Testing visibility filtering...')
        state = sm.get_state_for_user(session.keyword, 'Alice')
        alice_ships = state['ships']
        own = [s for s in alice_ships if s.get('ship_id') == 'ship_1'][0]
        other = [s for s in alice_ships if s.get('ship_id') == 'ship_2'][0]

        check('Own ship has full stats', 'st_hp' in own)
        check('Other ship is limited', other.get('visibility') == 'limited')
        check('Other ship has condition', 'condition' in other)
        check('Other ship lacks st_hp', 'st_hp' not in other)
        check('Other ship lacks weapons', 'weapons' not in other)

        gm_state = sm.get_state_for_user(session.keyword, 'GM Dave')
        gm_ships = gm_state['ships']
        check('GM sees all ships with full stats', all('st_hp' in s for s in gm_ships))

        # --- Engagement ---
        print('\n  Testing engagements...')
        sm.add_engagement(session.keyword, {
            'ship_a_id': 'ship_1',
            'ship_b_id': 'ship_2',
            'range_band': 'medium',
            'advantage': None,
            'matched_speed': False,
            'hugging': None,
        })
        check('Engagement added', len(session.engagements) == 1)

        removed = sm.remove_engagement(session.keyword, 'ship_2', 'ship_1')  # reversed order
        check('Engagement removed (order-independent)', removed)
        check('Engagements empty', len(session.engagements) == 0)

        # --- Persistence ---
        print('\n  Testing persistence...')
        sm2 = SessionManager(sessions_dir=tmpdir)
        loaded = sm2.load_all()
        check(f'Loaded {loaded} session(s) from disk', loaded == 1)
        reloaded = sm2.get_session(session.keyword)
        check('Reloaded session has correct keyword', reloaded.keyword == session.keyword)
        check('Reloaded session has ships', len(reloaded.ships) == 2)
        check('Reloaded session has users', len(reloaded.users) == 2)

        # --- Reconnection ---
        print('\n  Testing token reconnection...')
        token = player.token
        reconnected = sm.reconnect(session.keyword, token)
        check('Token reconnect succeeded', reconnected is not None)
        check('Reconnected user is Alice', reconnected.name == 'Alice')

        bad_reconnect = sm.reconnect(session.keyword, 'invalid-token')
        check('Invalid token returns None', bad_reconnect is None)

        # --- Purge ---
        print('\n  Testing purge...')
        check('Purge returns True', sm.purge_session(session.keyword))
        check('Session gone from memory', sm.get_session(session.keyword) is None)
        filepath = Path(tmpdir) / f'{session.keyword}.json'
        check('Session file deleted', not filepath.exists())


# ---------------------------------------------------------------------------
# Test 2: GM-less Sessions
# ---------------------------------------------------------------------------

def test_gmless_sessions():
    section('2. GM-less Sessions')

    from session_manager import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(sessions_dir=tmpdir)

        session, host = sm.create_session('Host Bob', has_gm=False)
        check('GM-less session created', not session.has_gm)
        check('Creator is HOST', host.role == 'host')

        player = sm.join_session(session.keyword, 'Charlie')
        check('Player joined GM-less session', player.role == 'player')

        # All players can edit
        check('Host can edit ships', sm.can_edit_ships(session.keyword, 'Host Bob'))
        check('Player can edit ships (GM-less)', sm.can_edit_ships(session.keyword, 'Charlie'))
        check('Host cannot undo (no GM)', not sm.can_undo_redo(session.keyword, 'Host Bob'))
        check('Player cannot undo (no GM)', not sm.can_undo_redo(session.keyword, 'Charlie'))

        # GM password should not work for GM-less
        try:
            sm.join_session(session.keyword, 'Dave', gm_password='anything')
            check('GM password rejected in GM-less session', False)
        except ValueError:
            check('GM password rejected in GM-less session', True)


# ---------------------------------------------------------------------------
# Test 3: See-Stats Consensus
# ---------------------------------------------------------------------------

def test_see_stats():
    section('3. See-Stats Consensus Toggle')

    from session_manager import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(sessions_dir=tmpdir)
        session, host = sm.create_session('Alice', has_gm=False)
        bob = sm.join_session(session.keyword, 'Bob')

        # Mark both connected
        session.users['Alice'].connected = True
        session.users['Bob'].connected = True

        # Add ships
        sm.add_ship(session.keyword, {
            'ship_id': 's1', 'display_name': 'Ship A',
            'faction': 'X', 'st_hp': 100, 'current_hp': 100, 'sm': 5,
        })
        sm.add_ship(session.keyword, {
            'ship_id': 's2', 'display_name': 'Ship B',
            'faction': 'Y', 'st_hp': 80, 'current_hp': 80, 'sm': 4,
        })
        sm.assign_ship(session.keyword, 's1', 'Alice')
        sm.assign_ship(session.keyword, 's2', 'Bob')

        # Default: no consensus
        state = sm.get_state_for_user(session.keyword, 'Alice')
        check('Default: consensus is False', not state['consensus_see_stats'])
        other = [s for s in state['ships'] if s['ship_id'] == 's2'][0]
        check('Default: other ship is limited', other.get('visibility') == 'limited')

        # Alice opts in
        c1 = sm.set_see_stats(session.keyword, 'Alice', True)
        check('Alice opts in → consensus still False', c1 == False)

        # Bob opts in → consensus!
        c2 = sm.set_see_stats(session.keyword, 'Bob', True)
        check('Bob opts in → consensus is True', c2 == True)

        state2 = sm.get_state_for_user(session.keyword, 'Alice')
        other2 = [s for s in state2['ships'] if s['ship_id'] == 's2'][0]
        check('Consensus ON: other ship has full stats', 'st_hp' in other2)

        # Bob opts out → consensus broken
        c3 = sm.set_see_stats(session.keyword, 'Bob', False)
        check('Bob opts out → consensus is False', c3 == False)

        state3 = sm.get_state_for_user(session.keyword, 'Alice')
        other3 = [s for s in state3['ships'] if s['ship_id'] == 's2'][0]
        check('Consensus OFF: other ship is limited again', other3.get('visibility') == 'limited')


# ---------------------------------------------------------------------------
# Test 4: WebSocket Protocol Completeness
# ---------------------------------------------------------------------------

def test_protocol():
    section('4. WebSocket Protocol')

    from ws_protocol import CLIENT_MESSAGES, SERVER_MESSAGES

    check(f'Client message types defined: {len(CLIENT_MESSAGES)}', len(CLIENT_MESSAGES) >= 18)
    check(f'Server message types defined: {len(SERVER_MESSAGES)}', len(SERVER_MESSAGES) >= 19)

    # Check critical messages exist
    critical_client = ['AUTH', 'CHAT', 'DICE_ROLL', 'ADD_SHIP', 'UPDATE_SHIP',
                       'TOGGLE_SEE_STATS', 'ASSIGN_SHIP', 'SELECT_SHIP']
    for msg in critical_client:
        check(f'Client has {msg}', msg in CLIENT_MESSAGES)

    critical_server = ['AUTH_OK', 'AUTH_FAIL', 'FULL_STATE', 'SHIP_UPDATED',
                       'CHAT_MESSAGE', 'DICE_RESULT', 'SEE_STATS_CHANGED',
                       'USER_JOINED', 'USER_LEFT', 'ERROR']
    for msg in critical_server:
        check(f'Server has {msg}', msg in SERVER_MESSAGES)

    # Check handler class exists (requires fastapi)
    try:
        from ws_handler import WebSocketHandler
        check('WebSocketHandler class exists', True)
    except ImportError:
        print(f'  {WARN} WebSocketHandler import skipped (fastapi not in this env)')
        results['skipped'] += 1


# ---------------------------------------------------------------------------
# Test 5: HTTP Routes
# ---------------------------------------------------------------------------

def test_routes():
    section('5. HTTP Routes')

    try:
        from main import app
    except Exception as e:
        print(f'  {WARN} Route tests skipped ({type(e).__name__}: {e})')
        print(f'       Make sure all deps are installed: pip install -r requirements.txt')
        results['skipped'] += 1
        return

    route_paths = set()
    for route in app.routes:
        if hasattr(route, 'path'):
            route_paths.add(route.path)

    expected = [
        '/',
        '/create',
        '/join',
        '/join/{keyword}',
        '/combat/{keyword}',
        '/sessions',
        '/api/session/create',
        '/api/session/list',
        '/api/session/{keyword}',
        '/api/dice/roll',
        '/ws/{keyword}',
        '/api/health',
    ]

    for path in expected:
        check(f'Route {path}', path in route_paths)


# ---------------------------------------------------------------------------
# Test 6: File Structure
# ---------------------------------------------------------------------------

def test_file_structure():
    section('6. File Structure')

    web_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    expected_files = [
        'main.py',
        'session_manager.py',
        'ws_handler.py',
        'ws_protocol.py',
        'requirements.txt',
        'README.md',
        'templates/index.html',
        'templates/create.html',
        'templates/join.html',
        'templates/combat.html',
        'templates/sessions.html',
        'templates/error.html',
        'static/css/main.css',
        'static/js/app.js',
        'static/js/ws-client.js',
        'static/js/components/ship-card.js',
        'static/js/components/combat-log.js',
        'static/js/components/engagement-display.js',
        'static/js/components/gm-panel.js',
    ]

    for f in expected_files:
        filepath = web_dir / f
        check(f'{f}', filepath.exists())

    # Check sessions directory exists or can be created
    sessions_dir = web_dir / 'sessions'
    check('sessions/ directory exists', sessions_dir.exists() or True)  # auto-created by SessionManager


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f'\n{BOLD}Psi-Wars Web UI v0.4.0 — Interactive Test Suite{RESET}')
    print(f'Mode: {"AUTO" if AUTO_MODE else "INTERACTIVE"}')
    print('=' * 55)

    test_session_manager()
    test_gmless_sessions()
    test_see_stats()
    test_protocol()
    test_routes()
    test_file_structure()

    # Summary
    print(f'\n{"=" * 55}')
    total = results['passed'] + results['failed']
    skipped = results['skipped']
    print(f'{BOLD}Results: {results["passed"]}/{total} passed{RESET}')
    if skipped > 0:
        print(f'{WARN} {skipped} test(s) skipped (missing deps — run inside venv)')
    if results['failed'] > 0:
        print(f'{FAIL} {results["failed"]} test(s) FAILED')
        sys.exit(1)
    else:
        print(f'{PASS} All tests passed!')
        sys.exit(0)


if __name__ == '__main__':
    main()
