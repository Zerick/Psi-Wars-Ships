// =============================================================================
// useSession.js
// =============================================================================
// Session state management. Holds auth info and participants list.
// Token is stored in React state (not localStorage per spec).
// =============================================================================
import { useState, useCallback } from 'react'

const API = (path) => path  // paths are relative; Vite proxies to backend

export function useSession() {
  const [session, setSession] = useState(null)
  // session shape: { sessionId, token, userId, role, displayName, inviteCode }

  const [participants, setParticipants] = useState([])
  const [error, setError] = useState(null)

  // -------------------------------------------------------------------------
  // Create a new session (GM flow)
  // -------------------------------------------------------------------------
  const createSession = useCallback(async (displayName) => {
    setError(null)
    try {
      const res = await fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: displayName }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to create session')
      const data = await res.json()
      const sess = {
        sessionId:   data.session_id,
        token:       data.token,
        userId:      data.user_id,
        role:        data.role,
        displayName: data.display_name,
        inviteCode:  data.invite_code,
      }
      setSession(sess)
      return sess
    } catch (e) {
      setError(e.message)
      return null
    }
  }, [])

  // -------------------------------------------------------------------------
  // Join an existing session (player/spectator flow)
  // -------------------------------------------------------------------------
  const joinSession = useCallback(async (inviteCode, displayName, role) => {
    setError(null)
    try {
      const res = await fetch(`/sessions/${inviteCode.toUpperCase()}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: displayName, role }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to join session')
      const data = await res.json()
      const sess = {
        sessionId:   data.session_id,
        token:       data.token,
        userId:      data.user_id,
        role:        data.role,
        displayName: data.display_name,
        inviteCode:  data.invite_code,
      }
      setSession(sess)
      return sess
    } catch (e) {
      setError(e.message)
      return null
    }
  }, [])

  // -------------------------------------------------------------------------
  // Load participants for the current session
  // -------------------------------------------------------------------------
  const loadParticipants = useCallback(async (sessionId, token) => {
    try {
      const res = await fetch(`/sessions/${sessionId}/participants?token=${token}`)
      if (!res.ok) return
      const data = await res.json()
      setParticipants(data)
    } catch (e) {
      // non-fatal
    }
  }, [])

  const addParticipant = useCallback((participant) => {
    setParticipants(prev => {
      // Avoid duplicates
      if (prev.some(p => p.user_id === participant.user_id)) return prev
      return [...prev, participant]
    })
  }, [])

  return {
    session,
    participants,
    error,
    createSession,
    joinSession,
    loadParticipants,
    addParticipant,
  }
}
