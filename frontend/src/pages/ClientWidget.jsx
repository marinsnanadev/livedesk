import { useEffect, useRef, useState } from 'react'
import { createConversation, getOnlineAgentCount } from '../api'
import { CLOSE_BAD_REQUEST } from '../closeCodes'
import ChatPanel from '../components/ChatPanel'
import './ClientWidget.css'

const NAME_KEY = 'livedesk_client_name'
const CONVO_KEY = 'livedesk_conversation_id'
const CLIENT_TOKEN_KEY = 'livedesk_client_token'
const AGENT_COUNT_POLL_MS = 20000

export default function ClientWidget() {
  const [open, setOpen] = useState(false)
  const [conversationId, setConversationId] = useState(sessionStorage.getItem(CONVO_KEY))
  const [clientToken, setClientToken] = useState(sessionStorage.getItem(CLIENT_TOKEN_KEY))
  const [onlineAgentCount, setOnlineAgentCount] = useState(null)
  const [startFailed, setStartFailed] = useState(false)
  const [startAttempt, setStartAttempt] = useState(0)
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
    createConversation(name)
      .then((c) => {
        setConversationId(c.id)
        setClientToken(c.client_token)
        sessionStorage.setItem(CONVO_KEY, c.id)
        sessionStorage.setItem(CLIENT_TOKEN_KEY, c.client_token)
      })
      .catch(() => setStartFailed(true))
  }, [open, conversationId, clientToken, name, startAttempt])

  const retryStart = () => {
    setStartFailed(false)
    setStartAttempt((n) => n + 1)
  }

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
      <header className="widget-header">
        <span className="widget-header__brand">livedesk</span>
        <span className="widget-header__context">Customer support</span>
      </header>

      {!open && (
        <main className="support-home">
          <section className="support-card" aria-labelledby="support-title">
            <p className="support-card__label">We're here to help</p>
            <h1 id="support-title">What can we help you with?</h1>
            <p className="support-card__description">
              Send our team a message and we’ll help you find an answer.
            </p>
            <div className="support-card__availability">
              <span className={`status-dot ${onlineAgentCount > 0 ? 'online' : ''}`} />
              <span>
                {onlineAgentCount > 0
                  ? `${onlineAgentCount} agent${onlineAgentCount === 1 ? '' : 's'} online`
                  : "Our team will get back to you soon"}
              </span>
            </div>
            <button className="support-request-button" onClick={() => setOpen(true)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M4 4H20V16H7L4 19V4Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
              </svg>
              Request support
            </button>
          </section>
        </main>
      )}

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
            ) : startFailed ? (
              <div className="widget-window__error" role="alert">
                <p>We couldn't start the chat.</p>
                <button onClick={retryStart}>Try again</button>
              </div>
            ) : (
              <p className="widget-window__loading">Connecting…</p>
            )}
          </div>
        </div>
      )}

    </div>
  )
}