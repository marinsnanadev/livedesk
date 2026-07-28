import { useState } from 'react'
import './AgentLogin.css'

export default function AgentLogin({ onSubmit, error }) {
  const [value, setValue] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!value.trim()) return
    onSubmit(value.trim())
  }

  return (
    <div className="agent-login">
      <form className="agent-login__card" onSubmit={handleSubmit}>
        <span className="agent-login__eyebrow mono">LIVEDESK // AGENT</span>
        <h1>Enter your agent token</h1>
        <p className="agent-login__hint">
          Set locally via <code>AGENT_TOKEN</code> in the backend's <code>.env</code>.
          See <code>backend/.env.example</code>.
        </p>
        <input
          className="agent-login__input mono"
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="agent token"
        />
        {error && <p className="agent-login__error">{error}</p>}
        <button className="agent-login__submit" type="submit" disabled={!value.trim()}>
          Connect
        </button>
      </form>
    </div>
  )
}
