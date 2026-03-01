// components/ShipHPBar.jsx
// Animated HP bar. Colour shifts green → amber → red as HP drops.

import { useMemo } from "react";

const WOUND_COLOURS = {
  none: "text-slate-400",
  minor: "text-yellow-400",
  major: "text-orange-400",
  crippling: "text-red-500",
  mortal: "text-red-700",
  lethal: "bg-red-900 text-white px-1 rounded",
};

export default function ShipHPBar({ hpCurrent, hpMax, woundLevel }) {
  const pct = hpMax > 0 ? Math.max(0, Math.min(100, (hpCurrent / hpMax) * 100)) : 0;

  const barColour = useMemo(() => {
    if (pct > 60) return "bg-emerald-500";
    if (pct > 30) return "bg-amber-400";
    return "bg-red-500";
  }, [pct]);

  const woundClass = WOUND_COLOURS[woundLevel] || "text-slate-400";

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">HP</span>
        <span className="text-slate-200 font-mono">
          {hpCurrent} / {hpMax}
        </span>
        <span className={`font-bold uppercase text-xs ${woundClass}`}>
          {woundLevel !== "none" ? woundLevel : ""}
        </span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColour}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
