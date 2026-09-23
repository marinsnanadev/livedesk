import { useEffect, useRef, useState } from 'react'
import { listConversations, updateConversation, WS_BASE } from '../api'
import ChatPanel from '../components/ChatPanel'
import TicketDetailPanel from '../components/TicketDetailPanel'
import AgentLogin from '../components/AgentLogin'
import './AgentDashboard.css'

const AGENT_NAME = 'Amy'
const TOKEN_KEY = 'livedesk_agent_token'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'unassigned', label: 'Unassigned' },
  { key: 'urgent', label: 'Urgent' },
]

function matchesFilter(convo, filterKey) {
  if (filterKey === 'unassigned') return !convo.assigned_to
  if (filterKey === 'urgent') return convo.priority === 'urgent'
  return true
}

function relativeTime(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes}min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function AgentDashboard() {
  const [agentToken, setAgentToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || '')
  const [authError, setAuthError] = useState('')
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [presence, setPresence] = useState({}) // conversation_id -> 'online' | 'offline'
  const [unread, setUnread] = useState({}) // conversation_id -> count
  const [filter, setFilter] = useState('all')
  const wsRef = useRef(null)
  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId

  const handleLogin = (token) => {
    sessionStorage.setItem(TOKEN_KEY, token)
    setAuthError('')
    setAgentToken(token)
  }

  useEffect(() => {
    if (!agentToken) return
    listConversations().then(setConversations).catch(() => {})
  }, [agentToken])

  useEffect(() => {
    if (!agentToken) return

    // Guarded against React StrictMode's dev-only double-mount: closing a
    // socket mid-handshake doesn't stop it from connecting, so without this
    // flag a stray duplicate connection would double-count unread badges.
    let cancelled = false
    let ws = null
    let attempt = 0
    let reconnectTimer = null

    const connect = () => {
      if (cancelled) return
      ws = new WebSocket(
        `${WS_BASE}/ws/agents?name=${encodeURIComponent(AGENT_NAME)}&token=${encodeURIComponent(agentToken)}`
      )
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) {
          ws.close()
          return
        }
        attempt = 0
      }

      ws.onclose = (evt) => {
        if (cancelled) return

        // 4401 = the token was rejected server-side — bounce back to the
        // login screen instead of retrying with a token that won't work.
        if (evt.code === 4401) {
          sessionStorage.removeItem(TOKEN_KEY)
          setAuthError('That token was rejected. Check AGENT_TOKEN in the backend and try again.')
          setAgentToken('')
          return
        }

        // Any other drop (network hiccup, tab backgrounded, laptop sleep)
        // reconnects with backoff instead of silently leaving the sidebar
        // — presence, new tickets, unread badges — stale until a manual
        // page refresh.
        const delay = Math.min(1000 * 2 ** attempt, 8000)
        attempt += 1
        reconnectTimer = setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }

      ws.onmessage = (evt) => {
        if (cancelled) return
        const event = JSON.parse(evt.data)

        if (event.type === 'presence') {
          setPresence((prev) => ({ ...prev, [event.conversation_id]: event.status }))
        }

        if (event.type === 'new_activity') {
          setConversations((prev) => {
            if (prev.some((c) => c.id === event.conversation_id)) return prev
            return [
              {
                id: event.conversation_id,
                client_name: event.client_name,
                created_at: new Date().toISOString(),
                // Matches the backend's own defaults for a freshly created
                // conversation — kept in sync until the next full refetch.
                status: 'open',
                priority: 'medium',
                assigned_to: null,
              },
              ...prev,
            ]
          })
          setPresence((prev) => ({ ...prev, [event.conversation_id]: 'online' }))
        }

        if (event.type === 'new_message') {
          setUnread((prev) => {
            if (event.conversation_id === activeIdRef.current) return prev
            return { ...prev, [event.conversation_id]: (prev[event.conversation_id] || 0) + 1 }
          })
        }

        // Another agent (or this same one, echoed back) changed a ticket's
        // status/priority/assignment — keep every connected dashboard in sync
        // instead of only updating on the next page load.
        if (event.type === 'ticket_updated') {
          setConversations((prev) =>
            prev.map((c) =>
              c.id === event.conversation_id
                ? { ...c, status: event.status, priority: event.priority, assigned_to: event.assigned_to }
                : c
            )
          )
        }
      }
    }

    connect()

    return () => {
      cancelled = true
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [agentToken])

  const openConversation = (id) => {
    setActiveId(id)
    setUnread((prev) => ({ ...prev, [id]: 0 }))
    // Opening an unassigned ticket claims it — mirrors how a real agent
    // "picks up" a ticket from the queue. Persisted on the backend; the
    // UI updates when the resulting ticket_updated event comes back.
    const convo = conversations.find((c) => c.id === id)
    if (convo && !convo.assigned_to) {
      updateConversation(id, { assigned_to: AGENT_NAME }, agentToken).catch(() => {})
    }
  }

  const updateTicket = (id, patch) => {
    updateConversation(id, patch, agentToken).catch(() => {})
  }

  const activeConvo = conversations.find((c) => c.id === activeId)
  const visibleConversations = conversations.filter((c) => matchesFilter(c, filter))

  const openCount = conversations.filter((c) => c.status !== 'resolved').length
  const unassignedCount = conversations.filter((c) => !c.assigned_to).length
  const urgentCount = conversations.filter((c) => c.priority === 'urgent').length

  if (!agentToken) {
    return <AgentLogin onSubmit={handleLogin} error={authError} />
  }

  return (
    <div className="dashboard">
      <aside className="dashboard__sidebar">
        <div className="dashboard__brand">
          <span className="status-dot online" />
          <span className="mono">LIVEDESK // AGENT</span>
        </div>

        <div className="dashboard__metrics">
          <div className="metric">
            <span className="metric__value mono">{openCount}</span>
            <span className="metric__label">open</span>
          </div>
          <div className="metric">
            <span className="metric__value mono">{unassignedCount}</span>
            <span className="metric__label">in queue</span>
          </div>
          <div className="metric metric--urgent">
            <span className="metric__value mono">{urgentCount}</span>
            <span className="metric__label">urgent</span>
          </div>
        </div>

        <div className="dashboard__filters">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`filter-chip ${filter === f.key ? 'filter-chip--active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="dashboard__list scrollbar-thin">
          {visibleConversations.length === 0 && (
            <p className="dashboard__empty">No tickets here.</p>
          )}
          {visibleConversations.map((c) => (
            <button
              key={c.id}
              className={`convo-row ${c.id === activeId ? 'convo-row--active' : ''}`}
              onClick={() => openConversation(c.id)}
            >
              <span className={`status-dot ${presence[c.id] === 'online' ? 'online' : ''}`} />
              <span className="convo-row__body">
                <span className="convo-row__name">{c.client_name}</span>
                <span className={`priority-pill priority-pill--${c.priority}`}>{c.priority}</span>
              </span>
              {unread[c.id] > 0 && <span className="convo-row__badge">{unread[c.id]}</span>}
            </button>
          ))}
        </div>
      </aside>

      <main className="dashboard__main">
        {activeConvo ? (
          <ChatPanel
            key={activeConvo.id}
            conversationId={activeConvo.id}
            role="agent"
            name={AGENT_NAME}
            token={agentToken}
            placeholder={`Reply to ${activeConvo.client_name}…`}
          />
        ) : (
          <div className="dashboard__placeholder">
            <p>Select a ticket to work on.</p>
          </div>
        )}
      </main>

      {activeConvo && (
        <TicketDetailPanel
          conversation={activeConvo}
          openedLabel={relativeTime(activeConvo.created_at)}
          onChange={(patch) => updateTicket(activeConvo.id, patch)}
        />
      )}
    </div>
  )
}