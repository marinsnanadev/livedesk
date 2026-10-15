import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mergeHistory } from './mergeMessages.js'

const msg = (id) => ({ id, body: `message ${id}` })
const ids = (list) => list.map((m) => m.id)

test('a message that arrived over the socket before the fetch resolved is kept', () => {
  assert.deepEqual(ids(mergeHistory([msg('a')], [msg('b')])), ['a', 'b'])
})

test('a message present in both is not duplicated', () => {
  assert.deepEqual(ids(mergeHistory([msg('a'), msg('b')], [msg('b')])), ['a', 'b'])
})

test('messages missed while the socket was down show up from the history', () => {
  assert.deepEqual(ids(mergeHistory([msg('a'), msg('b'), msg('c')], [msg('a')])), ['a', 'b', 'c'])
})

test('an older fetch resolving late does not drop or reorder newer messages', () => {
  const current = [msg('a'), msg('b'), msg('c')]
  assert.deepEqual(ids(mergeHistory([msg('a')], current)), ['a', 'b', 'c'])
})
