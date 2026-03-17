"""
Psi-Wars Web UI — FastAPI Server (v0.4.0)
==========================================

Main application entry point. Handles:
  - HTTP routes for pages (landing, create, join, combat, sessions)
  - REST API for session management and ship templates
  - WebSocket endpoint for real-time multiplayer
  - Dice rolling API (server-side)

Route map:
  GET  /                   → Landing page
  GET  /create             → Session creation form
  GET  /join               → Session join form
  GET  /join/{keyword}     → Pre-filled join form for a specific session
  GET  /combat/{keyword}   → Combat UI for a specific session
  GET  /sessions           → Session browser (GM management page)
  WS   /ws/{keyword}       → WebSocket for real-time session sync

  POST /api/session/create → Create a new session (REST)
  GET  /api/session/list   → List all sessions (REST)
  DELETE /api/session/{keyword} → Delete a session (REST)
  POST /api/dice/roll      → Roll dice (REST, for non-WS clients)

Modification guide:
  - To add a new page: add template + route function
  - To add a new API endpoint: add route with @app.post/get/etc
  - To change WebSocket behavior: edit ws_handler.py
  - To change session logic: edit session_manager.py
  - To change dice behavior: edit psi_dice.py

Dependencies: fastapi, uvicorn, psi_dice
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from session_manager import SessionManager
from ws_handler import WebSocketHandler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

# Version stamp — update with each deploy
VERSION = "0.4.7"

app = FastAPI(
    title="Psi-Wars Combat Simulator",
    version=VERSION,
)

# Paths (relative to this file)
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
SESSIONS_DIR = BASE_DIR / "sessions"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    """
    Prevent browser caching of JS and CSS files during development.

    ES module imports (import ... from './component.js') don't carry
    query-string cache busters, so the browser caches them aggressively.
    This middleware adds no-cache headers for all static JS/CSS requests.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") and (path.endswith(".js") or path.endswith(".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Core services
session_manager = SessionManager(sessions_dir=SESSIONS_DIR)

# Dice roller — import with graceful fallback
dice_roller = None
try:
    from psi_dice import roll_dice
    dice_roller = roll_dice
    logger.info("Dice engine loaded (psi_dice).")
except ImportError:
    logger.warning("psi_dice not available. Dice rolls will be disabled.")

