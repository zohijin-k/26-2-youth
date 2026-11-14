import assert from 'node:assert/strict'
import { readReceiptSteps } from '../src/lib/receipt-steps.ts'
assert.deepEqual(readReceiptSteps(null), [])
assert.deepEqual(readReceiptSteps('{'), [])
assert.deepEqual(readReceiptSteps('{"steps":[]}'), [])
assert.deepEqual(readReceiptSteps('["안내",3]'), [])
assert.deepEqual(readReceiptSteps('["서류 검토","결과 안내"]'), ['서류 검토', '결과 안내'])
