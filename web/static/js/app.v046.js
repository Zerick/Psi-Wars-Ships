/* =============================================================================
   Psi-Wars Combat Simulator — Main App (v0.4.0)
   =========================================================================

   Entry point for the combat UI. Connects the WebSocket client to all
   UI components. Replaces the mock-data-driven v0.3.0 app.js.

   Responsibilities:
     - Initialize WebSocket connection
     - Handle auth flow (show overlay → connect → auth → show UI)
     - Route server events to the correct UI components
     - Manage role-based visibility (GM vs player)
     - Handle the see-stats consensus toggle
     - Manage the chat/combat log view toggle

   Modification guide:
     - To add a new server event handler: register with ws.on() in init()
     - To add a new UI component: import it, initialize in _showCombatUI()
     - To change role-based visibility: edit _applyRoleVisibility()
     - To change state rendering: edit _renderFullState()
   ============================================================================= */

import { WSClient, clearStoredCredentials } from './ws-client.v046.js';
import { renderShipStrip } from './components/ship-card.v046.js';
import { createCombatLog, loadMockLog } from './components/combat-log.v046.js';
import { renderEngagementStrip } from './components/engagement-display.v046.js';
import { createGMPanel } from './components/gm-panel.v046.js';


// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/** Current session state received from server */
let sessionState = null;

/** WebSocket client instance */
let ws = null;

/** Combat log component instance */
let combatLog = null;

/** GM panel component instance */
let gmPanel = null;

/** Current log view mode: 'both', 'combat', 'chat' */
let logViewMode = 'both';


// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  const keyword = window.PSI_WARS_KEYWORD;
  if (!keyword) {
    console.error('[App] No session keyword found.');
    return;
  }

  ws = new WSClient(keyword);

  // ------------------------------------------------------------------
  // Connection lifecycle events
  // ------------------------------------------------------------------

  ws.on('CONNECTING', () => {
    _setConnectionStatus('Connecting to server…');
  });

  ws.on('RECONNECTING', ({ attempt, maxAttempts, delayMs }) => {
    _setConnectionStatus(
      `Connection lost. Reconnecting (${attempt}/${maxAttempts})…`
    );
  });

  ws.on('DISCONNECTED', ({ willReconnect }) => {
    if (willReconnect) {
      _setConnectionStatus('Disconnected. Attempting to reconnect…');
    } else {
      _setConnectionStatus('Disconnected.');
    }
    _showOverlay();
  });

  ws.on('RECONNECT_FAILED', () => {
    _setConnectionStatus('Unable to reconnect. Please refresh the page.');
    _showRejoinLink();
  });

  ws.on('CONNECTION_ERROR', ({ error }) => {
    _setConnectionError(`Connection error: ${error}`);
  });

  // ------------------------------------------------------------------
  // Authentication
  // ------------------------------------------------------------------

  ws.on('AUTH_OK', ({ user, state }) => {
    console.log('[App] Authenticated:', user.name, user.role);
    sessionState = state;
    _hideOverlay();
    try {
      _showCombatUI(user, state);
    } catch (err) {
      console.error('[App] Combat UI initialization error:', err);
      document.getElementById('combat-ui').hidden = false;
    }
  });

  ws.on('AUTH_FAIL', ({ error }) => {
    console.error('[App] Auth failed:', error);
    _setConnectionError(error);
    _showRejoinLink();
  });

  // ------------------------------------------------------------------
  // State sync events
  // ------------------------------------------------------------------

  ws.on('FULL_STATE', ({ state }) => {
    sessionState = state;
    _renderFullState(state);
  });

  ws.on('SHIP_UPDATED', ({ ship_id, updates, silent }) => {
    if (sessionState) {
      const ship = sessionState.ships.find(s => s.ship_id === ship_id);
      if (ship) {
        Object.assign(ship, updates);
        _renderShips();
      }
    }
  });

  ws.on('SHIP_ADDED', ({ ship }) => {
    if (sessionState) {
      sessionState.ships.push(ship);
      _renderShips();
    }
  });

  ws.on('SHIP_REMOVED', ({ ship_id }) => {
    if (sessionState) {
      sessionState.ships = sessionState.ships.filter(s => s.ship_id !== ship_id);
      _renderShips();
      _renderEngagements();
    }
  });

  ws.on('SHIP_ASSIGNED', ({ ship_id, player_name }) => {
    // Update will come via FULL_STATE since visibility may change
  });

  ws.on('SHIP_UNASSIGNED', ({ ship_id, player_name }) => {
    // Update will come via FULL_STATE
  });

  // ------------------------------------------------------------------
  // Engagement events
  // ------------------------------------------------------------------

  ws.on('ENGAGEMENT_ADDED', ({ engagement }) => {
    if (sessionState) {
      sessionState.engagements.push(engagement);
      _renderEngagements();
    }
  });

  ws.on('ENGAGEMENT_REMOVED', ({ ship_a_id, ship_b_id }) => {
    if (sessionState) {
      sessionState.engagements = sessionState.engagements.filter(e =>
        !(
          (e.ship_a_id === ship_a_id && e.ship_b_id === ship_b_id) ||
          (e.ship_a_id === ship_b_id && e.ship_b_id === ship_a_id)
        )
      );
      _renderEngagements();
    }
  });

  ws.on('ENGAGEMENT_UPDATED', ({ ship_a_id, ship_b_id, updates }) => {
    if (sessionState) {
      const eng = sessionState.engagements.find(e =>
        (e.ship_a_id === ship_a_id && e.ship_b_id === ship_b_id) ||
        (e.ship_a_id === ship_b_id && e.ship_b_id === ship_a_id)
      );
      if (eng) {
        Object.assign(eng, updates);
        _renderEngagements();
      }
    }
  });

  // ------------------------------------------------------------------
  // Log events
  // ------------------------------------------------------------------

  ws.on('COMBAT_LOG_ENTRY', ({ entry }) => {
    if (combatLog && (logViewMode === 'both' || logViewMode === 'combat')) {
      combatLog.addEntry(entry.message, entry.event_type);
    }
    if (sessionState) {
      sessionState.combat_log.push(entry);
    }
  });

  ws.on('CHAT_MESSAGE', ({ sender, message, timestamp, role }) => {
    if (combatLog && (logViewMode === 'both' || logViewMode === 'chat')) {
      const prefix = `[${sender}]`;
      combatLog.addEntry(`${prefix} ${message}`, 'chat');
    }
    if (sessionState) {
      sessionState.chat_log.push({ sender, message, timestamp, role });
    }
  });

  ws.on('DICE_RESULT', ({ roller, expression, result, breakdown, is_verbose, context, dice_entry }) => {
    if (combatLog) {
      if (is_verbose) {
        // Verbose: show full breakdown inline
        combatLog.addEntry(`${roller} rolls ${breakdown}`, 'info');
      } else {
        // Normal: show total only, breakdown on hover
        combatLog.addEntry(`${roller} rolls ${result}`, 'info', `${expression}: ${breakdown}`);
      }
    }
    if (gmPanel && dice_entry) {
      gmPanel.addDiceEntry(dice_entry);
    }
  });

  // ------------------------------------------------------------------
  // User events
  // ------------------------------------------------------------------

  ws.on('USER_JOINED', ({ name, role }) => {
    if (combatLog) {
      combatLog.addEntry(`${name} joined as ${role}`, 'info');
    }
    _updateConnectedCount();
  });

  ws.on('USER_LEFT', ({ name }) => {
    if (combatLog) {
      combatLog.addEntry(`${name} disconnected`, 'info');
    }
    _updateConnectedCount();
  });

  // ------------------------------------------------------------------
  // Active state and session status
  // ------------------------------------------------------------------

  ws.on('ACTIVE_STATE_UPDATED', ({ active_state }) => {
    if (sessionState) {
      Object.assign(sessionState.active_state, active_state);
      _renderActiveState();
    }
  });

  ws.on('SESSION_STATUS_CHANGED', ({ status }) => {
    if (sessionState) {
      sessionState.status = status;
      _renderSessionStatus();
    }
  });

  ws.on('SETTINGS_UPDATED', ({ settings }) => {
    if (sessionState) {
      Object.assign(sessionState.settings, settings);
    }
  });

  // ------------------------------------------------------------------
  // See Stats consensus
  // ------------------------------------------------------------------

  ws.on('SEE_STATS_CHANGED', ({ user_name, value, consensus }) => {
    // Update local state
    if (sessionState) {
      const u = sessionState.connected_users.find(u => u.name === user_name);
      if (u) u.see_stats = value;
      sessionState.consensus_see_stats = consensus;
    }
    _renderSeeStatsIndicator();
    // Note: FULL_STATE will follow from the server with updated ship visibility
  });

  // ------------------------------------------------------------------
  // Errors
  // ------------------------------------------------------------------

  ws.on('ERROR', ({ error, request_id }) => {
    console.error('[App] Server error:', error);
    if (combatLog) {
      combatLog.addEntry(`⚠ ${error}`, 'info');
    }
  });

  // ------------------------------------------------------------------
  // Debug: log all messages
  // ------------------------------------------------------------------
  // ws.on('*', (type, payload) => { console.log('[WS]', type, payload); });

  // ------------------------------------------------------------------
  // Wire up header controls
  // ------------------------------------------------------------------

  // Log view toggle
  document.querySelectorAll('.log-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      logViewMode = btn.dataset.view;
      document.querySelectorAll('.log-toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _renderLogs();
    });
  });

  // See Stats checkbox
  const seeStatsCheckbox = document.getElementById('see-stats-checkbox');
  if (seeStatsCheckbox) {
    seeStatsCheckbox.addEventListener('change', () => {
      ws.send('TOGGLE_SEE_STATS', { value: seeStatsCheckbox.checked });
    });
  }

  // GM panel toggle
  const gmToggle = document.getElementById('gm-toggle');
  if (gmToggle) {
    gmToggle.addEventListener('click', () => {
      const panel = document.getElementById('gm-panel');
      if (panel) {
        panel.hidden = !panel.hidden;
        gmToggle.classList.toggle('active', !panel.hidden);
      }
    });
  }

  // ------------------------------------------------------------------
  // Connect!
  // ------------------------------------------------------------------
  ws.connect();
});


