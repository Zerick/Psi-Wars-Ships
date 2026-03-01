// components/DeclarationPanel.jsx
// Shown to each player for their own ship (or GM for all ships) during Declaration phase.
// Includes maneuver legality checking and submission.

import { useState, useMemo } from "react";

const MANEUVERS = [
  { key: "move_pursue",    label: "Move (Pursue)",   facing: "F",   hasChase: true,  canAttack: false },
  { key: "move_evade",     label: "Move (Evade)",    facing: "B",   hasChase: true,  canAttack: false },
  { key: "move_and_attack",label: "Move & Attack",   facing: "F",   hasChase: true,  canAttack: true  },
  { key: "attack",         label: "Attack (Static)", facing: "F",   hasChase: false, canAttack: true,  isStatic: true },
  { key: "evade",          label: "Evade",           facing: "B",   hasChase: true,  canAttack: false },
  { key: "stunt",          label: "Stunt",           facing: "any", hasChase: true,  canAttack: false },
  { key: "stunt_escape",   label: "Stunt Escape",    facing: "any", hasChase: true,  canAttack: false },
  { key: "stop",           label: "Stop (Static)",   facing: "any", hasChase: false, canAttack: false, isStatic: true },
  { key: "precision_aim",  label: "Precision Aim",   facing: "F",   hasChase: false, canAttack: false, isStatic: true },
  { key: "hide",           label: "Hide",            facing: "any", hasChase: false, canAttack: false },
  { key: "emergency_action", label: "Emergency Action", facing: "any", hasChase: false, canAttack: false },
];

function checkLegalityClient(maneuverKey, ship, pairWithThisShip) {
  // Client-side legality checks — mirrors combat_manager.py check_maneuver_legality
  if (!ship) return { legal: false, reason: "No ship data" };
  if (ship.is_destroyed === true) return { legal: false, reason: "Ship is destroyed" };
  if (ship.is_uncontrolled === true) return { legal: false, reason: "Ship is uncontrolled" };

  const systems = ship.systems || {};
  if (systems.controls === "destroyed") return { legal: false, reason: "Controls destroyed" };
  if (systems.propulsion === "destroyed" && ["move_pursue", "move_evade", "evade"].includes(maneuverKey)) {
    return { legal: false, reason: "Propulsion destroyed" };
  }

  const stall = ship.stall_speed > 0;
  const opponentHasAdv = pairWithThisShip && pairWithThisShip.advantage_ship_id && pairWithThisShip.advantage_ship_id !== ship.ship_id;

  if (maneuverKey === "move_pursue" && stall && opponentHasAdv) {
    return { legal: false, reason: "Cannot pursue: opponent has Advantage and you have stall speed" };
  }
  if (maneuverKey === "stunt" && stall && opponentHasAdv) {
    return { legal: false, reason: "Cannot stunt vs advantaged opponent with stall speed" };
  }
  if (maneuverKey === "attack" && stall) {
    return { legal: false, reason: "Stall-speed ships cannot use Attack maneuver" };
  }

  return { legal: true, reason: "" };
}

