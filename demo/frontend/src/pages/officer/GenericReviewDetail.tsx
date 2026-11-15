import { useEffect, useState } from 'react'
import type { DecisionKey } from '../../api.ts'
import { fetchGenericReview, saveGenericChecks, decideGeneric, type GenericReviewData } from '../../generic-officer-api.ts'
import DocumentViewer from './DocumentViewer.tsx'
import { OfficerDrawer } from './OfficerModern.tsx'
import { officerDestination, officerLabel } from './officer-modern-model.ts'
import './generic-review.css'
import './program-modern-workspace.css'

export default function GenericReviewDetail({ postingId, applicationId, onBack }: { postingId: number; applicationId: number; onBack: () => void }) {
  const [data, setData] = useState<GenericReviewData | null>(null)
  const [active, setActive] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [memo, setMemo] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let current = true
    fetchGenericReview(postingId, applicationId).then((next) => { if (current) { setData(next); setMemo(next.decision.memo || ''); setError('') } })
      .catch((problem: unknown) => { if (current) setError(problem instanceof Error ? problem.message : '심사 정보를 불러오지 못했습니다.') })
    return () => { current = false }
  }, [postingId, applicationId, attempt])
  const run = async (work: () => Promise<GenericReviewData>) => {
    if (busy) return
    setBusy(true); setError('')
    try { setData(await work()) }
    catch (problem: unknown) { setError(problem instanceof Error ? problem.message : '처리하지 못했습니다.') }
    finally { setBusy(false) }
  }
  const document = data?.documents.find((item) => item.document_id === active) || data?.documents[0]
  const viewerDocument = document?.page_image_url
    ? { ...document, file_url: document.page_image_url, file_format: 'png' }
    : document
  const toggle = (kind: 'document_ids' | 'checklist_ids', id: string, checked: boolean) => {
    if (!data) return
    const prior = data.checks.current ? data.checks[kind] : []
    const checks = { document_ids: data.checks.current ? data.checks.document_ids : [],
      checklist_ids: data.checks.current ? data.checks.checklist_ids : [], fingerprint: data.checks.fingerprint,
      [kind]: checked ? [...new Set([...prior, id])] : prior.filter((key) => key !== id) }
    void run(() => saveGenericChecks(postingId, applicationId, checks))
  }
  const decide = (decision: DecisionKey) => {
    if (!data || busy || data.status === 'decided' || (decision === 'approve' ? !data.can_approve : !memo.trim())) return
    void run(() => decideGeneric(postingId, applicationId, decision, memo))
  }
  return <main className="generic-review">
    {error && <div className="om"><p className="om-notice" role="alert">{error} <button type="button" className="om-text" onClick={() => setAttempt((value) => value + 1)}>다시 시도</button></p></div>}
    {!data ? !error && <div className="om"><p role="status">심사 정보를 불러오는 중입니다.</p></div> : <>
      <header className="om om-review-head"><OfficerDrawer postingId={postingId} current="applications" disabled={busy} onTab={(tab) => { if (tab === 'applications') onBack(); else window.location.assign(officerDestination(`/officer/programs/${postingId}`, tab)) }} /><div><p>{data.program_name}</p><h1>{data.name} · {data.application_no}</h1></div><span className="om-chip">{data.decision.decision ? officerLabel(data.decision.decision) : '검토 중'}</span></header>
      <div className="generic-review__columns"><section className="generic-review__original" aria-label="제출 원본">
        <div role="tablist" aria-label="제출 서류">{data.documents.map((item) => <button type="button" role="tab" aria-selected={document?.document_id === item.document_id} className="btn" key={item.document_id} onClick={() => setActive(item.document_id)}>{item.label}</button>)}</div>
        {viewerDocument ? <DocumentViewer doc={viewerDocument} highlight={null} /> : <p>제출 서류가 없습니다.</p>}
      </section><aside className="om om-review generic-review__findings" aria-label="판정과 확인">
        <div className="om-review__scroll"><h2>서류별 판정과 확인</h2><p className="om-subtle">원본을 읽고 항목별로 확인해 주세요.</p>
          {data.documents.map((item) => {
            const id = item.slot_key === 'written' ? 'written' : String(item.document_id)
            const reason = item.findings[0]?.message || '제출 원본을 확인해 주세요.'
            return <section className="om-review__card" key={item.document_id}>
              <div className="om-review__card-head"><strong>{item.label}</strong><span className={`om-chip${item.status === 'PASS' ? ' om-chip--success' : item.status === 'FAIL' ? ' om-chip--danger' : ' om-chip--warning'}`}>{officerLabel(item.status)}</span></div>
              <p className="om-review__reason" title={reason}>{reason}</p>
              {(item.ocr_engine || item.findings.length > 0 || item.ocr_fallback_reason) && <details><summary>자세히</summary><div className="om-review__details">{item.findings.map((finding, index) => <p key={index}>{finding.message}</p>)}{item.ocr_engine && <p>판독 방식: {officerLabel(item.ocr_engine, '기타 판독 방식')}</p>}{item.ocr_fallback_reason && <p>{/[가-힣]/.test(item.ocr_fallback_reason) ? item.ocr_fallback_reason : '보조 판독 경로를 사용했습니다.'}</p>}</div></details>}
              <label className="om-review__check"><input type="checkbox" disabled={busy || data.status === 'decided'} checked={data.checks.current && data.checks.document_ids.includes(id)} onChange={(event) => toggle('document_ids', id, event.target.checked)} />{item.label} 원본 확인함</label>
            </section>
          })}
          <h2>이 사업의 기준</h2>{data.criteria.map((criterion) => {
            const reason = criterion.basis || (criterion.requires_check ? '공고문 기준과 제출 원본을 확인해 주세요.' : '이 기준의 자동 판정 결과입니다.')
            return <section className="om-review__card" key={criterion.id}>
              <div className="om-review__card-head"><strong>{criterion.label}</strong><span className={`om-chip${criterion.result === 'PASS' ? ' om-chip--success' : criterion.result === 'FAIL' ? ' om-chip--danger' : ' om-chip--warning'}`}>{officerLabel(criterion.result)}</span></div>
              <p className="om-review__reason" title={reason}>{reason}</p>
              <details><summary>자세히</summary><div className="om-review__details"><p>판정 방식: {criterion.type === 'checklist' ? '담당자 확인' : '자동 판정'}</p>{criterion.basis && <p>{criterion.basis}</p>}{criterion.quote && <blockquote>{criterion.quote}</blockquote>}{!!criterion.source_document_ids.length && <div className="om-chips" aria-label="근거 서류">{criterion.source_document_ids.map((id) => <button type="button" className="om-chip" key={id} onClick={() => setActive(id)}>{data.documents.find((item) => item.document_id === id)?.label || '근거 서류'}</button>)}</div>}</div></details>
              {criterion.requires_check && <label className="om-review__check"><input type="checkbox" disabled={busy || data.status === 'decided'} checked={data.checks.current && data.checks.checklist_ids.includes(criterion.id)} onChange={(event) => toggle('checklist_ids', criterion.id, event.target.checked)} />{criterion.label} 확인함</label>}
            </section>
          })}
        </div>
        <div className="om-review__process"><label htmlFor="generic-review-memo">처리 사유 <span className="om-subtle">(보류·반려 시 필수)</span></label><textarea id="generic-review-memo" maxLength={2000} value={memo} disabled={busy || data.status === 'decided'} onChange={(event) => setMemo(event.target.value)} />
          {!!data.approval_blockers.length && <details className="om-review__blockers"><summary>선정 전 남은 확인 {data.approval_blockers.length}개</summary><ul>{data.approval_blockers.map((item) => <li key={item}>{item}</li>)}</ul></details>}
          <div className="generic-review__actions"><button type="button" className="btn btn--primary" disabled={busy || !data.can_approve || data.status === 'decided'} onClick={() => decide('approve')}>최종 선정</button><button type="button" className="btn" disabled={busy || !memo.trim() || data.status === 'decided'} onClick={() => decide('hold')}>보류</button><button type="button" className="btn" disabled={busy || !memo.trim() || data.status === 'decided'} onClick={() => decide('reject')}>반려</button></div>
        </div>
      </aside></div>
    </>}
  </main>
}
