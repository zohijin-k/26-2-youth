/** Shared year/month/day input used by identity verification and uploads. */
import type { YMD } from './ymd.ts'
import './form-sheet.css'

export function DateTriple({
  value,
  onChange,
  ariaPrefix,
  readOnly = false,
  describedBy,
  invalid = false,
}: {
  value: YMD
  onChange: (v: YMD) => void
  ariaPrefix: string
  readOnly?: boolean
  describedBy?: string
  invalid?: boolean
}) {
  const set = (key: keyof YMD) => (raw: string) => onChange({ ...value, [key]: raw })
  return (
    <span className="form-date">
      <input
        className="form-date__y"
        inputMode="numeric"
        aria-label={`${ariaPrefix} 년`}
        readOnly={readOnly}
        aria-describedby={describedBy}
        aria-invalid={invalid}
        value={value.y}
        onChange={(e) => set('y')(e.target.value)}
      />
      <span className="form-date__unit">년</span>
      <input
        className="form-date__m"
        inputMode="numeric"
        aria-label={`${ariaPrefix} 월`}
        readOnly={readOnly}
        aria-describedby={describedBy}
        aria-invalid={invalid}
        value={value.m}
        onChange={(e) => set('m')(e.target.value)}
      />
      <span className="form-date__unit">월</span>
      <input
        className="form-date__d"
        inputMode="numeric"
        aria-label={`${ariaPrefix} 일`}
        readOnly={readOnly}
        aria-describedby={describedBy}
        aria-invalid={invalid}
        value={value.d}
        onChange={(e) => set('d')(e.target.value)}
      />
      <span className="form-date__unit">일</span>
    </span>
  )
}
