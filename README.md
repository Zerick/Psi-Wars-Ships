# Psi-Wars Space Combat Simulator
## Slice 1 — The Table

Shared session · Chat/Roll log · Dice roller · GM review

---

## What Slice 1 does

When complete, a GM and two or more players can:

- Open the app in a browser — no installation on their end
- Join a shared session using an invite code
- Type messages that appear in a shared log for everyone
- Roll dice using `[[3d6+2]]` syntax — results appear for everyone
- The GM sees each roll privately first and can **Approve**, **Override**, or **Re-roll** it
- Refresh the browser and rejoin — session and full log history persist

No ships, no combat rules — those are Slice 2 onwards.

---

## Prerequisites (on the Raspberry Pi)

```bash
# Python 3.11+
python3 --version

# Node 18+
node --version
npm --version
```

If Node is not installed:
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

---

## Setup

### 1. Create a dedicated user (recommended)

```bash
sudo adduser psiwars
sudo su - psiwars
```

All subsequent commands run as the `psiwars` user.

### 2. Clone / copy the project

```bash
# If you have git set up:
git clone <your-repo-url> psi-wars
cd psi-wars

# Or copy the zip and unzip it:
# unzip psi-wars.zip
# cd psi-wars
```

### 3. Backend setup

```bash
cd backend

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy dice_engine.py from SquareBracketDiceBot
# It is already included in this project — no action needed.
# (Source: https://github.com/Zerick/SquareBracketDiceBot — MIT licence)
```

#### Database location

By default the SQLite database is created as `./psiwars.db` in the `backend/`
directory. This is fine for development on the SD card.

When you add an SSD later, point it at your mount:
```bash
# In backend/config.py, change:
DB_PATH = "/mnt/ssd/psiwars/psiwars.db"
# Or set the environment variable:
export PSIWARS_DB_PATH=/mnt/ssd/psiwars/psiwars.db
```

### 4. Frontend setup

Open a second terminal (or SSH session):

```bash
cd psi-wars/frontend
npm install
```

---

## Running in development

### Terminal 1 — Backend

```bash
cd psi-wars/backend
source venv/bin/activate
python main.py
# Starts on http://0.0.0.0:8000
```

### Terminal 2 — Frontend (Vite dev server)

```bash
cd psi-wars/frontend
npm run dev
# Starts on http://localhost:5173
# Proxies /sessions and /ws to the backend automatically
```

Open **http://localhost:5173** in your browser (or use the Pi's IP from another machine).

To test multiplayer: open two browser tabs — create a session in one, join with the invite code in the other.

---

## Running in production (single process)

Build the frontend once and serve it from FastAPI directly:

```bash
cd psi-wars/frontend
npm run build
# Produces frontend/dist/

cd ../backend
source venv/bin/activate
python main.py
```

Now visit **http://<pi-ip>:8000** — no Vite server needed.

---

## Making it accessible via Cloudflare Tunnel

You already have `cloudflared` running for other services.

Add a route to your tunnel config (usually `~/.cloudflared/config.yml`):

```yaml
ingress:
  - hostname: psiwars.simonious.com
    service: http://localhost:8000
  # ... your other rules
  - service: http_status:404
```

Then restart cloudflared:
```bash
sudo systemctl restart cloudflared
```

And add the DNS route in Cloudflare:
```bash
cloudflared tunnel route dns kepler-tunnel psiwars.simonious.com
```

---

## Making it a service (when you're ready)

Once you've confirmed everything works in a terminal, create a systemd service:

```bash
sudo nano /etc/systemd/system/psiwars.service
```

```ini
[Unit]
Description=Psi-Wars Combat Simulator
After=network.target

[Service]
User=psiwars
WorkingDirectory=/home/psiwars/psi-wars/backend
ExecStart=/home/psiwars/psi-wars/backend/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable psiwars
sudo systemctl start psiwars
sudo systemctl status psiwars
```

---

## Testing the acceptance criteria

Open the app in two browser tabs. The build passes when:

