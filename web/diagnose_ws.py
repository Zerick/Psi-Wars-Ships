#!/usr/bin/env python3
"""
Psi-Wars WebSocket Diagnostic — Run ON the Raspberry Pi
========================================================

This script diagnoses WebSocket connectivity issues by testing
each layer independently:
  1. Python package availability (websockets, uvicorn, fastapi)
  2. HTTP health check (localhost)
  3. WebSocket connection to localhost (bypasses Cloudflare)
  4. Full auth handshake over WebSocket
  5. Service configuration
  6. Cloudflare tunnel configuration

Usage:
    cd /home/psiwars/psi-wars/web
    source venv/bin/activate
    python3 diagnose_ws.py
"""

import asyncio
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
WARN = '\033[93m⚠\033[0m'
INFO = '\033[94mℹ\033[0m'
BOLD = '\033[1m'
RESET = '\033[0m'


def section(title):
    print(f'\n{BOLD}═══ {title} ═══{RESET}')


def ok(msg):
    print(f'  {PASS} {msg}')


def fail(msg):
    print(f'  {FAIL} {msg}')


def warn(msg):
    print(f'  {WARN} {msg}')


def info(msg):
    print(f'  {INFO} {msg}')


# ---------------------------------------------------------------------------
# 1. Package checks
# ---------------------------------------------------------------------------

def check_packages():
    section('1. Python Packages')

    packages = {
        'fastapi': 'FastAPI web framework',
        'uvicorn': 'ASGI server',
        'websockets': 'WebSocket protocol library (required by uvicorn for WS)',
        'jinja2': 'Template engine',
        'd20': 'Dice rolling library',
        'starlette': 'ASGI toolkit (installed with FastAPI)',
    }

    all_ok = True
    for pkg, desc in packages.items():
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, '__version__', 'unknown')
            ok(f'{pkg} {version} — {desc}')
        except ImportError:
            fail(f'{pkg} NOT INSTALLED — {desc}')
            all_ok = False

    if not all_ok:
        print()
        fail('Fix missing packages:')
        print('    source venv/bin/activate')
        print('    pip install fastapi uvicorn websockets jinja2 d20')
        print('    sudo systemctl restart psiwars-web')

    # Check if websockets is the right version for uvicorn
    try:
        import uvicorn
        # Check uvicorn's WebSocket implementation
        try:
            from uvicorn.config import Config
            config = Config(app=None)
            ws_impl = config.ws
            ok(f'uvicorn WebSocket implementation: {ws_impl}')
        except Exception as e:
            warn(f'Could not determine uvicorn WS implementation: {e}')
    except ImportError:
        pass

    return all_ok


# ---------------------------------------------------------------------------
# 2. HTTP health check
# ---------------------------------------------------------------------------

def check_http():
    section('2. HTTP Health Check (localhost:8080)')

    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request('http://localhost:8080/api/health')
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            ok(f'Server responding: version={data.get("version")}, '
               f'sessions={data.get("active_sessions")}, '
               f'dice={data.get("dice_available")}')
            return True
    except urllib.error.URLError as e:
        fail(f'Cannot reach server: {e}')
        print('    Is the service running? Check: sudo systemctl status psiwars-web')
        return False
    except Exception as e:
        fail(f'Health check error: {e}')
        return False


# ---------------------------------------------------------------------------
# 3. WebSocket connection test (localhost, bypasses Cloudflare)
# ---------------------------------------------------------------------------

