# =============================================================================
# Psi-Wars Space Combat Simulator — main.py
# =============================================================================
import logging
import re
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
import models
import session_manager as sm
import log_manager as lm
import roll_handler as rh
from ws_manager import manager

from scenario_manager import (
    init_schema as init_scenario_schema,
    create_scenario as _create_scenario,
    get_scenario as _get_scenario,
    get_scenario_by_session as _get_scenario_by_session,
    add_ship as _add_ship,
    patch_ship as _patch_ship,
    patch_pilot as _patch_pilot,
    patch_system as _patch_system,
    patch_weapon as _patch_weapon,
    assign_ship as _assign_ship,
    delete_ship as _delete_ship,
)
from combat_manager import (
    init_combat_schema,
    start_combat as _start_combat,
    get_combat as _get_combat,
    get_active_combat as _get_active_combat,
    get_combat_ranges as _get_combat_ranges,
    update_range as _update_range,
    submit_declaration as _submit_declaration,
    reveal_declarations as _reveal_declarations,
    roll_chase_for_ship as _roll_chase_for_ship,
    submit_attack as _submit_attack,
    submit_defense as _submit_defense,
    submit_damage as _submit_damage,
    advance_phase as _advance_phase,
    mark_ship_acted as _mark_ship_acted,
    end_combat as _end_combat,
    run_npc_declarations as _run_npc_declarations,
    # run_npc_chase_rolls intentionally NOT imported — GM triggers manually
    run_npc_action as _run_npc_action,
    calculate_chase_bonus as _calculate_chase_bonus,
)
from ship_library import SHIP_LIBRARY
from typing import Optional, Any
import aiosqlite


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.init_db()
    await init_scenario_schema()
    await init_combat_schema()
    log.info(f"Psi-Wars backend starting on {config.HOST}:{config.PORT}")
    yield
    log.info("Psi-Wars backend shutting down.")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Psi-Wars Combat Simulator", version="0.1.0-slice1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _require_token(token: str = Query(...)):
    data = sm.resolve_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return data


def _require_gm(token_data: dict = Depends(_require_token)):
    if token_data["role"] != "gm":
        raise HTTPException(status_code=403, detail="GM role required.")
    return token_data

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class CreateSessionRequest(BaseModel):
    display_name: str

class JoinSessionRequest(BaseModel):
    display_name: str
    role: str = "player"

class ChatRequest(BaseModel):
    content: str

class OverrideRequest(BaseModel):
    value: int

class CreateScenarioBody(BaseModel):
    name: str

class AddShipBody(BaseModel):
    library_key: Optional[str] = None
    ship: Optional[dict] = None

class PatchShipBody(BaseModel):
    fields: dict

class PatchPilotBody(BaseModel):
    fields: dict

class PatchSystemBody(BaseModel):
    status: str

class PatchWeaponBody(BaseModel):
    fields: dict

class AssignShipBody(BaseModel):
    user_id: str

class StartCombatBody(BaseModel):
    initiative_roll_style: str = "stat_only"

class DeclarationBody(BaseModel):
    ship_id: str
    round_number: int
    maneuver: str
    pursuit_target_id: Optional[str] = None
    afterburner_active: bool = False
    active_config: Optional[str] = None

class ChaseRollBody(BaseModel):
    ship_id: str
    roll: int

class UpdateRangeBody(BaseModel):
    fields: dict

class AttackBody(BaseModel):
    acting_ship_id: str
    target_ship_id: str
    weapon_id: str
    attack_roll: int
    called_shot_system: Optional[str] = None

class DefenseBody(BaseModel):
    dodge_roll: int

