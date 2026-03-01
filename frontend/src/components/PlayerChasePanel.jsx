// PlayerChasePanel.jsx
// Player sees their chase bonus, rolls physical 3d6, enters the result.

import { useState, useMemo } from "react";

export default function PlayerChasePanel({ ship, combat, token, onResolvePair }) {
  const [roll, setRoll] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const myPairs = useMemo(() => {
    if (!combat?.pairs) return [];
    return combat.pairs.filter(
      p => p.active && (p.ship_a_id === ship.ship_id || p.ship_b_id === ship.ship_id)
    );
  }, [combat, ship]);

  // Chase bonus: handling + sr + speed bonus
  const chaseBonus = useMemo(() => {
    let bonus = (ship.handling || 0) + (ship.sr || 0);
    const move = ship.move_space || 0;
    if (ship.ship_class === "fighter") bonus += Math.min(Math.floor(move / 25), 20);
    else if (ship.ship_class === "corvette") bonus += Math.min(Math.floor(move / 50), 15);
    return bonus;
  }, [ship]);

  const handleSubmit = async () => {
    if (!roll || myPairs.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      for (const pair of myPairs) {
        await fetch(`/combats/${combat.combat_id}/pairs/${pair.pair_id}/player-roll?token=${token}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ship_id: ship.ship_id, roll: parseInt(roll) }),
        });
      }
      setSubmitted(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (myPairs.length === 0) return null;

  if (submitted) {
    return (
      <div style={{
        background: "var(--bg-panel)", borderBottom: "1px solid var(--border)",
        padding: "12px 16px",
      }}>
        <span style={{ color: "#4caf6a", fontFamily: "Barlow Condensed, sans-serif", fontSize: "12px", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          ✓ {ship.name} — roll submitted. Waiting for opponent…
        </span>
      </div>
    );
  }

  return (
    <div style={{
      background: "var(--bg-panel)", borderBottom: "1px solid var(--border)",
      padding: "14px 16px", flexShrink: 0,
    }}>
      <div style={{ fontFamily: "Barlow Condensed, sans-serif", fontSize: "13px", letterSpacing: "0.08em", textTransform: "uppercase", color: "#4a9ede", marginBottom: "10px" }}>
        Chase Roll — {ship.name}
      </div>

      <div style={{ background: "var(--bg-deep)", border: "1px solid var(--border)", padding: "10px 14px", marginBottom: "12px", display: "inline-block" }}>
        <div style={{ fontSize: "10px", color: "var(--text-secondary)", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "4px" }}>
          Your chase bonus
        </div>
        <div className="font-mono" style={{ fontSize: "28px", fontWeight: 700, color: "var(--accent-blue)", lineHeight: 1 }}>
          {chaseBonus}
        </div>
      </div>

      <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "10px" }}>
        Roll 3d6 physically. Your MOS = <span className="font-mono">{chaseBonus}</span> − your roll.
      </div>

      {error && <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>}

      <div style={{ display: "flex", gap: "10px", alignItems: "flex-end" }}>
        <div>
          <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "4px" }}>Enter your 3d6 result</div>
          <input
            className="tactical-input font-mono"
            style={{ width: "90px", padding: "8px 12px", fontSize: "26px", textAlign: "center" }}
            type="number" min={3} max={18}
            value={roll}
            onChange={e => setRoll(e.target.value)}
            placeholder="—"
            autoFocus
          />
        </div>
        <button
          className="btn btn-approve"
          style={{ padding: "8px 20px", fontSize: "13px" }}
          disabled={!roll || busy}
          onClick={handleSubmit}
        >
          Submit
        </button>
      </div>
    </div>
  );
}
