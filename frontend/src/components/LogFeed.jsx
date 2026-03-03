// components/LogFeed.jsx
import { useEffect, useRef, useState } from 'react'

function ChatEntry({ entry }) {
  return (
    <div style={{ padding: '8px 12px', borderLeft: '2px solid var(--border)', marginBottom: '2px' }}>
      <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.05em' }}>{entry.author_name || 'Unknown'}</span>
      <span style={{ color: 'var(--text-secondary)', margin: '0 6px' }}>·</span>
      <span style={{ color: 'var(--text-primary)' }}>{entry.content}</span>
    </div>
  )
}

function RollEntry({ entry }) {
  const dice = Array.isArray(entry.dice_results) ? entry.dice_results : []
  const isOverridden = entry.gm_overridden
  return (
    <div style={{ padding: '10px 12px', borderLeft: '3px solid var(--accent-blue-dim)', marginBottom: '2px', background: 'rgba(45,156,219,0.04)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif' }}>{entry.author_name || 'Unknown'}</span>
        <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>rolled</span>
        <span className="font-mono" style={{ color: 'var(--text-mono)', fontSize: '13px' }}>[[{entry.expression}]]</span>
        {entry.content && <><span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>—</span><span style={{ color: 'var(--text-secondary)', fontSize: '12px', fontStyle: 'italic' }}>{entry.content}</span></>}
        {isOverridden && <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--accent-red)', border: '1px solid var(--accent-red-dim)', padding: '1px 5px' }}>GM Override</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {dice.length > 0 && (
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            {dice.map((val, i) => (
              <span key={i} className="font-mono" style={{ display: 'inline-block', minWidth: '28px', textAlign: 'center', padding: '3px 6px', background: 'var(--bg-deep)', border: '1px solid var(--border)', color: 'var(--text-mono)', fontSize: '13px' }}>{val}</span>
            ))}
            <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>→</span>
          </div>
        )}
        <span className="font-mono" style={{ fontSize: '22px', fontWeight: 700, lineHeight: 1, color: isOverridden ? 'var(--accent-red)' : 'var(--accent-blue)' }}>{entry.total}</span>
      </div>
    </div>
  )
}

function SystemEntry({ entry }) {
  return (
    <div style={{ padding: '6px 12px', marginBottom: '2px', display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 600, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'var(--system-color)', minWidth: '50px' }}>SYS</span>
      <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{entry.content}</span>
    </div>
  )
}

