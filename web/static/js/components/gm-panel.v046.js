/* =============================================================================
   GM Panel Component (v0.4.0)
   =========================================================================

   Right-side panel visible to GM only. Contains:
     - Combat controls (Undo, Redo, Pause, End Combat)
     - Dice review log with filters (All, NPC Only, Player Only, None)
     - Quick actions (placeholders for future features)

   Updated from v0.3.0: callbacks now fire WebSocket messages instead of
   local-only actions.

   Usage:
     const panel = createGMPanel(container, {
       onUndo: () => ws.send('UNDO'),
       onRedo: () => ws.send('REDO'),
     });
     panel.loadDiceLog(entries);
     panel.addDiceEntry(entry);

   Modification guide:
     - To add new controls: add buttons in _createControls()
     - To change dice review format: edit _renderDiceEntry()
     - To add new filters: extend the filter buttons and _applyFilter()
   ============================================================================= */


/**
 * Create the GM panel component.
 *
 * @param {HTMLElement} container - Container element.
 * @param {Object} callbacks - Event callbacks:
 *   @param {Function} callbacks.onUndo - Called when Undo button clicked.
 *   @param {Function} callbacks.onRedo - Called when Redo button clicked.
 * @returns {Object} Panel API: { loadDiceLog, addDiceEntry }
 */
export function createGMPanel(container, callbacks = {}) {
  container.innerHTML = '';

  // --- Combat Controls ---
  const controlsSection = document.createElement('div');
  controlsSection.className = 'gm-section';
  controlsSection.innerHTML = `
    <div class="gm-section-title">Combat Controls</div>
    <div class="gm-controls">
      <button class="btn btn-small" id="gm-undo">Undo</button>
      <button class="btn btn-small" id="gm-redo">Redo</button>
      <button class="btn btn-small" id="gm-pause">Pause</button>
      <button class="btn btn-small btn-danger" id="gm-end">End Combat</button>
    </div>
  `;
  container.appendChild(controlsSection);

  // Wire control buttons
  controlsSection.querySelector('#gm-undo')?.addEventListener('click', () => callbacks.onUndo?.());
  controlsSection.querySelector('#gm-redo')?.addEventListener('click', () => callbacks.onRedo?.());

  // --- Dice Review ---
  const diceSection = document.createElement('div');
  diceSection.className = 'gm-section';
  diceSection.innerHTML = `
    <div class="gm-section-title">Dice Review</div>
    <div class="gm-controls" id="dice-filters">
      <button class="btn btn-small btn-ghost" data-filter="none">None</button>
      <button class="btn btn-small btn-ghost active" data-filter="all">All</button>
      <button class="btn btn-small btn-ghost" data-filter="npc">NPC</button>
      <button class="btn btn-small btn-ghost" data-filter="player">Player</button>
    </div>
    <div class="dice-review" id="dice-review"></div>
  `;
  container.appendChild(diceSection);

  // Filter state
  let currentFilter = 'all';
  let diceEntries = [];
  const diceReview = diceSection.querySelector('#dice-review');

  // Wire filter buttons
  diceSection.querySelectorAll('#dice-filters button').forEach(btn => {
    btn.addEventListener('click', () => {
      currentFilter = btn.dataset.filter;
      diceSection.querySelectorAll('#dice-filters button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _refreshDiceLog();
    });
  });

  function _refreshDiceLog() {
    if (!diceReview) return;

    let filtered;
    switch (currentFilter) {
      case 'none':
        filtered = [];
        break;
      case 'npc':
        filtered = diceEntries.filter(d => d.is_npc);
        break;
      case 'player':
        filtered = diceEntries.filter(d => !d.is_npc);
        break;
      default:
        filtered = diceEntries;
    }

    diceReview.innerHTML = filtered.map(d => `
      <div class="dice-entry">
        <strong>${_esc(d.ship || d.roller || '?')}</strong>
        ${_esc(d.context || '')}:
        ${d.expression} = ${d.total ?? d.result ?? '?'}
        ${d.target != null ? ` vs ${d.target}` : ''}
        ${d.success != null ? (d.success ? ' ✓' : ' ✗') : ''}
        ${d.margin != null ? `(${d.margin >= 0 ? '+' : ''}${d.margin})` : ''}
      </div>
    `).join('');
  }

  return {
    loadDiceLog(entries) {
      diceEntries = entries || [];
      _refreshDiceLog();
    },
    addDiceEntry(entry) {
      diceEntries.push(entry);
      _refreshDiceLog();
    },
  };
}


function _esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
