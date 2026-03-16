/* =============================================================================
   Ship Card Component v0.3.0
   Redesigned to match ship_cards.png:
   - Ship name (links to source) + class tag
   - Pilot row: name, piloting, gunnery, dodge
   - HP bar editable
   - Force screen bar (if applicable)
   - SYSTEMS: full names as colored text in 3-col grid, click to cycle
   - WEAPONS: name, damage, acc, rof, range, mount tag
   - Notes (GM only) section
   ============================================================================= */

const SYSTEMS = [
  'armor', 'cargo', 'controls',
  'equipment', 'fuel', 'habitat',
  'power', 'propulsion', 'weaponry'
];

function hpPercent(s) { return Math.max(0, Math.min(100, (s.current_hp / s.st_hp) * 100)); }
function hpClass(p) {
  if (p > 80) return 'hp-full'; if (p > 60) return 'hp-high';
  if (p > 35) return 'hp-medium'; if (p > 15) return 'hp-low'; return 'hp-critical';
}
function fdrPercent(s) {
  if (!s.fdr_max) return 0;
  return Math.max(0, Math.min(100, (s.current_fdr / s.fdr_max) * 100));
}
function sysStatus(ship, sys) {
  if (ship.destroyed_systems?.includes(sys)) return 'destroyed';
  if (ship.disabled_systems?.includes(sys)) return 'disabled';
  return 'ok';
}
function factionColor(f) {
  return { Empire:'#e05454', Alliance:'#3fb5e5', Trader:'#3fb950', Pirate:'#d4a843' }[f] || '#6e7681';
}
function sourceUrl(ship) {
  // Lookup table for all Psi-Wars ship wikidot URLs
  const SHIP_URLS = {
    'hammerhead':    'http://psi-wars.wikidot.com/hammerhead-class-striker',
    'javelin':       'http://psi-wars.wikidot.com/javelin-class-fighter',
    'peltast':       'http://psi-wars.wikidot.com/peltast-class-striker',
    'piranha':       'http://psi-wars.wikidot.com/wiki:piranha-class-fighter',
    'drifter':       'http://psi-wars.wikidot.com/drifter-class-racer',
    'wildcat':       'http://psi-wars.wikidot.com/wildcat-class-fighter',
    'grappler':      'http://psi-wars.wikidot.com/grappler-class-assault-boat',
    'vespa':         'http://psi-wars.wikidot.com/vespa-class-interceptor',
    'flanker':       'http://psi-wars.wikidot.com/wiki:flanker-class-fighter',
    'raptor':        'http://psi-wars.wikidot.com/raptor-pattern-striker',
    'hornet':        'http://psi-wars.wikidot.com/hornet-class-interceptor',
    'tempest':       'http://psi-wars.wikidot.com/tempest-class-interceptor',
    'valiant':       'http://psi-wars.wikidot.com/valiant-pattern-fighter',
    'valkyrie':      'http://psi-wars.wikidot.com/valkyrie-pattern-fighter',
    'fugitive':      'http://psi-wars.wikidot.com/wiki:fugitive-class-escape-craft',
    'gypsy_moth':    'http://psi-wars.wikidot.com/wiki:gypsy-moth-class-blockade-runner',
    'high_roller':   'http://psi-wars.wikidot.com/wiki:high-roller-class-yacht',
    'lancer':        'http://psi-wars.wikidot.com/lancer-pattern-assault-frigate',
    'nomad':         'http://psi-wars.wikidot.com/nomad-class-modular-corvette',
    'prestige':      'http://psi-wars.wikidot.com/prestige-pattern-shuttle',
    'raider':        'http://psi-wars.wikidot.com/wiki:raider-class-assault-carrier',
    'ronin':         'http://psi-wars.wikidot.com/ronin-pattern-yacht',
    'scarab':        'http://psi-wars.wikidot.com/scarab-class-defense-frigate',
    'skirmisher':    'http://psi-wars.wikidot.com/wiki:skirmisher-class-corvette',
    'tigershark':    'http://psi-wars.wikidot.com/tigershark-class-assault-corvette',
    'toad':          'http://psi-wars.wikidot.com/wiki:toad-class-heavy-corvette',
    'wrangler':      'http://psi-wars.wikidot.com/wrangler-class-corvette',
    'arcana':        'http://psi-wars.wikidot.com/arcana-pattern-carrier',
    'dominion':      'http://psi-wars.wikidot.com/dominion-class-cruiser',
    'executioner':   'http://psi-wars.wikidot.com/executioner-class-cruiser',
    'imperator':     'http://psi-wars.wikidot.com/imperator-class-dreadnought',
    'kodiak':        'http://psi-wars.wikidot.com/wiki:kodiak-class-light-cruiser',
    'legion':        'http://psi-wars.wikidot.com/legion-class-carrier',
    'mauler':        'http://psi-wars.wikidot.com/wiki:mauler-class-battle-carrier',
    'regal':         'http://psi-wars.wikidot.com/regal-pattern-cruiser',
    'spire':         'http://psi-wars.wikidot.com/wiki:spire-class-mobile-fortress',
    'sword':         'http://psi-wars.wikidot.com/sword-pattern-battleship',
    'trader_ark':    'http://psi-wars.wikidot.com/trader-ark',
    'trader_ark_tender': 'http://psi-wars.wikidot.com/trader-ark-tender',
  };
  // Extract base name from template_id (e.g. "wildcat_v1" -> "wildcat")
  const baseName = (ship.template_id || '').replace(/_v\d+$/, '');
  return SHIP_URLS[baseName] || null;
}
function mountTag(mount) {
  if (!mount) return '';
  if (mount.includes('fixed_front')) return '[F]';
  if (mount.includes('turret')) return '[T]';
  if (mount.includes('wing')) return '[W]';
  return `[${mount.charAt(0).toUpperCase()}]`;
}

