// components/CombatActionPanels.jsx
// AttackPanel, DefensePanel, DamagePanel — combat action phase UI.
// Exported individually for use in GMPanel.

import { useState, useMemo } from "react";

const RANGE_LABELS = {
  close: "Close (0)", short: "Short (-3)", medium: "Medium (-7)",
  long: "Long (-11)", extreme: "Extreme (-15)", distant: "Distant (-19)",
  beyond_visual: "Beyond Visual (-23)",
};

// ============================================================
// AttackPanel
// ============================================================
export function AttackPanel({ combat, actingShip, ships, isGm, onSubmitAttack, onMarkActed }) {
  const [targetId, setTargetId] = useState("");
  const [weaponId, setWeaponId] = useState("");
  const [calledShot, setCalledShot] = useState(false);
  const [calledShotSystem, setCalledShotSystem] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const shipMap = useMemo(() => {
    const m = {};
    (ships || []).forEach((s) => { m[s.ship_id] = s; });
    return m;
  }, [ships]);

  // Paired ships for target selection
  const pairedShipIds = useMemo(() => {
    if (!combat?.pairs || !actingShip) return [];
    return combat.pairs
      .filter((p) => p.active && (p.ship_a_id === actingShip.ship_id || p.ship_b_id === actingShip.ship_id))
      .map((p) => p.ship_a_id === actingShip.ship_id ? p.ship_b_id : p.ship_a_id);
  }, [combat, actingShip]);

  // Weapons with valid facing
  const eligibleWeapons = useMemo(() => {
    if (!actingShip?.weapons) return [];
    return actingShip.weapons.filter((w) => !w.is_disabled);
  }, [actingShip]);

  // Find pair for range/advantage lookup
  const activePair = useMemo(() => {
    if (!targetId || !actingShip || !combat?.pairs) return null;
    return combat.pairs.find(
      (p) => p.active && (
        (p.ship_a_id === actingShip.ship_id && p.ship_b_id === targetId) ||
        (p.ship_b_id === actingShip.ship_id && p.ship_a_id === targetId)
      )
    ) || null;
  }, [targetId, actingShip, combat]);

  const selectedWeapon = eligibleWeapons.find((w) => w.weapon_id === weaponId);
  const decl = (combat?.declarations || []).find((d) => d.ship_id === actingShip?.ship_id);

  // Compute modifier preview
  const modPreview = useMemo(() => {
    if (!selectedWeapon || !activePair || !actingShip) return null;
    const pilot = actingShip.pilot || {};
    const target = shipMap[targetId];
    const rangePenalties = { close: 0, short: -3, medium: -7, long: -11, extreme: -15, distant: -19, beyond_visual: -23 };
    const rangePen = rangePenalties[activePair.range_band] || -7;
    const matched = activePair.matched_speed === true;
    const maneuver = decl?.maneuver || "";
    const accuracy = (maneuver === "attack" || matched) ? (selectedWeapon.accuracy || 0) : 0;
    const sensorLock = (actingShip.sensor_lock_active === true) ? (actingShip.has_targeting_computer ? 5 : 3) : 0;

    const attackerClass = actingShip.ship_class || "fighter";
    const targetClass = target?.ship_class || "fighter";
    const moveA = actingShip.move_space || 0;
    const moveB = target?.move_space || 0;
    const speedPenA = attackerClass === "fighter" ? -Math.floor(moveA / 25) : (attackerClass === "corvette" ? -Math.floor(moveA / 50) : 0);
    const speedPenB = targetClass === "fighter" ? -Math.floor(moveB / 25) : (targetClass === "corvette" ? -Math.floor(moveB / 50) : 0);
    const speedPen = Math.min(speedPenA, speedPenB);

    let sizePen = 0;
    const isLight = selectedWeapon.is_light_turret === true;
    if (attackerClass === "corvette" && targetClass === "fighter") sizePen = isLight ? -3 : -5;
    else if (attackerClass === "capital" && targetClass === "corvette") sizePen = isLight ? -3 : -5;
    else if (attackerClass === "capital" && targetClass === "fighter") sizePen = isLight ? -5 : -10;

    const calledPen = calledShot ? -5 : 0;
    const gunner = pilot.gunner_skill || 10;
    const total = gunner + accuracy + sensorLock + rangePen + speedPen + sizePen + calledPen;

    return { gunner, accuracy, sensorLock, rangePen, speedPen, sizePen, calledPen, total };
  }, [selectedWeapon, activePair, actingShip, targetId, shipMap, decl, calledShot]);

  const handleSubmit = async () => {
    if (!targetId || !weaponId) return;
    setBusy(true);
    setError(null);
    try {
      const action = await onSubmitAttack({
        acting_ship_id: actingShip.ship_id,
        target_ship_id: targetId,
        weapon_id: weaponId,
        called_shot_system: calledShot ? calledShotSystem : null,
      });
      setResult(action);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!actingShip) return null;

  const systems = actingShip.systems || {};
  const weaponryDestroyed = systems.weaponry === "destroyed";

  return (
    <div style={{ background: "var(--bg-deep)", border: "1px solid var(--accent-red)", padding: "10px", marginBottom: "8px" }}>
      <div style={{ fontFamily: "Barlow Condensed, sans-serif", fontSize: "12px", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--accent-red)", marginBottom: "8px" }}>
        Attack — {actingShip.name}
      </div>

      {weaponryDestroyed && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>
          ⚠ Weaponry system is destroyed — cannot attack
        </div>
      )}

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>
      )}

      {!result && !weaponryDestroyed && (
        <>
          {/* Target */}
          <div style={{ marginBottom: "6px" }}>
            <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "3px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Target</div>
            <select
              className="tactical-input"
              style={{ width: "100%", fontSize: "11px" }}
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
            >
              <option value="">— Select target —</option>
              {pairedShipIds.map((id) => (
                <option key={id} value={id}>{shipMap[id]?.name || id}</option>
              ))}
            </select>
          </div>

          {/* Weapon */}
          <div style={{ marginBottom: "6px" }}>
            <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "3px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>Weapon</div>
            <select
              className="tactical-input"
              style={{ width: "100%", fontSize: "11px" }}
              value={weaponId}
              onChange={(e) => setWeaponId(e.target.value)}
            >
              <option value="">— Select weapon —</option>
              {eligibleWeapons.map((w) => (
                <option key={w.weapon_id} value={w.weapon_id}>
                  {w.name} ({w.damage_dice}d×{w.damage_mult} {w.damage_type}) [{w.facings?.join(",") || "?"}]
                </option>
              ))}
            </select>
          </div>

          {/* Called shot */}
          <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              onClick={() => setCalledShot(!calledShot)}
              style={{
                background: calledShot ? "#4a9ede" : "transparent",
                border: `1px solid ${calledShot ? "#4a9ede" : "var(--border)"}`,
                color: calledShot ? "#fff" : "var(--text-secondary)",
                padding: "3px 8px",
                cursor: "pointer",
                fontSize: "10px",
                fontFamily: "Barlow Condensed, sans-serif",
              }}
            >
              Called Shot (-5)
            </button>
            {calledShot && (
              <input
                className="tactical-input"
                style={{ flex: 1, fontSize: "11px" }}
                placeholder="Target system…"
                value={calledShotSystem}
                onChange={(e) => setCalledShotSystem(e.target.value)}
              />
            )}
          </div>

          {/* Modifier breakdown */}
          {modPreview && (
            <div style={{ background: "#0a0f15", border: "1px solid var(--border)", padding: "8px", marginBottom: "8px", fontSize: "11px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "2px 8px", color: "var(--text-secondary)" }}>
                <span>Gunner skill:</span><span className="font-mono">{modPreview.gunner}</span>
                <span>+ Accuracy:</span><span className="font-mono">{modPreview.accuracy >= 0 ? "+" : ""}{modPreview.accuracy}</span>
                <span>+ Sensor lock:</span><span className="font-mono">{modPreview.sensorLock >= 0 ? "+" : ""}{modPreview.sensorLock}</span>
                <span>+ Range:</span><span className="font-mono">{modPreview.rangePen}</span>
                <span>+ Speed:</span><span className="font-mono">{modPreview.speedPen}</span>
                <span>+ Size:</span><span className="font-mono">{modPreview.sizePen}</span>
                {calledShot && <><span>+ Called shot:</span><span className="font-mono">-5</span></>}
                <span style={{ borderTop: "1px solid var(--border)", paddingTop: "2px", color: "var(--text-primary)", fontWeight: 600 }}>= Roll target:</span>
                <span className="font-mono" style={{ borderTop: "1px solid var(--border)", paddingTop: "2px", color: "var(--accent-blue)", fontWeight: 700, fontSize: "14px" }}>{modPreview.total}</span>
              </div>
              <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginTop: "4px" }}>Roll 3d6 under {modPreview.total} to hit</div>
            </div>
          )}

          <button
            className="btn btn-approve"
            style={{ width: "100%" }}
            disabled={!targetId || !weaponId || busy}
            onClick={handleSubmit}
          >
            Roll Attack
          </button>
        </>
      )}

      {result && (
        <div>
          <div style={{ fontSize: "12px", marginBottom: "4px" }}>
            Roll: <span className="font-mono" style={{ color: "var(--text-mono)", fontSize: "18px" }}>{result.attack_roll ?? "—"}</span>
            {" "}vs <span className="font-mono">{result.attack_total}</span>
          </div>
          {result.attack_roll != null && (
            <div style={{
              fontSize: "14px",
              fontWeight: 700,
              color: result.attack_hit ? "var(--accent-red)" : "#4caf6a",
              fontFamily: "Barlow Condensed, sans-serif",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}>
              {result.attack_hit ? "HIT" : "MISS"}
            </div>
          )}
          {result.attack_roll == null && (
            <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
              Awaiting GM review — action ID: {result.action_id.slice(0, 8)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ============================================================
// DefensePanel
// ============================================================
export function DefensePanel({ action, targetShip, isGm, onSubmitDefense }) {
  const [dodgeRoll, setDodgeRoll] = useState("");
  const [highG, setHighG] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!action || !targetShip) return null;
  if (action.dodge_roll != null) return null; // already resolved

  const pilot = targetShip.pilot || {};
  const baseDoc = pilot.dodge || 8;
  const eligible = (targetShip.move_space || 0) >= 400;

  const handleSubmit = async () => {
    if (!dodgeRoll) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmitDefense(action.action_id, { dodge_roll: parseInt(dodgeRoll), high_g: highG });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ background: "var(--bg-deep)", border: "1px solid #4a9ede", padding: "10px", marginBottom: "8px" }}>
      <div style={{ fontFamily: "Barlow Condensed, sans-serif", fontSize: "12px", letterSpacing: "0.08em", textTransform: "uppercase", color: "#4a9ede", marginBottom: "8px" }}>
        Defense — {targetShip.name}
      </div>

      <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "6px" }}>
        Base dodge: <span className="font-mono" style={{ color: "var(--text-mono)" }}>{baseDoc}</span>
        {eligible && <span style={{ marginLeft: "8px" }}>High-G available (+1, HT roll)</span>}
      </div>

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>
      )}

      {eligible && (
        <button
          onClick={() => setHighG(!highG)}
          style={{
            background: highG ? "#4a9ede" : "transparent",
            border: `1px solid ${highG ? "#4a9ede" : "var(--border)"}`,
            color: highG ? "#fff" : "var(--text-secondary)",
            padding: "3px 8px",
            cursor: "pointer",
            fontSize: "10px",
            fontFamily: "Barlow Condensed, sans-serif",
            marginBottom: "6px",
            display: "block",
          }}
        >
          High-G Dodge {highG ? "ON (+1)" : "OFF"}
        </button>
      )}

      <div style={{ display: "flex", gap: "8px", alignItems: "flex-end" }}>
        <div>
          <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "3px" }}>Dodge roll (3d6)</div>
          <input
            className="tactical-input font-mono"
            style={{ width: "70px", padding: "6px 8px", fontSize: "18px" }}
            type="number" min={3} max={18}
            value={dodgeRoll}
            onChange={(e) => setDodgeRoll(e.target.value)}
            placeholder="—"
          />
        </div>
        <button
          className="btn btn-approve"
          disabled={!dodgeRoll || busy}
          onClick={handleSubmit}
        >
          Roll Dodge
        </button>
      </div>
    </div>
  );
}


