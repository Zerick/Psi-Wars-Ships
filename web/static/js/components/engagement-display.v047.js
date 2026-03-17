/* =============================================================================
   Engagement Display Component (v0.4.0)
   =========================================================================

   Renders the engagement strip showing range/advantage between paired ships.
   Logic preserved from v0.3.0 — no multiplayer-specific changes needed since
   engagements are rendered from server state.

   Usage:
     renderEngagementStrip(container, engagements, ships);

   Modification guide:
     - To change range colors: edit CSS .range-{band} classes
     - To change layout: edit _renderEngagement()
     - To add new engagement tags: add to the tags section
   ============================================================================= */


/**
 * Render the engagement strip.
 *
 * @param {HTMLElement} container - The engagement strip container.
 * @param {Array} engagements - Array of engagement objects.
 * @param {Array} ships - Array of ship data objects (for name lookup).
 */
export function renderEngagementStrip(container, engagements, ships) {
  if (!container) return;
  container.innerHTML = '';

  if (!engagements || engagements.length === 0) {
    container.innerHTML = '<span style="color:var(--text-muted);font-size:0.8rem;">No engagements</span>';
    return;
  }

  const shipMap = {};
  for (const s of (ships || [])) {
    shipMap[s.ship_id] = s;
  }

  for (const eng of engagements) {
    container.appendChild(_renderEngagement(eng, shipMap));
  }
}


// ---------------------------------------------------------------------------
// Internal
// ---------------------------------------------------------------------------

function _renderEngagement(eng, shipMap) {
  const el = document.createElement('div');
  el.className = 'engagement-pair';

  const shipA = shipMap[eng.ship_a_id] || { display_name: eng.ship_a_id, faction: '' };
  const shipB = shipMap[eng.ship_b_id] || { display_name: eng.ship_b_id, faction: '' };
  const range = eng.range_band || 'long';
  const rangeClass = `range-${range}`;

  // Advantage indicator
  let advText = 'NO ADV';
  if (eng.advantage === eng.ship_a_id) {
    advText = `◀ ${_esc(shipA.display_name || eng.ship_a_id)}`;
  } else if (eng.advantage === eng.ship_b_id) {
    advText = `${_esc(shipB.display_name || eng.ship_b_id)} ▶`;
  }

  // Tags
  let tags = '';
  if (eng.matched_speed) {
    tags += '<span class="engagement-tag tag-matched">MATCHED SPD</span> ';
  }
  if (eng.hugging) {
    tags += '<span class="engagement-tag tag-hugging">HUGGING</span> ';
  }

  el.innerHTML = `
    <span class="engagement-ship-name" title="${_esc(shipA.faction || '')}">${_esc(shipA.display_name || eng.ship_a_id)}</span>
    <span class="engagement-line"></span>
    <span class="engagement-range ${rangeClass}">${range.toUpperCase()}</span>
    <span class="engagement-line"></span>
    <span class="engagement-ship-name" title="${_esc(shipB.faction || '')}">${_esc(shipB.display_name || eng.ship_b_id)}</span>
    <div class="engagement-advantage">${advText} ${tags}</div>
  `;

  return el;
}

function _esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
