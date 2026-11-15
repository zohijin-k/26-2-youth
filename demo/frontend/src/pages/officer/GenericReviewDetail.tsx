import { useEffect, useState } from 'react'
import type { DecisionKey } from '../../api.ts'
import { fetchGenericReview, saveGenericChecks, decideGeneric, type GenericReviewData } from '../../generic-officer-api.ts'
import DocumentViewer from './DocumentViewer.tsx'
import './generic-review.css'

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
  const toggle = (kind: 'document_ids' | 'checklist_ids', id: string, checked: boolean) => {
    if (!data) return
    const prior = data.checks.current ? data.checks[kind] : []
    const checks = { document_ids: data.checks.current ? data.checks.document_ids : [],
      checklist_ids: data.checks.current ? data.checks.checklist_ids : [], fingerprint: data.checks.fingerprint,
      [kind]: checked ? [...new Set([...prior, id])] : prior.filter((key) => key !== id) }
    void run(() => saveGenericChecks(postingId, applicationId, checks))
  }
  const decide = (decision: DecisionKey) => void run(() => decideGeneric(postingId, applicationId, decision, memo))
  return <main className="generic-review">
    <nav><button type="button" className="btn" onClick={onBack}>신청 목록으로</button></nav>
    {error && <p role="alert">{error} <button className="btn" onClick={() => setAttempt((value) => value + 1)}>다시 불러오기</button></p>}
    {!data ? <p role="status">심사 정보를 불러오는 중입니다.</p> : <>
      <header><div><p>{data.program_name}</p><h1>{data.name} · {data.application_no}</h1></div><strong>{data.decision.decision === 'approve' ? '최종 선정' : data.decision.decision === 'hold' ? '보류' : data.decision.decision === 'reject' ? '반려' : '검토 중'}</strong></header>
      <div className="generic-review__columns"><section className="generic-review__original" aria-label="제출 원본">
        <div role="tablist" aria-label="제출 서류">{data.documents.map((item) => <button type="button" role="tab" aria-selected={document?.document_id === item.document_id} className="btn" key={item.document_id} onClick={() => setActive(item.document_id)}>{item.label}</button>)}</div>
        {document ? <DocumentViewer doc={document} highlight={null} /> : <p>제출 서류가 없습니다.</p>}
      </section><aside className="generic-review__findings">
        <h2>서류별 판정과 확인</h2><p>원본을 읽고 확인 표시를 남겨 주세요.</p>
        {data.documents.map((item) => { const id = item.slot_key === 'written' ? 'written' : String(item.document_id); return <section key={item.document_id}>
          <button className="generic-review__doc-link" onClick={() => setActive(item.document_id)}>{item.label} · {item.status || '확인 필요'}</button>
          {item.findings.map((finding, index) => <p key={index}>{finding.message}</p>)}
          {item.ocr_engine && <small>판독: {item.ocr_engine}{item.ocr_fallback_reason ? ` · ${item.ocr_fallback_reason}` : ''}</small>}
          <label><input type="checkbox" disabled={busy || data.status === 'decided'} checked={data.checks.current && data.checks.document_ids.includes(id)} onChange={(event) => toggle('document_ids', id, event.target.checked)} />{item.label} 원본 확인함</label>
        </section> })}
        <h2>이 사업의 기준</h2>{data.criteria.map((criterion) => <section key={criterion.id}>
          <strong>{criterion.label}</strong><p>{criterion.type === 'checklist' ? '담당자 확인' : `자동 판정 · ${criterion.result}`}</p>
          {criterion.basis && <p>{criterion.basis}</p>}{criterion.quote && <blockquote>{criterion.quote}</blockquote>}
          {!!criterion.source_document_ids.length && <p>근거 서류: {criterion.source_document_ids.map((id) => <button className="btn" key={id} onClick={() => setActive(id)}>{data.documents.find((item) => item.document_id === id)?.label || id}</button>)}</p>}
          {criterion.requires_check && <label><input type="checkbox" disabled={busy || data.status === 'decided'} checked={data.checks.current && data.checks.checklist_ids.includes(criterion.id)} onChange={(event) => toggle('checklist_ids', criterion.id, event.target.checked)} />{criterion.label} 확인함</label>}
        </section>)}
        <h2>처리</h2><label htmlFor="generic-review-memo">처리 사유 (보류·반려 시 필수)</label><textarea id="generic-review-memo" maxLength={2000} value={memo} disabled={busy || data.status === 'decided'} onChange={(event) => setMemo(event.target.value)} />
        {!!data.approval_blockers.length && <ul>{data.approval_blockers.map((item) => <li key={item}>{item}</li>)}</ul>}
        <div className="generic-review__actions"><button className="btn btn--primary" disabled={busy || !data.can_approve || data.status === 'decided'} onClick={() => decide('approve')}>최종 선정</button>
          <button className="btn" disabled={busy || !memo.trim() || data.status === 'decided'} onClick={() => decide('hold')}>보류</button><button className="btn btn--danger" disabled={busy || !memo.trim() || data.status === 'decided'} onClick={() => decide('reject')}>반려</button></div>
      </aside></div>
    </>}
  </main>
}
