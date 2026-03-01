// components/ForceScreenBar.jsx
// Blue force screen DR bar. Only shown on own card and GM view.

export default function ForceScreenBar({ current, max, hardened }) {
  if (!max) return null;

  const pct = max > 0 ? Math.max(0, Math.min(100, (current / max) * 100)) : 0;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">
          Force Screen {hardened && <span className="text-blue-400">[H]</span>}
        </span>
        <span className="text-slate-200 font-mono">
          {current} / {max}
        </span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 bg-blue-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
