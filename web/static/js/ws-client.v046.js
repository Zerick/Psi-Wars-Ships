/* =============================================================================
   Psi-Wars WebSocket Client (ws-client.js)
   =========================================================================

   Manages the WebSocket connection to the game server. Handles:
     - Connection establishment and authentication
     - Token-based reconnection via localStorage
     - Automatic reconnect with exponential backoff
     - Message dispatch to registered event handlers
     - Outgoing message queue during disconnections

   Usage (from app.js):
     import { WSClient } from './ws-client.js';

     const ws = new WSClient(keyword);

     // Register handlers for server messages
     ws.on('AUTH_OK', (payload) => { ... });
     ws.on('FULL_STATE', (payload) => { ... });
     ws.on('SHIP_UPDATED', (payload) => { ... });

     // Send messages to server
     ws.send('CHAT', { message: 'Hello!' });
     ws.send('DICE_ROLL', { expression: '3d6' });

     // Connect (triggers auth flow)
     ws.connect();

   Modification guide:
     - To change reconnect behavior: edit _scheduleReconnect()
     - To add message validation: add to send()
     - To change auth flow: edit _authenticate()
     - To add middleware: wrap _dispatch()
   ============================================================================= */


// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RECONNECT_BASE_DELAY_MS = 1000;    // Start at 1 second
const RECONNECT_MAX_DELAY_MS = 30000;    // Cap at 30 seconds
const RECONNECT_MAX_ATTEMPTS = 20;       // Give up after 20 tries
const HEARTBEAT_INTERVAL_MS = 30000;     // Ping every 30 seconds

// localStorage keys
const LS_KEYWORD = 'psi-wars-keyword';
const LS_TOKEN = 'psi-wars-token';
const LS_NAME = 'psi-wars-name';
const LS_ROLE = 'psi-wars-role';
const LS_GM_PASSWORD = 'psi-wars-gm-password';


// ---------------------------------------------------------------------------
// WSClient
// ---------------------------------------------------------------------------

export class WSClient {

  /**
   * Create a WebSocket client for a specific session.
   *
   * @param {string} keyword - The session keyword to connect to.
   */
  constructor(keyword) {
    this.keyword = keyword;
    this._ws = null;
    this._handlers = {};          // type -> [callback, ...]
    this._reconnectAttempts = 0;
    this._reconnectTimer = null;
    this._heartbeatTimer = null;
    this._intentionalClose = false;
    this._authenticated = false;
    this._pendingQueue = [];      // Messages queued during disconnect

    // Auth state (populated after AUTH_OK)
    this.user = null;             // { name, role, ship_ids, token }
  }

  // ------------------------------------------------------------------
  // Event registration
  // ------------------------------------------------------------------

  /**
   * Register a handler for a server message type.
   *
   * Multiple handlers can be registered for the same type.
   * They are called in registration order.
   *
   * @param {string} type - Message type (e.g. 'AUTH_OK', 'FULL_STATE')
   * @param {Function} callback - Handler function receiving (payload)
   */
  on(type, callback) {
    if (!this._handlers[type]) {
      this._handlers[type] = [];
    }
    this._handlers[type].push(callback);
  }

  /**
   * Remove a handler for a message type.
   *
   * @param {string} type - Message type
   * @param {Function} callback - The specific handler to remove
   */
  off(type, callback) {
    if (!this._handlers[type]) return;
    this._handlers[type] = this._handlers[type].filter(cb => cb !== callback);
  }

  // ------------------------------------------------------------------
  // Connection
  // ------------------------------------------------------------------

  /**
   * Open the WebSocket connection and begin the auth flow.
   *
   * Authentication happens automatically:
   *   1. Check localStorage for a stored token → attempt reconnect
   *   2. If no token, use stored name + optional GM password → fresh join
   *   3. If no stored credentials at all → fire 'AUTH_FAIL' so UI can redirect
   */
  connect() {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      console.warn('[WS] Already connected.');
      return;
    }

    this._intentionalClose = false;

    // Build WebSocket URL (ws:// for http, wss:// for https)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/${this.keyword}`;

    console.log(`[WS] Connecting to ${url}`);
    this._dispatch('CONNECTING', { url });

