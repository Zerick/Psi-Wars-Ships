// components/CombatSetupPanel.jsx
// GM-only. Shown in GMPanel before/during combat setup.
// Manages combat pairs, initiative style, GM review mode, and Start Combat.

import { useState } from "react";

const RANGE_BANDS = ["close", "short", "medium", "long", "extreme", "distant", "beyond_visual"];
const FACINGS = ["F", "R", "L", "B", "U", "D"];

function PairRow({ pair, ships, combat, onUpdate, onRemove }) {
  const shipMap = {};
  (ships || []).forEach((s) => { shipMap[s.ship_id] = s; });

  const shipA = shipMap[pair.ship_a_id];
  const shipB = shipMap[pair.ship_b_id];

  return (
    <div style={{
      background: "var(--bg-deep)",
      border: "1px solid var(--border)",
      padding: "8px",
      marginBottom: "6px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px", flexWrap: "wrap" }}>
        <span style={{ fontSize: "11px", color: "var(--text-secondary)", flex: 1 }}>
          {shipA?.name || "?"} ↔ {shipB?.name || "?"}
        </span>
        <button
          onClick={() => onRemove(pair.pair_id)}
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            color: "var(--text-secondary)",
            padding: "2px 6px",
            cursor: "pointer",
            fontSize: "10px",
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
        {/* Range band */}
        <div>
          <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Range</div>
          <select
            className="tactical-input"
            style={{ fontSize: "11px", padding: "3px 4px" }}
            value={pair.range_band}
            onChange={(e) => onUpdate(pair.pair_id, { range_band: e.target.value })}
          >
            {RANGE_BANDS.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        {/* Advantage */}
        <div>
          <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Advantage</div>
          <select
            className="tactical-input"
            style={{ fontSize: "11px", padding: "3px 4px" }}
            value={pair.advantage_ship_id || ""}
            onChange={(e) => onUpdate(pair.pair_id, { advantage_ship_id: e.target.value || null })}
          >
            <option value="">Neutral</option>
            <option value={pair.ship_a_id}>{shipA?.name || "Ship A"}</option>
            <option value={pair.ship_b_id}>{shipB?.name || "Ship B"}</option>
          </select>
        </div>

        {/* Facing A */}
        <div>
          <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>{shipA?.name?.slice(0, 6)} facing</div>
          <select
            className="tactical-input"
            style={{ fontSize: "11px", padding: "3px 4px" }}
            value={pair.facing_a}
            onChange={(e) => onUpdate(pair.pair_id, { facing_a: e.target.value })}
          >
            {FACINGS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>

        {/* Facing B */}
        <div>
          <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "2px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>{shipB?.name?.slice(0, 6)} facing</div>
          <select
            className="tactical-input"
            style={{ fontSize: "11px", padding: "3px 4px" }}
            value={pair.facing_b}
            onChange={(e) => onUpdate(pair.pair_id, { facing_b: e.target.value })}
          >
            {FACINGS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}

export default function CombatSetupPanel({
  combat,
  ships,
  sessionId,
  token,
  onStartCombat,
  onAddPair,
  onUpdatePair,
  onEndCombat,
}) {
  const [initiativeStyle, setInitiativeStyle] = useState("stat_only");
  const [gmReview, setGmReview] = useState(true);
  const [addingPair, setAddingPair] = useState(false);
  const [pairShipA, setPairShipA] = useState("");
  const [pairShipB, setPairShipB] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isActive = combat && combat.status === "active";
  const showPairs = isActive || (combat && combat.pairs && combat.pairs.length > 0);
  const isEnded = combat && combat.status === "ended";

  const handleStartCombat = async () => {
    setBusy(true);
    setError(null);
    try {
      await onStartCombat({ initiative_roll_style: initiativeStyle });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleAddPair = async () => {
    if (!pairShipA || !pairShipB || pairShipA === pairShipB) return;
    setBusy(true);
    setError(null);
    try {
      await onAddPair({ ship_a_id: pairShipA, ship_b_id: pairShipB });
      setPairShipA("");
      setPairShipB("");
      setAddingPair(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleRemovePair = async (pairId) => {
    try {
      await onUpdatePair(pairId, { active: false });
    } catch (e) {
      setError(e.message);
    }
  };

  const activePairs = (combat?.pairs || []).filter((p) => p.active === true);

  return (
    <div style={{ marginTop: "10px" }}>
      <div style={{
        fontFamily: "Barlow Condensed, sans-serif",
        fontSize: "11px",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: "var(--accent-red)",
        marginBottom: "8px",
      }}>
        Combat
      </div>

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>
          {error}
        </div>
      )}

      {/* Setup options — only before combat starts */}
      {!isActive && !isEnded && (
        <div style={{ marginBottom: "8px" }}>
          {/* Initiative style */}
          <div style={{ marginBottom: "6px" }}>
            <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "4px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Initiative</div>
            <div style={{ display: "flex", gap: "6px" }}>
              {[["stat_only", "Initiative"], ["stat_plus_1d6", "Initiative + 1d6"]].map(([val, label]) => (
                <button
                  key={val}
                  onClick={() => setInitiativeStyle(val)}
                  style={{
                    background: initiativeStyle === val ? "var(--accent-red)" : "transparent",
                    border: `1px solid ${initiativeStyle === val ? "var(--accent-red)" : "var(--border)"}`,
                    color: initiativeStyle === val ? "#fff" : "var(--text-secondary)",
                    padding: "3px 8px",
                    cursor: "pointer",
                    fontSize: "10px",
                    fontFamily: "Barlow Condensed, sans-serif",
                    letterSpacing: "0.04em",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* GM review rolls */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <button
              onClick={() => setGmReview(!gmReview)}
              style={{
                background: gmReview ? "var(--accent-red)" : "transparent",
                border: `1px solid ${gmReview ? "var(--accent-red)" : "var(--border)"}`,
                color: gmReview ? "#fff" : "var(--text-secondary)",
                padding: "3px 8px",
                cursor: "pointer",
                fontSize: "10px",
                fontFamily: "Barlow Condensed, sans-serif",
                letterSpacing: "0.04em",
              }}
            >
              {gmReview ? "✓ GM reviews rolls" : "Auto-roll"}
            </button>
          </div>
        </div>
      )}

      {/* Combat pairs */}
      <div style={{ marginBottom: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
          <span style={{ fontSize: "10px", color: "var(--text-secondary)", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            Engagements
          </span>
          {!isEnded && (
            <button
              onClick={() => setAddingPair(!addingPair)}
              style={{
                background: "transparent",
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
                padding: "2px 6px",
                cursor: "pointer",
                fontSize: "10px",
              }}
            >
              + Add
            </button>
          )}
        </div>

        {addingPair && !isEnded && (
          <div style={{
            background: "var(--bg-deep)",
            border: "1px solid var(--border)",
            padding: "8px",
            marginBottom: "6px",
          }}>
            <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
              <select
                className="tactical-input"
                style={{ flex: 1, fontSize: "11px" }}
                value={pairShipA}
                onChange={(e) => setPairShipA(e.target.value)}
              >
                <option value="">Ship A…</option>
                {(ships || []).map((s) => (
                  <option key={s.ship_id} value={s.ship_id}>{s.name}</option>
                ))}
              </select>
              <span style={{ color: "var(--text-secondary)", fontSize: "11px", alignSelf: "center" }}>↔</span>
              <select
                className="tactical-input"
                style={{ flex: 1, fontSize: "11px" }}
                value={pairShipB}
                onChange={(e) => setPairShipB(e.target.value)}
              >
                <option value="">Ship B…</option>
                {(ships || []).filter((s) => s.ship_id !== pairShipA).map((s) => (
                  <option key={s.ship_id} value={s.ship_id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
              <button
                className="btn btn-approve"
                disabled={!pairShipA || !pairShipB || busy}
                onClick={handleAddPair}
              >
                Add Engagement
              </button>
              <button
                className="btn"
                style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                onClick={() => { setAddingPair(false); setPairShipA(""); setPairShipB(""); }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {activePairs.length === 0 ? (
          <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontStyle: "italic" }}>
            No engagements defined
          </div>
        ) : (
          activePairs.map((pair) => (
            <PairRow
              key={pair.pair_id}
              pair={pair}
              ships={ships}
              combat={combat}
              onUpdate={onUpdatePair}
              onRemove={handleRemovePair}
            />
          ))
        )}
      </div>

      {/* Start / End combat buttons */}
      {!isActive && !isEnded && (
        <button
          className="btn btn-approve"
          style={{ width: "100%" }}
          disabled={busy}
          onClick={handleStartCombat}
        >
          ▶ Start Combat
        </button>
      )}

      {isActive && (
        <button
          className="btn"
          style={{ width: "100%", borderColor: "var(--border)", color: "var(--text-secondary)" }}
          disabled={busy}
          onClick={onEndCombat}
        >
          ■ End Combat
        </button>
      )}

      {isEnded && (
        <div style={{ fontSize: "11px", color: "var(--text-secondary)", textAlign: "center", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Combat ended
        </div>
      )}
    </div>
  );
}
