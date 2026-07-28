export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
export const WS_BASE = API_BASE.replace(/^http/, 'ws')

export async function createConversation(clientName) {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_name: clientName }),
  })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function listConversations() {
  const res = await fetch(`${API_BASE}/api/conversations`)
  if (!res.ok) throw new Error('Failed to list conversations')
  return res.json()
}

export async function getMessages(conversationId) {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}/messages`)
  if (!res.ok) throw new Error('Failed to fetch history')
  return res.json()
}

export async function updateConversation(conversationId, patch, agentToken) {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'X-Agent-Token': agentToken || '' },
    body: JSON.stringify(patch),
  })
  if (res.status === 401) throw new Error('unauthorized')
  if (!res.ok) throw new Error('Failed to update ticket')
  return res.json()
}
