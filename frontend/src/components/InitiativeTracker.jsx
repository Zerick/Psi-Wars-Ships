// components/InitiativeTracker.jsx
// Shown to all participants above ShipsZone when combat is active.
// Displays ship initiative order, current phase, round, and has-acted state.

const PHASE_LABELS = {
  setup:       "Setup",
  declaration: "Declaration",
  chase:       "Chase",
  action:      "Action",
  end_round:   "End of Round",
};

const PHASE_COLORS = {
  setup:       "var(--text-secondary)",
  declaration: "#d4a017",
  chase:       "#4a9ede",
  action:      "var(--accent-red)",
  end_round:   "#4caf6a",
};

export default function InitiativeTracker({ combat, ships }) {
  if (!combat) return null;

  const { initiative_order = [], current_phase, current_round } = combat;

  // Build a lookup from ship_id → ship name
  const shipMap = {};
  (ships || []).forEach((s) => { shipMap[s.ship_id] = s; });

  return (
    <div style={{
      background: "var(--bg-panel)",
      borderBottom: "1px solid var(--border)",
      padding: "8px 14px",
      display: "flex",
      alignItems: "center",
      gap: "16px",
      flexWrap: "wrap",
      flexShrink: 0,
    }}>
      {/* Round + Phase */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
        <span style={{
          fontFamily: "Barlow Condensed, sans-serif",
          fontSize: "11px",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--text-secondary)",
        }}>
          Round {current_round}
        </span>
        <span style={{
          fontFamily: "Barlow Condensed, sans-serif",
          fontSize: "13px",
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: PHASE_COLORS[current_phase] || "var(--text-secondary)",
        }}>
          {PHASE_LABELS[current_phase] || current_phase}
        </span>
      </div>

      <div style={{ width: "1px", height: "24px", background: "var(--border)", flexShrink: 0 }} />

      {/* Initiative order */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", flex: 1 }}>
        {initiative_order.map((entry, idx) => {
          const ship = shipMap[entry.ship_id];
          const hasActed = entry.has_acted === true;
          const isCurrentActor =
            current_phase === "action" &&
            !hasActed &&
            idx === initiative_order.findIndex((e) => !e.has_acted);

          return (
            <div
              key={entry.ship_id}
              title={`Initiative: ${entry.initiative_value}${entry.initiative_roll != null ? ` (rolled ${entry.initiative_roll})` : ""}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "5px",
                padding: "3px 8px",
                border: `1px solid ${isCurrentActor ? "var(--accent-red)" : "var(--border)"}`,
                background: isCurrentActor ? "rgba(232,65,10,0.12)" : "var(--bg-deep)",
                opacity: hasActed ? 0.4 : 1,
                transition: "opacity 0.2s, border-color 0.2s",
                position: "relative",
              }}
            >
              {/* Turn order indicator */}
              <span style={{
                fontFamily: "Barlow Condensed, sans-serif",
                fontSize: "10px",
                color: isCurrentActor ? "var(--accent-red)" : "var(--text-secondary)",
                fontWeight: 700,
                minWidth: "12px",
              }}>
                {idx + 1}.
              </span>

              <span style={{
                fontSize: "11px",
                color: isCurrentActor ? "var(--text-primary)" : "var(--text-secondary)",
                fontWeight: isCurrentActor ? 600 : 400,
                maxWidth: "100px",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}>
                {ship?.name || entry.ship_id.slice(0, 8)}
              </span>

              <span className="font-mono" style={{
                fontSize: "10px",
                color: "var(--text-secondary)",
              }}>
                {entry.initiative_value}
              </span>

              {hasActed && (
                <span style={{
                  position: "absolute",
                  top: 0,
                  right: 2,
                  fontSize: "8px",
                  color: "#4caf6a",
                  fontFamily: "Barlow Condensed, sans-serif",
                  letterSpacing: "0.04em",
                }}>
                  ✓
                </span>
              )}
            </div>
          );
        })}
      </div>

      {combat.status === "ended" && (
        <span style={{
          fontFamily: "Barlow Condensed, sans-serif",
          fontSize: "11px",
          color: "var(--text-secondary)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          border: "1px solid var(--border)",
          padding: "2px 8px",
        }}>
          Combat Ended
        </span>
      )}
    </div>
  );
}
