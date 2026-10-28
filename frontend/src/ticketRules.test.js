import { test } from 'node:test'
import assert from 'node:assert/strict'
import { shouldClaimOnOpen } from './ticketRules.js'

test('an unassigned open or in-progress ticket is claimed when opened', () => {
  assert.equal(shouldClaimOnOpen({ assigned_to: null, status: 'open' }), true)
  assert.equal(shouldClaimOnOpen({ assigned_to: null, status: 'in_progress' }), true)
})

test('a ticket that already has an owner is left alone', () => {
  assert.equal(shouldClaimOnOpen({ assigned_to: 'Bruna', status: 'open' }), false)
})

test('a resolved ticket is never claimed just by looking at it', () => {
  assert.equal(shouldClaimOnOpen({ assigned_to: null, status: 'resolved' }), false)
})
