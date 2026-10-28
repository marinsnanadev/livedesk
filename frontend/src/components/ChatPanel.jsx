import { useCallback, useEffect, useRef, useState } from 'react'
import { getMessages } from '../api'
import { useConversationSocket } from '../useConversationSocket'
import { useTypingSignal } from '../useTypingSignal'
import { mergeHistory } from '../mergeMessages'
import './ChatPanel.css'

export default function ChatPanel({ conversationId, role, name, token, placeholder, onRejected }) {
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [peerTyping, setPeerTyping] = useState(false)
  const scrollRef = useRef(null)

  const handleIncoming = (event) => {
    if (event.type === 'message') {
      setMessages((prev) => (prev.some((m) => m.id === event.id) ? prev : [...prev, event]))
      setPeerTyping(false)
    } else if (event.type === 'typing') {
      setPeerTyping(Boolean(event.is_typing))
    }
  }

  const { connected, send } = useConversationSocket({
    conversationId,
    role,
    name,
    token,
    onMessage: handleIncoming,
    onRejected,
  })

  // If our own connection drops we stop hearing the other side, so a
  // "typing…" shown before the drop could never be cleared.
  useEffect(() => {
    if (!connected) setPeerTyping(false)
  }, [connected])
  const { notifyTyping, notifyStopped } = useTypingSignal(send)

  const loadHistory = useCallback(() => {
    if (!conversationId) return
    getMessages(conversationId, role, token)
      .then((history) => setMessages((current) => mergeHistory(history, current)))
      .catch(() => {})
  }, [conversationId, role, token])

  // Refetch on every (re)connect: whatever was sent while the socket was down
  // never comes back through it, and the first fetch can run before the
  // socket has joined the room, leaving a gap in between.
  useEffect(() => {
    loadHistory()
  }, [loadHistory, connected])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, peerTyping])

  const handleSend = () => {
    const body = draft.trim()
    if (!body) return
    if (!send({ type: 'message', body })) return
    notifyStopped()
    setDraft('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel__status mono">
        <span className={`status-dot ${connected ? 'online' : ''}`} />
        {connected ? 'CONNECTED' : 'RECONNECTING…'}
      </div>

      <div className="chat-panel__messages scrollbar-thin" ref={scrollRef}>
        {messages.length === 0 && <p className="chat-panel__empty">No messages yet. Say hi.</p>}
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.sender_role === role ? 'bubble--mine' : 'bubble--theirs'}`}>
            <span className="bubble__meta mono">{m.sender_name}</span>
            <p>{m.body}</p>
          </div>
        ))}
        {peerTyping && (
          <div className="typing-indicator">
            <span className="status-dot typing" />
            typing…
          </div>
        )}
      </div>

      <div className="chat-panel__composer">
        <textarea
          value={draft}
          placeholder={placeholder || 'Write a message…'}
          onChange={(e) => {
            setDraft(e.target.value)
            if (e.target.value) notifyTyping()
            else notifyStopped()
          }}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button className="chat-panel__send" onClick={handleSend} disabled={!draft.trim() || !connected}>
          Send
        </button>
      </div>
    </div>
  )
}
