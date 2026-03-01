// =============================================================================
// JoinView.jsx — Landing page: create session or join with code
// =============================================================================
import { useState } from 'react'

export default function JoinView({ onJoined }) {
  const [mode, setMode]               = useState(null) // 'create' | 'join'
  const [displayName, setDisplayName] = useState('')
  const [inviteCode, setInviteCode]   = useState('')
  const [role, setRole]               = useState('player')
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!displayName.trim()) return
    setLoading(true); setError(null)
    try {
      const res = await fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: displayName.trim() }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to create session')
      const data = await res.json()
      onJoined({
        sessionId:   data.session_id,
        token:       data.token,
        userId:      data.user_id,
        role:        data.role,
        displayName: data.display_name,
        inviteCode:  data.invite_code,
      })
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleJoin = async (e) => {
    e.preventDefault()
    if (!displayName.trim() || !inviteCode.trim()) return
    setLoading(true); setError(null)
    try {
      const res = await fetch(`/sessions/${inviteCode.trim().toUpperCase()}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: displayName.trim(), role }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Invite code not found')
      const data = await res.json()
      onJoined({
        sessionId:   data.session_id,
        token:       data.token,
        userId:      data.user_id,
        role:        data.role,
        displayName: data.display_name,
        inviteCode:  data.invite_code,
      })
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="grid-bg" style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '48px' }}>
        <div style={{
          fontFamily: 'Barlow Condensed, sans-serif',
          fontWeight: 300,
          fontSize: '11px',
          letterSpacing: '0.4em',
          textTransform: 'uppercase',
          color: 'var(--text-secondary)',
          marginBottom: '10px',
        }}>
          Psi-Wars GURPS
        </div>
        <h1 style={{
          fontFamily: 'Barlow Condensed, sans-serif',
          fontWeight: 700,
          fontSize: '42px',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--text-primary)',
          lineHeight: 1,
          marginBottom: '6px',
        }}>
          Combat Simulator
        </h1>
        <div style={{
          width: '60px',
          height: '2px',
          background: 'var(--accent-red)',
          margin: '14px auto 0',
        }} />
      </div>

      {/* Mode selector */}
      {!mode && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            className="btn btn-primary"
            style={{ padding: '16px 32px', fontSize: '14px' }}
            onClick={() => setMode('create')}
          >
            ⬡ Create Session
            <div style={{ fontSize: '10px', fontWeight: 300, letterSpacing: '0.05em', textTransform: 'none', marginTop: '3px', opacity: 0.7 }}>
              I am the GM
            </div>
          </button>
          <button
            className="btn btn-secondary"
            style={{ padding: '16px 32px', fontSize: '14px' }}
            onClick={() => setMode('join')}
          >
            → Join Session
            <div style={{ fontSize: '10px', fontWeight: 300, letterSpacing: '0.05em', textTransform: 'none', marginTop: '3px', opacity: 0.7 }}>
              I have an invite code
            </div>
          </button>
        </div>
      )}

      {/* Create form */}
      {mode === 'create' && (
        <form onSubmit={handleCreate} style={{ width: '100%', maxWidth: '360px' }}>
          <div style={{ marginBottom: '16px' }}>
            <div className="section-label" style={{ marginBottom: '6px' }}>Your callsign</div>
            <input
              className="tactical-input"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="GM display name"
              autoFocus
              required
            />
          </div>

          {error && <ErrorBox message={error} />}

          <div style={{ display: 'flex', gap: '10px' }}>
            <button type="button" className="btn" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', padding: '10px 16px', fontSize: '13px' }} onClick={() => { setMode(null); setError(null) }}>
              ← Back
            </button>
            <button type="submit" className="btn btn-primary" style={{ flex: 1, padding: '10px 16px', fontSize: '13px' }} disabled={loading || !displayName.trim()}>
              {loading ? 'Creating...' : 'Create Session'}
            </button>
          </div>
        </form>
      )}

      {/* Join form */}
      {mode === 'join' && (
        <form onSubmit={handleJoin} style={{ width: '100%', maxWidth: '360px' }}>
          <div style={{ marginBottom: '12px' }}>
            <div className="section-label" style={{ marginBottom: '6px' }}>Invite code</div>
            <input
              className="tactical-input font-mono"
              style={{ textTransform: 'uppercase', letterSpacing: '0.1em', fontSize: '18px' }}
              value={inviteCode}
              onChange={e => setInviteCode(e.target.value)}
              placeholder="WOLF-7"
              autoFocus
              required
            />
          </div>
          <div style={{ marginBottom: '12px' }}>
            <div className="section-label" style={{ marginBottom: '6px' }}>Your callsign</div>
            <input
              className="tactical-input"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Display name"
              required
            />
          </div>
          <div style={{ marginBottom: '20px' }}>
            <div className="section-label" style={{ marginBottom: '8px' }}>Role</div>
            <div style={{ display: 'flex', gap: '10px' }}>
              {['player', 'spectator'].map(r => (
                <label key={r} style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '9px',
                  border: `1px solid ${role === r ? 'var(--accent-blue)' : 'var(--border)'}`,
                  background: role === r ? 'rgba(45,156,219,0.08)' : 'transparent',
                  cursor: 'pointer',
                  fontFamily: 'Barlow Condensed, sans-serif',
                  fontWeight: 600,
                  fontSize: '12px',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: role === r ? 'var(--accent-blue)' : 'var(--text-secondary)',
                  transition: 'all 0.15s',
                }}>
                  <input
                    type="radio"
                    name="role"
                    value={r}
                    checked={role === r}
                    onChange={() => setRole(r)}
                    style={{ display: 'none' }}
                  />
                  {r}
                </label>
              ))}
            </div>
          </div>

          {error && <ErrorBox message={error} />}

          <div style={{ display: 'flex', gap: '10px' }}>
            <button type="button" className="btn" style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)', padding: '10px 16px', fontSize: '13px' }} onClick={() => { setMode(null); setError(null) }}>
              ← Back
            </button>
            <button type="submit" className="btn btn-secondary" style={{ flex: 1, padding: '10px 16px', fontSize: '13px' }} disabled={loading || !displayName.trim() || !inviteCode.trim()}>
              {loading ? 'Joining...' : 'Join Session'}
            </button>
          </div>
        </form>
      )}

      {/* Footer */}
      <div style={{
        position: 'fixed',
        bottom: '16px',
        fontSize: '10px',
        color: 'var(--text-secondary)',
        fontFamily: 'Barlow Condensed, sans-serif',
        letterSpacing: '0.15em',
        textTransform: 'uppercase',
      }}>
        Slice 1 — The Table
      </div>
    </div>
  )
}

function ErrorBox({ message }) {
  return (
    <div style={{
      padding: '10px 14px',
      border: '1px solid var(--accent-red-dim)',
      color: 'var(--accent-red)',
      marginBottom: '14px',
      fontSize: '12px',
      fontFamily: 'Barlow Condensed, sans-serif',
    }}>
      ⚠ {message}
    </div>
  )
}
