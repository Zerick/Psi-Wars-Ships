/* =============================================================================
   Ship Card Component (v0.4.0)
   =========================================================================

   Renders ship cards in the ship strip. Updated from v0.3.0 to support:
     - Role-based rendering (full vs limited visibility)
     - Live edit callbacks via WebSocket (instead of local-only edits)
     - "Own ship" highlighting based on current user's ship_ids
     - Condition descriptors for limited-visibility ships

   The ship card rendering logic (compact/full/expanded, click-to-edit,
   systems coloring, weapon display, source links) is preserved from
   v0.3.0. The main changes are:
     - renderShipStrip() now accepts an options object with callbacks
     - Limited visibility ships render a minimal card with condition text
     - Edit callbacks fire WebSocket messages instead of mutating local data

   Modification guide:
     - To change card layout: edit _renderFullCard() / _renderCompactCard()
     - To add new editable fields: add to _makeEditable() calls
     - To change limited ship display: edit _renderLimitedCard()
     - To change source URL lookup: edit SHIP_SOURCE_URLS
   ============================================================================= */


// ---------------------------------------------------------------------------
// Ship source URL lookup (39 ships)
// ---------------------------------------------------------------------------

const SHIP_SOURCE_URLS = {
  'arcana':       'https://psi-wars.wikidot.com/arcana-pattern-carrier',
  'dominion':     'https://psi-wars.wikidot.com/dominion-class-heavy-cruiser',
  'drifter':      'https://psi-wars.wikidot.com/drifter-class-racer',
  'executioner':  'https://psi-wars.wikidot.com/executioner-class-artillery-cruiser',
  'flanker':      'https://psi-wars.wikidot.com/flanker-class-fighter',
  'fugitive':     'https://psi-wars.wikidot.com/fugitive-class-escape-craft',
  'grappler':     'https://psi-wars.wikidot.com/grappler-class-assault-boat',
  'gypsy_moth':   'https://psi-wars.wikidot.com/gypsy-moth-class-blockade-runner',
  'hammerhead':   'https://psi-wars.wikidot.com/hammerhead-class-striker',
  'high_roller':  'https://psi-wars.wikidot.com/high-roller-class-yacht',
  'hornet':       'https://psi-wars.wikidot.com/hornet-class-interceptor',
  'imperator':    'https://psi-wars.wikidot.com/imperator-class-dreadnought',
  'javelin':      'https://psi-wars.wikidot.com/javelin-class-fighter',
  'kodiak':       'https://psi-wars.wikidot.com/kodiak-class-light-cruiser',
  'lancer':       'https://psi-wars.wikidot.com/lancer-pattern-assault-frigate',
  'legion':       'https://psi-wars.wikidot.com/legion-class-super-carrier',
  'mauler':       'https://psi-wars.wikidot.com/mauler-class-battle-carrier',
  'nomad':        'https://psi-wars.wikidot.com/nomad-class-modular-corvette',
  'peltast':      'https://psi-wars.wikidot.com/peltast-class-striker',
  'piranha':      'https://psi-wars.wikidot.com/piranha-class-fighter',
  'prestige':     'https://psi-wars.wikidot.com/prestige-pattern-diplomatic-shuttle',
  'raider':       'https://psi-wars.wikidot.com/raider-class-assault-carrier',
  'raptor':       'https://psi-wars.wikidot.com/raptor-pattern-striker',
  'regal':        'https://psi-wars.wikidot.com/regal-pattern-cruiser',
  'scarab':       'https://psi-wars.wikidot.com/scarab-class-defense-frigate',
  'skirmisher':   'https://psi-wars.wikidot.com/skirmisher-class-corvette',
  'spire':        'https://psi-wars.wikidot.com/spire-class-mobile-fortress',
  'sword':        'https://psi-wars.wikidot.com/sword-pattern-battleship',
  'tempest':      'https://psi-wars.wikidot.com/tempest-class-interceptor',
  'tigershark':   'https://psi-wars.wikidot.com/tigershark-assault-corvette',
  'toad':         'https://psi-wars.wikidot.com/toad-class-heavy-corvette',
  'trader_ark':   'https://psi-wars.wikidot.com/trader-ark',
  'trader_ark_tender': 'https://psi-wars.wikidot.com/trader-ark-tender',
  'valiant':      'https://psi-wars.wikidot.com/valiant-pattern-fighter',
  'valkyrie':     'https://psi-wars.wikidot.com/valkyrie-pattern-fighter',
  'vespa':        'https://psi-wars.wikidot.com/vespa-class-interceptor',
  'wildcat':      'https://psi-wars.wikidot.com/wildcat-class-fighter',
  'wrangler':     'https://psi-wars.wikidot.com/wrangler-class-corvette',
};


// ---------------------------------------------------------------------------
// System names (for subsystem display)
// ---------------------------------------------------------------------------

