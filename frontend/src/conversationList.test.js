import { test } from 'node:test'
import assert from 'node:assert/strict'
import { lastActivity, sortByActivity, mergeConversations, withNewMessage } from './conversationList.js'

const ticket = (id, createdAt, lastMessageAt = null) => ({
  id,
  created_at: createdAt,
  last_message_at: lastMessageAt,
})
const ids = (list) => list.map((c) => c.id)

test('tickets are ordered by their latest message, not by when they were created', () => {
  const old = ticket('old', '2026-10-01T10:00:00+00:00', '2026-10-22T09:00:00+00:00')
  const recent = ticket('recent', '2026-10-20T10:00:00+00:00', '2026-10-20T10:05:00+00:00')
  assert.deepEqual(ids(sortByActivity([recent, old])), ['old', 'recent'])
})

test('a ticket without a last message falls back to its creation time', () => {
  const fresh = ticket('fresh', '2026-10-22T10:00:00+00:00')
  assert.equal(lastActivity(fresh), '2026-10-22T10:00:00+00:00')
  const stale = ticket('stale', '2026-10-01T10:00:00+00:00', '2026-10-02T10:00:00+00:00')
  assert.deepEqual(ids(sortByActivity([stale, fresh])), ['fresh', 'stale'])
})

test('sorting leaves the original list untouched', () => {
  const list = [ticket('a', '2026-10-01T00:00:00+00:00'), ticket('b', '2026-10-02T00:00:00+00:00')]
  sortByActivity(list)
  assert.deepEqual(ids(list), ['a', 'b'])
})

test('a ticket known only from a live event survives a refetch', () => {
  const merged = mergeConversations(
    [ticket('a', '2026-10-01T00:00:00+00:00')],
    [ticket('live', '2026-10-22T00:00:00+00:00')],
  )
  assert.deepEqual(ids(merged).sort(), ['a', 'live'])
})

test('the fetched copy wins for a ticket present in both', () => {
  const merged = mergeConversations([{ id: 'a', status: 'resolved' }], [{ id: 'a', status: 'open' }])
  assert.deepEqual(merged, [{ id: 'a', status: 'resolved' }])
})

test('a new message updates only its own ticket', () => {
  const event = {
    conversation_id: 'a',
    created_at: '2026-10-22T11:00:00+00:00',
    preview: 'hi there',
    sender_role: 'client',
  }
  const [a, b] = withNewMessage(
    [ticket('a', '2026-10-01T00:00:00+00:00'), ticket('b', '2026-10-01T00:00:00+00:00')],
    event,
  )
  assert.equal(a.last_message_preview, 'hi there')
  assert.equal(a.last_message_at, '2026-10-22T11:00:00+00:00')
  assert.equal(a.last_sender_role, 'client')
  assert.equal(b.last_message_preview, undefined)
})
