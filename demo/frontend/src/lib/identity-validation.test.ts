import {
  IDENTITY_ERROR_COPY,
  firstInvalidField,
  validateBirth,
  validateIdentity,
  validateName,
  validatePhone,
  type CalendarDay,
} from './identity-validation.ts'

function expect(label: string, actual: unknown, expected: unknown): void {
  if (actual !== expected) throw new Error(`${label} returned ${String(actual)}, expected ${String(expected)}`)
}

const TODAY: CalendarDay = { year: 2026, month: 11, day: 14 }

expect('name empty', validateName('  '), IDENTITY_ERROR_COPY.name)
expect('name ok', validateName('가상신청'), null)

const births: Array<[string, { y: string; m: string; d: string }, string | null]> = [
  ['empty', { y: '', m: '', d: '' }, IDENTITY_ERROR_COPY.birthMissing],
  ['partial', { y: '2000', m: '5', d: '' }, IDENTITY_ERROR_COPY.birthMissing],
  ['ok', { y: '2000', m: '5', d: '15' }, null],
  ['two-digit parts', { y: '2000', m: '05', d: '09' }, null],
  ['short year', { y: '200', m: '5', d: '15' }, IDENTITY_ERROR_COPY.birthInvalid],
  ['month 13', { y: '2000', m: '13', d: '1' }, IDENTITY_ERROR_COPY.birthInvalid],
  ['Feb 30', { y: '2001', m: '2', d: '30' }, IDENTITY_ERROR_COPY.birthInvalid],
  ['leap day', { y: '2000', m: '2', d: '29' }, null],
  ['non-leap century', { y: '1900', m: '2', d: '29' }, IDENTITY_ERROR_COPY.birthInvalid],
  ['before 1900', { y: '1899', m: '12', d: '31' }, IDENTITY_ERROR_COPY.birthInvalid],
  ['today', { y: '2026', m: '11', d: '14' }, null],
  ['tomorrow', { y: '2026', m: '11', d: '15' }, IDENTITY_ERROR_COPY.birthInvalid],
]
for (const [label, birth, expected] of births) expect(`validateBirth(${label})`, validateBirth(birth, TODAY), expected)

expect('phone ok', validatePhone('010-1234-5678'), null)
expect('phone 011', validatePhone('011-1234-5678'), IDENTITY_ERROR_COPY.phone)
expect('phone short', validatePhone('010-1234-567'), IDENTITY_ERROR_COPY.phone)

const empty = validateIdentity({ name: '', birth: { y: '', m: '', d: '' }, phone: '', pledge: false, signature: '' }, TODAY)
expect('all missing count', Object.keys(empty).length, 5)
expect('first invalid is name', firstInvalidField(empty), 'name')

const onlySignature = validateIdentity({ name: '가상신청', birth: { y: '2000', m: '5', d: '15' }, phone: '010-1234-5678', pledge: true, signature: '' }, TODAY)
expect('only signature missing', Object.keys(onlySignature).join(','), 'signature')
expect('first invalid is signature', firstInvalidField(onlySignature), 'signature')

const ready = validateIdentity({ name: '가상신청', birth: { y: '2000', m: '5', d: '15' }, phone: '010-1234-5678', pledge: true, signature: 'data:image/png;base64,AAAA' }, TODAY)
expect('ready has no errors', Object.keys(ready).length, 0)
expect('ready first invalid', firstInvalidField(ready), null)