function ev(field, value, gm) {
  if (!gm) return String(value);
  return `<span class="editable-stat" data-field="${field}" title="Click to edit">${value}</span>`;
}

function attachEditable(container, onChange) {
  container.querySelectorAll('.editable-stat').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (el.querySelector('input')) return;
      const field = el.dataset.field;
      const cur = el.textContent.trim();
      const w = Math.max(3, cur.length + 1);
      const inp = document.createElement('input');
      inp.type = 'number'; inp.className = 'editable-stat-input';
      inp.value = cur; inp.style.width = w + 'ch';
      el.textContent = ''; el.appendChild(inp);
      inp.focus(); inp.select();
      function commit() { const v = parseInt(inp.value); if (!isNaN(v)) onChange(field, v); }
      inp.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') { ev.preventDefault(); commit(); }
        if (ev.key === 'Escape') { el.textContent = cur; }
        ev.stopPropagation();
      });
      inp.addEventListener('blur', commit);
      inp.addEventListener('click', (ev) => ev.stopPropagation());
    });
  });
}

function attachSystemCycling(card, callbacks) {
  card.querySelectorAll('.sys-name').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const sys = el.dataset.system;
      const cur = el.dataset.status;
      const next = cur === 'ok' ? 'disabled' : cur === 'disabled' ? 'destroyed' : 'ok';
      if (callbacks.onSubsystemChange) {
        callbacks.onSubsystemChange(card.dataset.shipId, sys, next);
      }
    });
  });
}

function buildSystemsHTML(ship) {
  return `<div class="sys-grid">${SYSTEMS.map(sys => {
    const st = sysStatus(ship, sys);
    const label = sys.charAt(0).toUpperCase() + sys.slice(1);
    return `<span class="sys-name sys-${st}" data-system="${sys}" data-status="${st}" title="Click to cycle: ${sys} (${st})">${label}</span>`;
  }).join('')}</div>`;
}

function buildWeaponsHTML(ship) {
  return ship.weapons.map(w => {
    const mt = mountTag(w.mount);
    return `<div class="wpn-block">
      <div class="wpn-header">
        <span class="wpn-mount">${mt}</span>
        <span class="wpn-name">${w.name}</span>
      </div>
      <div class="wpn-stats">${w.damage_str}  Acc ${w.acc}  RoF ${w.rof}  ${w.range_str}</div>
    </div>`;
  }).join('');
}

function templateLinkHTML(ship, srcUrl, templateName) {
  if (srcUrl) {
    return `<a class="card-template-link" href="${srcUrl}" target="_blank" title="Open ${templateName} on Psi-Wars wiki">${templateName}</a>`;
  }
  return `<div class="card-template">${templateName}</div>`;
}