function PhaseCard({ entry }) {
  const { round, phase, description } = entry.data
  return (
    <div style={{ padding: '6px 12px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
      {round != null && round !== '' && (
        <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#4caf6a', minWidth: '60px' }}>Round {round}</span>
      )}
      <span style={{ fontSize: '11px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-primary)' }}>{phase}</span>
      {description && <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{description}</span>}
    </div>
  )
}

function ChaseCard({ entry, onRoll, isGm }) {
  const { ship_name, chase_bonus, breakdown, roll, mos, npc, rolled, combat_id, ship_id, owner_user_id, faction } = entry.data
  const canRoll = !rolled && onRoll && (isGm || (!npc && owner_user_id))

  const factionColor = faction === 'hostile_npc' ? '#e8410a' : faction === 'friendly_npc' ? '#4caf6a' : 'var(--text-secondary)'
  const mosColor = mos == null ? 'var(--text-secondary)' : mos <= 0 ? '#4caf6a' : mos <= 4 ? '#d4a017' : '#e8410a'
  const mosLabel = mos == null ? '' : mos <= 0 ? `Success by ${Math.abs(mos)}` : `Failure by ${mos}`

  return (
    <div style={{ padding: '10px 12px', borderLeft: '3px solid #2d9cdb', marginBottom: '4px', background: '#2d9cdb0d' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#2d9cdb', marginRight: '8px' }}>Chase</span>
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        {npc && (
          <span style={{ fontSize: '9px', color: factionColor, fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.1em', border: `1px solid ${factionColor}44`, padding: '1px 5px' }}>
            {faction === 'hostile_npc' ? 'HOSTILE' : faction === 'friendly_npc' ? 'FRIENDLY' : 'NPC'}
          </span>
        )}
        {rolled && <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.1em', color: '#4caf6a', border: '1px solid #4caf6a44', padding: '1px 5px' }}>ROLLED</span>}
      </div>

      <div style={{ marginBottom: '6px', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
        {(breakdown || []).map((b, i) => (
          <span key={i}>{i > 0 ? ' + ' : ''}{b.label} {b.value >= 0 ? '+' : ''}{b.value}</span>
        ))}
        {' '}= <span className="font-mono" style={{ color: 'var(--accent-blue)', fontWeight: 700 }}>{chase_bonus}</span>
      </div>

      {rolled && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
            <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>Roll</span>
            <span className="font-mono" style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>{roll}</span>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
            <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>Target</span>
            <span className="font-mono" style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>{chase_bonus}</span>
          </span>
          <span className="font-mono" style={{ fontSize: '15px', fontWeight: 700, color: mosColor }}>{mosLabel}</span>
        </div>
      )}

      {canRoll && (
        <button onClick={() => onRoll(combat_id, ship_id)} style={{
          marginTop: '8px', padding: '5px 14px',
          background: 'var(--accent-blue-dim)', border: '1px solid var(--accent-blue)',
          color: '#fff', cursor: 'pointer',
          fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px',
          fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>
          Roll Chase — need ≤ {chase_bonus}
        </button>
      )}
    </div>
  )
}

function ChaseResolutionCard({ entry }) {
  const { winner, new_range, description } = entry.data
  return (
    <div style={{ padding: '10px 12px', borderLeft: '3px solid #4caf6a', marginBottom: '4px', background: '#4caf6a0d' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#4caf6a' }}>Chase Result</span>
        {winner && <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{winner}</span>}
      </div>
      {description && <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{description}</div>}
      {new_range && <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--accent-blue)', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700 }}>Range: {new_range}</div>}
    </div>
  )
}

function AttackCard({ entry }) {
  const { ship_name, target_name, weapon_name, attack_bonus, attack_total, roll, hit, npc, rolled } = entry.data
  const displayBonus = attack_total || attack_bonus
  return (
    <div style={{ padding: '10px 12px', borderLeft: '3px solid #e8a030', marginBottom: '4px', background: '#e8a0300d' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#e8a030' }}>Attack</span>
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>→ {target_name}</span>
        {weapon_name && <span style={{ fontSize: '11px', color: '#d4a017' }}>{weapon_name}</span>}
      </div>
      {rolled && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>Roll <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{roll}</span></span>
          {displayBonus != null && <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>Skill <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{displayBonus}</span></span>}
          <span className="font-mono" style={{ fontSize: '15px', fontWeight: 700, color: hit ? '#4caf6a' : '#e8410a' }}>{hit ? 'HIT' : 'MISS'}</span>
        </div>
      )}
    </div>
  )
}

function DamageCard({ entry }) {
  const { ship_name, attacker_name, damage_raw, damage_net, hp_before, hp_after, screen_before, screen_after, wound_after } = entry.data
  const destroyed = wound_after === 'lethal'
  return (
    <div style={{ padding: '10px 12px', borderLeft: '3px solid #e8410a', marginBottom: '4px', background: '#e8410a0d' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#e8410a' }}>Damage</span>
        <span style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>{ship_name}</span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>from {attacker_name}</span>
        {destroyed && <span style={{ fontSize: '9px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, letterSpacing: '0.1em', color: '#e8410a', border: '1px solid #e8410a55', padding: '1px 5px' }}>DESTROYED</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        {damage_net != null && <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>Net <span className="font-mono" style={{ fontSize: '13px', fontWeight: 700, color: 'var(--accent-blue)' }}>{damage_net}</span></span>}
        {hp_before != null && hp_after != null && (
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Barlow Condensed, sans-serif' }}>
            HP: <span className="font-mono">{hp_before}</span> → <span className="font-mono" style={{ color: '#e8410a' }}>{hp_after}</span>
          </span>
        )}
        {wound_after && wound_after !== 'none' && (
          <span style={{ fontSize: '10px', fontFamily: 'Barlow Condensed, sans-serif', fontWeight: 700, color: destroyed ? '#e8410a' : '#d4a017', border: `1px solid ${destroyed ? '#e8410a55' : '#d4a01744'}`, padding: '1px 5px' }}>{wound_after.toUpperCase()}</span>
        )}
      </div>
    </div>
  )
}

export default function LogFeed({ entries, onChaseRoll, onDodgeRoll, myUserId, isGm }) {
  const bottomRef    = useRef(null)
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
    setUserScrolled(el.scrollHeight - el.scrollTop - el.clientHeight > 60)
  }

  function renderEntry(entry, i) {
    const key = entry.entry_id || entry.data?.combat_card_id || i
    switch (entry.entry_type) {
      case 'roll':   return <RollEntry   key={key} entry={entry} />
      case 'system': return <SystemEntry key={key} entry={entry} />
      case 'combat_phase': return <PhaseCard key={key} entry={entry} />
      case 'combat_chase': {
        const isMyShip = myUserId && entry.data?.owner_user_id === myUserId
        const canRoll  = !entry.data?.rolled && (isGm || isMyShip)
        return <ChaseCard key={key} entry={entry} onRoll={canRoll ? onChaseRoll : null} isGm={isGm} />
      }
      case 'combat_chase_resolution': return <ChaseResolutionCard key={key} entry={entry} />
      case 'combat_attack': return <AttackCard key={key} entry={entry} />
      case 'combat_damage': return <DamageCard key={key} entry={entry} />
      default: return <ChatEntry key={key} entry={entry} />
    }
  }

  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
      <div ref={containerRef} onScroll={handleScroll} style={{ height: '100%', overflowY: 'auto', padding: '8px 0' }}>
        {entries.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '40px 20px', fontFamily: 'Barlow Condensed, sans-serif', letterSpacing: '0.1em', fontSize: '12px', textTransform: 'uppercase' }}>— Awaiting transmissions —</div>
        )}
        {entries.map((entry, i) => renderEntry(entry, i))}
        <div ref={bottomRef} />
      </div>
      {userScrolled && (
        <button onClick={() => { setUserScrolled(false); bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }}
          style={{ position: 'absolute', bottom: '12px', right: '12px', background: 'var(--accent-blue-dim)', border: '1px solid var(--accent-blue)', color: '#fff', padding: '6px 14px', cursor: 'pointer', fontFamily: 'Barlow Condensed, sans-serif', fontSize: '11px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', zIndex: 10 }}>
          ↓ Jump to Latest
        </button>
      )}
    </div>
  )
}