const SYSTEM_NAMES = [
  'armor', 'cargo', 'controls', 'equipment', 'fuel',
  'habitat', 'power', 'propulsion', 'weaponry',
];


// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Render the full ship strip with all ships.
 *
 * @param {HTMLElement} container - The ship strip container element.
 * @param {Array} ships - Array of ship data objects from session state.
 * @param {Object} activeState - Current active state { active_ship_id, targets, ... }.
 * @param {Object} [options] - Rendering options:
 *   @param {string[]} options.currentUserShipIds - Ship IDs the current user controls.
 *   @param {string}   options.userRole - Current user's role ('gm', 'host', 'player').
 *   @param {Function} options.onShipEdit - Callback(shipId, field, value) for stat edits.
 *   @param {Function} options.onSubsystemCycle - Callback(shipId, system, newStatus).
 */
export function renderShipStrip(container, ships, activeState, options = {}) {
  if (!container || !ships) return;

  container.innerHTML = '';

  const {
    currentUserShipIds = [],
    userRole = 'player',
    onShipEdit = null,
    onSubsystemCycle = null,
  } = options;

  const activeId = activeState?.active_ship_id;
  const targets = new Set(activeState?.targets || []);

  for (const ship of ships) {
    const shipId = ship.ship_id;
    const isOwn = currentUserShipIds.includes(shipId);
    const isActive = shipId === activeId;
    const isTarget = targets.has(shipId);
    const isLimited = ship.visibility === 'limited';
    const canEdit = userRole === 'gm' || (isOwn && !isLimited);

    let card;
    if (isLimited) {
      card = _renderLimitedCard(ship);
    } else if (isActive || isTarget) {
      card = _renderFullCard(ship, canEdit, onShipEdit, onSubsystemCycle);
    } else {
      card = _renderCompactCard(ship, canEdit, onShipEdit);
    }

    // Apply CSS classes
    if (isActive) card.classList.add('active');
    if (isOwn) card.classList.add('own-ship');
    if (isLimited) card.classList.add('limited');

    container.appendChild(card);
  }
}


// ---------------------------------------------------------------------------
// Card renderers (internal)
// ---------------------------------------------------------------------------

function _renderLimitedCard(ship) {
  const card = document.createElement('div');
  card.className = 'ship-card';
  card.dataset.shipId = ship.ship_id;

  const condition = ship.condition || 'fine';
  const condClass = `condition-${condition.replace(/\s+/g, '-')}`;

  card.innerHTML = `
    <div class="ship-card-header">
      <span class="ship-name">${_esc(ship.display_name || ship.ship_id)}</span>
      <span class="ship-class-badge">${_esc(ship.ship_class || '?')}</span>
    </div>
    <div class="ship-faction">${_esc(ship.faction || '')}</div>
    <div class="ship-condition ${condClass}">${condition.toUpperCase()}</div>
  `;

  return card;
}

function _renderCompactCard(ship, canEdit, onShipEdit) {
  const card = document.createElement('div');
  card.className = 'ship-card';
  card.dataset.shipId = ship.ship_id;

  const hpPct = ship.st_hp > 0 ? (ship.current_hp / ship.st_hp * 100) : 0;
  const hpColor = _hpColor(hpPct);
  const templateName = _extractTemplateName(ship.template_id);
  const sourceUrl = SHIP_SOURCE_URLS[templateName];

  const templateLink = sourceUrl
    ? `<a href="${sourceUrl}" target="_blank" rel="noopener" class="ship-source-link">${_esc(templateName)}</a>`
    : `<span>${_esc(templateName)}</span>`;

  card.innerHTML = `
    <div class="ship-card-header">
      <span class="ship-name">${_esc(ship.display_name || ship.ship_id)}</span>
      <span class="ship-class-badge">${_esc(ship.ship_class || '?')}</span>
    </div>
    <div class="ship-template">${templateLink}</div>
    <div class="ship-pilot-name">${_esc(ship.pilot?.name || 'Unknown')}</div>
    <div class="hp-bar">
      <div class="hp-bar-fill" style="width:${hpPct}%; background:${hpColor}"></div>
    </div>
    <div class="ship-hp-text">
      <span class="editable" data-field="current_hp">${ship.current_hp}</span>
      / ${ship.st_hp} HP
    </div>
    ${ship.fdr_max > 0 ? `
      <div class="fdr-bar">
        <div class="fdr-bar-fill" style="width:${ship.fdr_max > 0 ? (ship.current_fdr / ship.fdr_max * 100) : 0}%"></div>
      </div>
      <div class="ship-fdr-text">
        fDR: <span class="editable" data-field="current_fdr">${ship.current_fdr}</span>/${ship.fdr_max}
        ${ship.force_screen_type === 'hardened' ? ' [H]' : ''}
      </div>
    ` : ''}
  `;

  if (canEdit && onShipEdit) {
    _wireEditableFields(card, ship.ship_id, onShipEdit);
  }

  return card;
}

