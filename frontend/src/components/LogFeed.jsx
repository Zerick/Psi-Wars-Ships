// =============================================================================
// LogFeed.jsx — Shared roll/chat log display + combat cards
// =============================================================================
import { useEffect, useRef, useState } from 'react'

// ---------------------------------------------------------------------------
// Plain entry types
// ---------------------------------------------------------------------------
function ChatEntry({ entry }) {
  return (
    <div style={{
      padding: '8px 12px',
      borderLeft: '2px solid var(--border)',
      marginBottom: '2px',
    }}>
      <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.05em' }}>
        {entry.author_name || 'Unknown'}
      </span>
      <span style={{ color: 'var(--text-secondary)', margin: '0 6px' }}>·</span>
      <span style={{ color: 'var(--text-primary)' }}>{entry.content}</span>
    </div>
  )
}

function RollEntry({ entry }) {
  const dice = Array.isArray(entry.dice_results) ? entry.dice_results : []
  const isOverridden = entry.gm_overridden
  return (
    <div style={{
      padding: '10px 12px',
      borderLeft: '3px solid var(--accent-blue-dim)',
      marginBottom: '2px',
      background: 'rgba(45, 156, 219, 0.04)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif' }}>
          {entry.author_name || 'Unknown'}
        </span>
        <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>rolled</span>
        <span className="font-mono" style={{ color: 'var(--text-mono)', fontSize: '13px' }}>
          [[{entry.expression}]]
        </span>
        {entry.content && (
          <>
            <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>—</span>
            <span style={{ color: 'var(--text-secondary)', fontSize: '12px', fontStyle: 'italic' }}>{entry.content}</span>
          </>
        )}
        {isOverridden && (
          <span style={{
            fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700,
            letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--accent-red)',
            border: '1px solid var(--accent-red-dim)', padding: '1px 5px',
          }}>GM Override</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {dice.length > 0 && (
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            {dice.map((val, i) => (
              <span key={i} className="font-mono" style={{
                display: 'inline-block', minWidth: '28px', textAlign: 'center',
                padding: '3px 6px', background: 'var(--bg-deep)', border: '1px solid var(--border)',
                color: 'var(--text-mono)', fontSize: '13px',
              }}>{val}</span>
            ))}
            <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>→</span>
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isOverridden && entry.original_total != null && (
            <span className="font-mono struck" style={{ fontSize: '18px', color: 'var(--text-secondary)' }}>
              {entry.original_total}
            </span>
          )}
          <span className="font-mono" style={{
            fontSize: '22px', fontWeight: 700, lineHeight: 1,
            color: isOverridden ? 'var(--accent-red)' : 'var(--accent-blue)',
          }}>{entry.total}</span>
        </div>
      </div>
    </div>
  )
}

function SystemEntry({ entry }) {
  return (
    <div style={{
      padding: '6px 12px', marginBottom: '2px',
      display: 'flex', alignItems: 'center', gap: '8px',
    }}>
      <span style={{
        fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 600,
        letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--system-color)', minWidth: '50px',
      }}>SYS</span>
      <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{entry.content}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Combat card entry types
// ---------------------------------------------------------------------------

const CARD_BORDER = {
  chase:      '#2d9cdb',
  attack:     '#e8a030',
  dodge:      '#9b59b6',
  damage:     '#e8410a',
  resolution: '#4caf6a',
  phase:      '#4caf6a',
}

function cardStyle(type) {
  const color = CARD_BORDER[type] || '#666'
  return {
    padding: '10px 12px',
    borderLeft: `3px solid ${color}`,
    marginBottom: '4px',
    background: `${color}0d`,
  }
}

function CardLabel({ text, color }) {
  return (
    <span style={{
      fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700,
      letterSpacing: '0.15em', textTransform: 'uppercase',
      color: color || 'var(--text-secondary)',
      marginRight: '8px',
    }}>{text}</span>
  )
}

function StatPill({ label, value, highlight }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
      <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>{label}</span>
      <span className="font-mono" style={{
        fontSize: '13px', fontWeight: 700,
        color: highlight ? 'var(--accent-blue)' : 'var(--text-primary)',
      }}>{value}</span>
    </span>
  )
}

function RollButton({ label, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        marginTop: '8px',
        padding: '5px 14px',
        background: disabled ? 'transparent' : 'var(--accent-blue-dim)',
        border: `1px solid ${disabled ? 'var(--border)' : 'var(--accent-blue)'}`,
        color: disabled ? 'var(--text-secondary)' : '#fff',
        cursor: disabled ? 'default' : 'pointer',
        fontFamily: 'Barlow Condensed, sans-serif',
        fontSize: '11px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase',
      }}
    >{label}</button>
  )
}

