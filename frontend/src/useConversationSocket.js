import { useReconnectingSocket } from './useReconnectingSocket'
import { WS_BASE } from './api'

/**
 * Connects to one conversation room's WebSocket. Reconnection-with-backoff
 * and the StrictMode double-mount guard live in useReconnectingSocket —
 * see that file for why they're needed.
 */
export function useConversationSocket({ conversationId, role, name, onMessage }) {
  const url = conversationId
    ? `${WS_BASE}/ws/conversations/${conversationId}?role=${role}&name=${encodeURIComponent(name)}`
    : null

  return useReconnectingSocket(url, onMessage)
}
