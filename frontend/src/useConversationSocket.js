import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_BASE } from './api'

/**
 * Owns one WebSocket connection to a conversation room.
 *
 * Handles the unglamorous but essential parts of "real-time": the
 * connection WILL drop (tab backgrounded, wifi hiccup, laptop sleeps),
 * so we track connection state explicitly and reconnect with backoff
 * instead of just letting the UI silently go stale.
 *
 * It also guards against a subtle trap: React's StrictMode (dev only)
 * mounts every component twice to surface exactly this kind of bug.
 * Calling `.close()` on a socket that's still CONNECTING does NOT stop
 * it from finishing its handshake — the server still accepts it, and
 * its onmessage can still fire before the close completes. Without the
 * `cancelled` guard below, that stray socket stays alive just long
 * enough to receive and render every message a second time. The guard
 * makes any event arriving after cleanup a no-op, and closes the
 * socket the instant it opens instead of relying on close() alone.
 */
export function useConversationSocket({ conversationId, role, name, token, onMessage }) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!conversationId) return

    let cancelled = false
    let socket = null
    let attempt = 0
    let reconnectTimer = null

    const connect = () => {
      if (cancelled) return
      const tokenParam = token ? `&token=${encodeURIComponent(token)}` : ''
      const url = `${WS_BASE}/ws/conversations/${conversationId}?role=${role}&name=${encodeURIComponent(name)}${tokenParam}`
      socket = new WebSocket(url)
      wsRef.current = socket

      socket.onopen = () => {
        if (cancelled) {
          socket.close()
          return
        }
        setConnected(true)
        attempt = 0
      }

      socket.onmessage = (evt) => {
        if (cancelled) return
        onMessageRef.current?.(JSON.parse(evt.data))
      }

      socket.onclose = () => {
        setConnected(false)
        if (cancelled) return
        const delay = Math.min(1000 * 2 ** attempt, 8000)
        attempt += 1
        reconnectTimer = setTimeout(connect, delay)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [conversationId, role, name, token])

  const send = useCallback((payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    }
  }, [])

  return { connected, send }
}