// ============================================================
// DamagePanel
// ============================================================
export function DamagePanel({ action, actingShip, targetShip, ships, isGm, onSubmitDamage, onApplyDamage }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [damageResult, setDamageResult] = useState(
    action?.damage_net != null ? action : null
  );

  if (!action) return null;
  if (!action.attack_hit) return null;
  if (action.dodge_success === true) return null;

  const handleRollDamage = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await onSubmitDamage(action.action_id);
      setDamageResult(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleApplyDamage = () => {
    if (!damageResult) return;
    onApplyDamage(damageResult);
  };

  const WOUND_COLORS = {
    scratch: "var(--text-secondary)",
    minor: "#d4a017",
    major: "#e88a0a",
    crippling: "var(--accent-red)",
    mortal: "#cc0000",
    lethal: "#ff0000",
  };

  const weapon = actingShip?.weapons?.find((w) => w.weapon_id === action.weapon_id);

  return (
    <div style={{ background: "var(--bg-deep)", border: "1px solid var(--accent-red)", padding: "10px", marginBottom: "8px" }}>
      <div style={{ fontFamily: "Barlow Condensed, sans-serif", fontSize: "12px", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--accent-red)", marginBottom: "8px" }}>
        Damage — {targetShip?.name || "Target"}
      </div>

      {weapon && (
        <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "6px" }}>
          {weapon.name} — {weapon.damage_dice}d×{weapon.damage_mult} {weapon.damage_type}
          {weapon.armor_divisor > 1 && ` (AD ÷${weapon.armor_divisor})`}
        </div>
      )}

      {error && (
        <div style={{ color: "var(--accent-red)", fontSize: "11px", marginBottom: "6px" }}>{error}</div>
      )}

      {!damageResult && (
        <button
          className="btn btn-approve"
          style={{ width: "100%" }}
          disabled={busy}
          onClick={handleRollDamage}
        >
          Roll Damage
        </button>
      )}

      {damageResult && (
        <div>
          {/* Dice */}
          <div style={{ display: "flex", alignItems: "center", gap: "4px", marginBottom: "8px", flexWrap: "wrap" }}>
            {(damageResult.damage_roll || []).map((v, i) => (
              <span key={i} className="font-mono" style={{
                display: "inline-block",
                minWidth: "24px",
                textAlign: "center",
                padding: "3px 4px",
                background: "#0a0f15",
                border: "1px solid var(--border)",
                color: "var(--text-mono)",
                fontSize: "13px",
              }}>{v}</span>
            ))}
            {(damageResult.damage_mult || 1) > 1 && (
              <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>× {damageResult.damage_mult}</span>
            )}
            <span style={{ color: "var(--text-secondary)" }}>= </span>
            <span className="font-mono" style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-mono)" }}>{damageResult.damage_raw}</span>
          </div>

          {/* Absorption breakdown */}
          <div style={{ fontSize: "11px", marginBottom: "8px" }}>
            {(damageResult.damage_screen_absorbed || 0) > 0 && (
              <div style={{ color: "var(--text-secondary)" }}>
                Force screen absorbed: <span className="font-mono" style={{ color: "#4a9ede" }}>-{damageResult.damage_screen_absorbed}</span>
              </div>
            )}
            {(damageResult.damage_hull_absorbed || 0) > 0 && (
              <div style={{ color: "var(--text-secondary)" }}>
                Hull DR absorbed: <span className="font-mono">-{damageResult.damage_hull_absorbed}</span>
              </div>
            )}
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "4px", marginTop: "4px" }}>
              Net damage: <span className="font-mono" style={{ color: "var(--accent-red)", fontWeight: 700, fontSize: "16px" }}>{damageResult.damage_net}</span>
            </div>
          </div>

          {/* Wound level */}
          {damageResult.wound_level_after && damageResult.wound_level_after !== "scratch" && (
            <div style={{ marginBottom: "8px" }}>
              <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Wound: </span>
              <span style={{
                fontSize: "13px",
                fontWeight: 700,
                fontFamily: "Barlow Condensed, sans-serif",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: WOUND_COLORS[damageResult.wound_level_after] || "var(--text-primary)",
              }}>
                {damageResult.wound_level_after}
              </span>
              {damageResult.wound_level_before !== "none" && damageResult.wound_level_before !== damageResult.wound_level_after && (
                <span style={{ fontSize: "10px", color: "var(--text-secondary)", marginLeft: "6px" }}>
                  (was {damageResult.wound_level_before})
                </span>
              )}
            </div>
          )}

          {/* System damage */}
          {damageResult.system_damaged && (
            <div style={{ marginBottom: "8px", background: "#0a0f15", border: "1px solid var(--accent-red)", padding: "6px" }}>
              <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "2px", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                System roll: {damageResult.system_damage_roll}
              </div>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--accent-red)", fontFamily: "Barlow Condensed, sans-serif", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                {["crippling", "mortal", "lethal"].includes(damageResult.wound_level_after) ? "DESTROY" : "DISABLE"}: {damageResult.system_damaged}
              </div>
            </div>
          )}

          {/* HT roll */}
          {damageResult.ht_roll_result != null && (
            <div style={{ marginBottom: "8px", fontSize: "11px", color: "var(--text-secondary)" }}>
              HT roll: <span className="font-mono" style={{ color: "var(--text-mono)" }}>{damageResult.ht_roll_result}</span>
              {" "}vs {targetShip?.ht || 10}
              {" — "}
              <span style={{ color: damageResult.ht_roll_result <= (targetShip?.ht || 10) ? "#4caf6a" : "var(--accent-red)", fontWeight: 700 }}>
                {damageResult.ht_roll_result <= (targetShip?.ht || 10) ? "SURVIVES" : "DESTROYED"}
              </span>
            </div>
          )}

          {/* Apply button */}
          {isGm && (
            <button
              className="btn btn-approve"
              style={{ width: "100%" }}
              onClick={handleApplyDamage}
            >
              Apply to Ship (patch HP / systems)
            </button>
          )}
        </div>
      )}
    </div>
  );
}
