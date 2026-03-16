# Psi-Wars Combat Simulator — Web UI

## Version: 0.2.9
## Last Updated: 2026-03-15

---

## Overview

Web-based tactical combat display for a GURPS Psi-Wars space combat simulator.
Built as a modular vanilla JS frontend served by a Python FastAPI backend.
Runs on a Raspberry Pi behind a Cloudflare tunnel.

Currently in **Phase 2** — UI skeleton with mock data. No engine integration yet.

---

## Architecture

```
Browser                         Raspberry Pi
  │                                │
  ├── /combat ──────────────────── FastAPI (uvicorn, port 8080)
  │     ├── main.css               │
  │     ├── app.js (module root)   ├── main.py (routes, API stubs)
  │     │   ├── ship-card.js       ├── psi_dice.py (SBDB dice engine)
  │     │   ├── combat-log.js      └── templates/ & static/
  │     │   ├── engagement-display.js
  │     │   ├── gm-panel.js
  │     │   └── mock-data.js
  │     │
  │     └── (future: real API calls replace mock-data.js)
  │
  └── Cloudflare tunnel ────────── pwdev.simonious.com → localhost:8080
```

---

## File Inventory

### Backend (Python)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server. Routes for pages (`/`, `/combat`), API stubs matching WEB_UI_API_CONTRACT.md, dice roll endpoint `/api/dice/roll`. |
| `psi_dice.py` | Complete port of SquareBracketDiceBot dice engine. Handles: basic rolls (`3d6`), keep/drop (`4d6kh3`), advantage/disadvantage (`1d20a`), batch (`10x3d6`, `4t3d6`), verbose (`v` flag), stats command, help, about. Uses `d20` Python library. |
| `requirements.txt` | Python dependencies: fastapi, uvicorn, d20. |

### Frontend (JavaScript ES Modules)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `app.js` | **Entry point.** Initializes all components, wires callbacks between them. Imports mock data and all components. | (none — runs on DOMContentLoaded) |
| `mock-data.js` | **Test data.** 4 ships, 2 engagements, combat log entries, dice log entries, active state. Replace with API calls in Phase 6. | `MOCK_SHIPS`, `MOCK_ENGAGEMENTS`, `MOCK_COMBAT_LOG`, `MOCK_DICE_LOG`, `MOCK_ACTIVE_STATE` |
| `components/ship-card.js` | **Ship card rendering.** Compact and full modes. Click-to-edit stats (GM always on). Systems as colored text. Weapons with ranges. Source page links via URL lookup table. Expandable detail section. | `createShipCard()`, `renderShipStrip()` |
| `components/combat-log.js` | **Combat log.** Scrolling text feed. Inline dice roller routes `[[expr]]` to server. Total shown inline, breakdown on hover. Verbose mode shows full breakdown. Unknown commands silently ignored. | `createCombatLog()`, `loadMockLog()` |
| `components/engagement-display.js` | **Engagement display.** Shows range band, advantage, matched speed, hugging between engaged ship pairs. Faction on hover. | `createEngagementDisplay()` |
| `components/gm-panel.js` | **GM panel.** Combat controls (undo/redo/pause/end), dice review with filters (none/all/NPC/player), quick actions. | `createGMPanel()` |

### Templates (HTML)

| File | Purpose |
|------|---------|
| `templates/index.html` | Landing page with system status and "Enter Combat" button. |
| `templates/combat.html` | Main combat UI. Grid layout: header, ship strip, engagement strip, combat log, GM panel. Loads `app.js` as ES module. |

### Styles (CSS)

| File | Purpose |
|------|---------|
| `static/css/main.css` | All styles. CSS variables for theming. Sections: layout grid, header, ship cards (full/compact/expanded), systems grid, weapons, HP bars, click-to-edit, engagement strip, combat log (color-coded by event type), GM panel, dice results, version stamp. |

---

## Component API Reference

### Ship Card (`ship-card.js`)

```javascript
// Render a single card
createShipCard(ship, highlight, isCompact, callbacks)
  ship:       Ship data object (matches API contract serialized ship schema)
  highlight:  'active' | 'target' | 'targeting' | null
  isCompact:  boolean — narrow card with minimal info
  callbacks:  {
    gmMode: boolean,                              // enables click-to-edit
    onFieldChange: (shipId, field, newValue) => {},  // dot-path field, e.g. 'pilot.piloting_skill'
    onSubsystemChange: (shipId, sys, newStatus) => {} // sys name, 'ok'|'disabled'|'destroyed'
  }

// Render all cards in the strip
renderShipStrip(containerEl, ships, activeState, callbacks)
  activeState: { active_ship_id, targets: [], targeting: [], current_turn }
```

**Systems list:** armor, cargo, controls, equipment, fuel, habitat, power, propulsion, weaponry

**Source URL lookup:** Internal `SHIP_URLS` map keyed by template base name (e.g. 'wildcat'). Add new ships by adding entries to this map.

