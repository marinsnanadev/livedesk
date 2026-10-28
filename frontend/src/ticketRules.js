// Opening a ticket from the queue claims it for the agent. A resolved ticket
// is only being looked at, and one that already has an owner isn't ours to take.
export function shouldClaimOnOpen(conversation) {
  return !conversation.assigned_to && conversation.status !== 'resolved'
}
