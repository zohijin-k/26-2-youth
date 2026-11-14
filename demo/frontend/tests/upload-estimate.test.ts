import assert from 'node:assert/strict'
import { estimateSeconds, slowThresholdSec, rememberObservation } from '../src/lib/upload-estimate.ts'
assert.equal(estimateSeconds('image', 1, []), null)
const history = [{kind: 'pdf-scan' as const, pages: 2, ms: 10000}]
assert.equal(estimateSeconds('pdf-scan', 3, history), 15)
assert.equal(estimateSeconds('image', 1, history), null)
assert.equal(estimateSeconds('image', 1, [{kind: 'image', pages: 1, ms: NaN}]), null)
assert.equal(slowThresholdSec(null), 10)
assert.equal(slowThresholdSec(2), 3)
assert.equal(slowThresholdSec(20), 10)
assert.equal(rememberObservation(Array(20).fill(history[0]), history[0]).length, 20)
