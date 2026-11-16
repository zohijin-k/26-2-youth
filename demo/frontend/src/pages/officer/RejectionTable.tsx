/** 반려 탭의 표: 신청번호 · 성명 · 반려일 · 신청자에게 보낸 안내. 신청번호를 누르면 심사 화면이 열린다. */
import { useState } from 'react'
import type { OfficerRow } from '../../api.ts'
import { formatDayTime } from '../../posting-format.ts'
import { OfficerDialog } from './OfficerModern.tsx'
import './rejection-table.css'

const NO_NOTICE = '안내 없음 (일괄 반려 또는 반려 페이지 이전 처리)'

export default function RejectionTable({ rows, tableClassName, onOpen }: { rows: OfficerRow[]; tableClassName: string; onOpen: (applicationId: number) => void }) {
  const [reading, setReading] = useState<{ number: string; notice: string } | null>(null)
  if (!rows.length) return <p className="rejection-table__empty">반려한 신청이 없습니다.</p>
  return <>
    <table className={`${tableClassName} rejection-table`}>
      <colgroup><col className="rejection-table__no" /><col className="rejection-table__name" /><col className="rejection-table__date" /><col /></colgroup>
      <thead><tr><th scope="col">신청번호</th><th scope="col">성명</th><th scope="col">반려일</th><th scope="col">신청자에게 보낸 안내</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.application_id}>
        <td><button type="button" className="alist__open" aria-label={`${row.application_no} ${row.name} 심사 화면 열기`} onClick={() => onOpen(row.application_id)}>{row.application_no}</button></td>
        <td><strong>{row.name}</strong></td>
        <td>{row.decided_at ? formatDayTime(row.decided_at) : '-'}</td>
        <td>{row.reject_notice
          ? <div className="rejection-table__notice"><p>{row.reject_notice}</p><button type="button" className="rejection-table__more" onClick={() => setReading({ number: row.application_no, notice: row.reject_notice || '' })}>전체 보기</button></div>
          : <span className="rejection-table__none">{NO_NOTICE}</span>}</td>
      </tr>)}</tbody>
    </table>
    {reading && <OfficerDialog title={`${reading.number} 반려 안내`} onClose={() => setReading(null)}><p className="rejection-table__full">{reading.notice}</p></OfficerDialog>}
  </>
}
