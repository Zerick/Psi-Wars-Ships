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
