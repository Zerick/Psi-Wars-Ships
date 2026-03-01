// =============================================================================
// App.jsx — Root component. Simple state-based routing between views.
// =============================================================================
import { useState } from 'react'
import JoinView    from './views/JoinView'
import SessionView from './views/SessionView'

export default function App() {
  // session: null | { sessionId, token, userId, role, displayName, inviteCode }
  const [session, setSession] = useState(null)

  if (!session) {
    return <JoinView onJoined={setSession} />
  }

  return (
    <SessionView
      session={session}
      onLeave={() => setSession(null)}
    />
  )
}
