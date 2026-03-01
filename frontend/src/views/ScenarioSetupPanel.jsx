// views/ScenarioSetupPanel.jsx
// GM-only panel for scenario creation and ship management.
// Rendered inside the existing GMPanel.

import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";

const FACTION_LABELS = {
  imperial: "Imperial",
  trader: "Trader",
  redjack: "Redjack",
  neutral: "Neutral",
};

const CLASS_LABELS = {
  fighter: "Fighter",
  corvette: "Corvette",
  capital: "Capital",
};

export default function ScenarioSetupPanel({
  scenario,
  participants,
  token,
  sessionId,
  onCreateScenario,
  onAddShip,
  onRemoveShip,
}) {
  const [scenarioName, setScenarioName] = useState("New Scenario");
  const [library, setLibrary] = useState([]);
  const [selectedLib, setSelectedLib] = useState(null);
  const [shipForm, setShipForm] = useState(null);
  const [showManage, setShowManage] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Load ship library
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/library/ships?token=${token}`)
      .then((r) => r.json())
      .then((data) => setLibrary(Array.isArray(data) ? data : []))
      .catch(() => setLibrary([]));
  }, [token]);

  // Pre-fill form when GM picks a library ship
  const selectLibraryShip = (libShip) => {
    setSelectedLib(libShip);
    setShipForm({
      // Ship fields
      name: libShip.name,
      hp_max: libShip.hp_max,
      hp_current: libShip.hp_current,
      ht: libShip.ht,
      handling: libShip.handling,
      sr: libShip.sr,
      move_space: libShip.move_space,
      dr_hull: libShip.dr_hull,
      force_screen_max: libShip.force_screen_max,
      afterburner_available: libShip.afterburner_available,
      fuel_max: libShip.fuel_max,
      notes: libShip.notes || "",
      // Pilot defaults
      pilot_name: "Unknown Pilot",
      piloting_skill: 12,
      gunner_skill: 12,
      dodge: 9,
      assigned_user_id: "",
    });
  };

  const updateForm = (field, value) => {
    setShipForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleAddShip = async () => {
    if (!shipForm || !scenario) return;
    setBusy(true);
    setError(null);
    try {
      const payload = {
        library_key: selectedLib?.library_key || null,
        ship: {
          ...selectedLib,
          name: shipForm.name,
          hp_max: Number(shipForm.hp_max),
          hp_current: Number(shipForm.hp_current),
          ht: Number(shipForm.ht),
          handling: Number(shipForm.handling),
          sr: Number(shipForm.sr),
          move_space: Number(shipForm.move_space),
          dr_hull: Number(shipForm.dr_hull),
          force_screen_max: Number(shipForm.force_screen_max),
          force_screen_current: Number(shipForm.force_screen_max),
          assigned_user_id: shipForm.assigned_user_id || null,
          notes: shipForm.notes,
          pilot: {
            name: shipForm.pilot_name,
            piloting_skill: Number(shipForm.piloting_skill),
            gunner_skill: Number(shipForm.gunner_skill),
            dodge: Number(shipForm.dodge),
          },
        },
      };
      await onAddShip(payload);
      setShipForm(null);
      setSelectedLib(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── No scenario yet ──────────────────────────────────────────────────────
  if (!scenario) {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
          Scenario Setup
        </h3>
        <div className="flex gap-2">
          <input
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
            placeholder="Scenario name"
            className="flex-1 bg-slate-800 border border-slate-600 rounded px-2 py-1 text-sm text-slate-100"
          />
          <button
            onClick={() => onCreateScenario(scenarioName)}
            className="px-3 py-1 bg-blue-700 hover:bg-blue-600 text-white text-sm rounded font-semibold"
          >
            Create
          </button>
        </div>
      </div>
    );
  }

  // ── Scenario exists ──────────────────────────────────────────────────────
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">
          Ships
          <span className="ml-2 text-slate-500 font-normal normal-case">
            {scenario.name}
          </span>
        </h3>
        <button
          onClick={() => { setShowManage((v) => !v); setShipForm(null); setSelectedLib(null); }}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          {showManage ? "Close" : "＋ Add Ship"}
        </button>
      </div>

      {/* Add ship panel */}
      {showManage && (
        <div className="space-y-3 border border-slate-700 rounded p-3 bg-slate-800/50">

          {/* Library picker */}
          {!shipForm && (
            <>
              <p className="text-xs text-slate-400">Select a ship from the library:</p>
              <div className="grid grid-cols-1 gap-1.5">
                {library.map((libShip) => (
                  <button
                    key={libShip.library_key}
                    onClick={() => selectLibraryShip(libShip)}
                    className="flex items-center justify-between px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-left"
                  >
                    <span className="text-sm text-slate-200">{libShip.name}</span>
                    <div className="flex gap-1.5">
                      <span className="text-xs text-slate-500 capitalize">{libShip.ship_class}</span>
                      <span className={`text-xs px-1 rounded ${factionBadge(libShip.faction)}`}>
                        {FACTION_LABELS[libShip.faction] || libShip.faction}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* Ship setup form */}
          {shipForm && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold text-slate-300">
                  Configure: {selectedLib?.name}
                </p>
                <button
                  onClick={() => { setShipForm(null); setSelectedLib(null); }}
                  className="text-xs text-slate-500 hover:text-slate-300"
                >
                  ← Back
                </button>
              </div>

              <FormRow label="Ship Name">
                <input
                  value={shipForm.name}
                  onChange={(e) => updateForm("name", e.target.value)}
                  className={INPUT_CLS}
                />
              </FormRow>

              <div className="grid grid-cols-2 gap-2">
                <FormRow label="HP Max">
                  <input type="number" value={shipForm.hp_max} onChange={(e) => updateForm("hp_max", e.target.value)} className={INPUT_CLS} />
                </FormRow>
                <FormRow label="HT">
                  <input type="number" value={shipForm.ht} onChange={(e) => updateForm("ht", e.target.value)} className={INPUT_CLS} />
                </FormRow>
              </div>

              <div className="border-t border-slate-700 pt-2">
                <p className="text-xs text-slate-500 mb-1.5 uppercase">Pilot</p>
                <FormRow label="Pilot Name">
                  <input
                    value={shipForm.pilot_name}
                    onChange={(e) => updateForm("pilot_name", e.target.value)}
                    className={INPUT_CLS}
                  />
                </FormRow>
                <div className="grid grid-cols-3 gap-2 mt-1">
                  <FormRow label="Piloting">
                    <input type="number" value={shipForm.piloting_skill} onChange={(e) => updateForm("piloting_skill", e.target.value)} className={INPUT_CLS} />
                  </FormRow>
                  <FormRow label="Gunner">
                    <input type="number" value={shipForm.gunner_skill} onChange={(e) => updateForm("gunner_skill", e.target.value)} className={INPUT_CLS} />
                  </FormRow>
                  <FormRow label="Dodge">
                    <input type="number" value={shipForm.dodge} onChange={(e) => updateForm("dodge", e.target.value)} className={INPUT_CLS} />
                  </FormRow>
                </div>
              </div>

              <div className="border-t border-slate-700 pt-2">
                <p className="text-xs text-slate-500 mb-1.5 uppercase">Assignment</p>
                <select
                  value={shipForm.assigned_user_id}
                  onChange={(e) => updateForm("assigned_user_id", e.target.value)}
                  className={INPUT_CLS}
                >
                  <option value="">— Unassigned —</option>
                  {participants?.map((p) => (
                    <option key={p.user_id} value={p.user_id}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              </div>

              <FormRow label="Notes">
                <textarea
                  value={shipForm.notes}
                  onChange={(e) => updateForm("notes", e.target.value)}
                  className={`${INPUT_CLS} h-14 resize-none`}
                />
              </FormRow>

              {error && <p className="text-xs text-red-400">{error}</p>}

              <button
                onClick={handleAddShip}
                disabled={busy}
                className="w-full py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-sm rounded font-semibold disabled:opacity-50"
              >
                {busy ? "Adding…" : "Add Ship to Scenario"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Current ships list */}
      {scenario.ships && scenario.ships.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-slate-500 uppercase tracking-wider">Active Ships</p>
          {scenario.ships.map((ship) => {
            const player = participants?.find((p) => p.user_id === ship.assigned_user_id);
            return (
              <div
                key={ship.ship_id}
                className="flex items-center justify-between text-xs px-2 py-1.5 bg-slate-800 rounded border border-slate-700"
              >
                <span className="text-slate-200 font-semibold truncate">{ship.name}</span>
                <span className="text-slate-500 truncate ml-2">
                  {player?.display_name || "Unassigned"}
                </span>
                <button
                  onClick={() => {
                    if (confirm(`Remove ${ship.name}?`)) onRemoveShip(ship.ship_id);
                  }}
                  className="text-red-600 hover:text-red-400 ml-2 flex-shrink-0"
                  title="Remove ship"
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const INPUT_CLS =
  "w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100 focus:border-blue-500 focus:outline-none";

function FormRow({ label, children }) {
  return (
    <div className="space-y-0.5">
      <label className="text-xs text-slate-500">{label}</label>
      {children}
    </div>
  );
}

function factionBadge(faction) {
  return {
    imperial: "bg-blue-900 text-blue-300",
    trader: "bg-amber-900 text-amber-300",
    redjack: "bg-red-900 text-red-300",
    neutral: "bg-slate-700 text-slate-400",
  }[faction] || "bg-slate-700 text-slate-400";
}