function renderCard(card, ship, highlight, isCompact, callbacks) {
  const hp = hpPercent(ship);
  const fdr = fdrPercent(ship);
  const gm = !!callbacks.gmMode;
  const templateName = ship.template_id.replace(/_v\d+$/, '').replace(/_/g, ' ');
  const srcUrl = sourceUrl(ship);
  const tplLink = templateLinkHTML(ship, srcUrl, templateName);
  const dodge = Math.floor(ship.pilot.piloting_skill / 2) + ship.hnd;

  if (isCompact) {
    card.innerHTML = `
      <div class="card-header">
        <div>
          <div class="card-name">${ship.display_name}</div>
          ${tplLink}
        </div>
        <div class="card-class">${ship.ship_class}</div>
      </div>
      <div class="hp-bar-container">
        <div class="hp-bar-label"><span>HP</span><span>${ev('current_hp', ship.current_hp, gm)}/${ship.st_hp}</span></div>
        <div class="hp-bar"><div class="hp-bar-fill ${hpClass(hp)}" style="width:${hp}%"></div></div>
      </div>
      ${buildSystemsHTML(ship)}
    `;
  } else {
    card.innerHTML = `
      <div class="card-header">
        <div>
          <div class="card-name">${ship.display_name}</div>
          ${tplLink}
        </div>
        <div class="card-class-badge"><span class="card-class">${ship.ship_class}</span> <span class="card-sm">${ship.sm}</span></div>
      </div>
      <div class="card-faction" style="color:${factionColor(ship.faction)}">${ship.faction} · ${ship.control}</div>

      <div class="pilot-stats-row">
        <span class="pilot-stat-name" title="${ship.pilot.name}">${ship.pilot.name.length > 10 ? ship.pilot.name.substring(0,9)+'…' : ship.pilot.name}</span>
        <span class="pilot-stat">Pilot <strong>${ev('pilot.piloting_skill', ship.pilot.piloting_skill, gm)}</strong></span>
        <span class="pilot-stat">Gunner <strong>${ev('pilot.gunnery_skill', ship.pilot.gunnery_skill, gm)}</strong></span>
        <span class="pilot-stat">Dodge <strong>${dodge}</strong></span>
      </div>

      <div class="hp-bar-container">
        <div class="hp-bar-label">
          <span>HP</span>
          <span>${ev('current_hp', ship.current_hp, gm)} / ${ev('st_hp', ship.st_hp, gm)}</span>
        </div>
        <div class="hp-bar"><div class="hp-bar-fill ${hpClass(hp)}" style="width:${hp}%"></div></div>
      </div>

      ${ship.fdr_max > 0 ? `
      <div class="hp-bar-container fdr-bar-container">
        <div class="hp-bar-label">
          <span>Force Screen${ship.force_screen_type === 'hardened' ? ' [H]' : ''}</span>
          <span>${ev('current_fdr', ship.current_fdr, gm)} / ${ev('fdr_max', ship.fdr_max, gm)}</span>
        </div>
        <div class="hp-bar"><div class="fdr-bar-fill" style="width:${fdr}%"></div></div>
      </div>
      ` : ''}

      <div class="card-section-label">SYSTEMS</div>
      ${buildSystemsHTML(ship)}

      <div class="card-section-label">WEAPONS</div>
      ${buildWeaponsHTML(ship)}

      <div class="card-expanded-details">
        <div class="detail-section-title">Performance</div>
        <div class="detail-grid">
          <dt>Handling</dt><dd>${ev('hnd', ship.hnd, gm)}</dd>
          <dt>Stability</dt><dd>${ev('sr', ship.sr, gm)}</dd>
          <dt>Acceleration</dt><dd>${ev('accel', ship.accel, gm)}</dd>
          <dt>Top Speed</dt><dd>${ev('top_speed', ship.top_speed, gm)}</dd>
          <dt>Stall Speed</dt><dd>${ev('stall_speed', ship.stall_speed, gm)}</dd>
          <dt>HT</dt><dd>${ev('ht', parseInt(ship.ht)||0, gm)}</dd>
        </div>
        <div class="detail-section-title">Armor (DR by facing)</div>
        <div class="detail-grid">
          <dt>Front</dt><dd>${ev('dr_front', ship.dr_front, gm)}</dd>
          <dt>Rear</dt><dd>${ev('dr_rear', ship.dr_rear, gm)}</dd>
          <dt>Left</dt><dd>${ev('dr_left', ship.dr_left, gm)}</dd>
          <dt>Right</dt><dd>${ev('dr_right', ship.dr_right, gm)}</dd>
          <dt>Top</dt><dd>${ev('dr_top', ship.dr_top, gm)}</dd>
          <dt>Bottom</dt><dd>${ev('dr_bottom', ship.dr_bottom, gm)}</dd>
        </div>
        <div class="detail-section-title">Electronics</div>
        <div class="detail-grid">
          <dt>ECM Rating</dt><dd>${ev('ecm_rating', ship.ecm_rating, gm)}</dd>
          <dt>Targeting Bonus</dt><dd>+${ev('targeting_bonus', ship.targeting_bonus, gm)}</dd>
          <dt>Tactical ESM</dt><dd>${ship.has_tactical_esm ? 'Yes' : 'No'}</dd>
          <dt>Decoy Launcher</dt><dd>${ship.has_decoy_launcher ? 'Yes' : 'No'}</dd>
        </div>
        <div class="detail-section-title">Pilot</div>
        <div class="detail-grid">
          <dt>Ace Pilot</dt><dd>${ship.pilot.is_ace_pilot ? 'Yes' : 'No'}</dd>
          <dt>Luck</dt><dd>${ship.pilot.luck_level}</dd>
          <dt>FP</dt><dd>${ev('pilot.current_fp', ship.pilot.current_fp, gm)}/${ev('pilot.max_fp', ship.pilot.max_fp, gm)}</dd>
          <dt>EP Reserves</dt><dd>${ev('emergency_power_reserves', ship.emergency_power_reserves, gm)}</dd>
        </div>
      </div>

      <div class="card-notes">
        <span class="card-notes-label">Notes (GM only)</span>
        <div class="card-notes-text" contenteditable="true" data-ship-id="${ship.ship_id}">Click to add notes…</div>
      </div>
    `;
  }

  attachSystemCycling(card, callbacks);
  if (gm && callbacks.onFieldChange) {
    attachEditable(card, (field, val) => callbacks.onFieldChange(ship.ship_id, field, val));
  }
}