1. GM creates a session and receives an invite code
2. Player opens second tab, enters the code, joins as Player
3. Both see each other in the participant list
4. GM types a message — appears in both tabs
5. Player types a message — appears in both tabs
6. Player types `[[3d6]] I test the engines` — does **not** appear in the shared log yet
7. GM sees the roll in their review panel with dice breakdown
8. GM clicks **Approve** — roll appears in both tabs with individual dice shown
9. Player types `[[3d6]] another roll` — GM clicks **Override**, enters 18 — log shows 18 with original struck through
10. GM refreshes their tab — full log history still present, pending rolls still in queue
11. Player refreshes their tab — full log history still present

---

## Dice syntax

Supported by the underlying `dice_engine.py` (SquareBracketDiceBot):

| Syntax | Meaning |
|--------|---------|
| `[[3d6]]` | Roll 3 six-sided dice |
| `[[1d20+5]]` | Roll 1d20, add 5 |
| `[[2d6-1]]` | Roll 2d6, subtract 1 |
| `[[4d6dl1]]` | Roll 4d6, drop lowest 1 (stat generation) |
| `[[1d20a]]` | Advantage (roll twice, keep highest) |
| `[[1d20d]]` | Disadvantage (roll twice, keep lowest) |

You can include a label: `[[3d6]] I attempt to repair the engines`

---

## Project structure

```
psi-wars/
  backend/
    main.py              # FastAPI app — REST + WebSocket endpoints
    session_manager.py   # Session creation, join, token store
    log_manager.py       # Append/retrieve combat log, pending rolls
    roll_handler.py      # Wraps dice_engine.py
    dice_engine.py       # SquareBracketDiceBot — do not modify
    ws_manager.py        # WebSocket connection manager + broadcast
    models.py            # SQLite schema + init
    config.py            # Environment config
    requirements.txt
  frontend/
    src/
      App.jsx
      views/
        JoinView.jsx
        SessionView.jsx
      components/
        LogFeed.jsx
        RollInput.jsx
        GMPanel.jsx
        RoleTag.jsx
      hooks/
        useWebSocket.js
        useSession.js
    index.html
    package.json
    vite.config.js
    tailwind.config.js
  README.md
```

---

## Architecture notes

- **No auth passwords** — tokens are UUIDs issued at join, held in server memory. Proper auth is a later slice.
- **Tokens survive browser refresh** — they are stored in React state only, so a hard refresh means rejoining with your invite code. This is intentional for the PoC.
- **Rolls are never broadcast until the GM acts** — the flow is: roll detected → log entry created in DB (hidden) → pending_roll record created → GM notified via WebSocket → GM approves/overrides/rerolls → broadcast to all.
- **SQLite WAL mode** is enabled for better concurrent read performance on the Pi.
- **Async-first** — no simultaneous presence required. Pending rolls persist server-side across GM reconnects.

---

*Slice 1 of the Psi-Wars Space Combat Simulator — built on the SquareBracketDiceBot dice engine (MIT) by Simonious.*
# Psi-Wars-Ships

---

<!-- FILE_INDEX_START -->
## File Index

_Auto-generated by `update_readme_index.py` — do not edit this section manually._

