// History from the server is the source of truth for everything already
// persisted. Anything we only know from the socket (it was committed after
// that fetch ran) is newer, so it goes after.
export function mergeHistory(history, current) {
  const known = new Set(history.map((m) => m.id))
  return [...history, ...current.filter((m) => !known.has(m.id))]
}