async def check_websocket():
    section('3. WebSocket Connection (localhost:8080)')

    try:
        import websockets
    except ImportError:
        fail('websockets package not installed!')
        print('    Fix: pip install websockets')
        return False

    # First, create a test session via HTTP
    import urllib.request
    try:
        test_name = f'diag_{os.getpid()}'
        req = urllib.request.Request(
            'http://localhost:8080/api/session/create',
            data=json.dumps({
                'creator_name': test_name,
                'has_gm': False,
            }).encode(),
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            session_data = json.loads(resp.read().decode())

        keyword = session_data['keyword']
        token = session_data['user']['token']
        ok(f'Test session created: {keyword}')
    except Exception as e:
        fail(f'Could not create test session: {e}')
        return False

    # Now test WebSocket connection
    ws_url = f'ws://localhost:8080/ws/{keyword}'
    info(f'Connecting to {ws_url}')

    try:
        async with websockets.connect(ws_url, open_timeout=5) as ws:
            ok('WebSocket connection OPENED')

            # Send AUTH
            auth_msg = json.dumps({
                'type': 'AUTH',
                'payload': {
                    'name': test_name,
                    'token': token,
                    'gm_password': '',
                },
            })
            await ws.send(auth_msg)
            ok('AUTH message sent')

            # Wait for response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)

                if data.get('type') == 'AUTH_OK':
                    user = data['payload']['user']
                    ok(f'AUTH_OK received — {user["name"]} ({user["role"]})')
                    state = data['payload'].get('state', {})
                    ok(f'State: {len(state.get("ships", []))} ships, '
                       f'{len(state.get("connected_users", []))} users')
                elif data.get('type') == 'AUTH_FAIL':
                    fail(f'AUTH_FAIL: {data["payload"].get("error", "unknown")}')
                else:
                    warn(f'Unexpected response: {data.get("type")}')

            except asyncio.TimeoutError:
                fail('Timed out waiting for AUTH response')

    except ConnectionRefusedError:
        fail('Connection refused — server not listening on port 8080')
        return False
    except websockets.exceptions.InvalidStatusCode as e:
        fail(f'WebSocket upgrade rejected: HTTP {e.status_code}')
        if e.status_code == 403:
            print('    Server returned 403 — check CORS or middleware config')
        elif e.status_code == 404:
            print('    Server returned 404 — /ws/ route may not be registered')
        return False
    except Exception as e:
        fail(f'WebSocket error: {type(e).__name__}: {e}')
        return False
    finally:
        # Cleanup: delete test session
        try:
            req = urllib.request.Request(
                f'http://localhost:8080/api/session/{keyword}',
                method='DELETE',
            )
            urllib.request.urlopen(req, timeout=5)
            info(f'Cleaned up test session {keyword}')
        except Exception:
            pass

    return True


# ---------------------------------------------------------------------------
# 4. Service configuration
# ---------------------------------------------------------------------------

def check_service():
    section('4. Service Configuration')

    service_file = Path('/etc/systemd/system/psiwars-web.service')
    if not service_file.exists():
        # Try user services
        for p in [
            Path('/etc/systemd/system/psiwars-web.service'),
            Path('/home/psiwars/.config/systemd/user/psiwars-web.service'),
        ]:
            if p.exists():
                service_file = p
                break

    if service_file.exists():
        content = service_file.read_text()
        ok(f'Service file found: {service_file}')
        print(f'    Content:')
        for line in content.strip().split('\n'):
            print(f'      {line}')

        # Check if it's using the right working directory
        if '/home/psiwars/psi-wars/web' in content:
            ok('Working directory looks correct')
        else:
            warn('Working directory may not point to web/')

        # Check the ExecStart command
        if 'uvicorn' in content:
            ok('Using uvicorn')
            if '--ws' in content:
                info('Explicit --ws flag found in ExecStart')
            else:
                info('No explicit --ws flag (uvicorn auto-detects, should be fine)')
        else:
            warn('ExecStart does not mention uvicorn')
    else:
        warn('Service file not found at expected locations')
        info('Checking running process instead...')

    # Check if uvicorn is actually running
    try:
        result = subprocess.run(
            ['pgrep', '-af', 'uvicorn'],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            ok('uvicorn process found:')
            for line in result.stdout.strip().split('\n'):
                print(f'      {line}')
        else:
            fail('No uvicorn process running!')
    except Exception as e:
        warn(f'Could not check process: {e}')


# ---------------------------------------------------------------------------
# 5. Cloudflare tunnel configuration
# ---------------------------------------------------------------------------

def check_tunnel():
    section('5. Cloudflare Tunnel Configuration')

    config_path = Path('/etc/cloudflared/config.yml')
    if not config_path.exists():
        config_path = Path('/etc/cloudflared/config.yaml')

    if config_path.exists():
        content = config_path.read_text()
        ok(f'Tunnel config found: {config_path}')
        print(f'    Content:')
        for line in content.strip().split('\n'):
            print(f'      {line}')

        # Check for WebSocket-relevant settings
        if 'noTLSVerify' in content:
            info('noTLSVerify setting found')
        if 'disableChunkedEncoding' in content:
            warn('disableChunkedEncoding found — this can affect WebSocket')

        # Cloudflare tunnels support WebSocket by default when using http://
        if 'http://localhost:8080' in content or 'http://127.0.0.1:8080' in content:
            ok('Tunnel points to localhost:8080 via HTTP — WebSocket should work')
        else:
            warn('Expected "http://localhost:8080" in tunnel config')

    else:
        warn('Cloudflare tunnel config not found')
        info('Checked: /etc/cloudflared/config.yml and config.yaml')

    # Check if cloudflared is running
    try:
        result = subprocess.run(
            ['pgrep', '-af', 'cloudflared'],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            ok('cloudflared process running')
        else:
            warn('cloudflared process not found')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 6. uvicorn WebSocket capability test
# ---------------------------------------------------------------------------

def check_uvicorn_ws():
    section('6. uvicorn WebSocket Support')

    try:
        import uvicorn
        ok(f'uvicorn {uvicorn.__version__}')
    except ImportError:
        fail('uvicorn not installed')
        return

    # Check which WS implementation uvicorn will use
    try:
        # uvicorn tries to import websockets, falls back to wsproto
        try:
            import websockets
            ok(f'websockets {websockets.__version__} available (preferred by uvicorn)')
        except ImportError:
            fail('websockets NOT available')
            try:
                import wsproto
                ok(f'wsproto {wsproto.__version__} available (fallback)')
            except ImportError:
                fail('wsproto NOT available either')
                fail('uvicorn has NO WebSocket support!')
                print('    Fix: pip install websockets')
                return

        # Try to actually configure uvicorn with WS
        from uvicorn.config import Config
        try:
            config = Config(app="main:app", ws="auto")
            ok(f'uvicorn WS config valid (ws={config.ws})')
        except Exception as e:
            fail(f'uvicorn WS config failed: {e}')

    except Exception as e:
        warn(f'Could not fully test uvicorn WS: {e}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f'{BOLD}Psi-Wars WebSocket Diagnostic{RESET}')
    print(f'Running on: {os.uname().nodename}')
    print(f'Python: {sys.version}')
    print(f'Venv: {"Yes" if sys.prefix != sys.base_prefix else "NO — activate your venv!"}')
    print('=' * 55)

    if sys.prefix == sys.base_prefix:
        warn('Not running inside a virtual environment!')
        print('    Run: source venv/bin/activate')
        print()

    check_packages()
    http_ok = check_http()

    if http_ok:
        asyncio.run(check_websocket())
    else:
        print()
        fail('Skipping WebSocket test — HTTP not responding')

    check_service()
    check_tunnel()
    check_uvicorn_ws()

    print()
    print('=' * 55)
    print(f'{BOLD}Done.{RESET} Review any {FAIL} items above.')
    print(f'If WebSocket works on localhost but not via Cloudflare,')
    print(f'the issue is in the tunnel. Try accessing via LAN:')
    print(f'  http://192.168.0.95:8080/diagnostic')
    print()


if __name__ == '__main__':
    main()