# ---------------------------------------------------------------------------
# Helper: build per-ship chase card data for WS broadcast
# ---------------------------------------------------------------------------
async def _build_chase_cards(combat: dict, db_path: str = "psiwars.db") -> list[dict]:
    """
    Build one chase card payload per ship in the combat.
    Used when broadcasting the chase phase start so the frontend can render
    a Roll button for each ship.
    """
    cards = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        round_number = combat["current_round"]

        for init_row in combat["initiative_order"]:
            ship_id = init_row["ship_id"]

            # Fetch ship and pilot
            async with db.execute("SELECT * FROM ships WHERE ship_id=?", (ship_id,)) as cur:
                ship_row = await cur.fetchone()
            async with db.execute("SELECT * FROM pilots WHERE ship_id=?", (ship_id,)) as cur:
                pilot_row = await cur.fetchone()

            if not ship_row:
                continue

            ship  = dict(ship_row)
            pilot = dict(pilot_row) if pilot_row else {}

            # Coerce booleans
            for f in ["afterburner_available", "afterburner_active"]:
                if f in ship:
                    ship[f] = bool(ship[f])

            # Fetch declaration for this round (may not exist yet if round just started)
            async with db.execute(
                """SELECT * FROM combat_declarations
                   WHERE combat_id=? AND ship_id=? AND round_number=?""",
                (combat["combat_id"], ship_id, round_number)
            ) as cur:
                decl_row = await cur.fetchone()
            decl = dict(decl_row) if decl_row else {}

            # Fetch range row (first one found — single opponent scenario)
            range_row = None
            for r in combat.get("ranges", []):
                if r["ship_a_id"] == ship_id or r["ship_b_id"] == ship_id:
                    range_row = r
                    break
            if range_row is None:
                range_row = {"advantage_ship_id": None}

            # Calculate chase bonus with breakdown
            handling = ship.get("handling", 0)
            sr = ship.get("sr", 0)
            move = ship.get("move_space", 0)
            ship_class = ship.get("ship_class", "fighter")

            if decl.get("afterburner_active") and ship.get("afterburner_available"):
                move += ship.get("afterburner_move_bonus", 0)

            if ship_class == "fighter":
                speed_bonus = min(move // 25, 20)
            elif ship_class == "corvette":
                speed_bonus = min(move // 50, 15)
            else:
                speed_bonus = 0

            breakdown = [
                {"label": "Handling", "value": handling},
                {"label": "SR", "value": sr},
                {"label": "Speed", "value": speed_bonus},
            ]

            adv_bonus = 0
            if range_row.get("advantage_ship_id") == ship_id:
                adv_bonus = 2
                breakdown.append({"label": "Advantage", "value": 2})

            maneuver = decl.get("maneuver", "")
            man_bonus = 0
            if maneuver in ("evade", "move_evade"):
                man_bonus = -2
                breakdown.append({"label": "Evade", "value": -2})
            elif maneuver == "stunt":
                man_bonus = 2
                breakdown.append({"label": "Stunt", "value": 2})
            elif maneuver == "high_g_stunt":
                man_bonus = 3
                breakdown.append({"label": "High-G Stunt", "value": 3})

            chase_bonus = handling + sr + speed_bonus + adv_bonus + man_bonus

            faction = ship.get("faction", "player")
            is_npc = faction in ("hostile_npc", "friendly_npc")

            cards.append({
                "ship_id":        ship_id,
                "ship_name":      ship.get("name", "Unknown"),
                "chase_bonus":    chase_bonus,
                "breakdown":      breakdown,
                "npc":            is_npc,
                "faction":        faction,
                "rolled":         False,
                "roll":           None,
                "mos":            None,
                "combat_id":      combat["combat_id"],
                "owner_user_id":  ship.get("assigned_user_id"),
            })

    return cards

# ---------------------------------------------------------------------------
# REST — Sessions
# ---------------------------------------------------------------------------
@app.post("/sessions")
async def create_session(body: CreateSessionRequest):
    if not body.display_name.strip():
        raise HTTPException(status_code=400, detail="display_name is required.")
    return sm.create_session(body.display_name.strip())


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    session = sm.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    participants = sm.get_participants(session_id)
    return {**session, "participants": participants}


@app.post("/sessions/{invite_code}/join")
async def join_session(invite_code: str, body: JoinSessionRequest):
    if body.role not in ("player", "spectator"):
        raise HTTPException(status_code=400, detail="role must be 'player' or 'spectator'.")
    if not body.display_name.strip():
        raise HTTPException(status_code=400, detail="display_name is required.")

    result = sm.join_session(invite_code, body.display_name.strip(), body.role)
    if not result:
        raise HTTPException(status_code=404, detail="Invite code not found.")

    session_id = result["session_id"]
    await manager.broadcast(session_id, {
        "type": "participant_joined",
        "data": {
            "user_id": result["user_id"],
            "display_name": result["display_name"],
            "role": result["role"],
        }
    })

    log_entries = lm.get_log(session_id, limit=1)
    if log_entries:
        latest = log_entries[-1]
        if latest.get("entry_type") == "system":
            await manager.broadcast(session_id, {"type": "log_entry", "data": latest})

    return result

# ---------------------------------------------------------------------------
# REST — Log
# ---------------------------------------------------------------------------
@app.get("/sessions/{session_id}/log")
async def get_log(session_id: str, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    return lm.get_log(session_id)

# ---------------------------------------------------------------------------
# REST — Chat / Roll
# ---------------------------------------------------------------------------
ROLL_RE = re.compile(r'\[\[([^\]]+)\]\]')

@app.post("/sessions/{session_id}/chat")
async def post_chat(session_id: str, body: ChatRequest, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")

    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required.")

    author_id   = token["user_id"]
    author_name = token["display_name"]
    roll_matches = ROLL_RE.findall(content)

    if not roll_matches:
        entry = lm.append_chat(session_id, author_id, author_name, content)
        await manager.broadcast(session_id, {"type": "log_entry", "data": entry})
        return {"status": "broadcast", "entry": entry}

    results = []
    for expression in roll_matches:
        roll_result = rh.process_roll(expression, author_name, author_id)
        if not roll_result:
            entry = lm.append_chat(session_id, author_id, author_name, content)
            await manager.broadcast(session_id, {"type": "log_entry", "data": entry})
            return {"status": "broadcast", "entry": entry}

        label = ROLL_RE.sub("", content).strip()
        log_entry, pending = lm.create_pending_roll(
            session_id=session_id,
            author_id=author_id,
            author_name=author_name,
            expression=roll_result["expression"],
            dice_results=roll_result["dice_results"],
            total=roll_result["total"],
            content=label,
        )

        await manager.send_to_role(session_id, "gm", {
            "type": "pending_roll",
            "data": {
                "pending_id":   pending["pending_id"],
                "entry_id":     log_entry["entry_id"],
                "rolled_by":    author_name,
                "expression":   roll_result["expression"],
                "breakdown":    roll_result["breakdown"],
                "dice_results": json.loads(roll_result["dice_results"]) if isinstance(roll_result["dice_results"], str) else roll_result["dice_results"],
                "total":        roll_result["total"],
                "label":        label,
            }
        })

        results.append({"status": "pending_gm_review", "pending_id": pending["pending_id"]})

    return {"results": results}

# ---------------------------------------------------------------------------
# REST — GM Roll Actions
# ---------------------------------------------------------------------------
@app.post("/sessions/{session_id}/rolls/{pending_id}/approve")
async def approve_roll(session_id: str, pending_id: str, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    entry = lm.approve_pending_roll(pending_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Pending roll not found.")
    await manager.broadcast(session_id, {"type": "log_entry", "data": entry})
    return {"status": "approved"}


@app.post("/sessions/{session_id}/rolls/{pending_id}/override")
async def override_roll(session_id: str, pending_id: str, body: OverrideRequest, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    entry = lm.override_pending_roll(pending_id, body.value)
    if not entry:
        raise HTTPException(status_code=404, detail="Pending roll not found.")
    await manager.broadcast(session_id, {"type": "log_entry", "data": entry})
    return {"status": "overridden"}


@app.post("/sessions/{session_id}/rolls/{pending_id}/reroll")
async def reroll(session_id: str, pending_id: str, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")

    pending_rows = lm.get_pending_rolls(session_id)
    target = next((p for p in pending_rows if p["pending_id"] == pending_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Pending roll not found.")

    import roll_handler as rh2
    roll_result = rh2.process_roll(target["expression"], target["author_name"], "system")
    if not roll_result:
        raise HTTPException(status_code=500, detail="Re-roll failed.")

    import json as _json
    lm.reroll_pending(pending_id, roll_result["dice_results"], roll_result["total"])

    await manager.send_to_role(session_id, "gm", {
        "type": "pending_roll",
        "data": {
            "pending_id":   pending_id,
            "entry_id":     target.get("log_entry_id", target.get("entry_id", "")),
            "rolled_by":    target["author_name"],
            "expression":   target["expression"],
            "breakdown":    roll_result["breakdown"],
            "dice_results": _json.loads(roll_result["dice_results"]) if isinstance(roll_result["dice_results"], str) else roll_result["dice_results"],
            "total":        roll_result["total"],
            "label":        target.get("content", ""),
        }
    })
    return {"status": "rerolled"}


@app.get("/sessions/{session_id}/pending-rolls")
async def get_pending_rolls(session_id: str, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    return lm.get_pending_rolls(session_id)

# ---------------------------------------------------------------------------
# REST — Participants
# ---------------------------------------------------------------------------
@app.get("/sessions/{session_id}/participants")
async def get_participants(session_id: str, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    return sm.get_participants(session_id)

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = Query(...)):
    token_data = sm.resolve_token(token)
    if not token_data or token_data["session_id"] != session_id:
        await websocket.close(code=4001)
        return

    user_id = token_data["user_id"]
    role    = token_data["role"]

    await manager.connect(websocket, session_id, user_id, role)

    try:
        await websocket.send_json({"type": "connected", "data": {"user_id": user_id, "role": role}})
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        log.info(f"WS disconnected: session={session_id} user={user_id}")

# =============================================================================
# REST — Ship Library, Scenarios, Ships
# =============================================================================

@app.get("/library/ships")
async def get_ship_library(token: dict = Depends(_require_token)):
    return list(SHIP_LIBRARY.values())


@app.post("/scenarios")
async def create_scenario_route(session_id: str = Query(...), body: CreateScenarioBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    scenario = await _create_scenario(session_id, body.name)
    await manager.broadcast(session_id, {"type": "scenario_created", "data": scenario})
    return scenario


@app.get("/sessions/{session_id}/scenario")
async def get_session_scenario(session_id: str, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    is_gm = token["role"] == "gm"
    return await _get_scenario_by_session(session_id, token["user_id"], is_gm)


@app.get("/scenarios/{scenario_id}")
async def get_scenario_route(scenario_id: str, token: dict = Depends(_require_token)):
    is_gm = token["role"] == "gm"
    scenario = await _get_scenario(scenario_id, token["user_id"], is_gm)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


@app.post("/scenarios/{scenario_id}/ships")
async def add_ship_route(scenario_id: str, session_id: str = Query(...), body: AddShipBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    ship = await _add_ship(scenario_id, body.library_key, body.ship)
    await manager.broadcast(session_id, {"type": "ship_added", "data": ship})
    return ship


@app.patch("/scenarios/{scenario_id}/ships/{ship_id}")
async def patch_ship_route(scenario_id: str, ship_id: str, session_id: str = Query(...), body: PatchShipBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    ship = await _patch_ship(ship_id, body.fields)
    if not ship:
        raise HTTPException(status_code=404, detail="Ship not found.")
    await manager.broadcast(session_id, {"type": "ship_updated", "data": ship})
    return ship


@app.patch("/scenarios/{scenario_id}/ships/{ship_id}/pilot")
async def patch_pilot_route(scenario_id: str, ship_id: str, session_id: str = Query(...), body: PatchPilotBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    ship = await _patch_pilot(ship_id, body.fields)
    if not ship:
        raise HTTPException(status_code=404, detail="Ship not found.")
    await manager.broadcast(session_id, {"type": "ship_updated", "data": ship})
    return ship


@app.patch("/scenarios/{scenario_id}/ships/{ship_id}/systems/{system_name}")
async def patch_system_route(scenario_id: str, ship_id: str, system_name: str, session_id: str = Query(...), body: PatchSystemBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    ship = await _patch_system(ship_id, system_name, body.status)
    if not ship:
        raise HTTPException(status_code=404, detail="Ship not found.")
    await manager.broadcast(session_id, {"type": "ship_updated", "data": ship})
    return ship


@app.patch("/scenarios/{scenario_id}/ships/{ship_id}/weapons/{weapon_id}")
async def patch_weapon_route(scenario_id: str, ship_id: str, weapon_id: str, session_id: str = Query(...), body: PatchWeaponBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    ship = await _patch_weapon(ship_id, weapon_id, body.fields)
    if not ship:
        raise HTTPException(status_code=404, detail="Ship not found.")
    await manager.broadcast(session_id, {"type": "ship_updated", "data": ship})
    return ship


@app.put("/scenarios/{scenario_id}/ships/{ship_id}/assign")
async def assign_ship_route(scenario_id: str, ship_id: str, session_id: str = Query(...), body: AssignShipBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    ship = await _assign_ship(ship_id, body.user_id)
    if not ship:
        raise HTTPException(status_code=404, detail="Ship not found.")
    await manager.broadcast(session_id, {
        "type": "ship_assigned",
        "data": {"ship_id": ship_id, "user_id": body.user_id, "ship": ship},
    })
    return ship


@app.delete("/scenarios/{scenario_id}/ships/{ship_id}")
async def delete_ship_route(scenario_id: str, ship_id: str, session_id: str = Query(...), token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    await _delete_ship(ship_id)
    await manager.broadcast(session_id, {"type": "ship_removed", "data": {"ship_id": ship_id}})
    return {"ok": True}

# =============================================================================
# REST — Combat Engine
# =============================================================================

@app.post("/scenarios/{scenario_id}/combat/start")
async def start_combat_route(scenario_id: str, session_id: str = Query(...), body: StartCombatBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    body = body or StartCombatBody()
    combat = await _start_combat(scenario_id, body.initiative_roll_style)
    await manager.broadcast(session_id, {"type": "combat_started", "data": combat})

    # Advance setup -> declaration
    combat = await _advance_phase(combat["combat_id"])
    await manager.broadcast(session_id, {
        "type": "phase_changed",
        "data": {"combat_id": combat["combat_id"], "round": combat["current_round"], "phase": combat["current_phase"]},
    })

    # Auto-submit NPC declarations
    npc_decls = await _run_npc_declarations(combat["combat_id"])
    for nd in npc_decls:
        await manager.broadcast(session_id, {
            "type": "declaration_submitted",
            "data": {"combat_id": combat["combat_id"], "ship_id": nd["ship_id"]},
        })

    # If all ships are NPCs, phase auto-advances to chase — broadcast chase cards
    combat = await _get_combat(combat["combat_id"])
    if combat and combat["current_phase"] == "chase":
        decls = await _reveal_declarations(combat["combat_id"], combat["current_round"])
        await manager.broadcast(session_id, {
            "type": "declarations_revealed",
            "data": {"combat_id": combat["combat_id"], "round": combat["current_round"], "declarations": decls},
        })
        await manager.broadcast(session_id, {
            "type": "phase_changed",
            "data": {"combat_id": combat["combat_id"], "round": combat["current_round"], "phase": "chase"},
        })
        # Broadcast per-ship chase cards — GM will press Roll buttons manually
        chase_cards = await _build_chase_cards(combat)
        await manager.broadcast(session_id, {
            "type": "chase_phase_started",
            "data": {"combat_id": combat["combat_id"], "round": combat["current_round"], "ships": chase_cards},
        })

    return combat


@app.get("/scenarios/{scenario_id}/combat")
async def get_scenario_combat(scenario_id: str, token: dict = Depends(_require_token)):
    combat = await _get_active_combat(scenario_id)
    return combat


@app.get("/combats/{combat_id}/ranges")
async def get_ranges_route(combat_id: str, token: dict = Depends(_require_token)):
    return await _get_combat_ranges(combat_id)


@app.patch("/combats/{combat_id}/ranges/{range_id}")
async def update_range_route(combat_id: str, range_id: str, session_id: str = Query(...), body: UpdateRangeBody = None, token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    rng = await _update_range(range_id, body.fields)
    if not rng:
        raise HTTPException(status_code=404, detail="Range row not found.")
    await manager.broadcast(session_id, {"type": "range_updated", "data": rng})
    return rng


@app.post("/combats/{combat_id}/declare")
async def declare_route(combat_id: str, body: DeclarationBody, token: dict = Depends(_require_token)):
    session_id = token["session_id"]
    try:
        result = await _submit_declaration(
            combat_id, body.ship_id, body.round_number,
            body.maneuver, body.pursuit_target_id,
            body.afterburner_active, body.active_config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await manager.broadcast(session_id, {
        "type": "declaration_submitted",
        "data": {"combat_id": combat_id, "ship_id": body.ship_id, "round": body.round_number},
    })

    if result.get("all_submitted"):
        declarations = await _reveal_declarations(combat_id, body.round_number)
        await manager.broadcast(session_id, {
            "type": "declarations_revealed",
            "data": {"combat_id": combat_id, "round": body.round_number, "declarations": declarations},
        })
        combat = await _get_combat(combat_id)
        if combat:
            await manager.broadcast(session_id, {
                "type": "phase_changed",
                "data": {"combat_id": combat_id, "round": combat["current_round"], "phase": combat["current_phase"]},
            })
        # Broadcast chase cards — no auto NPC rolls
        if combat and combat["current_phase"] == "chase":
            chase_cards = await _build_chase_cards(combat)
            await manager.broadcast(session_id, {
                "type": "chase_phase_started",
                "data": {"combat_id": combat_id, "round": combat["current_round"], "ships": chase_cards},
            })

    return result


@app.post("/combats/{combat_id}/chase/roll")
async def chase_roll_route(combat_id: str, body: ChaseRollBody, token: dict = Depends(_require_token)):
    """
    GM or player submits a chase roll for a ship.
    NPC ships: GM presses the Roll button in the log.
    Player ships: player presses their own Roll button.
    """
    session_id = token["session_id"]
    try:
        result = await _roll_chase_for_ship(combat_id, body.ship_id, body.roll)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await manager.broadcast(session_id, {
        "type": "chase_roll_submitted",
        "data": {
            "combat_id": combat_id,
            "ship_id":   body.ship_id,
            "roll":      body.roll,
            "mos":       result["declaration"].get("chase_mos"),
            "bonus":     result["declaration"].get("chase_bonus_used"),
            "round":     result["declaration"].get("round_number"),
        },
    })

    if result["all_rolled"]:
        await manager.broadcast(session_id, {
            "type": "chase_resolved",
            "data": {"combat_id": combat_id, "updated_ranges": result["updated_ranges"]},
        })
        combat = await _get_combat(combat_id)
        if combat:
            await manager.broadcast(session_id, {
                "type": "phase_changed",
                "data": {"combat_id": combat_id, "round": combat["current_round"], "phase": combat["current_phase"]},
            })

        # Action phase: run NPC actions automatically
        if combat and combat["current_phase"] == "action":
            for init_row in combat["initiative_order"]:
                npc_action = await _run_npc_action(combat_id, init_row["ship_id"])
                if npc_action:
                    # Auto-apply damage to ship
                    if npc_action.get("damage_net") is not None:
                        target_id = npc_action["target_ship_id"]
                        async with aiosqlite.connect("psiwars.db") as db:
                            db.row_factory = aiosqlite.Row
                            async with db.execute("SELECT * FROM ships WHERE ship_id=?", (target_id,)) as cur:
                                t_row = await cur.fetchone()
                        if t_row:
                            t = dict(t_row)
                            new_hp  = max(0, t.get("hp_current", 0) - npc_action["damage_net"])
                            new_fs  = max(0, t.get("force_screen_current", 0) - (npc_action.get("damage_screen_absorbed") or 0))
                            fields  = {
                                "hp_current":           new_hp,
                                "wound_level":          npc_action.get("wound_level_after") or t.get("wound_level", "none"),
                                "force_screen_current": new_fs,
                            }
                            if npc_action.get("wound_level_after") == "lethal":
                                fields["is_destroyed"] = True
                            updated_ship = await _patch_ship(target_id, fields)
                            if updated_ship:
                                await manager.broadcast(session_id, {"type": "ship_updated", "data": updated_ship})

                        # Enrich action with ship/weapon names for log cards
                        async with aiosqlite.connect("psiwars.db") as _db2:
                            _db2.row_factory = aiosqlite.Row
                            async with _db2.execute("SELECT name FROM ships WHERE ship_id=?", (init_row["ship_id"],)) as _c:
                                _actor = await _c.fetchone()
                            async with _db2.execute("SELECT name FROM ships WHERE ship_id=?", (target_id,)) as _c:
                                _tgt = await _c.fetchone()
                            _wpn = None
                            if npc_action.get("weapon_id"):
                                async with _db2.execute("SELECT name FROM weapons WHERE weapon_id=?", (npc_action["weapon_id"],)) as _c:
                                    _wpn = await _c.fetchone()
                        npc_action["acting_ship_name"] = _actor["name"] if _actor else "Attacker"
                        npc_action["target_ship_name"] = _tgt["name"] if _tgt else "Target"
                        npc_action["weapon_name"]      = _wpn["name"] if _wpn else "Weapon"
                        npc_action["hp_before"]        = t.get("hp_current", 0) if t_row else None
                        npc_action["hp_after"]         = new_hp if t_row else None
                        npc_action["screen_before"]    = t.get("force_screen_current", 0) if t_row else None
                        npc_action["screen_after"]     = new_fs if t_row else None

                    await manager.broadcast(session_id, {"type": "action_submitted", "data": npc_action})
                    if npc_action.get("damage_net") is not None:
                        await manager.broadcast(session_id, {"type": "damage_submitted", "data": npc_action})
                    await manager.broadcast(session_id, {
                        "type": "ship_acted",
                        "data": {"combat_id": combat_id, "ship_id": init_row["ship_id"]},
                    })

                    # Check if target is destroyed — end combat automatically
                    if npc_action.get("wound_level_after") == "lethal":
                        ended = await _end_combat(combat_id)
                        await manager.broadcast(session_id, {"type": "combat_ended", "data": {"combat_id": combat_id}})
                        return result

            # After all NPC actions, check if all have acted → new round
            combat = await _get_combat(combat_id)
            if combat and all(i["has_acted"] for i in combat["initiative_order"]):
                combat = await _advance_phase(combat_id)  # action -> end_round
                combat = await _advance_phase(combat_id)  # end_round -> declaration (new round)
                await manager.broadcast(session_id, {
                    "type": "round_ended",
                    "data": {"combat_id": combat_id, "round": combat["current_round"]},
                })
                # Auto-submit NPC declarations for new round
                npc_decls = await _run_npc_declarations(combat_id)
                for nd in npc_decls:
                    await manager.broadcast(session_id, {
                        "type": "declaration_submitted",
                        "data": {"combat_id": combat_id, "ship_id": nd["ship_id"]},
                    })
                # If all NPC, advance to chase and broadcast chase cards
                combat = await _get_combat(combat_id)
                if combat and combat["current_phase"] == "chase":
                    decls = await _reveal_declarations(combat_id, combat["current_round"])
                    await manager.broadcast(session_id, {
                        "type": "declarations_revealed",
                        "data": {"combat_id": combat_id, "round": combat["current_round"], "declarations": decls},
                    })
                    await manager.broadcast(session_id, {
                        "type": "phase_changed",
                        "data": {"combat_id": combat_id, "round": combat["current_round"], "phase": "chase"},
                    })
                    chase_cards = await _build_chase_cards(combat)
                    await manager.broadcast(session_id, {
                        "type": "chase_phase_started",
                        "data": {"combat_id": combat_id, "round": combat["current_round"], "ships": chase_cards},
                    })

    return result


@app.post("/combats/{combat_id}/actions")
async def submit_attack_route(combat_id: str, session_id: str = Query(...), body: AttackBody = None, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    combat = await _get_combat(combat_id)
    if not combat:
        raise HTTPException(status_code=404, detail="Combat not found.")
    try:
        action = await _submit_attack(
            combat_id, combat["current_round"],
            body.acting_ship_id, body.target_ship_id,
            body.weapon_id, body.attack_roll, body.called_shot_system,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await manager.broadcast(session_id, {"type": "action_submitted", "data": action})
    return action


@app.post("/combats/{combat_id}/actions/{action_id}/defense")
async def submit_defense_route(combat_id: str, action_id: str, session_id: str = Query(...), body: DefenseBody = None, token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    try:
        action = await _submit_defense(action_id, body.dodge_roll)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await manager.broadcast(session_id, {"type": "defense_submitted", "data": action})
    return action


@app.post("/combats/{combat_id}/actions/{action_id}/damage")
async def submit_damage_route(combat_id: str, action_id: str, session_id: str = Query(...), token: dict = Depends(_require_token)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    try:
        action = await _submit_damage(action_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Auto-apply damage to ship — no GM click required
    target_id = action.get("target_ship_id")
    if target_id and action.get("damage_net") is not None:
        async with aiosqlite.connect("psiwars.db") as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ships WHERE ship_id=?", (target_id,)) as cur:
                t_row = await cur.fetchone()
        if t_row:
            t = dict(t_row)
            new_hp = max(0, t.get("hp_current", 0) - action["damage_net"])
            new_fs = max(0, t.get("force_screen_current", 0) - (action.get("damage_screen_absorbed") or 0))
            fields = {
                "hp_current":           new_hp,
                "wound_level":          action.get("wound_level_after") or t.get("wound_level", "none"),
                "force_screen_current": new_fs,
            }
            if action.get("wound_level_after") == "lethal":
                fields["is_destroyed"] = True
            updated_ship = await _patch_ship(target_id, fields)
            if updated_ship:
                await manager.broadcast(session_id, {"type": "ship_updated", "data": updated_ship})
            action["hp_before"]     = t.get("hp_current", 0)
            action["hp_after"]      = new_hp
            action["screen_before"] = t.get("force_screen_current", 0)
            action["screen_after"]  = new_fs

    await manager.broadcast(session_id, {"type": "damage_submitted", "data": action})

    # If ship destroyed, end combat
    if action.get("wound_level_after") == "lethal":
        ended = await _end_combat(combat_id)
        await manager.broadcast(session_id, {"type": "combat_ended", "data": {"combat_id": combat_id}})

    return action


@app.post("/combats/{combat_id}/actions/{action_id}/acted")
async def mark_acted_route(combat_id: str, action_id: str, session_id: str = Query(...), ship_id: str = Query(...), token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    combat = await _mark_ship_acted(combat_id, ship_id)
    await manager.broadcast(session_id, {"type": "ship_acted", "data": {"combat_id": combat_id, "ship_id": ship_id}})

    if all(i["has_acted"] for i in combat["initiative_order"]):
        combat = await _advance_phase(combat_id)
        combat = await _advance_phase(combat_id)
        await manager.broadcast(session_id, {
            "type": "round_ended",
            "data": {"combat_id": combat_id, "round": combat["current_round"]},
        })
        npc_decls = await _run_npc_declarations(combat_id)
        for nd in npc_decls:
            await manager.broadcast(session_id, {
                "type": "declaration_submitted",
                "data": {"combat_id": combat_id, "ship_id": nd["ship_id"]},
            })
        combat = await _get_combat(combat_id)
        if combat and combat["current_phase"] == "chase":
            decls = await _reveal_declarations(combat_id, combat["current_round"])
            await manager.broadcast(session_id, {
                "type": "declarations_revealed",
                "data": {"combat_id": combat_id, "round": combat["current_round"], "declarations": decls},
            })
            await manager.broadcast(session_id, {
                "type": "phase_changed",
                "data": {"combat_id": combat_id, "round": combat["current_round"], "phase": "chase"},
            })
            chase_cards = await _build_chase_cards(combat)
            await manager.broadcast(session_id, {
                "type": "chase_phase_started",
                "data": {"combat_id": combat_id, "round": combat["current_round"], "ships": chase_cards},
            })

    return combat


@app.post("/combats/{combat_id}/phase/advance")
async def advance_phase_route(combat_id: str, session_id: str = Query(...), token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    try:
        combat = await _advance_phase(combat_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    event_type = "round_ended" if combat["current_phase"] == "declaration" else "phase_changed"
    await manager.broadcast(session_id, {
        "type": event_type,
        "data": {"combat_id": combat_id, "round": combat["current_round"], "phase": combat["current_phase"]},
    })
    return combat


@app.post("/combats/{combat_id}/end")
async def end_combat_route(combat_id: str, session_id: str = Query(...), token: dict = Depends(_require_gm)):
    if token["session_id"] != session_id:
        raise HTTPException(status_code=403, detail="Token not valid for this session.")
    combat = await _end_combat(combat_id)
    await manager.broadcast(session_id, {"type": "combat_ended", "data": {"combat_id": combat_id}})
    return combat


# ---------------------------------------------------------------------------
# Serve built frontend
# ---------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index))

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
