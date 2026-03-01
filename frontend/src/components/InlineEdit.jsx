// components/InlineEdit.jsx
// Reusable click-to-edit field. Pencil icon → input → check/x confirm.
// Used throughout GM ship card for live editing.

import { useState, useRef, useEffect } from "react";

export default function InlineEdit({
  value,
  onSave,
  type = "text",        // text | number | select
  options = [],         // for select type: [{value, label}]
  className = "",
  displayClassName = "",
  min,
  max,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value ?? ""));
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  useEffect(() => {
    setDraft(String(value ?? ""));
  }, [value]);

  const confirm = () => {
    const parsed = type === "number" ? Number(draft) : draft;
    onSave(parsed);
    setEditing(false);
  };

  const cancel = () => {
    setDraft(String(value ?? ""));
    setEditing(false);
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter") confirm();
    if (e.key === "Escape") cancel();
  };

  if (!editing) {
    return (
      <span
        className={`group flex items-center gap-1 cursor-pointer ${displayClassName}`}
        onClick={() => setEditing(true)}
        title="Click to edit"
      >
        <span>{value ?? "—"}</span>
        <svg
          className="w-3 h-3 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 112.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-1.414a2 2 0 01.586-1.414z"
          />
        </svg>
      </span>
    );
  }

  return (
    <span className={`flex items-center gap-1 ${className}`}>
      {type === "select" ? (
        <select
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          className="bg-slate-800 border border-blue-500 rounded px-1 py-0 text-xs text-slate-100"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          ref={inputRef}
          type={type}
          value={draft}
          min={min}
          max={max}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          className="bg-slate-800 border border-blue-500 rounded px-1 py-0 text-xs text-slate-100 w-20"
        />
      )}
      <button
        onClick={confirm}
        className="text-emerald-400 hover:text-emerald-300 text-xs font-bold"
        title="Confirm"
      >
        ✓
      </button>
      <button
        onClick={cancel}
        className="text-red-400 hover:text-red-300 text-xs"
        title="Cancel"
      >
        ✕
      </button>
    </span>
  );
}