// ---------------------------------------------------------------------------
// UI rendering
// ---------------------------------------------------------------------------

function _showCombatUI(user, state) {
  const combatUI = document.getElementById('combat-ui');
  combatUI.hidden = false;

  // Set user info in header
  document.getElementById('user-name-display').textContent = user.name;
  const roleBadge = document.getElementById('user-role-badge');
  roleBadge.textContent = user.role.toUpperCase();
  roleBadge.className = `role-badge role-${user.role}`;

  // Initialize combat log
  try {
    const logContainer = document.getElementById('combat-log');
    combatLog = createCombatLog(logContainer, (inputText) => {
      ws.send('DICE_ROLL', { expression: inputText, context: '' });
    }, (chatText) => {
      ws.send('CHAT', { message: chatText });
    });
  } catch (err) {
    console.error('[App] Combat log init failed:', err);
  }

  // Initialize GM panel (if GM)
  if (user.role === 'gm') {
    try {
      const gmContainer = document.getElementById('gm-panel');
      gmPanel = createGMPanel(gmContainer, {
        onUndo: () => ws.send('UNDO'),
        onRedo: () => ws.send('REDO'),
      });
      document.getElementById('gm-toggle').hidden = false;
    } catch (err) {
      console.error('[App] GM panel init failed:', err);
    }
  }

  // Apply role-based visibility
  _applyRoleVisibility(user);

  // Render initial state
  try {
    _renderFullState(state);
  } catch (err) {
    console.error('[App] Render state failed:', err);
  }
}

function _renderFullState(state) {
  if (!state) return;

  sessionState = state;

  _renderShips();
  _renderEngagements();
  _renderActiveState();
  _renderSessionStatus();
  _renderLogs();
  _updateConnectedCount();
  _renderSeeStatsIndicator();
}

function _renderShips() {
  if (!sessionState) return;

  const shipStrip = document.getElementById('ship-strip');
  const activeState = sessionState.active_state || {};
  const currentUser = sessionState.current_user || {};

  renderShipStrip(shipStrip, sessionState.ships, activeState, {
    currentUserShipIds: currentUser.ship_ids || [],
    userRole: currentUser.role,
    onShipEdit: (shipId, field, value) => {
      ws.send('UPDATE_SHIP', {
        ship_id: shipId,
        updates: { [field]: value },
        silent: currentUser.role === 'gm',
      });
    },
    onSubsystemCycle: (shipId, system, newStatus) => {
      ws.send('UPDATE_SHIP', {
        ship_id: shipId,
        updates: { [`subsystem_${system}`]: newStatus },
        silent: currentUser.role === 'gm',
      });
    },
  });
}

