import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseSse } from '../src/features/guide/sse.ts'

test('parses complete events and keeps the partial tail', () => {
  const { events, rest } = parseSse('data: {"type":"token","text":"Hi"}\n\ndata: {"type":"do')
  assert.deepEqual(events, [{ type: 'token', text: 'Hi' }])
  assert.equal(rest, 'data: {"type":"do')
  const next = parseSse(rest + 'ne"}\n\n')
  assert.deepEqual(next.events, [{ type: 'done' }])
  assert.equal(next.rest, '')
})

test('ignores keep-alive comments and blank blocks', () => {
  const { events } = parseSse(': keep-alive\n\n\n\ndata: {"a":1}\n\n')
  assert.deepEqual(events, [{ a: 1 }])
})

test('joins multi-line data fields', () => {
  const { events } = parseSse('data: {"text":\ndata: "x"}\n\n')
  assert.deepEqual(events, [{ text: 'x' }])
})
