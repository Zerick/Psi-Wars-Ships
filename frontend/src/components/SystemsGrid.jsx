// components/SystemsGrid.jsx
// 3×3 grid of system status dots. Shown on own card and GM view.

const SYSTEM_NAMES = [
  "armor", "cargo", "controls",
  "equipment", "fuel", "habitat",
  "power", "propulsion", "weaponry",
];

const STATUS_COLOURS = {
  operational: "bg-emerald-500",
  disabled: "bg-amber-400",
  destroyed: "bg-red-600",
};

export default function SystemsGrid({ systems, isGm, shipId, onStatusChange }) {
  if (!systems) return null;

  return (
    <div className="border-t border-slate-700 pt-2">
      <p className="text-xs text-slate-500 mb-1.5 uppercase tracking-wider">Systems</p>
      <div className="grid grid-cols-3 gap-1">
        {SYSTEM_NAMES.map((sys) => {
          const status = systems[sys] || "operational";
          const dot = STATUS_COLOURS[status] || "bg-slate-500";

          return (
            <div key={sys} className="flex items-center gap-1.5 group relative">
              {isGm ? (
                <button
                  title={`${sys}: ${status}`}
                  onClick={() => onStatusChange && onStatusChange(sys, cycleStatus(status))}
                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dot} hover:opacity-75 transition-opacity cursor-pointer`}
                />
              ) : (
                <span
                  title={`${sys}: ${status}`}
                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dot}`}
                />
              )}
              <span className="text-xs text-slate-400 capitalize truncate">{sys}</span>

              {/* Tooltip on hover */}
              <span className="absolute left-0 bottom-full mb-1 z-10 hidden group-hover:block
                              bg-slate-900 text-slate-200 text-xs px-2 py-0.5 rounded whitespace-nowrap shadow">
                {sys}: {status}
                {isGm && " (click to cycle)"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function cycleStatus(current) {
  const order = ["operational", "disabled", "destroyed"];
  const idx = order.indexOf(current);
  return order[(idx + 1) % order.length];
}
