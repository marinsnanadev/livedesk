export function lastActivity(conversation) {
  return conversation.last_message_at || conversation.created_at
}

export function sortByActivity(conversations) {
  return [...conversations].sort((a, b) => new Date(lastActivity(b)) - new Date(lastActivity(a)))
}

// The fetched list is the source of truth for what it contains. A ticket we
// only know from a live event showed up after that fetch ran, so it is kept.
export function mergeConversations(fetched, current) {
  const known = new Set(fetched.map((c) => c.id))
  return [...current.filter((c) => !known.has(c.id)), ...fetched]
}

export function withNewMessage(conversations, event) {
  return conversations.map((c) =>
    c.id === event.conversation_id
      ? {
          ...c,
          last_message_at: event.created_at,
          last_message_preview: event.preview,
          last_sender_role: event.sender_role,
        }
      : c
  )
}
