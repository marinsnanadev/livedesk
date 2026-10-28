import { useState } from 'react'
import './AgentLogin.css'

export default function AgentLogin({ onSubmit, error, initialName = '' }) {
  const [name, setName] = useState(initialName)
  const [token, setToken] = useState('')
  const canSubmit = name.trim() && token.trim()

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit({ name: name.trim(), token: token.trim() })
  }

  return (
    <div className="agent-login">
      <form className="agent-login__card" onSubmit={handleSubmit}>
        <span className="agent-login__eyebrow mono">LIVEDESK // AGENT</span>
        <h1>Sign in as an agent</h1>
        <p className="agent-login__hint">
          Your name is what customers see on your replies. The token is <code>AGENT_TOKEN</code> from the
          backend's <code>.env</code> (see <code>backend/.env.example</code>).
        </p>
        <input
          className="agent-login__input"
          type="text"
          autoFocus={!initialName}
          maxLength={30}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="your name"
          aria-label="Your name"
        />
        <input
          className="agent-login__input mono"
          type="password"
          autoFocus={Boolean(initialName)}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="agent token"
          aria-label="Agent token"
        />
        {error && <p className="agent-login__error">{error}</p>}
        <button className="agent-login__submit" type="submit" disabled={!canSubmit}>
          Connect
        </button>
      </form>
    </div>
  )
}
