import { useEffect, useState } from 'react'
import { createConversation, getOnlineAgentCount } from '../api'
import ChatPanel from '../components/ChatPanel'
import './ClientWidget.css'

const NAME_KEY = 'livedesk_client_name'
const CONVO_KEY = 'livedesk_conversation_id'
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
  const [onlineAgentCount, setOnlineAgentCount] = useState(null)
  const [name] = useState(() => {
    const existing = sessionStorage.getItem(NAME_KEY)
    if (existing) return existing
    const generated = `Visitor ${Math.floor(Math.random() * 900 + 100)}`
    sessionStorage.setItem(NAME_KEY, generated)
    return generated
  })

  useEffect(() => {
    if (!open || conversationId) return
    createConversation(name).then((c) => {
      setConversationId(c.id)
      sessionStorage.setItem(CONVO_KEY, c.id)
    })
  }, [open, conversationId, name])

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
            {conversationId ? (
              <ChatPanel conversationId={conversationId} role="client" name={name} placeholder="How can we help?" />
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