import { OFFICER_SORTS, type OfficerSort } from '../../api.ts'
import './sort-toggle.css'

/** 신청 목록 정렬: 중요도순(확인 필요 항목이 많은 건부터) · 최신순 · 등록순. */
export default function SortToggle({ value, disabled = false, onChange }: { value: string | undefined; disabled?: boolean; onChange: (sort: OfficerSort) => void }) {
  return <div className="sort-toggle" role="group" aria-label="정렬">
    {OFFICER_SORTS.map(({ key, label }) => <button key={key} type="button" className="sort-toggle__item" aria-pressed={value === key}
      title={key === 'importance' ? '확인 필요 항목이 많은 신청부터' : key === 'latest' ? '최근에 접수한 신청부터' : '먼저 접수한 신청부터'}
      disabled={disabled} onClick={() => { if (value !== key) onChange(key) }}>{label}</button>)}
  </div>
}
