// components/ShipCard.jsx
// Full ship card — shown to the owning player and the GM.
// GM gets inline editing on every field.

import { useState, useEffect } from "react";
import PilotBar from "./PilotBar";
import ShipHPBar from "./ShipHPBar";
import ForceScreenBar from "./ForceScreenBar";
import SystemsGrid from "./SystemsGrid";
import WeaponsList from "./WeaponsList";
import InlineEdit from "./InlineEdit";

// Faction → border colour
const FACTION_BORDER = {
  imperial: "border-blue-600",
  trader: "border-amber-500",
  redjack: "border-red-600",
  neutral: "border-slate-600",
};

const FACTION_GLOW = {
  imperial: "shadow-blue-900/40",
  trader: "shadow-amber-900/40",
  redjack: "shadow-red-900/40",
  neutral: "shadow-slate-900/40",
};

const CLASS_BADGE = {
  fighter: { label: "Fighter", colour: "bg-slate-700 text-slate-300" },
  corvette: { label: "Corvette", colour: "bg-indigo-900 text-indigo-300" },
  capital: { label: "Capital", colour: "bg-purple-900 text-purple-300" },
};

// Flash highlight when a value changes
function useFlash(value) {
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 800);
    return () => clearTimeout(t);
  }, [value]);
  return flash;
}

