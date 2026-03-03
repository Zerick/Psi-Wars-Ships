// =============================================================================
// SessionView.jsx — Main session UI
// =============================================================================
import { useState, useEffect, useCallback, useRef } from 'react'
import { useWebSocket }      from '../hooks/useWebSocket'
import LogFeed               from '../components/LogFeed'
import RollInput             from '../components/RollInput'
import GMPanel               from '../components/GMPanel'
import ShipsZone             from '../components/ShipsZone'
import InitiativeTracker     from '../components/InitiativeTracker'
import DeclarationPanel      from '../components/DeclarationPanel'
import { useScenario }       from '../hooks/useScenario'
import { useCombat }         from '../hooks/useCombat'

const STATUS_COLORS = {
  connected:    '#4caf6a',
  reconnecting: '#d4a017',
  disconnected: '#e8410a',
}

function tryParseJson(val) {
  if (Array.isArray(val)) return val
  try { return JSON.parse(val) } catch { return [] }
}

export default function SessionView({ session, onLeave }) {
  const { sessionId, token, role, displayName, inviteCode, userId } = session

  const [logEntries,   setLogEntries]   = useState([])
  const [participants, setParticipants] = useState([])
  const [pendingRolls, setPendingRolls] = useState([])
  const [codeCopied,   setCodeCopied]   = useState(false)
  const [gmPanelOpen,  setGmPanelOpen]  = useState(true)
  const [wsLastMessage, setWsLastMessage] = useState(null)

  // -------------------------------------------------------------------------
  // Load initial state
  // -------------------------------------------------------------------------
  useEffect(() => {
    const init = async () => {
      try {
        const [logRes, partRes] = await Promise.all([
          fetch(`/sessions/${sessionId}/log?token=${token}`),
          fetch(`/sessions/${sessionId}/participants?token=${token}`),
        ])
        if (logRes.ok)  setLogEntries(await logRes.json())
        if (partRes.ok) setParticipants(await partRes.json())
      } catch(e) { /* non-fatal */ }

      if (role === 'gm') {
        try {
          const res = await fetch(`/sessions/${sessionId}/pending-rolls?token=${token}`)
          if (res.ok) {
            const rows = await res.json()
            setPendingRolls(rows.map(r => ({
              pending_id:   r.pending_id,
              rolled_by:    r.author_name,
              expression:   r.expression,
              dice_results: tryParseJson(r.dice_results),
              total:        r.total,
              label:        r.content || '',
            })))
          }
        } catch(e) { /* non-fatal */ }
      }
    }
    init()
  }, [sessionId, token, role])

  // -------------------------------------------------------------------------
  // Combat log card injection
  // -------------------------------------------------------------------------
  const injectCombatLog = useCallback((entry) => {
    setLogEntries(prev => {
      // Handle chase roll update sentinel — find card by ship_id and mark rolled
      if (entry.entry_type === '__chase_roll_update__') {
        return prev.map(e => {
          if (e.entry_type === 'combat_chase' &&
              e.data?.ship_id === entry.ship_id &&
              e.data?.combat_id === entry.combat_id) {
            const mos = entry.bonus != null && entry.roll != null
              ? entry.bonus - entry.roll
              : null
            return {
              ...e,
              data: {
                ...e.data,
                rolled: true,
                roll:   entry.roll,
                mos,
              }
            }
          }
          return e
        })
      }

      // Normal card: replace by combat_card_id if exists
      if (entry.data?.combat_card_id) {
        const idx = prev.findIndex(e => e.data?.combat_card_id === entry.data.combat_card_id)
        if (idx >= 0) {
          const updated = [...prev]
          updated[idx] = entry
          return updated
        }
      }

      return [...prev, entry]
    })
  }, [])

  // -------------------------------------------------------------------------
  // WebSocket message handler
  // -------------------------------------------------------------------------
  const handleWsMessage = useCallback((msg) => {
    setWsLastMessage(msg)
    switch (msg.type) {
      case 'log_entry':
        setLogEntries(prev => {
          if (prev.some(e => e.entry_id === msg.data.entry_id)) return prev
          return [...prev, msg.data]
        })
        break
      case 'pending_roll':
        if (role === 'gm') {
          setPendingRolls(prev => {
            const exists = prev.findIndex(r => r.pending_id === msg.data.pending_id)
            const shaped = {
              pending_id:   msg.data.pending_id,
              rolled_by:    msg.data.rolled_by,
              expression:   msg.data.expression,
              dice_results: msg.data.dice_results,
              total:        msg.data.total,
              label:        msg.data.label || '',
            }
            if (exists >= 0) {
              const updated = [...prev]
              updated[exists] = shaped
              return updated
            }
            return [...prev, shaped]
          })
        }
        break
      case 'participant_joined':
        setParticipants(prev => {
          if (prev.some(p => p.user_id === msg.data.user_id)) return prev
          return [...prev, msg.data]
        })
        break
      default:
        break
    }
  }, [role])

  const wsStatus = useWebSocket(sessionId, token, handleWsMessage)

  const {
    scenario,
    createScenario,
    addShip,
    patchShip,
    patchPilot,
    patchSystem,
    assignShip,
    removeShip,
  } = useScenario({ sessionId, token, isGm: role === 'gm', wsLastMessage })

  const {
    combat,
    startCombat,
    submitDeclaration,
    rollChase,
    submitAttack,
    submitDefense,
    submitDamage,
    updateRange,
    endCombat,
  } = useCombat({
    sessionId,
    token,
    scenarioId: scenario?.scenario_id,
    isGm: role === 'gm',
    wsLastMessage,
    onInjectLog: injectCombatLog,
  })

  // -------------------------------------------------------------------------
  // Chase roll handler
  // GM can roll for any ship (NPC or player-owned).
  // Players can roll for their own ship.
  // -------------------------------------------------------------------------
  const handleChaseRoll = useCallback(async (combat_id, ship_id) => {
    try {
      await rollChase(combat_id, ship_id)
    } catch(e) {
      console.error('Chase roll failed:', e)
    }
  }, [rollChase])

  // -------------------------------------------------------------------------
  // Dodge roll handler
  // -------------------------------------------------------------------------
  const handleDodgeRoll = useCallback(async (combat_id, ship_id, action_id) => {
    try {
      const roll = Math.ceil(Math.random()*6) + Math.ceil(Math.random()*6) + Math.ceil(Math.random()*6)
      await submitDefense(combat_id, action_id, roll)
    } catch(e) {
      console.error('Dodge roll failed:', e)
    }
  }, [submitDefense])

  const handleRollResolved = useCallback((pendingId) => {
    setPendingRolls(prev => prev.filter(r => r.pending_id !== pendingId))
  }, [])

  const copyCode = () => {
    navigator.clipboard.writeText(inviteCode).then(() => {
      setCodeCopied(true)
      setTimeout(() => setCodeCopied(false), 2000)
    })
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ── Header ── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', height: '48px',
        background: 'var(--bg-panel)', borderBottom: '1px solid var(--border)',
        flexShrink: 0, gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700,
            fontSize: '16px', letterSpacing: '0.1em', textTransform: 'uppercase',
            color: 'var(--text-primary)',
          }}>Psi-Wars</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div className={wsStatus === 'connected' ? 'pulse' : ''} style={{
              width: '7px', height: '7px', borderRadius: '50%',
              background: STATUS_COLORS[wsStatus] || STATUS_COLORS.disconnected,
            }} />
            <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.05em' }}>
              {wsStatus}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="section-label">Code:</span>
          <button onClick={copyCode} title="Click to copy" className="font-mono" style={{
            background: 'transparent', border: '1px solid var(--border)',
            color: codeCopied ? 'var(--accent-blue)' : 'var(--text-mono)',
            padding: '3px 10px', cursor: 'pointer', fontSize: '14px',
            letterSpacing: '0.1em', transition: 'color 0.15s',
          }}>{codeCopied ? 'Copied!' : inviteCode}</button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{displayName}</span>
          <span className={`badge badge-${role}`}>{role}</span>
          {role === 'gm' && (
            <button onClick={() => setGmPanelOpen(v => !v)} style={{
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', padding: '3px 8px', cursor: 'pointer',
              fontSize: '10px', fontFamily: 'Barlow Condensed, sans-serif',
              letterSpacing: '0.05em', textTransform: 'uppercase',
            }}>{gmPanelOpen ? 'Hide GM' : 'Show GM'}</button>
          )}
        </div>
      </header>

      {/* ── Main content ── */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

        {/* ── Left sidebar: participants ── */}
        <div style={{
          width: '180px', minWidth: '150px', background: 'var(--bg-panel)',
          borderRight: '1px solid var(--border)', display: 'flex',
          flexDirection: 'column', flexShrink: 0,
        }}>
          <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
            <span className="section-label">Personnel</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
            {participants.map((p, i) => (
              <div key={p.user_id || i} style={{ padding: '6px 12px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span style={{
                  fontSize: '12px',
                  color: p.user_id === userId ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontWeight: p.user_id === userId ? 500 : 400,
                }}>
                  {p.display_name}
                  {p.user_id === userId && <span style={{ color: 'var(--text-secondary)', fontSize: '10px' }}> (you)</span>}
                </span>
                <span className={`badge badge-${p.role}`} style={{ alignSelf: 'flex-start' }}>{p.role}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Log feed + input ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {combat && (
            <InitiativeTracker combat={combat} ships={scenario?.ships || []} />
          )}
          {scenario && scenario.ships && scenario.ships.length > 0 && (
            <ShipsZone
              ships={scenario.ships}
              myUserId={userId}
              isGm={role === 'gm'}
              participants={participants}
              onPatchShip={patchShip}
              onPatchPilot={patchPilot}
              onPatchSystem={patchSystem}
              onRemoveShip={removeShip}
              onAssignShip={assignShip}
            />
          )}

          {/* Declaration panel — for player's own ships during declaration phase */}
          {combat && combat.status === 'active' && combat.current_phase === 'declaration' && (
            scenario?.ships
              ?.filter(s => role === 'gm' ? false : s.assigned_user_id === userId)
              ?.map(ship => {
                const alreadySubmitted = (combat.declarations || []).some(
                  d => d.ship_id === ship.ship_id && d.submitted
                )
                return (
                  <DeclarationPanel
                    key={ship.ship_id}
                    ship={ship}
                    combat={combat}
                    round={combat.current_round}
                    alreadySubmitted={alreadySubmitted}
                    onSubmit={submitDeclaration}
                    isGm={false}
                  />
                )
              })
          )}

          <LogFeed
            entries={logEntries}
            myUserId={userId}
            isGm={role === 'gm'}
            onChaseRoll={handleChaseRoll}
            onDodgeRoll={handleDodgeRoll}
          />
          <RollInput sessionId={sessionId} token={token} />
        </div>

        {/* ── GM Panel ── */}
        {role === 'gm' && gmPanelOpen && (
          <GMPanel
            pendingRolls={pendingRolls}
            sessionId={sessionId}
            token={token}
            onRollResolved={handleRollResolved}
            scenario={scenario}
            participants={participants}
            onCreateScenario={createScenario}
            onAddShip={addShip}
            onRemoveShip={removeShip}
            combat={combat}
            onStartCombat={startCombat}
            onEndCombat={endCombat}
            onPatchShip={patchShip}
            onUpdateRange={updateRange}
          />
        )}
      </div>
    </div>
  )
}
