"""
Psi-Wars Combat Simulator — Web UI Server v0.3.0
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import re
import time

from psi_dice import process_command

app = FastAPI(
    title="Psi-Wars Combat Simulator",
    version="0.3.0",
    docs_url="/api/docs",
)

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def render_template(name: str) -> HTMLResponse:
    path = BASE_DIR / "templates" / name
    return HTMLResponse(path.read_text())


# -- Pages --
@app.get("/", response_class=HTMLResponse)
async def index():
    return render_template("index.html")

@app.get("/combat", response_class=HTMLResponse)
async def combat():
    return render_template("combat.html")


# -- Health --
@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time(), "version": "0.3.0"}


# -- Dice --
@app.post("/api/dice/roll")
async def dice_roll(request: Request):
    """Process one or more [[expression]] commands.

    Body: { "expression": "3d6+2" }
      or: { "text": "I attack with [[3d6+4]] damage" }

    Single expression returns the command result.
    Text mode finds all [[...]] and returns processed results.
    """
    body = await request.json()

    # Single expression mode
    if "expression" in body:
        result = process_command(body["expression"])
        return result

    # Text mode — find all [[...]] in text
    if "text" in body:
        text = body["text"]
        pattern = re.compile(r'\[\[([^\]]+)\]\]')
        matches = pattern.findall(text)
        results = []
        for m in matches:
            result = process_command(m)
            results.append(result)
        return {"text": text, "matches": matches, "results": results}

    return JSONResponse({"error": "Provide 'expression' or 'text'"}, status_code=400)


# -- Ship Catalog --
@app.get("/api/catalog/ships")
async def catalog_ships():
    return {"categories": [], "_mock": True}


# -- Session Lifecycle --
@app.post("/api/session/create")
async def session_create():
    return {"session_id": "stub", "_mock": True}

@app.post("/api/session/add-faction")
async def session_add_faction(request: Request):
    body = await request.json()
    return {"ok": True, "faction": body.get("name"), "_mock": True}

@app.post("/api/session/set-relationship")
async def session_set_relationship(request: Request):
    return {"ok": True, "_mock": True}

@app.post("/api/session/add-ship")
async def session_add_ship(request: Request):
    body = await request.json()
    return {"ok": True, "ship_id": "ship_stub", "display_name": body.get("display_name", "Unknown"), "_mock": True}

@app.post("/api/session/create-engagement")
async def session_create_engagement(request: Request):
    return {"ok": True, "_mock": True}

@app.get("/api/session/state")
async def session_state():
    return {"ships": [], "engagements": [], "factions": [], "_mock": True}


# -- Combat Turn --
@app.post("/api/turn/begin")
async def turn_begin():
    return {"phase": "AWAITING_DECLARATIONS", "status": "Engine not connected.", "prompt": "", "prompt_type": "info", "options": [], "ship_id": None, "context": {}, "combat_log_entries": [], "_mock": True}

@app.post("/api/turn/decide")
async def turn_decide(request: Request):
    body = await request.json()
    return {"phase": "TURN_COMPLETE", "status": f"Received: {body.get('decision_type', '?')}", "prompt": "", "prompt_type": "info", "options": [], "ship_id": None, "context": {}, "combat_log_entries": [], "_mock": True}

@app.post("/api/turn/advance")
async def turn_advance():
    return {"phase": "TURN_COMPLETE", "status": "Nothing to advance.", "prompt": "", "prompt_type": "info", "options": [], "ship_id": None, "context": {}, "combat_log_entries": [], "_mock": True}
