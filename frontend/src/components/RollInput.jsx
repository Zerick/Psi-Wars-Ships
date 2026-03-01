// =============================================================================
// RollInput.jsx — Chat/roll input bar
// =============================================================================
import { useState, useRef } from 'react'

const ROLL_RE = /\[\[([^\]]+)\]\]/

export default function RollInput({ sessionId, token, onSent }) {
  const [text, setText]       = useState('')
  const [sending, setSending] = useState(false)
  const inputRef = useRef(null)

  const hasRoll = ROLL_RE.test(text)

  const send = async () => {
    const content = text.trim()
    if (!content || sending) return

    setSending(true)
    try {
      await fetch(`/sessions/${sessionId}/chat?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      setText('')
      if (onSent) onSent()
    } catch (e) {
      // silent — WS will deliver the result anyway
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0',
      borderTop: '1px solid var(--border)',
      background: 'var(--bg-input)',
    }}>
      {/* Dice indicator */}
      <div style={{
        padding: '0 12px',
        color: hasRoll ? 'var(--accent-blue)' : 'var(--border)',
        fontSize: '18px',
        transition: 'color 0.15s',
        userSelect: 'none',
        lineHeight: 1,
      }}
        title={hasRoll ? 'Roll detected' : 'No roll'}
      >
        ⬡
      </div>

      <input
        ref={inputRef}
        className="tactical-input"
        style={{
          flex: 1,
          border: 'none',
          borderRadius: 0,
          padding: '13px 0',
          background: 'transparent',
        }}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Type a message or roll [[3d6+2]]..."
        disabled={sending}
        autoFocus
      />

      <button
        onClick={send}
        disabled={!text.trim() || sending}
        style={{
          padding: '13px 20px',
          background: 'transparent',
          border: 'none',
          borderLeft: '1px solid var(--border)',
          color: text.trim() ? 'var(--accent-blue)' : 'var(--text-secondary)',
          cursor: text.trim() ? 'pointer' : 'default',
          fontFamily: 'Barlow Condensed, sans-serif',
          fontWeight: 700,
          fontSize: '12px',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          transition: 'color 0.15s',
        }}
      >
        Send
      </button>
    </div>
  )
}
