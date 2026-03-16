/* =============================================================================
   Engagement Display Component v0.3.0
   Range and advantage stacked vertically in center.
   Faction shown on hover. Matched speed / hugging as tags.
   ============================================================================= */

const RANGE_COLORS = {
  close:'var(--danger)', medium:'var(--warn)', long:'var(--accent)', extreme:'var(--text-dim)'
};
const RANGE_LABELS = { close:'CLOSE', medium:'MED', long:'LONG', extreme:'EXT' };

function getShip(ships, id) { return ships.find(s => s.ship_id === id); }
function fc(ships, id) {
  const s = getShip(ships, id);
  if (!s) return 'var(--text-dim)';
  return {Empire:'#e05454',Alliance:'#3fb5e5',Trader:'#3fb950',Pirate:'#d4a843'}[s.faction]||'var(--text-dim)';
}

export function createEngagementDisplay(containerEl) {
  function render(engagements, ships) {
    if (!engagements || !engagements.length) {
      containerEl.innerHTML = '<div class="engagement-empty">No active engagements</div>';
      return;
    }
    containerEl.innerHTML = engagements.map(eng => {
      const sA = getShip(ships, eng.ship_a_id), sB = getShip(ships, eng.ship_b_id);
      const nA = sA ? sA.display_name : eng.ship_a_id;
      const nB = sB ? sB.display_name : eng.ship_b_id;
      const fA = sA ? sA.faction : '', fB = sB ? sB.faction : '';
      const rc = RANGE_COLORS[eng.range_band] || 'var(--text-dim)';
      const rl = RANGE_LABELS[eng.range_band] || eng.range_band.toUpperCase();
      let advText = 'NO ADV', advClass = 'eng-no-advantage';
      if (eng.advantage === eng.ship_a_id) { advText = `◀ ${nA}`; advClass = 'eng-advantage'; }
      else if (eng.advantage === eng.ship_b_id) { advText = `${nB} ▶`; advClass = 'eng-advantage'; }
      let tags = [];
      if (eng.matched_speed) tags.push('<span class="eng-tag eng-matched">MATCHED SPD</span>');
      if (eng.hugging === eng.ship_a_id) tags.push(`<span class="eng-tag eng-hugging">${nA} HUGGING</span>`);
      if (eng.hugging === eng.ship_b_id) tags.push(`<span class="eng-tag eng-hugging">${nB} HUGGING</span>`);
      return `<div class="engagement-row">
        <span class="eng-ship" style="color:${fc(ships,eng.ship_a_id)}" title="${fA}">${nA}</span>
        <span class="eng-center">
          <span class="eng-line" style="border-color:${rc}"></span>
          <span class="eng-center-stack">
            <span class="eng-range" style="color:${rc};border-color:${rc}">${rl}</span>
            <span class="${advClass}">${advText}</span>
          </span>
          <span class="eng-line" style="border-color:${rc}"></span>
        </span>
        <span class="eng-ship" style="color:${fc(ships,eng.ship_b_id)}" title="${fB}">${nB}</span>
        ${tags.length ? `<span class="eng-tags">${tags.join('')}</span>` : ''}
      </div>`;
    }).join('');
  }
  return { render };
}
