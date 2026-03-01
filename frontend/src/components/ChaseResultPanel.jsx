// components/ChaseResultPanel.jsx
// Shown during Chase phase. Displays chase bonuses, rolls, MOS, outcomes.
// GM can auto-resolve or supply manual rolls in GM-review mode.

import { useState } from "react";

const RANGE_BANDS = ["close", "short", "medium", "long", "extreme", "distant", "beyond_visual"];

function PairChaseRow({ pair, ships, declarations, isGm, gmReview, onResolveAuto, onResolvePair }) {
  const [rollA, setRollA] = useState("");
  const [rollB, setRollB] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const shipMap = {};
  (ships || []).forEach((s) => { shipMap[s.ship_id] = s; });

  const shipA = shipMap[pair.ship_a_id];
  const shipB = shipMap[pair.ship_b_id];

  const declA = (declarations || []).find((d) => d.ship_id === pair.ship_a_id);
  const declB = (declarations || []).find((d) => d.ship_id === pair.ship_b_id);

  const hasResults = declA?.chase_roll_result != null || declB?.chase_roll_result != null;

  const handleManualResolve = async () => {
    if (!rollA || !rollB) return;
    setBusy(true);
    setError(null);
    try {
      await onResolvePair(pair.pair_id, parseInt(rollA), parseInt(rollB));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const advLabel = pair.advantage_ship_id
    ? (shipMap[pair.advantage_ship_id]?.name || "?") + " has ADV"
    : "Neutral";

  return (
    <div style={{
      background: "var(--bg-deep)",
      border: "1px solid var(--border)",
      padding: "10px",
      marginBottom: "8px",
    }}>
      {/* Pair header */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", flexWrap: "wrap", gap: "4px" }}>
        <span style={{ fontSize: "12px", color: "var(--text-primary)", fontWeight: 600 }}>
          {shipA?.name || "?"} ↔ {shipB?.name || "?"}
        </span>
        <span style={{ fontSize: "10px", color: "var(--text-secondary)", fontFamily: "Barlow Condensed, sans-serif" }}>
          {pair.range_band} · {advLabel}
        </span>
      </div>

      {/* Declarations */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "6px", flexWrap: "wrap" }}>
        {[{ ship: shipA, decl: declA, roll: declA?.chase_roll_result, mos: declA?.chase_mos },
          { ship: shipB, decl: declB, roll: declB?.chase_roll_result, mos: declB?.chase_mos }].map(
          ({ ship: s, decl: d, roll, mos }) => (
            <div key={s?.ship_id} style={{
              flex: 1,
              minWidth: "120px",
              background: "#0a0f15",
              border: "1px solid var(--border)",
              padding: "6px 8px",
            }}>
              <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "3px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                {s?.name || "?"}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-primary)", marginBottom: "2px" }}>
                {d?.maneuver?.replace(/_/g, " ") || "—"}
              </div>
              {roll != null && (
                <div style={{ fontSize: "11px", display: "flex", gap: "6px" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Roll: <span className="font-mono" style={{ color: "var(--text-mono)" }}>{roll}</span></span>
                  <span style={{ color: "var(--text-secondary)" }}>MOS: <span className="font-mono" style={{ color: mos >= 0 ? "#4caf6a" : "var(--accent-red)" }}>{mos >= 0 ? "+" : ""}{mos}</span></span>
                </div>
              )}
            </div>
          )
        )}
      </div>

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>
      )}

      {/* Resolution */}
      {isGm && !hasResults && (
        gmReview ? (
          <div style={{ display: "flex", gap: "6px", alignItems: "flex-end", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px" }}>{shipA?.name} roll</div>
              <input
                className="tactical-input font-mono"
                style={{ width: "60px", padding: "4px 6px", fontSize: "13px" }}
                type="number" min={3} max={18}
                value={rollA}
                onChange={(e) => setRollA(e.target.value)}
                placeholder="3d6"
              />
            </div>
            <div>
              <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px" }}>{shipB?.name} roll</div>
              <input
                className="tactical-input font-mono"
                style={{ width: "60px", padding: "4px 6px", fontSize: "13px" }}
                type="number" min={3} max={18}
                value={rollB}
                onChange={(e) => setRollB(e.target.value)}
                placeholder="3d6"
              />
            </div>
            <button
              className="btn btn-approve"
              disabled={!rollA || !rollB || busy}
              onClick={handleManualResolve}
            >
              Resolve
            </button>
          </div>
        ) : null
      )}

      {hasResults && (
        <div style={{ fontSize: "11px", color: "#4caf6a", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          ✓ Resolved — {pair.range_band} · {advLabel}{pair.matched_speed ? " · Matched Speed" : ""}
        </div>
      )}
    </div>
  );
}

export default function ChaseResultPanel({
  combat,
  ships,
  isGm,
  onResolveChase,
  onResolveChasePair,
  onAdvancePhase,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!combat) return null;

  const declarations = combat.declarations || [];
  const pairs = (combat.pairs || []).filter((p) => p.active);
  const gmReview = combat.gm_review_rolls === true;

  const allResolved = declarations.length > 0 && declarations.every(
    (d) => d.chase_roll_result != null || ["attack", "stop", "precision_aim"].includes(d.maneuver)
  );

  const handleAutoResolve = async () => {
    setBusy(true);
    setError(null);
    try {
      await onResolveChase();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleAdvance = async () => {
    setBusy(true);
    setError(null);
    try {
      await onAdvancePhase();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ marginBottom: "8px" }}>
      <div style={{
        fontFamily: "Barlow Condensed, sans-serif",
        fontSize: "11px",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: "#4a9ede",
        marginBottom: "8px",
      }}>
        Chase Phase — Round {combat.current_round}
      </div>

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>
      )}

      {pairs.map((pair) => (
        <PairChaseRow
          key={pair.pair_id}
          pair={pair}
          ships={ships}
          declarations={declarations}
          isGm={isGm}
          gmReview={gmReview}
          onResolveAuto={handleAutoResolve}
          onResolvePair={onResolveChasePair}
        />
      ))}

      {isGm && !gmReview && !allResolved && (
        <button
          className="btn btn-approve"
          style={{ width: "100%" }}
          disabled={busy}
          onClick={handleAutoResolve}
        >
          Roll All Chase Dice
        </button>
      )}

      {isGm && allResolved && combat.current_phase === "chase" && (
        <button
          className="btn btn-approve"
          style={{ width: "100%", marginTop: "6px" }}
          disabled={busy}
          onClick={handleAdvance}
        >
          → Advance to Action Phase
        </button>
      )}
    </div>
  );
}