export default function ShipCard({
  ship,
  isGm,
  participants,   // [{user_id, display_name}] for assignment dropdown
  onPatchShip,
  onPatchPilot,
  onPatchSystem,
  onRemoveShip,
  onAssignShip,
}) {
  const faction = ship.faction || "neutral";
  const border = FACTION_BORDER[faction] || FACTION_BORDER.neutral;
  const glow = FACTION_GLOW[faction] || FACTION_GLOW.neutral;
  const badge = CLASS_BADGE[ship.ship_class] || CLASS_BADGE.fighter;

  const hpFlash = useFlash(ship.hp_current);
  const fsFlash = useFlash(ship.force_screen_current);

  const assignedName =
    participants?.find((p) => p.user_id === ship.assigned_user_id)
      ?.display_name || "Unassigned";

  return (
    <div
      className={`
        relative flex flex-col gap-2 p-3 rounded-lg
        bg-slate-900 border ${border}
        shadow-lg ${glow}
        w-64 min-h-[360px] flex-shrink-0
        ${ship.is_destroyed ? "opacity-50 grayscale" : ""}
      `}
    >
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-1">
        <div className="flex-1 min-w-0">
          {isGm ? (
            <InlineEdit
              value={ship.name}
              onSave={(v) => onPatchShip(ship.ship_id, { name: v })}
              displayClassName="text-sm font-bold text-slate-100 truncate"
            />
          ) : (
            <p className="text-sm font-bold text-slate-100 truncate">{ship.name}</p>
          )}
          <p className="text-xs text-slate-400">{assignedName}</p>
        </div>
        <div className="flex items-center gap-1">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${badge.colour}`}>
            {badge.label}
          </span>
          {ship.is_uncontrolled === true && (
            <span className="text-[10px] px-1.5 py-0.5 rounded font-bold bg-red-900 text-red-300">
              UNCONTROLLED
            </span>
          )}
        </div>
      </div>

      {/* ── GM: Assign to player ── */}
      {isGm && participants && (
        <div className="flex items-center gap-1 text-xs">
          <span className="text-slate-500">Assign:</span>
          <select
            value={ship.assigned_user_id || ""}
            onChange={(e) => onAssignShip(ship.ship_id, e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-1 py-0 text-slate-200 text-xs flex-1"
          >
            <option value="">Unassigned</option>
            {participants.map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {p.display_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ── Pilot Bar ── */}
      <PilotBar pilot={ship.pilot} isGm={isGm} shipId={ship.ship_id} onSave={onPatchPilot} />

      {/* ── HP Bar ── */}
      <div className={`transition-all duration-200 ${hpFlash ? "ring-1 ring-amber-400 rounded" : ""}`}>
        {isGm ? (
          <div className="space-y-0.5">
            <div className="flex items-center justify-between text-xs mb-0.5">
              <span className="text-slate-400">HP</span>
              <div className="flex items-center gap-1">
                <InlineEdit
                  value={ship.hp_current}
                  type="number"
                  min={0}
                  max={ship.hp_max}
                  onSave={(v) => onPatchShip(ship.ship_id, { hp_current: v })}
                  displayClassName="text-slate-200 font-mono"
                />
                <span className="text-slate-500">/</span>
                <InlineEdit
                  value={ship.hp_max}
                  type="number"
                  min={1}
                  onSave={(v) => onPatchShip(ship.ship_id, { hp_max: v })}
                  displayClassName="text-slate-200 font-mono"
                />
              </div>
              <InlineEdit
                value={ship.wound_level}
                type="select"
                options={[
                  { value: "none", label: "None" },
                  { value: "minor", label: "Minor" },
                  { value: "major", label: "Major" },
                  { value: "crippling", label: "Crippling" },
                  { value: "mortal", label: "Mortal" },
                  { value: "lethal", label: "Lethal" },
                ]}
                onSave={(v) => onPatchShip(ship.ship_id, { wound_level: v })}
                displayClassName={woundLabelClass(ship.wound_level)}
              />
            </div>
            <HpBarVisual hpCurrent={ship.hp_current} hpMax={ship.hp_max} />
          </div>
        ) : (
          <ShipHPBar
            hpCurrent={ship.hp_current}
            hpMax={ship.hp_max}
            woundLevel={ship.wound_level}
          />
        )}
      </div>

      {/* ── Force Screen Bar ── */}
      {ship.force_screen_max > 0 && (
        <div className={`transition-all duration-200 ${fsFlash ? "ring-1 ring-blue-400 rounded" : ""}`}>
          {isGm ? (
            <div className="space-y-0.5">
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className="text-slate-400">
                  Force Screen {ship.force_screen_hardened && <span className="text-blue-400">[H]</span>}
                </span>
                <div className="flex items-center gap-1">
                  <InlineEdit
                    value={ship.force_screen_current}
                    type="number"
                    min={0}
                    max={ship.force_screen_max}
                    onSave={(v) => onPatchShip(ship.ship_id, { force_screen_current: v })}
                    displayClassName="text-slate-200 font-mono"
                  />
                  <span className="text-slate-500">/</span>
                  <InlineEdit
                    value={ship.force_screen_max}
                    type="number"
                    min={0}
                    onSave={(v) => onPatchShip(ship.ship_id, { force_screen_max: v })}
                    displayClassName="text-slate-200 font-mono"
                  />
                </div>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 bg-blue-500"
                  style={{
                    width: `${ship.force_screen_max > 0
                      ? Math.max(0, Math.min(100, (ship.force_screen_current / ship.force_screen_max) * 100))
                      : 0}%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <ForceScreenBar
              current={ship.force_screen_current}
              max={ship.force_screen_max}
              hardened={ship.force_screen_hardened}
            />
          )}
        </div>
      )}

      {/* ── Systems Grid ── */}
      <SystemsGrid
        systems={ship.systems}
        isGm={isGm}
        shipId={ship.ship_id}
        onStatusChange={(sysName, status) => onPatchSystem(ship.ship_id, sysName, status)}
      />

      {/* ── Weapons ── */}
      <WeaponsList weapons={ship.weapons} showFull={true} />

      {/* ── Config Modes (display only in Slice 2) ── */}
      {ship.config_modes && ship.config_modes.length > 0 && (
        <div className="border-t border-slate-700 pt-2">
          <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Config Mode</p>
          <div className="flex gap-1 flex-wrap">
            {ship.config_modes.map((mode) => (
              <span
                key={mode.key}
                className={`text-xs px-2 py-0.5 rounded border ${
                  ship.active_config === mode.key
                    ? "border-blue-500 text-blue-300 bg-blue-900/30"
                    : "border-slate-600 text-slate-500"
                }`}
              >
                {mode.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── GM Notes ── */}
      {isGm && (
        <div className="border-t border-slate-700 pt-2 mt-auto">
          <p className="text-xs text-slate-500 mb-1">Notes (GM only)</p>
          <GMNotes
            value={ship.notes}
            onSave={(v) => onPatchShip(ship.ship_id, { notes: v })}
          />
        </div>
      )}

      {/* ── GM Faction selector ── */}
      {isGm && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px' }}>
          <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-secondary)', minWidth: '44px' }}>Faction</span>
          <select
            value={ship.faction || 'player'}
            onChange={e => onPatchShip && onPatchShip(ship.ship_id, { faction: e.target.value })}
            style={{
              flex: 1, background: 'var(--bg-deep)', border: '1px solid var(--border)',
              color: ship.faction === 'hostile_npc' ? '#e8410a' : ship.faction === 'friendly_npc' ? '#4caf6a' : 'var(--text-secondary)',
              fontSize: '10px', fontFamily: 'Barlow Condensed, sans-serif', padding: '2px 4px',
              cursor: 'pointer',
            }}
          >
            <option value="player">Player</option>
            <option value="hostile_npc">Hostile NPC</option>
            <option value="friendly_npc">Friendly NPC</option>
          </select>
        </div>
      )}
      {/* ── GM Remove button ── */}
      {isGm && (
        <button
          onClick={() => {
            if (confirm(`Remove ${ship.name} from scenario?`)) {
              onRemoveShip(ship.ship_id);
            }
          }}
          className="mt-auto text-xs text-red-600 hover:text-red-400 text-right"
        >
          Remove ship
        </button>
      )}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function HpBarVisual({ hpCurrent, hpMax }) {
  const pct = hpMax > 0 ? Math.max(0, Math.min(100, (hpCurrent / hpMax) * 100)) : 0;
  const colour = pct > 60 ? "bg-emerald-500" : pct > 30 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${colour}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function woundLabelClass(level) {
  return (
    {
      none: "text-slate-500",
      minor: "text-yellow-400 font-bold",
      major: "text-orange-400 font-bold",
      crippling: "text-red-500 font-bold",
      mortal: "text-red-700 font-bold",
      lethal: "text-white bg-red-900 px-1 rounded font-bold",
    }[level] || "text-slate-500"
  );
}

function GMNotes({ value, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");

  useEffect(() => {
    setDraft(value || "");
  }, [value]);

  if (!editing) {
    return (
      <p
        className="text-xs text-slate-400 cursor-pointer hover:text-slate-300 min-h-[2rem]"
        onClick={() => setEditing(true)}
        title="Click to edit notes"
      >
        {value || <span className="text-slate-600 italic">Click to add notes…</span>}
      </p>
    );
  }

  return (
    <div className="space-y-1">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        className="w-full bg-slate-800 border border-blue-500 rounded px-2 py-1 text-xs text-slate-200 resize-none h-16"
        autoFocus
      />
      <div className="flex gap-2">
        <button
          onClick={() => { onSave(draft); setEditing(false); }}
          className="text-xs text-emerald-400 hover:text-emerald-300 font-bold"
        >
          ✓ Save
        </button>
        <button
          onClick={() => { setDraft(value || ""); setEditing(false); }}
          className="text-xs text-red-400 hover:text-red-300"
        >
          ✕ Cancel
        </button>
      </div>
    </div>
  );
}
