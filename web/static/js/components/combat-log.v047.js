/* =============================================================================
   Combat Log Component (v0.4.0)
   =========================================================================

   Scrolling text log with color-coded entries and input bar at bottom.
   Updated from v0.3.0 to support:
     - Dual-purpose input: dice rolls (via [[expr]]) and chat messages
     - WebSocket callbacks for both dice and chat
     - clear() method for log view switching
     - Preserved: hover-to-expand dice results, auto-scroll, event type colors

   Usage:
     const log = createCombatLog(container, onDiceRoll, onChatMessage);
     log.addEntry('Red Fox attacks!', 'attack');
     log.clear();

   Modification guide:
     - To add new event types: add CSS class .log-{type} in main.css
     - To change input parsing: edit the input handler in _createInputBar()
     - To change scroll behavior: edit _scrollToBottom()
   ============================================================================= */


/**
 * Create a combat log component.
 *
 * @param {HTMLElement} container - Container element for the log.
 * @param {Function} [onDiceRoll] - Callback(expression) when user types [[expr]].
 * @param {Function} [onChatMessage] - Callback(text) when user sends a chat message.
 * @returns {Object} Log API: { addEntry, clear }
 */
export function createCombatLog(container, onDiceRoll = null, onChatMessage = null) {
  container.innerHTML = '';

  // Entries area
  const entries = document.createElement('div');
  entries.className = 'combat-log-entries';
  container.appendChild(entries);

  // Input bar
  const inputBar = _createInputBar(onDiceRoll, onChatMessage);
  container.appendChild(inputBar);

  /**
   * Add an entry to the log.
   *
   * @param {string} message - Plain text message.
   * @param {string} eventType - CSS class suffix for coloring.
   * @param {string|null} tooltip - If provided, the message gets a hover tooltip.
   */
  function addEntry(message, eventType = 'info', tooltip = null) {
    const el = document.createElement('div');
    el.className = `log-entry log-${eventType}`;
    if (tooltip) {
      const span = document.createElement('span');
      span.textContent = message;
      span.className = 'dice-result-hover';
      span.dataset.tooltip = tooltip;
      el.appendChild(span);
    } else {
      el.textContent = message;
    }
    entries.appendChild(el);
    _scrollToBottom(entries);
  }

  /**
   * Add a rich entry with mixed plain text and hoverable dice results.
   *
   * @param {Array} parts - Array of { text, tooltip? } objects.
   *   Parts with a tooltip render as hoverable spans; others as plain text.
   * @param {string} eventType - CSS class suffix for coloring.
   */
  function addRichEntry(parts, eventType = 'info') {
    const el = document.createElement('div');
    el.className = `log-entry log-${eventType}`;
    for (const part of parts) {
      if (part.tooltip) {
        const span = document.createElement('span');
        span.textContent = part.text;
        span.className = 'dice-result-hover';
        span.dataset.tooltip = part.tooltip;
        el.appendChild(span);
      } else {
        el.appendChild(document.createTextNode(part.text));
      }
    }
    entries.appendChild(el);
    _scrollToBottom(entries);
  }

  function clear() {
    entries.innerHTML = '';
  }

  return { addEntry, addRichEntry, clear };
}


/**
 * Load an array of log entries (for initial state sync).
 *
 * @param {Object} logApi - The log API returned by createCombatLog().
 * @param {Array} logEntries - Array of { message, event_type } objects.
 */
export function loadMockLog(logApi, logEntries) {
  for (const entry of logEntries) {
    logApi.addEntry(entry.message, entry.event_type);
  }
}


// ---------------------------------------------------------------------------
// Internal
// ---------------------------------------------------------------------------

function _createInputBar(onDiceRoll, onChatMessage) {
  const bar = document.createElement('div');
  bar.className = 'combat-log-input';

  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Type [[3d6]] for dice, or chat message…';
  input.autocomplete = 'off';

  const sendBtn = document.createElement('button');
  sendBtn.className = 'btn btn-small btn-secondary';
  sendBtn.textContent = 'Send';

  const processInput = () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';

    // Find ALL dice expressions: [[...]]
    const diceMatches = [...text.matchAll(/\[\[(.+?)\]\]/g)];

    if (diceMatches.length > 0 && onDiceRoll) {
      // Send each expression as a separate roll, with the full text as context
      for (const match of diceMatches) {
        onDiceRoll(match[1], text);
      }
      return;
    }

    // No dice expressions — it's a chat message
    if (onChatMessage) {
      onChatMessage(text);
    }
  };

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      processInput();
    }
  });

  sendBtn.addEventListener('click', processInput);

  bar.appendChild(input);
  bar.appendChild(sendBtn);
  return bar;
}

function _scrollToBottom(el) {
  requestAnimationFrame(() => {
    el.scrollTop = el.scrollHeight;
  });
}