### Combat Log (`combat-log.js`)

```javascript
const log = createCombatLog(containerEl);
log.addEntry(message, eventType, turn);   // plain text
log.addHTML(html, eventType, turn);       // HTML content (dice results)
log.clear();
log.scrollToTurn(turnNumber);
loadMockLog(log, entries);                // bulk load from array
```

**Event types for color coding:** turn, chase, attack, defense_ok, defense_fail, damage, system_damage, force_screen, critical_success, critical_failure, info, npc_reasoning, dice

**Dice input:** User types `[[3d6+4]]` in chat → routes to `/api/dice/roll` → shows total inline with hover breakdown. `[[help]]`, `[[about]]`, `[[stats expr]]` also supported.

### Engagement Display (`engagement-display.js`)

```javascript
const eng = createEngagementDisplay(containerEl);
eng.render(engagements, ships);
```

Each engagement shows: Ship A — range band — Ship B, with advantage indicator below range, matched speed/hugging tags.

### GM Panel (`gm-panel.js`)

```javascript
const gm = createGMPanel(containerEl, {
  onUndo: () => {},
  onRedo: () => {},
  onDiceFilter: (filter) => {}  // 'none'|'all'|'npc'|'player'
});
gm.loadDiceLog(entries);
gm.addDiceEntry(entry);
```

---

## Theming (CSS Variables)

All colors, fonts, and dimensions are controlled via CSS variables in `:root`.
Key variables:

- `--bg-deep`, `--bg`, `--bg-panel`, `--bg-card` — background layers
- `--text`, `--text-bright`, `--text-dim`, `--text-muted` — text hierarchy
- `--accent` — primary cyan/blue
- `--success`, `--warn`, `--danger` — semantic colors
- `--highlight-active`, `--highlight-target`, `--highlight-targeting` — card borders
- `--log-*` — combat log event type colors
- `--font-mono`, `--font-display`, `--font-body` — typography
- `--card-width`, `--card-width-expanded` — card sizing
- `--ship-strip-height` — top strip height

---

## Deployment

### Prerequisites
- Python 3.11+ with venv
- `d20` library installed in venv
- systemd service `psiwars-web` running uvicorn on port 8080
- Cloudflare tunnel routing `pwdev.simonious.com` → localhost:8080

### Deploying Updates
1. Transfer zip to Pi via SCP overlay script
2. `sudo systemctl restart psiwars-web`
3. Hard refresh browser (Ctrl+Shift+R) or rely on `?v=X.Y.Z` cache busters
4. Verify version stamp in bottom-right corner

### File Locations on Pi
```
/home/psiwars/psi-wars/web/
├── main.py
├── psi_dice.py
├── requirements.txt
├── venv/
├── static/
│   ├── css/main.css
│   └── js/
│       ├── app.js
│       ├── mock-data.js
│       └── components/
│           ├── ship-card.js
│           ├── combat-log.js
│           ├── engagement-display.js
│           └── gm-panel.js
└── templates/
    ├── index.html
    └── combat.html
```

### Services
- `psiwars-web.service` — the web UI (port 8080)
- `sbdb.service` — SquareBracketDiceBot Discord bot (no port, outbound only)
- Apache on port 80 — serves shared files at `kepler-452b.simonious.com`
- Cloudflare tunnel — routes subdomains to local ports

---

## Roadmap

- [x] Phase 1: Web server setup (v0.1.0)
- [x] Phase 2: UI skeleton with mock data (v0.2.0 → v0.2.9)
- [ ] Phase 3: Session instances with shareable keywords
- [ ] Phase 4: Player/GM login and role-based visibility
- [ ] Phase 5: Engine integration (TurnResolver, replace mock data)
- [ ] Phase 6: Full combat flow with real ships from JSON fixtures

---

## Adding New Ships to URL Lookup

In `ship-card.js`, find the `SHIP_URLS` object inside `sourceUrl()`.
Add a new entry keyed by the template base name:

```javascript
'new_ship_name': 'http://psi-wars.wikidot.com/new-ship-name-class-type',
```

The key must match the template_id with `_vN` suffix stripped.
For example, template_id `hornet_v1` → key `hornet`.

---

## Maintenance Notes

- **All JS is vanilla ES modules** — no build step, no npm, no React.
  Edit files directly, restart service, refresh browser.
- **Each component is self-contained** — ship-card.js knows nothing about
  combat-log.js. The app.js wires them together via callbacks.
- **Mock data is the single source of test state** — change mock-data.js
  to test different scenarios (more ships, different damage states, etc.)
- **CSS is one file** — sections are clearly labeled with `/* === Section === */`
  comments. Use Ctrl+F to find what you need.
- **Cache busting** — version strings in `?v=X.Y.Z` on CSS/JS includes in
  combat.html must be updated with each deploy. Also update the version
  stamp `<div>` in combat.html.