export function createShipCard(ship, highlight = null, isCompact = false, callbacks = {}) {
  const card = document.createElement('div');
  card.className = 'ship-card';
  card.dataset.shipId = ship.ship_id;
  if (ship.is_destroyed) card.classList.add('destroyed');
  if (highlight === 'active') card.classList.add('active');
  if (highlight === 'target') card.classList.add('target');
  if (highlight === 'targeting') card.classList.add('targeting');
  if (isCompact) card.classList.add('compact');
  renderCard(card, ship, highlight, isCompact, callbacks);
  card.addEventListener('click', (e) => {
    if (e.target.closest('.sys-name')) return;
    if (e.target.closest('.editable-stat')) return;
    if (e.target.closest('.editable-stat-input')) return;
    if (e.target.closest('.card-name-link')) return;
    if (e.target.closest('.card-template-link')) return;
    if (e.target.closest('.card-notes-text')) return;
    card.classList.toggle('expanded');
  });
  return card;
}

export function renderShipStrip(containerEl, ships, activeState, callbacks = {}) {
  containerEl.innerHTML = '';
  const fullIds = new Set();
  if (activeState.active_ship_id) fullIds.add(activeState.active_ship_id);
  activeState.targets.forEach(id => fullIds.add(id));
  ships.forEach(ship => {
    let hl = null;
    if (ship.ship_id === activeState.active_ship_id) hl = 'active';
    else if (activeState.targets.includes(ship.ship_id)) hl = 'target';
    else if (activeState.targeting.includes(ship.ship_id)) hl = 'targeting';
    const compact = !fullIds.has(ship.ship_id);
    containerEl.appendChild(createShipCard(ship, hl, compact, callbacks));
  });
  const ac = containerEl.querySelector('.ship-card.active');
  if (ac) ac.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
}