function _renderEngagements() {
  if (!sessionState) return;

  const engStrip = document.getElementById('engagement-strip');
  renderEngagementStrip(engStrip, sessionState.engagements, sessionState.ships);
}

function _renderActiveState() {
  if (!sessionState) return;

  const turnDisplay = document.getElementById('turn-display');
  const turn = sessionState.active_state?.current_turn || 0;
  turnDisplay.textContent = `Turn ${turn}`;
}

function _renderSessionStatus() {
  if (!sessionState) return;

  const badge = document.getElementById('session-status-badge');
  badge.textContent = (sessionState.status || 'setup').toUpperCase();
  badge.className = `status-badge status-${sessionState.status || 'setup'}`;
}

function _renderLogs() {
  if (!sessionState || !combatLog) return;

  // Clear and reload based on current view mode
  combatLog.clear();

  if (logViewMode === 'combat' || logViewMode === 'both') {
    for (const entry of (sessionState.combat_log || [])) {
      combatLog.addEntry(entry.message, entry.event_type);
    }
  }

  if (logViewMode === 'chat' || logViewMode === 'both') {
    for (const msg of (sessionState.chat_log || [])) {
      combatLog.addEntry(`[${msg.sender}] ${msg.message}`, 'chat');
    }
  }
}

function _renderSeeStatsIndicator() {
  if (!sessionState) return;

  const toggle = document.getElementById('see-stats-toggle');
  const checkbox = document.getElementById('see-stats-checkbox');
  const indicator = document.getElementById('see-stats-indicator');
  const currentUser = sessionState.current_user;

  // Only show for non-GM users
  if (!currentUser || currentUser.role === 'gm') {
    if (toggle) toggle.hidden = true;
    return;
  }

  if (toggle) toggle.hidden = false;
  if (checkbox) checkbox.checked = currentUser.see_stats || false;

  // Build indicator: show which players have it on/off
  if (indicator && sessionState.see_stats_status) {
    const entries = Object.entries(sessionState.see_stats_status);
    const onCount = entries.filter(([_, v]) => v).length;
    const totalCount = entries.length;

    if (sessionState.consensus_see_stats) {
      indicator.textContent = '✓ All';
      indicator.className = 'see-stats-indicator consensus-on';
      indicator.title = 'All players have See Stats enabled — full visibility active';
    } else {
      indicator.textContent = `${onCount}/${totalCount}`;
      indicator.className = 'see-stats-indicator consensus-off';
      const names = entries
        .filter(([_, v]) => !v)
        .map(([name]) => name)
        .join(', ');
      indicator.title = `Waiting on: ${names || 'nobody'}`;
    }
  }
}

function _updateConnectedCount() {
  if (!sessionState) return;

  const el = document.getElementById('connected-count');
  if (el) {
    const count = (sessionState.connected_users || []).filter(u => u.connected).length;
    el.textContent = `${count} online`;
  }
}

function _applyRoleVisibility(user) {
  // GM-specific elements
  const isGM = user.role === 'gm';
  document.getElementById('gm-toggle').hidden = !isGM;

  // See Stats toggle: show for non-GM users
  const toggle = document.getElementById('see-stats-toggle');
  if (toggle) toggle.hidden = isGM;
}


// ---------------------------------------------------------------------------
// Connection overlay
// ---------------------------------------------------------------------------

function _showOverlay() {
  document.getElementById('connection-overlay').hidden = false;
}

function _hideOverlay() {
  document.getElementById('connection-overlay').hidden = true;
}

function _setConnectionStatus(msg) {
  document.getElementById('connection-status').textContent = msg;
  document.getElementById('connection-error').hidden = true;
  document.getElementById('rejoin-link').hidden = true;
}

function _setConnectionError(msg) {
  const el = document.getElementById('connection-error');
  el.textContent = msg;
  el.hidden = false;
}

function _showRejoinLink() {
  document.getElementById('rejoin-link').hidden = false;
}