# WebSocket handler
ws_handler = WebSocketHandler(
    session_manager=session_manager,
    dice_roller=dice_roller,
)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Load persisted sessions on server startup."""
    count = session_manager.load_all()
    logger.info("Server starting. Version %s. Loaded %d sessions.", VERSION, count)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing page — entry point for the web UI."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": VERSION,
    })


@app.get("/diagnostic", response_class=HTMLResponse)
async def diagnostic_page(request: Request):
    """WebSocket diagnostic page — tests connectivity layer by layer."""
    return templates.TemplateResponse("diagnostic.html", {
        "request": request,
        "version": VERSION,
    })


@app.get("/create", response_class=HTMLResponse)
async def create_page(request: Request):
    """Session creation form."""
    return templates.TemplateResponse("create.html", {
        "request": request,
        "version": VERSION,
    })


@app.get("/join", response_class=HTMLResponse)
async def join_page(request: Request):
    """Session join form (no keyword pre-filled)."""
    return templates.TemplateResponse("join.html", {
        "request": request,
        "version": VERSION,
    })


@app.get("/join/{keyword}", response_class=HTMLResponse)
async def join_page_with_keyword(request: Request, keyword: str):
    """Session join form with keyword pre-filled from URL."""
    return templates.TemplateResponse("join.html", {
        "request": request,
        "version": VERSION,
        "keyword": keyword,
    })


@app.get("/combat/{keyword}", response_class=HTMLResponse)
async def combat_page(request: Request, keyword: str):
    """
    Main combat UI for a specific session.

    The page loads, then the JavaScript opens a WebSocket to /ws/{keyword}
    and authenticates using the token stored in localStorage. If no token
    is found, it redirects to the join page.
    """
    session = session_manager.get_session(keyword)
    if not session:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "version": VERSION,
            "error_title": "Session Not Found",
            "error_message": f"No session with keyword '{keyword}' exists.",
        }, status_code=404)

    return templates.TemplateResponse("combat.html", {
        "request": request,
        "version": VERSION,
        "keyword": keyword,
    })


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    """Session browser — view all sessions, manage/purge them."""
    return templates.TemplateResponse("sessions.html", {
        "request": request,
        "version": VERSION,
    })


# ---------------------------------------------------------------------------
# API routes — Session management
# ---------------------------------------------------------------------------

@app.post("/api/session/create")
async def api_create_session(request: Request):
    """
    Create a new session.

    Body: {
        "creator_name": "GM Dave",
        "has_gm": true,
        "gm_password": "secret",
        "ship_assign_mode": "gm_assign"  // or "player_select"
    }

    Returns: {
        "keyword": "iron-hawk-7",
        "user": { "name": ..., "role": ..., "token": ... }
    }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    creator_name = body.get("creator_name", "").strip()
    has_gm = body.get("has_gm", True)
    gm_password = body.get("gm_password", "").strip()
    ship_assign_mode = body.get("ship_assign_mode", "gm_assign")

    if not creator_name:
        return JSONResponse({"error": "Creator name is required."}, status_code=400)

    try:
        session, user = session_manager.create_session(
            creator_name=creator_name,
            has_gm=has_gm,
            gm_password=gm_password,
            ship_assign_mode=ship_assign_mode,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return JSONResponse({
        "keyword": session.keyword,
        "user": {
            "name": user.name,
            "role": user.role,
            "ship_ids": user.ship_ids,
            "token": user.token,
        },
    })


@app.get("/api/session/list")
async def api_list_sessions():
    """List all sessions with summary info."""
    sessions = session_manager.list_sessions()
    return JSONResponse({"sessions": sessions})


@app.delete("/api/session/{keyword}")
async def api_delete_session(keyword: str):
    """Delete a session permanently."""
    deleted = session_manager.purge_session(keyword)
    if deleted:
        return JSONResponse({"deleted": keyword})
    return JSONResponse({"error": "Session not found."}, status_code=404)


# ---------------------------------------------------------------------------
# API routes — Dice
# ---------------------------------------------------------------------------

@app.post("/api/dice/roll")
async def api_dice_roll(request: Request):
    """
    Roll dice via the server-side engine.

    Body: { "expression": "3d6+4" }
    Returns: { "result": "14", "breakdown": "4, 5, 1 = 14", "total": 14 }
    """
    if not dice_roller:
        return JSONResponse({"error": "Dice engine not available."}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    expression = body.get("expression", "").strip()
    if not expression:
        return JSONResponse({"error": "Expression is required."}, status_code=400)

    try:
        raw = dice_roller(expression)
    except Exception as e:
        return JSONResponse({"error": f"Dice error: {e}"}, status_code=400)

    # Normalize: psi_dice returns tuple (total, breakdown, is_verbose)
    if isinstance(raw, tuple):
        total = raw[0] if len(raw) > 0 else 0
        breakdown = raw[1] if len(raw) > 1 else str(total)
        is_verbose = raw[2] if len(raw) > 2 else False

        # Check for error results
        if total == 'Error':
            return JSONResponse({"error": str(breakdown)}, status_code=400)

        return JSONResponse({
            "result": str(total),
            "breakdown": str(breakdown),
            "total": total,
            "is_verbose": is_verbose,
            "expression": expression,
        })
    elif isinstance(raw, dict):
        return JSONResponse(raw)
    else:
        return JSONResponse({
            "result": str(raw),
            "breakdown": str(raw),
            "total": str(raw),
        })


@app.get("/dice-test", response_class=HTMLResponse)
async def dice_test_page(request: Request):
    """Web-based dice roller test suite."""
    return templates.TemplateResponse("dice_test.html", {
        "request": request,
        "version": VERSION,
    })


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/{keyword}")
async def websocket_endpoint(websocket: WebSocket, keyword: str):
    """
    WebSocket endpoint for real-time session sync.

    The client connects, sends an AUTH message, and then enters
    bidirectional message exchange. See ws_protocol.py for the
    full message specification.
    """
    await ws_handler.handle_connection(websocket, keyword)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({
        "status": "ok",
        "version": VERSION,
        "active_sessions": len(session_manager._sessions),
        "dice_available": dice_roller is not None,
    })