// Chase roll card — shown for each ship during chase phase
function ChaseCard({ entry, onRoll }) {
  const { ship_name, chase_bonus, breakdown, roll, mos, npc, rolled, combat_id, ship_id } = entry.data
  const canRoll = !rolled && !npc && onRoll

  const mosColor = mos == null ? 'var(--text-secondary)'
    : mos <= 0 ? 'var(--accent-blue)'
    : mos <= 4 ? 'var(--accent-yellow, #d4a017)'
    : 'var(--accent-red)'

  const mosLabel = mos == null ? '' : mos <= 0 ? 'Success' : `Failure by ${mos}`

  return (
    <div style={cardStyle('chase')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <CardLabel text="Chase" color={CARD_BORDER.chase} />
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        {npc && <span style={{ fontSize: '9px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.1em' }}>NPC</span>}
      </div>

      {/* Bonus breakdown */}
      <div style={{ marginBottom: '6px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
        {breakdown && breakdown.map((b, i) => (
          <span key={i}>{i > 0 ? ' + ' : ''}{b.label} {b.value >= 0 ? '+' : ''}{b.value}</span>
        ))}
        {' '}= <span className="font-mono" style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>{chase_bonus}</span>
      </div>

      {/* Roll result */}
      {rolled && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <StatPill label="Roll" value={roll} />
          <StatPill label="Bonus" value={chase_bonus} />
          <span className="font-mono" style={{ fontSize: '15px', fontWeight: 700, color: mosColor }}>
            {mosLabel}
          </span>
          {/* Plaintext summary */}
          <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
            [{ship_name}: rolled {roll} vs {chase_bonus}{mos != null ? `, MOS ${mos <= 0 ? Math.abs(mos) : -mos}` : ''}]
          </span>
        </div>
      )}

      {canRoll && (
        <RollButton label={`Roll Chase (need ≤ ${chase_bonus})`} onClick={() => onRoll(combat_id, ship_id)} />
      )}
    </div>
  )
}

// Chase resolution card — shows what changed after all ships rolled
function ChaseResolutionCard({ entry }) {
  const { winner, loser, victory_margin, range_change, advantage_change, new_range, description } = entry.data
  return (
    <div style={cardStyle('resolution')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <CardLabel text="Chase Result" color={CARD_BORDER.resolution} />
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{winner} wins</span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>by {victory_margin}</span>
      </div>
      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {description}
      </div>
      <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
        [{winner} beats {loser} by {victory_margin} — {description}]
      </div>
    </div>
  )
}

// Attack card
function AttackCard({ entry, onRoll }) {
  const { ship_name, target_name, weapon_name, attack_bonus, breakdown, roll, hit, mos, npc, rolled, combat_id, ship_id, action_id } = entry.data
  const canRoll = !rolled && !npc && onRoll

  return (
    <div style={cardStyle('attack')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <CardLabel text="Attack" color={CARD_BORDER.attack} />
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>→ {target_name}</span>
        <span style={{ fontSize: '11px', color: 'var(--accent-yellow, #d4a017)' }}>{weapon_name}</span>
        {npc && <span style={{ fontSize: '9px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>NPC</span>}
      </div>
      <div style={{ marginBottom: '6px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
        {breakdown && breakdown.map((b, i) => (
          <span key={i}>{i > 0 ? ' + ' : ''}{b.label} {b.value >= 0 ? '+' : ''}{b.value}</span>
        ))}
        {' '}= <span className="font-mono" style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>{attack_bonus}</span>
      </div>
      {rolled && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <StatPill label="Roll" value={roll} />
          <StatPill label="Skill" value={attack_bonus} />
          <span className="font-mono" style={{
            fontSize: '15px', fontWeight: 700,
            color: hit ? 'var(--accent-blue)' : 'var(--accent-red)',
          }}>{hit ? 'HIT' : 'MISS'}</span>
          <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
            [{ship_name} attacks {target_name} with {weapon_name}: rolled {roll} vs {attack_bonus} — {hit ? 'HIT' : 'MISS'}]
          </span>
        </div>
      )}
      {canRoll && (
        <RollButton label={`Roll Attack (need ≤ ${attack_bonus})`} onClick={() => onRoll(combat_id, ship_id, action_id)} />
      )}
    </div>
  )
}

// Dodge card
function DodgeCard({ entry, onRoll }) {
  const { ship_name, attacker_name, dodge_bonus, breakdown, roll, dodged, npc, rolled, combat_id, ship_id, action_id } = entry.data
  const canRoll = !rolled && !npc && onRoll

  return (
    <div style={cardStyle('dodge')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <CardLabel text="Dodge" color={CARD_BORDER.dodge} />
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>← from {attacker_name}</span>
        {npc && <span style={{ fontSize: '9px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>NPC</span>}
      </div>
      <div style={{ marginBottom: '6px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
        {breakdown && breakdown.map((b, i) => (
          <span key={i}>{i > 0 ? ' + ' : ''}{b.label} {b.value >= 0 ? '+' : ''}{b.value}</span>
        ))}
        {' '}= <span className="font-mono" style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>{dodge_bonus}</span>
      </div>
      {rolled && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <StatPill label="Roll" value={roll} />
          <StatPill label="Dodge" value={dodge_bonus} />
          <span className="font-mono" style={{
            fontSize: '15px', fontWeight: 700,
            color: dodged ? 'var(--accent-blue)' : 'var(--accent-red)',
          }}>{dodged ? 'DODGED' : 'HIT'}</span>
          <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
            [{ship_name} dodge: rolled {roll} vs {dodge_bonus} — {dodged ? 'DODGED' : 'FAILED'}]
          </span>
        </div>
      )}
      {canRoll && (
        <RollButton label={`Roll Dodge (need ≤ ${dodge_bonus})`} onClick={() => onRoll(combat_id, ship_id, action_id)} />
      )}
    </div>
  )
}

// Damage card
function DamageCard({ entry }) {
  const { ship_name, attacker_name, damage_rolled, damage_net, hp_before, hp_after, screen_before, screen_after, description } = entry.data
  return (
    <div style={cardStyle('damage')}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <CardLabel text="Damage" color={CARD_BORDER.damage} />
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>from {attacker_name}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <StatPill label="Damage" value={damage_rolled} />
        {damage_net != null && <StatPill label="Net" value={damage_net} highlight />}
        {hp_before != null && hp_after != null && (
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
            HP: <span className="font-mono">{hp_before}</span> → <span className="font-mono" style={{ color: 'var(--accent-red)' }}>{hp_after}</span>
          </span>
        )}
        {screen_before != null && screen_after != null && screen_before !== screen_after && (
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
            Screen: <span className="font-mono">{screen_before}</span> → <span className="font-mono" style={{ color: 'var(--accent-blue)' }}>{screen_after}</span>
          </span>
        )}
      </div>
      {description && (
        <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
          [{attacker_name} hits {ship_name}: {damage_net} net damage — {description}]
        </div>
      )}
    </div>
  )
}

// Phase change card
function PhaseCard({ entry }) {
  const { round, phase, description } = entry.data
  return (
    <div style={{
      padding: '6px 12px', marginBottom: '4px',
      display: 'flex', alignItems: 'center', gap: '8px',
      borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)',
    }}>
      <span style={{
        fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700,
        letterSpacing: '0.15em', textTransform: 'uppercase', color: CARD_BORDER.resolution, minWidth: '50px',
      }}>Round {round}</span>
      <span style={{
        fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 600,
        letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-primary)',
      }}>{phase}</span>
      {description && <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{description}</span>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main LogFeed
// ---------------------------------------------------------------------------
export default function LogFeed({ entries, onChaseRoll, onAttackRoll, onDodgeRoll, myUserId }) {
  const bottomRef   = useRef(null)
  const containerRef = useRef(null)
  const [userScrolled, setUserScrolled] = useState(false)

  useEffect(() => {
    if (!userScrolled && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [entries, userScrolled])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    setUserScrolled(!atBottom)
  }

  const jumpToBottom = () => {
    setUserScrolled(false)
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  function renderEntry(entry, i) {
    const key = entry.entry_id || entry.combat_card_id || i

    switch (entry.entry_type) {
      case 'roll':   return <RollEntry   key={key} entry={entry} />
      case 'system': return <SystemEntry key={key} entry={entry} />
      case 'combat_phase':      return <PhaseCard      key={key} entry={entry} />
      case 'combat_chase': {
        // Only show roll button if this is the player's ship
        const isMyShip = myUserId && entry.data?.owner_user_id === myUserId
        return <ChaseCard key={key} entry={entry} onRoll={isMyShip && !entry.data?.rolled ? onChaseRoll : null} />
      }
      case 'combat_chase_resolution': return <ChaseResolutionCard key={key} entry={entry} />
      case 'combat_attack': {
        const isMyShip = myUserId && entry.data?.owner_user_id === myUserId
        return <AttackCard key={key} entry={entry} onRoll={isMyShip && !entry.data?.rolled ? onAttackRoll : null} />
      }
      case 'combat_dodge': {
        const isMyShip = myUserId && entry.data?.owner_user_id === myUserId
        return <DodgeCard key={key} entry={entry} onRoll={isMyShip && !entry.data?.rolled ? onDodgeRoll : null} />
      }
      case 'combat_damage': return <DamageCard key={key} entry={entry} />
      default: return <ChatEntry key={key} entry={entry} />
    }
  }

  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        style={{ height: '100%', overflowY: 'auto', padding: '8px 0' }}
      >
        {entries.length === 0 && (
          <div style={{
            textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 20px',
            fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.1em', fontSize: '12px', textTransform: 'uppercase',
          }}>— Awaiting transmissions —</div>
        )}
        {entries.map((entry, i) => renderEntry(entry, i))}
        <div ref={bottomRef} />
      </div>
      {userScrolled && (
        <button
          onClick={jumpToBottom}
          style={{
            position: 'absolute', bottom: '12px', right: '12px',
            background: 'var(--accent-blue-dim)', border: '1px solid var(--accent-blue)',
            color: '#fff', padding: '6px 14px', cursor: 'pointer',
            fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px',
            fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', zIndex: 10,
          }}
        >↓ Jump to Latest</button>
      )}
    </div>
  )
}
