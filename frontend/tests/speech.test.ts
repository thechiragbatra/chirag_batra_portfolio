import assert from 'node:assert/strict'
import { test } from 'node:test'
import { speakable } from '../src/features/guide/speech.ts'

test('drops citations in both bracket styles, bold markers and bullets', () => {
  const answer = 'He built **RADAR** [S1][S2].\n- Fraud recall 89.6% 【S3】\n- Latency 0.4 ms [S4†L2]'
  assert.equal(speakable(answer), 'He built RADAR. Fraud recall 89.6% Latency 0.4 ms')
})

test('drops bold citations too', () => {
  assert.equal(speakable('He knows causal inference [**S1**].'), 'He knows causal inference.')
})
