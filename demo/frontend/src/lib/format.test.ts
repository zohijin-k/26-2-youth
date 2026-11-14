import { formatBytes, formatDate, formatDateTime, formatDuration } from './format.ts'

function expect(label: string, actual: string, expected: string): void {
  if (actual !== expected) throw new Error(`${label} returned ${actual}, expected ${expected}`)
}

const dates: Array<[string, string]> = [
  ['2026-03-03', '2026. 3. 3.'],
  ['2026-11-14', '2026. 11. 14.'],
  [' 2026-12-31 ', '2026. 12. 31.'],
  ['2026-02-30', '2026-02-30'],
  ['2026.03.03', '2026.03.03'],
  ['', ''],
]
for (const [input, expected] of dates) expect(`formatDate(${input})`, formatDate(input), expected)

const dateTimes: Array<[string, string]> = [
  ['2026-11-14T17:20:00', '2026. 11. 14. 오후 5:20'],
  ['2026-11-14 00:35', '2026. 11. 14. 오전 12:35'],
  ['2026-11-14T12:05:09.123', '2026. 11. 14. 오후 12:05'],
  ['2026-11-14', '2026. 11. 14.'],
  ['2026-11-14T25:00:00', '2026-11-14T25:00:00'],
  ['not a date', 'not a date'],
]
for (const [input, expected] of dateTimes) expect(`formatDateTime(${input})`, formatDateTime(input), expected)

const bytes: Array<[number, string]> = [
  [0, '0B'],
  [1023, '1023B'],
  [1024, '1KB'],
  [1258291, '1.2MB'],
  [5 * 1024 * 1024, '5MB'],
]
for (const [input, expected] of bytes) expect(`formatBytes(${input})`, formatBytes(input), expected)

const durations: Array<[number, string]> = [
  [0.2, '약 1초'],
  [12, '약 12초'],
  [60, '약 1분'],
  [150, '약 3분'],
]
for (const [input, expected] of durations) expect(`formatDuration(${input})`, formatDuration(input), expected)
