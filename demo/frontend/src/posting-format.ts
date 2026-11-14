/** 사업 화면이 같이 쓰는 날짜 표기. */

/** 2026-11-01 → 2026.11.01 */
export function formatDay(value: string | null | undefined): string {
  if (!value) return '-'
  return value.slice(0, 10).replaceAll('-', '.')
}

/** 2026.11.01 ~ 2026.11.30 */
export function formatPeriod(start: string, end: string): string {
  return `${formatDay(start)} ~ ${formatDay(end)}`
}

/** 2026-11-14T09:12:00 → 2026.11.14 09:12 */
export function formatDayTime(value: string | null | undefined): string {
  if (!value) return '-'
  const time = value.slice(11, 16)
  return time ? `${formatDay(value)} ${time}` : formatDay(value)
}
