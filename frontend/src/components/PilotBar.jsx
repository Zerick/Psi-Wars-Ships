// components/PilotBar.jsx
// Pilot stats row. All stats are intentionally public — visible on all cards.

export default function PilotBar({ pilot, isGm, shipId, onSave }) {
  if (!pilot) return null;

  return (
    <div className="text-xs text-slate-300 py-1 border-t border-slate-700 space-y-0.5">
      <div className="font-semibold text-slate-200 truncate" title={pilot.name}>
        {pilot.name || "Unknown Pilot"}
      </div>
      <div className="flex items-center gap-3">
        <StatChip label="Pilot" value={pilot.piloting_skill} color="text-blue-300" />
        <StatChip label="Gunner" value={pilot.gunner_skill} color="text-amber-300" />
        <StatChip label="Dodge" value={pilot.dodge} color="text-emerald-300" />
      </div>
    </div>
  );
}

function StatChip({ label, value, color }) {
  return (
    <span className="flex items-center gap-1">
      <span className="text-slate-500">{label}</span>
      <span className={`font-bold ${color}`}>{value}</span>
    </span>
  );
}