### (root)
- [`.gitignore`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/.gitignore) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/.gitignore`
- [`README.md`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/README.md) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/README.md`
- [`update_readme_index.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/update_readme_index.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/update_readme_index.py`

### `backend/`
- [`backend/combat_manager.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/combat_manager.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/combat_manager.py`
- [`backend/config.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/config.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/config.py`
- [`backend/dice_engine.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/dice_engine.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/dice_engine.py`
- [`backend/log_manager.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/log_manager.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/log_manager.py`
- [`backend/main.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/main.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/main.py`
- [`backend/models.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/models.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/models.py`
- [`backend/requirements.txt`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/requirements.txt) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/requirements.txt`
- [`backend/roll_handler.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/roll_handler.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/roll_handler.py`
- [`backend/scenario_manager.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/scenario_manager.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/scenario_manager.py`
- [`backend/session_manager.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/session_manager.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/session_manager.py`
- [`backend/ship_library.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/ship_library.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/ship_library.py`
- [`backend/ws_manager.py`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/backend/ws_manager.py) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/backend/ws_manager.py`

### `frontend/`
- [`frontend/index.html`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/index.html) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/index.html`
- [`frontend/package-lock.json`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/package-lock.json) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/package-lock.json`
- [`frontend/package.json`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/package.json) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/package.json`
- [`frontend/postcss.config.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/postcss.config.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/postcss.config.js`
- [`frontend/src/App.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/App.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/App.jsx`
- [`frontend/src/components/ChaseResultPanel.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/ChaseResultPanel.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/ChaseResultPanel.jsx`
- [`frontend/src/components/CombatActionPanels.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/CombatActionPanels.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/CombatActionPanels.jsx`
- [`frontend/src/components/CombatSetupPanel.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/CombatSetupPanel.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/CombatSetupPanel.jsx`
- [`frontend/src/components/DeclarationPanel.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/DeclarationPanel.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/DeclarationPanel.jsx`
- [`frontend/src/components/ForceScreenBar.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/ForceScreenBar.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/ForceScreenBar.jsx`
- [`frontend/src/components/GMPanel.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/GMPanel.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/GMPanel.jsx`
- [`frontend/src/components/InitiativeTracker.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/InitiativeTracker.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/InitiativeTracker.jsx`
- [`frontend/src/components/InlineEdit.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/InlineEdit.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/InlineEdit.jsx`
- [`frontend/src/components/LogFeed.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/LogFeed.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/LogFeed.jsx`
- [`frontend/src/components/PilotBar.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/PilotBar.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/PilotBar.jsx`
- [`frontend/src/components/PlayerChasePanel.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/PlayerChasePanel.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/PlayerChasePanel.jsx`
- [`frontend/src/components/RoleTag.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/RoleTag.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/RoleTag.jsx`
- [`frontend/src/components/RollInput.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/RollInput.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/RollInput.jsx`
- [`frontend/src/components/ShipCard.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/ShipCard.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/ShipCard.jsx`
- [`frontend/src/components/ShipCardOpponent.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/ShipCardOpponent.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/ShipCardOpponent.jsx`
- [`frontend/src/components/ShipHPBar.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/ShipHPBar.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/ShipHPBar.jsx`
- [`frontend/src/components/ShipsZone.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/ShipsZone.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/ShipsZone.jsx`
- [`frontend/src/components/SystemsGrid.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/SystemsGrid.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/SystemsGrid.jsx`
- [`frontend/src/components/WeaponsList.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/components/WeaponsList.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/components/WeaponsList.jsx`
- [`frontend/src/hooks/useCombat.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/hooks/useCombat.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/hooks/useCombat.js`
- [`frontend/src/hooks/useScenario.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/hooks/useScenario.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/hooks/useScenario.js`
- [`frontend/src/hooks/useSession.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/hooks/useSession.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/hooks/useSession.js`
- [`frontend/src/hooks/useWebSocket.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/hooks/useWebSocket.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/hooks/useWebSocket.js`
- [`frontend/src/index.css`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/index.css) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/index.css`
- [`frontend/src/main.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/main.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/main.jsx`
- [`frontend/src/views/JoinView.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/views/JoinView.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/views/JoinView.jsx`
- [`frontend/src/views/ScenarioSetupPanel.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/views/ScenarioSetupPanel.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/views/ScenarioSetupPanel.jsx`
- [`frontend/src/views/SessionView.jsx`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/src/views/SessionView.jsx) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/src/views/SessionView.jsx`
- [`frontend/tailwind.config.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/tailwind.config.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/tailwind.config.js`
- [`frontend/vite.config.js`](https://github.com/Zerick/Psi-Wars-Ships/blob/main/frontend/vite.config.js) · raw: `https://raw.githubusercontent.com/Zerick/Psi-Wars-Ships/main/frontend/vite.config.js`

<!-- FILE_INDEX_END -->
