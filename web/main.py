"""
Psi-Wars Combat Simulator — Web UI Server
FastAPI application serving the combat simulator web interface.

Endpoints match WEB_UI_API_CONTRACT.md v1.0
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import json
import time

app = FastAPI(
    title="Psi-Wars Combat Simulator",
    version="0.1.0",
    docs_url="/api/docs",
)

# ---------------------------------------------------------------------------
# Static files & templates
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def render_template(name: str) -> HTMLResponse:
    """Serve an HTML file from templates/."""
    path = BASE_DIR / "templates" / name
    return HTMLResponse(path.read_text())


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time(), "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Ship Catalog (Setup Screen)
# ---------------------------------------------------------------------------
@app.get("/api/catalog/ships")
async def catalog_ships():
    """Return all available ship templates grouped by category.
    
    TODO: Load from JSON fixtures in the engine's data layer.
    Currently returns mock data for UI development.
    """
    return {"categories": [], "_mock": True}


# ---------------------------------------------------------------------------
# Session Lifecycle
# ---------------------------------------------------------------------------
@app.post("/api/session/create")
async def session_create():
    """Create a new empty combat session."""
    return {"session_id": "stub", "_mock": True}


@app.post("/api/session/add-faction")
async def session_add_faction(request: Request):
    """Add a faction to the session."""
    body = await request.json()
    return {"ok": True, "faction": body.get("name"), "_mock": True}


@app.post("/api/session/set-relationship")
async def session_set_relationship(request: Request):
    """Set relationship between two factions."""
    body = await request.json()
    return {"ok": True, "_mock": True}


@app.post("/api/session/add-ship")
async def session_add_ship(request: Request):
    """Add a ship to the session."""
    body = await request.json()
    return {
        "ok": True,
        "ship_id": "ship_stub",
        "display_name": body.get("display_name", "Unknown"),
        "_mock": True,
    }


@app.post("/api/session/create-engagement")
async def session_create_engagement(request: Request):
    """Create an engagement between two ships."""
    body = await request.json()
    return {"ok": True, "_mock": True}


@app.get("/api/session/state")
async def session_state():
    """Return full serialized session state."""
    return {"ships": [], "engagements": [], "factions": [], "_mock": True}


# ---------------------------------------------------------------------------
# Combat Turn
# ---------------------------------------------------------------------------
@app.post("/api/turn/begin")
async def turn_begin():
    """Begin a new turn. Returns first TurnState."""
    return {
        "phase": "AWAITING_DECLARATIONS",
        "status": "Waiting for engine integration.",
        "prompt": "Engine not connected yet.",
        "prompt_type": "info",
        "options": [],
        "ship_id": None,
        "context": {},
        "combat_log_entries": [],
        "_mock": True,
    }


@app.post("/api/turn/decide")
async def turn_decide(request: Request):
    """Submit a decision. Returns next TurnState."""
    body = await request.json()
    return {
        "phase": "TURN_COMPLETE",
        "status": f"Received decision: {body.get('decision_type', '?')}",
        "prompt": "Engine not connected yet.",
        "prompt_type": "info",
        "options": [],
        "ship_id": None,
        "context": {},
        "combat_log_entries": [],
        "_mock": True,
    }


@app.post("/api/turn/advance")
async def turn_advance():
    """Auto-advance through non-decision states."""
    return {
        "phase": "TURN_COMPLETE",
        "status": "Nothing to advance.",
        "prompt": "",
        "prompt_type": "info",
        "options": [],
        "ship_id": None,
        "context": {},
        "combat_log_entries": [],
        "_mock": True,
    }
