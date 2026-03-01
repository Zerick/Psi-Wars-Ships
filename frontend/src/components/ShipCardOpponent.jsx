// components/ShipCardOpponent.jsx
// Reduced opponent ship card for player view.
// Shows: name, class, assigned player, pilot stats (public), HP+wound, weapon names only.

import PilotBar from "./PilotBar";
import ShipHPBar from "./ShipHPBar";
import WeaponsList from "./WeaponsList";

const FACTION_BORDER = {
  imperial: "border-blue-800",
  trader: "border-amber-800",
  redjack: "border-red-800",
  neutral: "border-slate-700",
};

const CLASS_BADGE = {
  fighter: { label: "Fighter", colour: "bg-slate-700 text-slate-400" },
  corvette: { label: "Corvette", colour: "bg-indigo-900 text-indigo-400" },
  capital: { label: "Capital", colour: "bg-purple-900 text-purple-400" },
};

export default function ShipCardOpponent({ ship, assignedPlayerName }) {
  const faction = ship.faction || "neutral";
  const border = FACTION_BORDER[faction] || FACTION_BORDER.neutral;
  const badge = CLASS_BADGE[ship.ship_class] || CLASS_BADGE.fighter;

  return (
    <div
      className={`
        flex flex-col gap-2 p-3 rounded-lg
        bg-slate-900/70 border ${border}
        w-56 min-h-[240px] flex-shrink-0 opacity-90
        ${ship.is_destroyed === true ? "opacity-40 grayscale" : ""}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-1">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-slate-300 truncate">{ship.name}</p>
          <p className="text-xs text-slate-500">{assignedPlayerName || "Unassigned"}</p>
        </div>
        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${badge.colour}`}>
          {badge.label}
        </span>
      </div>

      {/* Pilot bar — public */}
      <PilotBar pilot={ship.pilot} isGm={false} />

      {/* HP bar */}
      <ShipHPBar
        hpCurrent={ship.hp_current}
        hpMax={ship.hp_max}
        woundLevel={ship.wound_level}
      />

      {/* Weapons — names and types only */}
      {ship.weapons && ship.weapons.length > 0 && (
        <WeaponsList weapons={ship.weapons} showFull={false} />
      )}

      {/* Classified notice */}
      <div className="mt-auto text-[10px] text-slate-600 italic border-t border-slate-800 pt-1">
        Systems / stats classified
      </div>
    </div>
  );
}
