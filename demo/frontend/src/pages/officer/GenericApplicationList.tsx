import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchOfficerList, postBulkDecision, type DecisionKey, type OfficerList, type OfficerListQuery, type OfficerRole } from '../../api.ts'
import ApplicationList, { ApplicationListSkeleton } from './ApplicationList.tsx'
import { officerSessionResponse } from '../../officer-session.ts'

export default function GenericApplicationList({ postingId, onOpen = () => undefined }: { postingId: number; onOpen?: (id: number) => void }) {
  const [query, setQuery] = useState<OfficerListQuery>({ role: 'province', program: `posting_${postingId}`, sort: 'submitted', queue: 'needs_check', page: 1, page_size: 20 })
  const [list, setList] = useState<OfficerList | null>(null)
  const [roles, setRoles] = useState<OfficerRole[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [memo, setMemo] = useState('')
  const request = useRef(0)
  useEffect(() => {
    void fetch('/api/officer/roles').then((response) => { officerSessionResponse('/api/officer/roles', response); if (!response.ok) throw new Error('역할을 불러오지 못했습니다.'); return response.json() as Promise<OfficerRole[]> }).then(setRoles).catch((problem: unknown) => setError(problem instanceof Error ? problem.message : '역할을 불러오지 못했습니다.'))
  }, [])
  const reload = useCallback(() => {
    const version = ++request.current
    return fetchOfficerList(query).then((next) => {
      if (version !== request.current) return
      if (next.page > next.page_count) {
        setQuery((current) => ({ ...current, page: Math.max(1, next.page_count) }))
        return
      }
      setList(next)
      setError('')
    }).catch((problem: unknown) => {
      if (version === request.current) setError(problem instanceof Error ? problem.message : '신청 목록을 불러오지 못했습니다.')
    })
  }, [query])
  useEffect(() => { void reload(); return () => { request.current += 1 } }, [reload])
  const bulk = async (decision: DecisionKey) => {
    if (decision !== 'approve' && !memo.trim()) { setError('일괄 보류·반려 사유를 입력해 주세요.'); return }
    setBusy(true); setError(''); setNotice('')
    try { const result = await postBulkDecision({ role: query.role, decision, memo: memo.trim(), application_ids: selected }); setSelected([]); setMemo(''); setNotice(`${result.processed}건을 처리했습니다.`); await reload() }
    catch (problem: unknown) { setError(problem instanceof Error ? problem.message : '처리하지 못했습니다.') }
    finally { setBusy(false) }
  }
  return <section className="managed-program__applications" aria-label="사업 신청 목록">
    <h2>신청 목록</h2><p>신청 건을 열어 제출 원본과 이 사업의 기준을 확인합니다.</p>
    <label>담당 역할 <select value={query.role} disabled={busy} onChange={(event) => { setQuery((current) => ({ ...current, role: event.target.value, page: 1 })); setSelected([]) }}>{roles.map((role) => <option key={role.key} value={role.key}>{role.name}</option>)}</select></label>
    {selected.length > 0 && <label>일괄 보류·반려 사유 <input aria-label="일괄 보류·반려 사유" maxLength={2000} value={memo} disabled={busy} onChange={(event) => setMemo(event.target.value)} /></label>}
    {error && <p role="alert">{error}<button className="btn" onClick={() => void reload()}>다시 시도</button></p>}
    {list ? <ApplicationList list={list} query={query} selected={selected} onSelect={setSelected} onOpen={onOpen} busy={busy} notice={notice} onBulk={bulk} onQuery={(patch) => { setQuery((current) => ({ ...current, ...patch, program: `posting_${postingId}` })); setSelected([]) }} /> : !error && <ApplicationListSkeleton />}
  </section>
}
