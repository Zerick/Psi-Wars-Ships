/* =============================================================================
   Combat Log Component v0.3.0
   Dice: shows ONLY total inline. Hover reveals breakdown.
   Verbose (v) shows full breakdown. Unknown commands ignored.
   ============================================================================= */

export function createCombatLog(containerEl) {
  containerEl.innerHTML = `
    <div class="log-header">
      <span class="log-header-title">Combat Log</span>
      <span class="log-header-title" id="log-entry-count" style="color:var(--text-muted)">0 entries</span>
    </div>
    <div class="log-body" id="log-body"></div>
    <div class="log-input-area">
      <input type="text" class="log-input" id="log-input"
             placeholder="Type message or [[3d6]] to roll… [[help]] for commands" autocomplete="off">
      <button class="log-send-btn" id="log-send">Send</button>
    </div>
  `;
  const logBody = containerEl.querySelector('#log-body');
  const logInput = containerEl.querySelector('#log-input');
  const logSend = containerEl.querySelector('#log-send');
  const logCount = containerEl.querySelector('#log-entry-count');
  let entryCount = 0;

  function addEntry(msg, type = 'info', turn = null) {
    const el = document.createElement('div');
    el.className = 'log-entry'; el.dataset.type = type;
    if (turn !== null) el.dataset.turn = turn;
    el.textContent = msg;
    logBody.appendChild(el); entryCount++;
    logCount.textContent = `${entryCount} entries`;
    logBody.scrollTop = logBody.scrollHeight;
    return el;
  }
  function addHTML(html, type = 'info', turn = null) {
    const el = document.createElement('div');
    el.className = 'log-entry'; el.dataset.type = type;
    if (turn !== null) el.dataset.turn = turn;
    el.innerHTML = html;
    logBody.appendChild(el); entryCount++;
    logCount.textContent = `${entryCount} entries`;
    logBody.scrollTop = logBody.scrollHeight;
    return el;
  }

  async function roll(expr) {
    const r = await fetch('/api/dice/roll', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expression: expr })
    });
    return await r.json();
  }

  function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  async function handleInput() {
    const text = logInput.value.trim();
    if (!text) return;
    logInput.value = ''; logInput.focus();

    const re = /\[\[([^\]]+)\]\]/g;
    const matches = [...text.matchAll(re)];
    if (!matches.length) { addEntry(text, 'info'); return; }

    const single = matches.length === 1 && text.trim() === `[[${matches[0][1]}]]`;

    if (single) {
      const res = await roll(matches[0][1]).catch(() => ({ type: 'error' }));
      if (res.type === 'help' || res.type === 'about') { addEntry(res.text, 'info'); return; }
      if (res.type === 'stats') { addEntry(res.text, 'dice'); return; }
      if (res.type === 'roll') {
        if (res.verbose) {
          addHTML(`🎲 <span class="dice-verbose">${esc(res.breakdown)}</span>`, 'dice');
        } else {
          addHTML(`🎲 <span class="dice-result" title="${esc(res.expression)}: ${esc(res.breakdown)}">${res.total}</span>`, 'dice');
        }
        return;
      }
      // error/unknown — silently ignore
      return;
    }

    // Inline: replace [[expr]] with just the total, hover shows breakdown
    let html = esc(text);
    for (const m of matches) {
      const res = await roll(m[1]).catch(() => ({ type: 'error' }));
      const escaped = esc(`[[${m[1]}]]`);
      if (res.type === 'roll') {
        if (res.verbose) {
          html = html.replace(escaped, `<span class="dice-verbose">${esc(res.breakdown)}</span>`);
        } else {
          html = html.replace(escaped, `<span class="dice-result" title="${esc(res.expression)}: ${esc(res.breakdown)}">${res.total}</span>`);
        }
      } else {
        // Unknown/error — leave the brackets as-is silently
        // (already in the html as escaped text)
      }
    }
    addHTML(html, 'dice');
  }

  logSend.addEventListener('click', handleInput);
  logInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleInput(); });

  return {
    addEntry, addHTML,
    clear() { logBody.innerHTML = ''; entryCount = 0; logCount.textContent = '0 entries'; },
    getEntryCount() { return entryCount; },
    scrollToBottom() { logBody.scrollTop = logBody.scrollHeight; },
    scrollToTurn(t) {
      const e = logBody.querySelectorAll(`[data-turn="${t}"][data-type="turn"]`);
      if (e.length) e[0].scrollIntoView({ behavior:'smooth', block:'start' });
    }
  };
}

export function loadMockLog(log, entries) {
  entries.forEach(e => log.addEntry(e.message, e.event_type, e.turn));
}
