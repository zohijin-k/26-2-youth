import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import {
  OFFICER_QUEUES, fetchApplicationReasons, fetchOfficerList, fetchOfficerRoles, fetchReasonExplanation, postBulkDecision,
  type ApplicationReasons, type DecisionKey, type OfficerList, type OfficerListQuery, type OfficerQueue, type OfficerRole,
} from '../../api.ts'
import { formatDayTime } from '../../posting-format.ts'
import { bulkActionsFor } from './bulk-actions.ts'
import SortToggle from './SortToggle.tsx'
import { OfficerDialog, OfficerMenu } from './OfficerModern.tsx'
import { officerLabel } from './officer-modern-model.ts'
import './program-modern-workspace.css'

const QUEUE_LABELS: Record<OfficerQueue, string> = { needs_check: '확인 필요', pass: '충족', done: '처리 완료' }
export default function GenericApplicationList({ postingId, onOpen = () => undefined }: { postingId: number; onOpen?: (id: number) => void }) {
  const [query, setQuery] = useState<OfficerListQuery>({ role: 'province', program: `posting_${postingId}`, sort: 'importance', queue: 'needs_check', page: 1, page_size: 20 })
  const [list, setList] = useState<OfficerList | null>(null)
  const [roles, setRoles] = useState<OfficerRole[]>([])
  const [rolesError, setRolesError] = useState('')
  const [rolesAttempt, setRolesAttempt] = useState(0)
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [loadedQuery, setLoadedQuery] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [memo, setMemo] = useState('')
  const [search, setSearch] = useState('')
  const [reasonTarget, setReasonTarget] = useState<{ id: number; number: string } | null>(null)
  const [reasonData, setReasonData] = useState<ApplicationReasons | null>(null)
  const [reasonError, setReasonError] = useState('')
  const [reasonAttempt, setReasonAttempt] = useState(0)
  const request = useRef(0)
  const selectAll = useRef<HTMLInputElement>(null)
  const tabs = useRef<Partial<Record<OfficerQueue, HTMLButtonElement | null>>>({})
  const uid = useId()
  useEffect(() => {
    let current = true
    fetchOfficerRoles().then((next) => { if (current) { setRoles(next); setRolesError('') } }).catch(() => { if (current) setRolesError('담당 역할을 불러오지 못했습니다.') })
    return () => { current = false }
  }, [rolesAttempt])
  const queryKey = JSON.stringify(query)
  const loading = loadedQuery !== queryKey
  const reload = useCallback(() => {
    const version = ++request.current
    return fetchOfficerList(query).then((next) => {
      if (version !== request.current) return
      if (next.page > Math.max(1, next.page_count)) { setQuery((current) => ({ ...current, page: Math.max(1, next.page_count) })); return }
      setList(next); setError('')
    }).catch((problem: unknown) => {
      if (version === request.current) setError(problem instanceof Error ? problem.message : '신청 목록을 불러오지 못했습니다.')
    }).finally(() => { if (version === request.current) setLoadedQuery(queryKey) })
  }, [query, queryKey])
  useEffect(() => { void reload(); return () => { request.current += 1 } }, [reload])
  useEffect(() => {
    const q = search.trim().slice(0, 50) || undefined
    if (query.q === q) return
    const timer = window.setTimeout(() => {
      setSelected([])
      setQuery((current) => ({ ...current, q, page: 1 }))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [search, query.q])
  useEffect(() => {
    if (!reasonTarget) return
    let current = true
    void fetchApplicationReasons(reasonTarget.id, query.role).then(async (data) => {
      const explanation = await fetchReasonExplanation(reasonTarget.id, query.role).catch(() => null)
      if (current) setReasonData({ ...data, explanation })
    }).catch(() => { if (current) setReasonError('확인 필요 사유를 불러오지 못했습니다.') })
    return () => { current = false }
  }, [reasonTarget, reasonAttempt, query.role])
  const queue = query.queue || 'needs_check'
  const shownQueue = OFFICER_QUEUES.find((key) => key === list?.filters.applied.queue) || queue
  const pageIds = list?.rows.map((row) => row.application_id) || []
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id))
  const blocked = busy || loading
  const someSelected = pageIds.some((id) => selected.includes(id))
  useEffect(() => { if (selectAll.current) selectAll.current.indeterminate = !allSelected && someSelected }, [allSelected, someSelected])
  const change = (patch: Partial<OfficerListQuery>) => { setQuery((current) => ({ ...current, ...patch, program: `posting_${postingId}` })); setSelected([]); setNotice('') }
  const queueKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const at = OFFICER_QUEUES.indexOf(queue)
    const next = event.key === 'ArrowRight' ? (at + 1) % 3 : event.key === 'ArrowLeft' ? (at + 2) % 3 : event.key === 'Home' ? 0 : event.key === 'End' ? 2 : -1
    if (next < 0) return
    event.preventDefault(); change({ queue: OFFICER_QUEUES[next], page: 1 }); tabs.current[OFFICER_QUEUES[next]]?.focus()
  }
  const bulk = async (decision: DecisionKey) => {
    if (blocked || !selected.length || !list?.role.can_bulk || !bulkActionsFor(shownQueue, list.role.actions).some((action) => action.key === decision)) return
    if (decision !== 'approve' && !memo.trim()) { setError('일괄 보류·반려 사유를 입력해 주세요.'); return }
    setBusy(true); setError(''); setNotice('')
    try { const result = await postBulkDecision({ role: query.role, decision, memo: memo.trim(), application_ids: selected }); setSelected([]); setMemo(''); setNotice(`${result.processed}건을 처리했습니다.`); await reload() }
    catch (problem: unknown) { setError(problem instanceof Error ? problem.message : '처리하지 못했습니다.') }
    finally { setBusy(false) }
  }
  return <section className="om om-generic-list managed-program__applications" aria-label="사업 신청 목록">
    <div className="om-generic-list__head"><h2>신청 목록</h2><label>담당 역할<select value={query.role} disabled={blocked} onChange={(event) => change({ role: event.target.value, region: undefined, town: undefined, page: 1 })}>{roles.length ? roles.map((role) => <option key={role.key} value={role.key}>{role.name}</option>) : <option value={query.role}>담당 역할 불러오는 중</option>}</select></label></div>
    <div className="om-chips" role="tablist" aria-label="신청 구분">{OFFICER_QUEUES.map((key) => <button ref={(element) => { tabs.current[key] = element }} key={key} type="button" role="tab" id={`${uid}-${key}`} aria-selected={key === queue} aria-controls={`${uid}-rows`} tabIndex={key === queue ? 0 : -1} className={`om-chip${key === 'needs_check' && (list?.queues[key] || 0) > 0 ? ' om-chip--warning' : ''}`} disabled={busy} onClick={() => change({ queue: key, page: 1 })} onKeyDown={queueKey}>{QUEUE_LABELS[key]} {list?.queues[key] ?? 0}</button>)}</div>
    <form className="om-generic-list__filters" role="search" onSubmit={(event) => { event.preventDefault(); change({ q: search.trim() || undefined, page: 1 }) }}>
      <label>신청번호 또는 성명<input type="search" aria-label="신청번호 또는 성명 검색" maxLength={50} autoComplete="off" value={search} disabled={busy} onChange={(event) => { setSearch(event.target.value); setSelected([]) }} /></label>
      <label>접수일 시작<input type="date" max={query.submitted_to || undefined} value={query.submitted_from || ''} disabled={busy} onChange={(event) => change({ submitted_from: event.target.value || undefined, page: 1 })} /></label>
      <label>접수일 종료<input type="date" min={query.submitted_from || undefined} value={query.submitted_to || ''} disabled={busy} onChange={(event) => change({ submitted_to: event.target.value || undefined, page: 1 })} /></label>
      {list?.scope.region_locked && <label>시군<select value={list.scope.region} disabled={blocked} onChange={(event) => change({ region: event.target.value, town: '', page: 1 })}>{list.scope.regions.map((region) => <option key={region} value={region}>{region}</option>)}</select></label>}
      {list?.scope.town_locked && <label>읍·면·동<select value={list.scope.town} disabled={blocked} onChange={(event) => change({ town: event.target.value, page: 1 })}>{list.scope.towns.length ? list.scope.towns.map((town) => <option key={town} value={town}>{town}</option>) : <option value="">접수 없음</option>}</select></label>}
      {(search || query.submitted_from || query.submitted_to) && <button type="button" className="om-text" disabled={busy} onClick={() => { setSearch(''); change({ q: undefined, submitted_from: undefined, submitted_to: undefined, page: 1 }) }}>조건 지우기</button>}
      <SortToggle value={query.sort} disabled={blocked} onChange={(sort) => change({ sort, page: 1 })} />
    </form>
    {(error || rolesError) && <p className="om-notice" role="alert">{error || rolesError} <button type="button" className="om-text" disabled={blocked} onClick={() => { setRolesAttempt((value) => value + 1); setLoadedQuery(''); void reload() }}>다시 시도</button></p>}
    {notice && <p className="om-notice" role="status">{notice}</p>}
    {selected.length > 0 && list?.role.can_bulk && <div className="om-generic-list__selection"><strong>{selected.length}건 선택</strong><label>일괄 보류·반려 사유<input aria-label="일괄 보류·반려 사유" maxLength={2000} value={memo} disabled={busy} onChange={(event) => setMemo(event.target.value)} /></label><div className="om-row">{bulkActionsFor(shownQueue, list.role.actions).map((action) => <button type="button" className="btn" key={action.key} disabled={blocked || (action.key !== 'approve' && !memo.trim())} onClick={() => void bulk(action.key)}>{action.result_label}</button>)}<button type="button" className="om-text" disabled={busy} onClick={() => setSelected([])}>선택 해제</button></div></div>}
    <div id={`${uid}-rows`} role="tabpanel" aria-labelledby={`${uid}-${queue}`} aria-busy={loading}>
      {!list ? !error && <p className="om-notice" role="status">신청 목록을 불러오는 중입니다.</p> : <table className="om-generic-list__table"><colgroup>{list.role.can_bulk && <col className="om-generic-list__check-col" />}<col /><col className="om-generic-list__name-col" /><col className="om-generic-list__time-col" /><col className="om-generic-list__status-col" /><col className="om-generic-list__more-col" /></colgroup><thead><tr>{list.role.can_bulk && <th scope="col"><input ref={selectAll} type="checkbox" aria-label="전체 선택" checked={allSelected} disabled={blocked || !pageIds.length} onChange={() => setSelected(allSelected ? [] : pageIds)} /></th>}<th scope="col">신청번호</th><th scope="col">성명</th><th scope="col">접수일시</th><th scope="col">처리상태</th><th scope="col"><span className="om-generic-list__sr">더보기</span></th></tr></thead><tbody>{list.rows.map((row) => <tr key={row.application_id}>
        {list.role.can_bulk && <td><input type="checkbox" aria-label={`${row.application_no} 선택`} disabled={blocked} checked={selected.includes(row.application_id)} onChange={() => setSelected(selected.includes(row.application_id) ? selected.filter((id) => id !== row.application_id) : [...selected, row.application_id])} /></td>}
        <td><button type="button" className="alist__open om-text" disabled={blocked} onClick={() => onOpen(row.application_id)}>{row.application_no}</button></td><td><strong>{row.name}</strong></td><td>{formatDayTime(row.submitted_at)}</td><td><span className={`om-chip${row.decision === 'approve' || (!row.decision && row.ai_status === 'PASS') ? ' om-chip--success' : row.decision === 'reject' || (!row.decision && row.ai_status === 'FAIL') ? ' om-chip--danger' : ' om-chip--warning'}`}>{row.decision ? officerLabel(row.decision) : officerLabel(row.ai_status)}</span>{!row.decision && !!row.check_count && <span className="alist__checks">확인 {row.check_count}건</span>}</td>
        <td><OfficerMenu label={`${row.application_no} 더보기`} disabled={blocked} actions={[{ label: '심사 화면 열기', onSelect: () => onOpen(row.application_id) }, { label: '확인 필요 사유', onSelect: () => { setReasonData(null); setReasonError(''); setReasonTarget({ id: row.application_id, number: row.application_no }) } }]} /></td>
      </tr>)}{list.rows.length === 0 && <tr><td colSpan={list.role.can_bulk ? 6 : 5}><p className="om-generic-list__empty">{query.q || query.submitted_from || query.submitted_to ? '조건에 맞는 신청이 없습니다.' : '이 구분의 신청이 없습니다.'} <button type="button" className="om-text" disabled={blocked} onClick={() => { setLoadedQuery(''); void reload() }}>다시 불러오기</button></p></td></tr>}</tbody></table>}
    </div>
    {list && list.page_count > 1 && <nav className="om-chips om-generic-list__pages" aria-label="쪽 이동">{Array.from({ length: list.page_count }, (_, index) => index + 1).map((page) => <button type="button" className="om-chip" key={page} disabled={blocked} aria-current={page === list.page ? 'page' : undefined} onClick={() => change({ page })}>{page}</button>)}</nav>}
    {reasonTarget && <OfficerDialog title={`${reasonTarget.number} 확인 필요 사유`} onClose={() => setReasonTarget(null)}>{reasonError ? <p role="alert">{reasonError} <button type="button" className="om-text" onClick={() => { setReasonError(''); setReasonAttempt((value) => value + 1) }}>다시 시도</button></p> : !reasonData ? <p role="status">확인 필요 사유를 불러오는 중입니다.</p> : <div className="om-stack">{reasonData.documents.map((document, index) => <div key={`${document.slot_key}-${index}`}><strong>{document.label}</strong> <span className="om-chip">{officerLabel(document.status)}</span>{document.findings.map((finding, at) => <p key={at}>{finding.message}</p>)}</div>)}{reasonData.missing.map((document) => <p key={document.slot_key}>{document.label} · 필수 서류 미제출</p>)}{!reasonData.documents.length && !reasonData.missing.length && <p>기록된 확인 필요 사유가 없습니다.</p>}{reasonData.explanation && <p>{reasonData.explanation.text}</p>}</div>}</OfficerDialog>}
  </section>
}
