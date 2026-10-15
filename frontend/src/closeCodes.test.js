import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isRejection, CLOSE_BAD_REQUEST, CLOSE_UNAUTHORIZED, CLOSE_NOT_FOUND } from './closeCodes.js'

test('server rejections are final, so the socket must not retry them', () => {
  for (const code of [CLOSE_BAD_REQUEST, CLOSE_UNAUTHORIZED, CLOSE_NOT_FOUND]) {
    assert.equal(isRejection(code), true)
  }
})

test('ordinary drops are still retried', () => {
  // 1000 normal, 1001 going away, 1006 abnormal (wifi drop), 1011 server error, 1012 restart
  for (const code of [1000, 1001, 1006, 1011, 1012]) {
    assert.equal(isRejection(code), false)
  }
})
