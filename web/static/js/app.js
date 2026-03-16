/* Psi-Wars Combat Simulator — Main App v0.3.0 */
import { MOCK_SHIPS, MOCK_ENGAGEMENTS, MOCK_COMBAT_LOG, MOCK_DICE_LOG, MOCK_ACTIVE_STATE } from './mock-data.js?v=0.2.9';
import { renderShipStrip } from './components/ship-card.js?v=0.2.9';
import { createCombatLog, loadMockLog } from './components/combat-log.js?v=0.2.9';
import { createGMPanel } from './components/gm-panel.js?v=0.2.9';
import { createEngagementDisplay } from './components/engagement-display.js?v=0.2.9';

document.addEventListener('DOMContentLoaded', () => {
  const shipStrip = document.getElementById('ship-strip');
  const engStrip = document.getElementById('engagement-strip');
  const turnDisplay = document.getElementById('turn-display');
  const logContainer = document.getElementById('combat-log');
  const gmContainer = document.getElementById('gm-panel');

  turnDisplay.textContent = `Turn ${MOCK_ACTIVE_STATE.current_turn}`;
  const combatLog = createCombatLog(logContainer);
  loadMockLog(combatLog, MOCK_COMBAT_LOG);
  const gmPanel = createGMPanel(gmContainer, {
    onUndo: () => combatLog.addEntry('[GM] Undo requested', 'info'),
    onRedo: () => combatLog.addEntry('[GM] Redo requested', 'info'),
  });
  gmPanel.loadDiceLog(MOCK_DICE_LOG);
  const engDisplay = createEngagementDisplay(engStrip);

  function setField(ship, field, val) {
    const p = field.split('.');
    if (p.length === 2) ship[p[0]][p[1]] = val;
    else if (field === 'ht') ship[field] = String(val);
    else ship[field] = val;
  }
  function updateWound(ship) {
    const pct = ship.st_hp > 0 ? ship.current_hp / ship.st_hp : 0;
    if (ship.current_hp <= 0) { ship.wound_level = 'destroyed'; ship.is_destroyed = true; }
    else if (pct <= 0.33) { ship.wound_level = 'crippling'; ship.is_destroyed = false; }
    else if (pct <= 0.66) { ship.wound_level = 'major'; ship.is_destroyed = false; }
    else { ship.wound_level = 'minor'; ship.is_destroyed = false; }
  }

  const cb = {
    gmMode: true,
    onSubsystemChange: (id, sys, st) => {
      const s = MOCK_SHIPS.find(x => x.ship_id === id); if (!s) return;
      s.disabled_systems = s.disabled_systems.filter(x => x !== sys);
      s.destroyed_systems = s.destroyed_systems.filter(x => x !== sys);
      if (st === 'disabled') s.disabled_systems.push(sys);
      if (st === 'destroyed') s.destroyed_systems.push(sys);
      refresh();
    },
    onFieldChange: (id, field, val) => {
      const s = MOCK_SHIPS.find(x => x.ship_id === id); if (!s) return;
      setField(s, field, val);
      if (field === 'current_hp' || field === 'st_hp') updateWound(s);
      refresh();
    }
  };

  function refresh() {
    cb.gmMode = true;
    renderShipStrip(shipStrip, MOCK_SHIPS, MOCK_ACTIVE_STATE, cb);
    engDisplay.render(MOCK_ENGAGEMENTS, MOCK_SHIPS);
  }
  refresh();

  const gmToggle = document.getElementById('gm-toggle');
  gmToggle.addEventListener('click', () => {
    const app = document.getElementById('app');
    app.classList.toggle('gm-hidden');
    gmToggle.classList.toggle('active');
    gmToggle.textContent = app.classList.contains('gm-hidden') ? 'Show GM' : 'Hide GM';
  });
  gmToggle.classList.add('active');
  gmToggle.textContent = 'Hide GM';
});