    try {
      this._ws = new WebSocket(url);
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err);
      this._dispatch('CONNECTION_ERROR', { error: err.message });
      this._scheduleReconnect();
      return;
    }

    this._ws.onopen = () => {
      console.log('[WS] Connected. Authenticating...');
      this._reconnectAttempts = 0;
      this._authenticate();
    };

    this._ws.onmessage = (event) => {
      this._handleMessage(event);
    };

    this._ws.onclose = (event) => {
      console.log(`[WS] Closed (code=${event.code}, reason=${event.reason})`);
      this._stopHeartbeat();
      this._authenticated = false;

      if (!this._intentionalClose) {
        this._dispatch('DISCONNECTED', {
          code: event.code,
          reason: event.reason,
          willReconnect: this._reconnectAttempts < RECONNECT_MAX_ATTEMPTS,
        });
        this._scheduleReconnect();
      }
    };

    this._ws.onerror = (event) => {
      console.error('[WS] Error:', event);
      // onclose will fire after this, which handles reconnection
    };
  }

  /**
   * Gracefully close the connection. No reconnect will be attempted.
   */
  disconnect() {
    this._intentionalClose = true;
    this._stopReconnect();
    this._stopHeartbeat();
    if (this._ws) {
      this._ws.close(1000, 'Client disconnect');
      this._ws = null;
    }
    this._authenticated = false;
  }

  /**
   * Check if the connection is open and authenticated.
   *
   * @returns {boolean}
   */
  get isConnected() {
    return this._ws
      && this._ws.readyState === WebSocket.OPEN
      && this._authenticated;
  }

  // ------------------------------------------------------------------
  // Sending messages
  // ------------------------------------------------------------------

  /**
   * Send a message to the server.
   *
   * If not currently connected, the message is queued and sent
   * after reconnection.
   *
   * @param {string} type - Message type (e.g. 'CHAT', 'DICE_ROLL')
   * @param {Object} payload - Message payload
   * @param {string} [requestId] - Optional request ID for tracking
   */
  send(type, payload = {}, requestId = '') {
    const message = { type, payload };
    if (requestId) {
      message.request_id = requestId;
    }

    if (this.isConnected) {
      this._ws.send(JSON.stringify(message));
    } else {
      // Queue for later (skip AUTH messages, those are handled internally)
      if (type !== 'AUTH') {
        this._pendingQueue.push(message);
      }
    }
  }

  // ------------------------------------------------------------------
  // Authentication (internal)
  // ------------------------------------------------------------------

  /**
   * Send the AUTH message after WebSocket opens.
   *
   * Tries token-based reconnect first, then fresh join with
   * name + optional GM password.
   */
  _authenticate() {
    const storedToken = localStorage.getItem(LS_TOKEN);
    const storedName = localStorage.getItem(LS_NAME);
    const storedKeyword = localStorage.getItem(LS_KEYWORD);
    const gmPassword = localStorage.getItem(LS_GM_PASSWORD) || '';

    // Token reconnect: must match the same session
    if (storedToken && storedKeyword === this.keyword) {
      console.log('[WS] Attempting token reconnect...');
      this._ws.send(JSON.stringify({
        type: 'AUTH',
        payload: {
          name: storedName || '',
          token: storedToken,
          gm_password: '',
        },
      }));
      return;
    }

    // Fresh join: need at least a name
    if (storedName) {
      console.log(`[WS] Fresh join as "${storedName}"`);
      this._ws.send(JSON.stringify({
        type: 'AUTH',
        payload: {
          name: storedName,
          token: '',
          gm_password: gmPassword,
        },
      }));
      // Clear the one-time GM password after sending
      localStorage.removeItem(LS_GM_PASSWORD);
      return;
    }

    // No credentials at all — can't authenticate
    console.warn('[WS] No stored credentials. Redirecting to join page.');
    this._dispatch('AUTH_FAIL', {
      error: 'No credentials found. Please join the session first.',
    });
    this.disconnect();
  }

  // ------------------------------------------------------------------
  // Message handling (internal)
  // ------------------------------------------------------------------

  /**
   * Process an incoming WebSocket message.
   */
  _handleMessage(event) {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error('[WS] Invalid JSON:', event.data);
      return;
    }

    const type = data.type;
    const payload = data.payload || {};

    // Handle auth responses specially
    if (type === 'AUTH_OK') {
      this._onAuthOK(payload);
      return;
    }
    if (type === 'AUTH_FAIL') {
      this._onAuthFail(payload);
      return;
    }

    // Dispatch to registered handlers
    this._dispatch(type, payload);
  }

  /**
   * Handle successful authentication.
   */
  _onAuthOK(payload) {
    this._authenticated = true;
    this.user = payload.user;

    // Store credentials for future reconnection
    localStorage.setItem(LS_KEYWORD, this.keyword);
    localStorage.setItem(LS_TOKEN, payload.user.token);
    localStorage.setItem(LS_NAME, payload.user.name);
    localStorage.setItem(LS_ROLE, payload.user.role);
    // Clear one-time GM password
    localStorage.removeItem(LS_GM_PASSWORD);

    console.log(`[WS] Authenticated as "${payload.user.name}" (${payload.user.role})`);

    // Start heartbeat
    this._startHeartbeat();

    // Flush queued messages
    this._flushQueue();

    // Dispatch to app
    this._dispatch('AUTH_OK', payload);
  }

  /**
   * Handle failed authentication.
   */
  _onAuthFail(payload) {
    console.error('[WS] Auth failed:', payload.error);

    // Clear stored credentials (they're invalid)
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_GM_PASSWORD);

    this._dispatch('AUTH_FAIL', payload);
    this.disconnect();
  }

  // ------------------------------------------------------------------
  // Dispatch
  // ------------------------------------------------------------------

  /**
   * Dispatch a message to all registered handlers for its type.
   */
  _dispatch(type, payload) {
    const handlers = this._handlers[type];
    if (handlers) {
      for (const cb of handlers) {
        try {
          cb(payload);
        } catch (err) {
          console.error(`[WS] Handler error for ${type}:`, err);
        }
      }
    }

    // Also fire a wildcard handler if registered (useful for debugging)
    const wildcardHandlers = this._handlers['*'];
    if (wildcardHandlers) {
      for (const cb of wildcardHandlers) {
        try {
          cb(type, payload);
        } catch (err) {
          console.error('[WS] Wildcard handler error:', err);
        }
      }
    }
  }

  // ------------------------------------------------------------------
  // Reconnection
  // ------------------------------------------------------------------

  _scheduleReconnect() {
    if (this._intentionalClose) return;
    if (this._reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
      console.error('[WS] Max reconnect attempts reached. Giving up.');
      this._dispatch('RECONNECT_FAILED', {
        attempts: this._reconnectAttempts,
      });
      return;
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      RECONNECT_BASE_DELAY_MS * Math.pow(2, this._reconnectAttempts),
      RECONNECT_MAX_DELAY_MS,
    );
    const jitter = delay * 0.2 * Math.random();
    const totalDelay = delay + jitter;

    this._reconnectAttempts++;
    console.log(
      `[WS] Reconnecting in ${Math.round(totalDelay)}ms ` +
      `(attempt ${this._reconnectAttempts}/${RECONNECT_MAX_ATTEMPTS})`
    );

    this._dispatch('RECONNECTING', {
      attempt: this._reconnectAttempts,
      maxAttempts: RECONNECT_MAX_ATTEMPTS,
      delayMs: Math.round(totalDelay),
    });

    this._reconnectTimer = setTimeout(() => {
      this.connect();
    }, totalDelay);
  }

  _stopReconnect() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  }

  // ------------------------------------------------------------------
  // Heartbeat
  // ------------------------------------------------------------------

  _startHeartbeat() {
    this._stopHeartbeat();
    this._heartbeatTimer = setInterval(() => {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        // WebSocket ping/pong is handled at protocol level,
        // but we can send a lightweight keepalive if needed
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  // ------------------------------------------------------------------
  // Queue
  // ------------------------------------------------------------------

  _flushQueue() {
    while (this._pendingQueue.length > 0) {
      const msg = this._pendingQueue.shift();
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        this._ws.send(JSON.stringify(msg));
      }
    }
  }
}


// ---------------------------------------------------------------------------
// Convenience: clear all stored credentials (for "log out")
// ---------------------------------------------------------------------------

export function clearStoredCredentials() {
  localStorage.removeItem(LS_KEYWORD);
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_NAME);
  localStorage.removeItem(LS_ROLE);
  localStorage.removeItem(LS_GM_PASSWORD);
}
