# Psi-Wars Web UI — v0.4.0

## Session & Multiplayer Phase

### What's New in v0.4.0

This release adds the multiplayer session system:

- **Session lifecycle:** Create, join, browse, and purge sessions via web UI
- **WebSocket real-time sync:** All connected clients see changes instantly
- **Role-based access:**
  - **GM sessions:** GM sees everything, edits silently, controls combat
  - **GM-less sessions:** All players share setup powers equally
- **Ship visibility:**
  - Players see full stats only for ships they control
  - Other ships show limited info (name, class, rough condition)
  - Consensus "See All Stats" toggle: when ALL players enable it, everyone sees everything
- **Reconnection:** Token-based auto-reconnect via localStorage on page refresh
- **Chat system:** Player chat messages with toggle between combat log, chat, or both
- **Session persistence:** Each session saves to a JSON file, survives server restarts
- **Session browser:** View all sessions, enter or delete them


### Quick Start

```bash
# On the Pi (or any machine with Python 3.11+)
cd /home/psiwars/psi-wars/web
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

Then visit `http://<pi-ip>:8080` or `https://pwdev.simonious.com`


### User Flow

1. **GM creates session:** Visit `/create`, enter name + GM password, get keyword
2. **GM shares keyword** with players (e.g. "iron-hawk-7")
3. **Players join:** Visit `/join`, enter keyword + display name
4. **Everyone enters combat UI:** Auto-connects via WebSocket
5. **GM adds ships** and creates engagements
6. **Players see their ships** in full detail, others in limited view
7. **Players can chat,** roll dice, and (when implemented) make combat decisions
8. **If disconnected,** refresh the page — auto-reconnects with stored token

For GM-less sessions: skip the password, all players can add ships/engagements.


### Architecture

```
web/
├── main.py                    ← FastAPI server, routes, WebSocket endpoint
├── session_manager.py         ← Session lifecycle, auth, persistence, permissions
├── ws_handler.py              ← WebSocket message routing, room management
├── ws_protocol.py             ← Protocol specification (message types reference)
├── psi_dice.py                ← SBDB dice engine (unchanged from v0.3.0)
├── requirements.txt           ← fastapi, uvicorn, d20, jinja2
├── sessions/                  ← Session JSON files (one per session, auto-created)
├── static/
│   ├── css/main.css           ← All styles, CSS variables for theming
│   └── js/
│       ├── app.js             ← Entry point, wires WebSocket to components
│       ├── ws-client.js       ← WebSocket client with reconnection
│       └── components/
│           ├── ship-card.js   ← Ship cards (full/limited visibility, click-to-edit)
│           ├── combat-log.js  ← Scrolling log with dice + chat input
│           ├── engagement-display.js ← Range/advantage between engaged ships
│           └── gm-panel.js    ← Dice review, combat controls (GM only)
└── templates/
    ├── index.html             ← Landing page
    ├── create.html            ← Session creation form
    ├── join.html              ← Session join form
    ├── combat.html            ← Main combat UI
    ├── sessions.html          ← Session browser/management
    └── error.html             ← Error page
```


### Session Files

Sessions are stored as JSON in `web/sessions/`. Each file is named `{keyword}.json`.

To delete a session from the command line:
```bash
rm /home/psiwars/psi-wars/web/sessions/iron-hawk-7.json
```

To delete via the web UI: visit `/sessions` and click Delete.


### WebSocket Protocol

Messages are JSON objects with `type` and `payload` fields.

**Client → Server:**
- `AUTH` — Authenticate (first message after connect)
- `CHAT` — Send chat message
- `DICE_ROLL` — Roll dice via server
- `ADD_SHIP` / `REMOVE_SHIP` / `UPDATE_SHIP` — Ship management
- `ASSIGN_SHIP` / `SELECT_SHIP` / `UNASSIGN_SHIP` — Ship assignment
- `ADD_ENGAGEMENT` / `REMOVE_ENGAGEMENT` / `UPDATE_ENGAGEMENT`
- `TOGGLE_SEE_STATS` — Toggle per-player "see all stats" preference
- `UPDATE_ACTIVE_STATE` / `SET_SESSION_STATUS` / `UPDATE_SETTINGS`
- `UNDO` / `REDO` — GM only (placeholders for engine integration)

**Server → Client:**
- `AUTH_OK` / `AUTH_FAIL` — Auth response
- `FULL_STATE` — Complete state push (role-filtered)
- `SHIP_UPDATED` / `SHIP_ADDED` / `SHIP_REMOVED` / `SHIP_ASSIGNED`
- `ENGAGEMENT_ADDED` / `ENGAGEMENT_REMOVED` / `ENGAGEMENT_UPDATED`
- `COMBAT_LOG_ENTRY` / `CHAT_MESSAGE` / `DICE_RESULT`
- `USER_JOINED` / `USER_LEFT`
- `SEE_STATS_CHANGED` — Consensus toggle update
- `ACTIVE_STATE_UPDATED` / `SESSION_STATUS_CHANGED` / `SETTINGS_UPDATED`
- `ERROR` — Error response

Full protocol spec: see `ws_protocol.py`.


### Permission Model

| Action                        | GM  | GM-less (any player) | Player (GM session) |
|-------------------------------|-----|----------------------|---------------------|
| Add/remove ships              | ✓   | ✓                    | ✗                   |
| Create engagements            | ✓   | ✓                    | ✗                   |
| Set factions & relationships  | ✓   | ✓                    | ✗                   |
| Assign ships to players       | ✓   | ✓                    | ✗                   |
| Edit own ship stats           | ✓   | ✓                    | ✓                   |
| Edit any ship stats           | ✓   | ✗                    | ✗                   |
| Silent edits (no log entry)   | ✓   | ✗                    | ✗                   |
| Undo / Redo                   | ✓   | ✗                    | ✗                   |
| See all ship stats always     | ✓   | via consensus toggle | via consensus toggle|
| Roll dice                     | ✓   | ✓                    | ✓                   |
| Send chat messages            | ✓   | ✓                    | ✓                   |
| Toggle "See All Stats"        | n/a | ✓                    | ✓                   |


### Visibility Model

| Ship relationship | Default view      | With "See All Stats" consensus |
|-------------------|-------------------|-------------------------------|
| Own ship          | Full stats        | Full stats                    |
| Any other ship    | Limited (name, class, rough condition) | Full stats |

The "See All Stats" toggle is per-player. When ALL connected non-GM players
have it enabled, the server sends full ship data to everyone. If any one
player turns it off, everyone reverts to the limited view for non-controlled ships.

The GM always sees everything regardless.


### Deploy

```bash
# From Windows: download the zip, then run the overlay script
scp psiwars-web-0.4.0.zip psiwars@192.168.0.95:/home/psiwars/psi-wars/
ssh psiwars@192.168.0.95 "cd /home/psiwars/psi-wars && unzip -o psiwars-web-0.4.0.zip -d web/"
ssh psiwars@192.168.0.95 "sudo systemctl restart psiwars-web"
```


### Version History

| Version | Date       | Changes |
|---------|------------|---------|
| 0.1.0   | 2026-03-15 | Web server setup, landing page, API stubs |
| 0.2.0   | 2026-03-15 | UI skeleton: ship cards, combat log, GM panel |
| 0.2.1–9 | 2026-03-15 | Iterative UI refinements (see handoff doc) |
| 0.3.0   | 2026-03-15 | Full documentation, README, consistent version headers |
| 0.4.0   | 2026-03-16 | Session/multiplayer system, WebSocket sync, role-based visibility |
