import { useEffect, useRef, useState } from 'react'
import { createConversation, getOnlineAgentCount } from '../api'
import { CLOSE_BAD_REQUEST } from '../closeCodes'
import ChatPanel from '../components/ChatPanel'
import './ClientWidget.css'

const NAME_KEY = 'livedesk_client_name'
const CONVO_KEY = 'livedesk_conversation_id'
const CLIENT_TOKEN_KEY = 'livedesk_client_token'
const AGENT_COUNT_POLL_MS = 20000

// Fictional backdrop content — just enough for the widget to feel like
// it's embedded on a real product site instead of floating in a void.
const FEATURES = [
  { title: 'Real-time boards', body: 'Watch the team work live, no need to refresh the page.' },
  { title: 'Routine automation', body: 'Simple rules handle the repetitive stuff, your team handles what matters.' },
  { title: 'Automatic reports', body: 'A weekly summary, ready every Monday at 8am.' },
]

export default function ClientWidget() {
  const [open, setOpen] = useState(false)
  const [conversationId, setConversationId] = useState(sessionStorage.getItem(CONVO_KEY))
  const [clientToken, setClientToken] = useState(sessionStorage.getItem(CLIENT_TOKEN_KEY))
  const [onlineAgentCount, setOnlineAgentCount] = useState(null)
  const recoveredRef = useRef(false)
  const [name] = useState(() => {
    const existing = sessionStorage.getItem(NAME_KEY)
    if (existing) return existing
    const generated = `Visitor ${Math.floor(Math.random() * 900 + 100)}`
    sessionStorage.setItem(NAME_KEY, generated)
    return generated
  })

  useEffect(() => {
    if (!open || (conversationId && clientToken)) return
    createConversation(name).then((c) => {
      setConversationId(c.id)
      setClientToken(c.client_token)
      sessionStorage.setItem(CONVO_KEY, c.id)
      sessionStorage.setItem(CLIENT_TOKEN_KEY, c.client_token)
    })
  }, [open, conversationId, clientToken, name])

  useEffect(() => {
    // Was a hardcoded "3 agents online now" regardless of whether anyone
    // was actually connected. Polls instead of a live socket since it's
    // a minor bit of copy, not worth a dedicated connection.
    let cancelled = false
    const poll = () => {
      getOnlineAgentCount()
        .then(({ count }) => {
          if (!cancelled) setOnlineAgentCount(count)
        })
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, AGENT_COUNT_POLL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  // The stored conversation is gone or no longer ours (e.g. the backend's
  // database was reset), so start a fresh one. Only once per page load, so a
  // server that keeps refusing can't make this create conversations in a loop.
  const handleRejected = (code) => {
    if (code === CLOSE_BAD_REQUEST || recoveredRef.current) return
    recoveredRef.current = true
    sessionStorage.removeItem(CONVO_KEY)
    sessionStorage.removeItem(CLIENT_TOKEN_KEY)
    setConversationId(null)
    setClientToken(null)
  }

  return (
    <div className="widget-stage">
      <p className="widget-stage__hint mono">SIMULATION — CLIENT VIEW</p>

      <header className="site-header">
        <span className="site-header__logo">orbit</span>
        <nav className="site-header__nav">
          <span>Product</span>
          <span>Pricing</span>
          <span>Help center</span>
        </nav>
      </header>

      <section className="site-hero">
        <h1>Organize your team without losing the rhythm.</h1>
        <p>Orbit brings tasks, deadlines, and conversations into one place — so nobody ever asks "hey, whatever happened with that?" again.</p>
        <button className="site-hero__cta">Start for free</button>
      </section>

      <section className="site-features">
        {FEATURES.map((f) => (
          <div className="feature-card" key={f.title}>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </section>

      {open && (
        <div className="widget-window">
          <div className="widget-window__header">
            <span>Talk to support</span>
            <button onClick={() => setOpen(false)} aria-label="Close chat">✕</button>
          </div>
          <div className="widget-window__body">
            {conversationId && clientToken ? (
              <ChatPanel
                conversationId={conversationId}
                role="client"
                name={name}
                token={clientToken}
                placeholder="How can we help?"
                onRejected={handleRejected}
              />
            ) : (
              <p className="widget-window__loading">Connecting…</p>
            )}
          </div>
        </div>
      )}

      {!open && (
        <div className="support-callout">
          <div className="support-callout__bubble">
            <span className={`status-dot ${onlineAgentCount > 0 ? 'online' : ''}`} />
            <span>
              {onlineAgentCount > 0
                ? `${onlineAgentCount} agent${onlineAgentCount === 1 ? '' : 's'} online now`
                : "We'll get back to you soon"}
            </span>
          </div>
          <button className="widget-launcher" onClick={() => setOpen(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 4H20V16H7L4 19V4Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            </svg>
            Request support
          </button>
        </div>
      )}
    </div>
  )
}