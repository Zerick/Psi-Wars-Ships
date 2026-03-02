// =============================================================================
// GMPanel.jsx — GM-only control panel
// Chase/attack/dodge/damage now handled via combat log cards.
// This panel handles: scenario setup, combat start/end, player declarations,
// pending roll review.
// =============================================================================
import { useState } from 'react'
import ScenarioSetupPanel from '../views/ScenarioSetupPanel'
import CombatSetupPanel from './CombatSetupPanel'
import DeclarationPanel from './DeclarationPanel'

// ---------------------------------------------------------------------------
// Pending roll review
// ---------------------------------------------------------------------------
function PendingRoll({ roll, sessionId, token, onResolved }) {
  const [overriding, setOverriding] = useState(false)
  const [overrideVal, setOverrideVal] = useState('')
  const [busy, setBusy] = useState(false)

  const act = async (action, body = {}) => {
    setBusy(true)
    try {
      await fetch(`/sessions/${sessionId}/rolls/${roll.pending_id}/${action}?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: Object.keys(body).length ? JSON.stringify(body) : undefined,
      })
      onResolved(roll.pending_id)
    } catch (e) { /* silent */ }
    finally { setBusy(false) }
  }

  const dice = Array.isArray(roll.dice_results) ? roll.dice_results : []

  return (
    <div style={{
      background: 'var(--bg-deep)', border: '1px solid var(--border)',
      borderLeft: '3px solid var(--accent-red)', padding: '12px', marginBottom: '8px',
    }}>
      <div style={{ marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
          {roll.rolled_by}
        </span>
        <span className="font-mono" style={{ color: 'var(--text-mono)', fontSize: '12px' }}>
          [[{roll.expression}]]
        </span>
        {roll.label && (
          <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontStyle: 'italic' }}>{roll.label}</span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px', flexWrap: 'wrap' }}>
        {dice.map((v, i) => (
          <span key={i} className="font-mono" style={{
            display: 'inline-block', minWidth: '26px', textAlign: 'center',
            padding: '3px 5px', background: '#0a0f15', border: '1px solid var(--border)',
            color: 'var(--text-mono)', fontSize: '13px',
          }}>{v}</span>
        ))}
        <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>→</span>
        <span className="font-mono" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--accent-blue)', lineHeight: 1 }}>
          {roll.total}
        </span>
      </div>

      {overriding && (
        <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
          <input
            className="tactical-input font-mono"
            style={{ width: '80px', padding: '6px 10px', fontSize: '16px' }}
            type="number" value={overrideVal}
            onChange={e => setOverrideVal(e.target.value)}
            placeholder="val" autoFocus
            onKeyDown={e => {
              if (e.key === 'Enter') act('override', { value: parseInt(overrideVal, 10) })
              if (e.key === 'Escape') { setOverriding(false); setOverrideVal('') }
            }}
          />
          <button className="btn btn-override" disabled={!overrideVal || busy}
            onClick={() => act('override', { value: parseInt(overrideVal, 10) })}>Confirm</button>
          <button className="btn" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
            onClick={() => { setOverriding(false); setOverrideVal('') }}>Cancel</button>
        </div>
      )}

      {!overriding && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button className="btn btn-approve" disabled={busy} onClick={() => act('approve')}>✓ Approve</button>
          <button className="btn btn-override" disabled={busy} onClick={() => setOverriding(true)}>✎ Override</button>
          <button className="btn btn-reroll" disabled={busy} onClick={() => act('reroll')}>↺ Re-roll</button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main GMPanel
// ---------------------------------------------------------------------------
export default function GMPanel({
  pendingRolls, sessionId, token, onRollResolved,
  scenario, participants, onCreateScenario, onAddShip, onRemoveShip,
  combat, onStartCombat, onEndCombat, onPatchShip, onUpdateRange,
  onSubmitDeclaration,
}) {
  return (
    <div style={{
      width: '280px', minWidth: '240px', maxWidth: '320px',
      display: 'flex', flexDirection: 'column',
      background: 'var(--bg-panel)', borderLeft: '1px solid var(--border)', flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 14px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span className="section-label" style={{ color: 'var(--accent-red)' }}>GM Control</span>
        {pendingRolls.length > 0 && (
          <span style={{
            background: 'var(--accent-red)', color: '#fff', borderRadius: '50%',
            width: '18px', height: '18px', display: 'inline-flex', alignItems: 'center',
            justifyContent: 'center', fontSize: '10px', fontWeight: 700,
          }}>{pendingRolls.length}</span>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>

        {/* Scenario setup */}
        <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '10px' }}>
          <ScenarioSetupPanel
            scenario={scenario} participants={participants}
            token={token} sessionId={sessionId}
            onCreateScenario={onCreateScenario} onAddShip={onAddShip} onRemoveShip={onRemoveShip}
          />
        </div>

        {/* Combat setup */}
        {scenario && (
          <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '10px' }}>
            <CombatSetupPanel
              combat={combat} ships={scenario.ships || []}
              sessionId={sessionId} token={token}
              onStartCombat={onStartCombat} onEndCombat={onEndCombat}
            />
          </div>
        )}

        {/* Declaration phase — player ships only (NPCs auto-declare) */}
        {combat && combat.status === 'active' && combat.current_phase === 'declaration' && (
          <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '10px' }}>
            <div style={{
              fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px',
              letterSpacing: '0.08em', textTransform: 'uppercase', color: '#d4a017', marginBottom: '8px',
            }}>
              Declaration — Round {combat.current_round}
            </div>
            {(scenario?.ships || [])
              .filter(ship => !ship.faction || ship.faction === 'player')
              .map(ship => {
                const alreadySubmitted = (combat.declarations || []).some(
                  d => d.ship_id === ship.ship_id && d.submitted
                )
                return (
                  <DeclarationPanel
                    key={ship.ship_id}
                    ship={ship} combat={combat}
                    round={combat.current_round}
                    alreadySubmitted={alreadySubmitted}
                    onSubmit={onSubmitDeclaration}
                    isGm={true}
                  />
                )
              })}
          </div>
        )}

        {/* Chase phase — log-driven, nothing to show here */}
        {combat && combat.status === 'active' && combat.current_phase === 'chase' && (
          <div style={{ padding: '8px 0', marginBottom: '10px' }}>
            <div style={{
              fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px',
              letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent-blue)',
            }}>
              Chase Phase — see combat log
            </div>
          </div>
        )}

        {/* Action phase — log-driven, nothing to show here */}
        {combat && combat.status === 'active' && combat.current_phase === 'action' && (
          <div style={{ padding: '8px 0', marginBottom: '10px' }}>
            <div style={{
              fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px',
              letterSpacing: '0.08em', textTransform: 'uppercase', color: '#d4a017',
            }}>
              Action Phase — see combat log
            </div>
          </div>
        )}

        {/* Pending rolls */}
        {pendingRolls.length === 0 ? (
          <div style={{
            textAlign: 'center', color: 'var(--text-secondary)', padding: '30px 10px',
            fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif',
            letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>No pending rolls</div>
        ) : (
          [...pendingRolls].reverse().map(roll => (
            <PendingRoll key={roll.pending_id} roll={roll}
              sessionId={sessionId} token={token} onResolved={onRollResolved} />
          ))
        )}
      </div>
    </div>
  )
}