function _renderFullCard(ship, canEdit, onShipEdit, onSubsystemCycle) {
  const card = _renderCompactCard(ship, canEdit, onShipEdit);

  // Add systems grid
  const systemsEl = document.createElement('div');
  systemsEl.className = 'ship-systems';
  systemsEl.innerHTML = SYSTEM_NAMES.map(sys => {
    const status = _getSystemStatus(ship, sys);
    const color = status === 'ok' ? 'var(--sys-ok)'
                : status === 'disabled' ? 'var(--sys-disabled)'
                : 'var(--sys-destroyed)';
    const className = canEdit ? 'system-name cycleable' : 'system-name';
    return `<span class="${className}" data-system="${sys}" style="color:${color}">${sys}</span>`;
  }).join('');

  if (canEdit && onSubsystemCycle) {
    systemsEl.querySelectorAll('.cycleable').forEach(el => {
      el.addEventListener('click', () => {
        const sys = el.dataset.system;
        const current = _getSystemStatus(ship, sys);
        const next = current === 'ok' ? 'disabled'
                   : current === 'disabled' ? 'destroyed'
                   : 'ok';
        onSubsystemCycle(ship.ship_id, sys, next);
      });
    });
  }

  card.appendChild(systemsEl);

  // Add weapons summary
  if (ship.weapons && ship.weapons.length > 0) {
    const weaponsEl = document.createElement('div');
    weaponsEl.className = 'ship-weapons';
    weaponsEl.innerHTML = ship.weapons.map(w => {
      const mount = w.mount || '';
      const mountTag = mount.includes('fixed') ? '[F]'
                     : mount.includes('turret') ? '[T]'
                     : mount.includes('wing') ? '[W]'
                     : '';
      return `<div class="weapon-entry">
        <span class="weapon-mount">${mountTag}</span>
        <span class="weapon-name">${_esc(w.name || 'Unknown')}</span>
        <span class="weapon-damage">${_esc(w.damage_str || '')}</span>
      </div>`;
    }).join('');
    card.appendChild(weaponsEl);
  }

  // Add stat grid
  const statsEl = document.createElement('div');
  statsEl.className = 'ship-stat-grid';
  const stats = [
    ['Hnd', ship.hnd], ['SR', ship.sr], ['SM', ship.sm],
    ['Accel', ship.accel], ['Top', ship.top_speed], ['Stall', ship.stall_speed],
  ];
  statsEl.innerHTML = stats.map(([label, val]) =>
    `<div class="stat-cell">
      <span class="stat-label">${label}</span>
      <span class="stat-value ${canEdit ? 'editable' : ''}" data-field="${label.toLowerCase()}">${val ?? '—'}</span>
    </div>`
  ).join('');

  if (canEdit && onShipEdit) {
    _wireEditableFields(statsEl, ship.ship_id, onShipEdit);
  }

  card.appendChild(statsEl);

  return card;
}


// ---------------------------------------------------------------------------
// Inline editing
// ---------------------------------------------------------------------------

function _wireEditableFields(container, shipId, onShipEdit) {
  container.querySelectorAll('.editable').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const field = el.dataset.field;
      const currentValue = el.textContent;

      const input = document.createElement('input');
      input.type = 'number';
      input.className = 'inline-edit';
      input.value = currentValue;

      const commit = () => {
        const newVal = parseInt(input.value, 10);
        if (!isNaN(newVal) && newVal !== parseInt(currentValue, 10)) {
          onShipEdit(shipId, field, newVal);
        }
        el.textContent = isNaN(newVal) ? currentValue : newVal;
        el.style.display = '';
        input.remove();
      };

      const cancel = () => {
        el.style.display = '';
        input.remove();
      };

      input.addEventListener('keydown', (ke) => {
        if (ke.key === 'Enter') commit();
        if (ke.key === 'Escape') cancel();
      });
      input.addEventListener('blur', commit);

      el.style.display = 'none';
      el.parentNode.insertBefore(input, el.nextSibling);
      input.focus();
      input.select();
    });
  });
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _getSystemStatus(ship, system) {
  if (ship.destroyed_systems?.includes(system)) return 'destroyed';
  if (ship.disabled_systems?.includes(system)) return 'disabled';
  return 'ok';
}

function _hpColor(pct) {
  if (pct >= 75) return 'var(--cond-fine)';
  if (pct >= 50) return 'var(--cond-damaged)';
  if (pct >= 25) return 'var(--cond-heavy)';
  return 'var(--cond-crippled)';
}

function _extractTemplateName(templateId) {
  if (!templateId) return '?';
  // Strip _v1, _v2 etc. suffix
  return templateId.replace(/_v\d+$/, '');
}

function _esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
