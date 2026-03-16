/* =============================================================================
   GM Panel Component v0.3.0
   Dice review, undo/redo, combat controls.
   Ship editing is handled inline on cards.
   ============================================================================= */

export function createGMPanel(containerEl, options = {}) {
  const { onUndo, onRedo, onDiceFilter } = options;

  containerEl.innerHTML = `
    <div class="gm-header">
      <span class="gm-header-title">GM Panel</span>
    </div>
    <div class="gm-body">

      <div class="gm-section">
        <div class="gm-section-title">Combat Controls</div>
        <button class="gm-btn" id="gm-undo">↩ Undo Last Round</button>
        <button class="gm-btn" id="gm-redo">↪ Redo Round</button>
        <button class="gm-btn" id="gm-pause">⏸ Pause Combat</button>
        <button class="gm-btn danger" id="gm-end">✕ End Combat</button>
      </div>

      <div class="gm-section">
        <div class="gm-section-title">Dice Review</div>
        <div class="gm-filter-row">
          <button class="gm-filter-btn" data-filter="none">None</button>
          <button class="gm-filter-btn active" data-filter="all">All</button>
          <button class="gm-filter-btn" data-filter="npc">NPC Only</button>
          <button class="gm-filter-btn" data-filter="player">Player Only</button>
        </div>
        <div class="gm-dice-log" id="gm-dice-log"></div>
      </div>

      <div class="gm-section">
        <div class="gm-section-title">Quick Actions</div>
        <button class="gm-btn" id="gm-add-log">+ Add GM Note</button>
        <button class="gm-btn" id="gm-reveal-npc">👁 Reveal NPC Rolls</button>
        <button class="gm-btn" id="gm-hide-npc">🔒 Hide NPC Rolls</button>
      </div>

    </div>
  `;

  const filterBtns = containerEl.querySelectorAll('.gm-filter-btn');
  let currentFilter = 'all';

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      if (onDiceFilter) onDiceFilter(currentFilter);
      refreshDiceLog();
    });
  });

  containerEl.querySelector('#gm-undo')?.addEventListener('click', () => { if (onUndo) onUndo(); });
  containerEl.querySelector('#gm-redo')?.addEventListener('click', () => { if (onRedo) onRedo(); });

  let diceEntries = [];
  const diceLogEl = containerEl.querySelector('#gm-dice-log');

  function refreshDiceLog() {
    const filtered = diceEntries.filter(d => {
      if (currentFilter === 'none') return false;
      if (currentFilter === 'npc') return d.is_npc;
      if (currentFilter === 'player') return !d.is_npc;
      return true;
    });

    diceLogEl.innerHTML = filtered.map(d => `
      <div class="gm-dice-entry">
        <span class="roll-ship">${d.ship}</span>
        ${d.context}:
        <span class="roll-value">${d.total}</span>
        vs ${d.target !== null ? d.target : '—'}
        ${d.success !== null ? (d.success ? ' ✓' : ' ✗') : ''}
        ${d.margin !== null ? `(${d.margin >= 0 ? '+' : ''}${d.margin})` : ''}
        <span style="color: var(--text-muted)">[${d.rolls.join(',')}]</span>
      </div>
    `).join('');
  }

  return {
    loadDiceLog(entries) { diceEntries = entries; refreshDiceLog(); },
    addDiceEntry(entry) { diceEntries.push(entry); refreshDiceLog(); },
    getCurrentFilter() { return currentFilter; }
  };
}
