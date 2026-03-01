// =============================================================================
// useWebSocket.js
// =============================================================================
// Manages a WebSocket connection with automatic reconnection (exponential
// backoff). Dispatches incoming messages to a provided handler callback.
// =============================================================================
import { useEffect, useRef, useState, useCallback } from 'react'

const BASE_DELAY_MS  = 1000
const MAX_DELAY_MS   = 30000
const BACKOFF_FACTOR = 2

export function useWebSocket(sessionId, token, onMessage) {
  const [status, setStatus] = useState('disconnected') // connected | reconnecting | disconnected
  const wsRef      = useRef(null)
  const retryDelay = useRef(BASE_DELAY_MS)
  const retryTimer = useRef(null)
  const unmounted  = useRef(false)

  const connect = useCallback(() => {
    if (!sessionId || !token) return
    if (unmounted.current) return

    setStatus('reconnecting')

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host  = window.location.host
    const url   = `${proto}://${host}/ws/${sessionId}?token=${token}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (unmounted.current) return
      setStatus('connected')
      retryDelay.current = BASE_DELAY_MS
    }

    ws.onmessage = (event) => {
      if (unmounted.current) return
      try {
        const msg = JSON.parse(event.data)
        if (msg !== 'pong') {
          onMessage(msg)
        }
      } catch (e) {
        // ignore parse errors
      }
    }

    ws.onerror = () => {
      // Let onclose handle reconnect
    }

    ws.onclose = () => {
      if (unmounted.current) return
      wsRef.current = null
      setStatus('reconnecting')

      retryTimer.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * BACKOFF_FACTOR, MAX_DELAY_MS)
        connect()
      }, retryDelay.current)
    }

    // Keepalive ping every 25s
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 25000)

    ws._pingInterval = pingInterval
  }, [sessionId, token, onMessage])

  useEffect(() => {
    unmounted.current = false
    connect()

    return () => {
      unmounted.current = true
      clearTimeout(retryTimer.current)
      if (wsRef.current) {
        if (wsRef.current._pingInterval) clearInterval(wsRef.current._pingInterval)
        wsRef.current.close()
      }
    }
  }, [connect])

  return status
}