export default function DeclarationPanel({
  ship,
  combat,
  round,
  alreadySubmitted,
  onSubmit,
  isGm,
}) {
  const [selectedManeuver, setSelectedManeuver] = useState(null);
  const [pursuitTarget, setPursuitTarget] = useState("");
  const [afterburner, setAfterburner] = useState(false);
  const [activeConfig, setActiveConfig] = useState(ship?.active_config || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Find the pair that involves this ship (for legality checks)
  const myPair = useMemo(() => {
    if (!combat?.pairs || !ship) return null;
    return combat.pairs.find(
      (p) => p.active && (p.ship_a_id === ship.ship_id || p.ship_b_id === ship.ship_id)
    ) || null;
  }, [combat, ship]);

  // All enemy ships as pursuit targets
  const pairedShipIds = useMemo(() => {
    return (combat?.initiative_order || [])
      .map(i => i.ship_id)
      .filter(id => id !== ship?.ship_id);
  }, [combat, ship]);

  // All ships in initiative order for name lookup
  const shipMap = useMemo(() => {
    const m = {};
    (combat?.initiative_order || []).forEach((i) => { m[i.ship_id] = i; });
    return m;
  }, [combat]);

  const configModes = ship?.config_modes || [];

  const handleSubmit = async () => {
    if (!selectedManeuver) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        combat_id: combat?.combat_id,
        ship_id: ship.ship_id,
        round_number: round,
        maneuver: selectedManeuver,
        pursuit_target_id: pursuitTarget || null,
        afterburner_active: afterburner,
        active_config: activeConfig || null,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!ship) return null;

  if (alreadySubmitted) {
    return (
      <div style={{
        background: "var(--bg-deep)",
        border: "1px solid #4caf6a",
        padding: "8px 10px",
        marginBottom: "8px",
        fontSize: "11px",
        color: "#4caf6a",
        fontFamily: "Barlow Condensed, sans-serif",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
      }}>
        ✓ {ship.name} — declaration submitted. Waiting for others…
      </div>
    );
  }

  return (
    <div style={{
      background: "var(--bg-deep)",
      border: "1px solid var(--border)",
      padding: "10px",
      marginBottom: "8px",
    }}>
      <div style={{
        fontFamily: "Barlow Condensed, sans-serif",
        fontSize: "12px",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        color: "var(--text-primary)",
        marginBottom: "8px",
      }}>
        {ship.name}
        {ship.pilot?.name && (
          <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}> — {ship.pilot.name}</span>
        )}
      </div>

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>
      )}

      {/* Maneuver picker */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "8px" }}>
        {MANEUVERS.map((m) => {
          const { legal, reason } = checkLegalityClient(m.key, ship, myPair);
          const isSelected = selectedManeuver === m.key;
          return (
            <button
              key={m.key}
              title={!legal ? reason : m.facing !== "any" ? `Facing: ${m.facing}` : ""}
              disabled={!legal}
              onClick={() => legal && setSelectedManeuver(m.key)}
              style={{
                background: isSelected ? "var(--accent-red)" : "transparent",
                border: `1px solid ${isSelected ? "var(--accent-red)" : legal ? "var(--border)" : "#333"}`,
                color: isSelected ? "#fff" : legal ? "var(--text-secondary)" : "#444",
                padding: "3px 7px",
                cursor: legal ? "pointer" : "not-allowed",
                fontSize: "10px",
                fontFamily: "Barlow Condensed, sans-serif",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                opacity: legal ? 1 : 0.5,
              }}
            >
              {m.label}
              {m.isStatic && <span style={{ fontSize: "8px", marginLeft: "3px", opacity: 0.7 }}>*</span>}
            </button>
          );
        })}
      </div>
      <div style={{ fontSize: "9px", color: "var(--text-secondary)", marginBottom: "6px" }}>* static maneuver (no chase roll, grants opponent free range shift)</div>

      {/* Pursuit target (if pursuing) */}
      {selectedManeuver && ["move_pursue", "move_and_attack"].includes(selectedManeuver) && (
        <div style={{ marginBottom: "6px" }}>
          <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "3px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Pursuit Target</div>
          <select
            className="tactical-input"
            style={{ width: "100%", fontSize: "11px" }}
            value={pursuitTarget}
            onChange={(e) => setPursuitTarget(e.target.value)}
          >
            <option value="">— Select target —</option>
            {pairedShipIds.map((id) => (
              <option key={id} value={id}>{shipMap[id]?.ship_name || shipMap[id]?.name || id.slice(0, 8)}</option>
            ))}
          </select>
        </div>
      )}

      {/* Afterburner toggle */}
      {ship.afterburner_available === true && (
        <div style={{ marginBottom: "6px" }}>
          <button
            onClick={() => setAfterburner(!afterburner)}
            style={{
              background: afterburner ? "#d4a017" : "transparent",
              border: `1px solid ${afterburner ? "#d4a017" : "var(--border)"}`,
              color: afterburner ? "#000" : "var(--text-secondary)",
              padding: "3px 8px",
              cursor: "pointer",
              fontSize: "10px",
              fontFamily: "Barlow Condensed, sans-serif",
              letterSpacing: "0.04em",
            }}
          >
            🔥 Afterburner {afterburner ? "ON" : "OFF"}
          </button>
        </div>
      )}

      {/* Config mode selector */}
      {configModes.length > 0 && (
        <div style={{ marginBottom: "6px" }}>
          <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "3px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Config Mode</div>
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
            {configModes.map((mode) => (
              <button
                key={mode}
                onClick={() => setActiveConfig(mode)}
                style={{
                  background: activeConfig === mode ? "var(--accent-blue)" : "transparent",
                  border: `1px solid ${activeConfig === mode ? "var(--accent-blue)" : "var(--border)"}`,
                  color: activeConfig === mode ? "#fff" : "var(--text-secondary)",
                  padding: "3px 7px",
                  cursor: "pointer",
                  fontSize: "10px",
                  fontFamily: "Barlow Condensed, sans-serif",
                }}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      )}

      <button
        className="btn btn-approve"
        disabled={!selectedManeuver || busy}
        onClick={handleSubmit}
        style={{ width: "100%" }}
      >
        Submit Declaration
      </button>
    </div>
  );
}
