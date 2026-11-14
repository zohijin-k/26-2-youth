import {
  GENERIC_ERROR_COPY,
  NETWORK_ERROR_COPY,
  NOT_FOUND_COPY,
  SERVER_ERROR_COPY,
  friendlyError,
  isCitizenSafe,
  statusOfMessage,
} from './error-copy.ts'

function expect(label: string, actual: unknown, expected: unknown): void {
  if (actual !== expected) throw new Error(`${label} returned ${String(actual)}, expected ${String(expected)}`)
}

const FALLBACK = '본인인증을 마치지 못했습니다. 다시 시도해 주세요.'

const cases: Array<[string, unknown, string]> = [
  ['network TypeError', new TypeError('Failed to fetch'), NETWORK_ERROR_COPY],
  ['network message', new Error('NetworkError when attempting to fetch resource.'), NETWORK_ERROR_COPY],
  ['server 500 with path', new Error('GET /api/applications/3 실패 (500)'), SERVER_ERROR_COPY],
  ['not found', new Error('본인인증 실패 (404)'), NOT_FOUND_COPY],
  ['forbidden', new Error('본인인증 실패 (403)'), NOT_FOUND_COPY],
  ['other status falls back', new Error('본인인증 실패 (422)'), FALLBACK],
  ['server Korean detail', new Error('생년월일을 다시 확인해 주세요.'), '생년월일을 다시 확인해 주세요.'],
  ['technical text', new Error('Traceback (most recent call last)'), FALLBACK],
  ['non-Korean detail', new Error('[object Object]'), FALLBACK],
  ['string error', '잠시 후 다시 시도해 주세요.', '잠시 후 다시 시도해 주세요.'],
  ['unknown value', 42, FALLBACK],
]
for (const [label, input, expected] of cases) expect(`friendlyError(${label})`, friendlyError(input, FALLBACK), expected)

expect('unsafe fallback', friendlyError(42, 'POST /api/x failed'), GENERIC_ERROR_COPY)
expect('statusOfMessage', statusOfMessage('업로드 실패 (413)'), 413)
expect('statusOfMessage none', statusOfMessage('업로드하지 못했습니다.'), null)
expect('isCitizenSafe Korean', isCitizenSafe('파일을 다시 골라 주세요.'), true)
expect('isCitizenSafe path', isCitizenSafe('GET /api/postings 실패'), false)
expect('isCitizenSafe status', isCitizenSafe('요청을 처리하지 못했습니다 (500)'), false)
expect('isCitizenSafe empty', isCitizenSafe('  '), false)
