import { useEffect, useRef, useState } from 'react'
import { listConversations, WS_BASE } from '../api'
import { useReconnectingSocket } from '../useReconnectingSocket'
import ChatPanel from '../components/ChatPanel'
import TicketDetailPanel from '../components/TicketDetailPanel'
import './AgentDashboard.css'

const AGENT_NAME = 'Nana'

// NOTE: ticketStatus / priority / assignedTo are LOCAL-ONLY for now —
// the backend doesn't persist these fields yet. They live in this
// component's state so we can shape the UI before touching the schema.
// Once the direction is approved, these move into the Conversation
// model on the backend and get loaded from the API instead of defaulted
// here.
const DEFAULT_TICKET_FIELDS = { ticketStatus: 'open', priority: 'medium', assignedTo: null }

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'unassigned', label: 'Unassigned' },
  { key: 'urgent', label: 'Urgent' },
]

function matchesFilter(convo, filterKey) {
  if (filterKey === 'unassigned') return !convo.assignedTo
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
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [presence, setPresence] = useState({}) // conversation_id -> 'online' | 'offline'
  const [unread, setUnread] = useState({}) // conversation_id -> count
  const [filter, setFilter] = useState('all')
  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId

  useEffect(() => {
    listConversations().then((list) => {
      setConversations(list.map((c) => ({ ...c, ...DEFAULT_TICKET_FIELDS })))
    }).catch(() => {})
  }, [])

  const handleAgentEvent = (event) => {
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
            ...DEFAULT_TICKET_FIELDS,
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
  }

  // Reconnects with backoff on drop — see useReconnectingSocket for why
  // this matters. Without it, a dropped agents-feed socket used to leave
  // the sidebar (presence, new tickets, unread badges) silently stale
  // until a manual page refresh.
  useReconnectingSocket(`${WS_BASE}/ws/agents?name=${encodeURIComponent(AGENT_NAME)}`, handleAgentEvent)

  const openConversation = (id) => {
    setActiveId(id)
    setUnread((prev) => ({ ...prev, [id]: 0 }))
    // Opening an unassigned ticket claims it — mirrors how a real agent
    // "picks up" a ticket from the queue.
    setConversations((prev) =>
      prev.map((c) => (c.id === id && !c.assignedTo ? { ...c, assignedTo: AGENT_NAME } : c))
    )
  }

  const updateTicket = (id, patch) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  }

  const activeConvo = conversations.find((c) => c.id === activeId)
  const visibleConversations = conversations.filter((c) => matchesFilter(c, filter))

  const openCount = conversations.filter((c) => c.ticketStatus !== 'resolved').length
  const unassignedCount = conversations.filter((c) => !c.assignedTo).length
  const urgentCount = conversations.filter((c) => c.priority === 'urgent').length

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