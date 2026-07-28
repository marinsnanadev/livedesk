import './TicketDetailPanel.css'

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
]

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
]

export default function TicketDetailPanel({ conversation, openedLabel, onChange }) {
  return (
    <aside className="ticket-panel">
      <div className="ticket-panel__section">
        <span className="ticket-panel__eyebrow mono">TICKET</span>
        <h2 className="ticket-panel__client">{conversation.client_name}</h2>
        <span className="ticket-panel__opened mono">opened {openedLabel}</span>
      </div>

      <div className="ticket-panel__section">
        <label className="ticket-panel__label" htmlFor="ticket-status">Status</label>
        <select
          id="ticket-status"
          className={`ticket-panel__select ticket-panel__select--status-${conversation.status}`}
          value={conversation.status}
          onChange={(e) => onChange({ status: e.target.value })}
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="ticket-panel__section">
        <label className="ticket-panel__label" htmlFor="ticket-priority">Priority</label>
        <select
          id="ticket-priority"
          className={`ticket-panel__select ticket-panel__select--priority-${conversation.priority}`}
          value={conversation.priority}
          onChange={(e) => onChange({ priority: e.target.value })}
        >
          {PRIORITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="ticket-panel__section">
        <span className="ticket-panel__label">Assigned to</span>
        <p className="ticket-panel__value">{conversation.assigned_to || 'Nobody yet'}</p>
      </div>
    </aside>
  )
}