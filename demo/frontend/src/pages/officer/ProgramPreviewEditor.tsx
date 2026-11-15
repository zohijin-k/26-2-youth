import { useEffect, useState, type ReactNode } from 'react'
import { closePosting, publishPosting, type OfficerPosting } from '../../api.ts'
import { fetchProgramWorkspace, unpublishProgram, type ManagedProgramData } from '../../program-workspace-api.ts'
import { pendingDraftItems, saveProgramAnalysis, type AnalyzedProgramData, type DraftCriterion, type DraftDocument, type DraftEvidence, type NoticeDraft } from '../../notice-draft-api.ts'
import ProgramGuidance from '../../components/ProgramGuidance.tsx'
import Modal from '../../components/Modal.tsx'
import PdfPages from '../../components/PdfPages.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import ProgramTemplateEditor from './ProgramTemplateEditor.tsx'
import './managed-program.css'
import './program-preview.css'

const kinds: Record<string, string> = { checklist: '담당자 확인', age: '나이 범위', residence: '거주지', issue_date: '서류 발급일', work_continuity: '근로 계속성', income: '중위소득' }
const valueFields: Record<string, [string, string, string][]> = {
  age: [['birth_start', '허용 출생 시작일', 'date'], ['birth_end', '허용 출생 종료일', 'date'], ['basis_date', '기준일', 'date']],
  residence: [['province', '도·광역시', 'text'], ['city', '시군 (미지원 시 담당자 확인)', 'text'], ['basis_date', '기준일', 'date']],
  issue_date: [['date', '인정 시작일 (이후·당일 포함)', 'date'], ['basis_date', '기준일', 'date']],
  work_continuity: [['months', '계속 근로 개월 수', 'number'], ['basis_date', '기준일', 'date']],
  income: [['percent', '중위소득 비율 (%)', 'number']], checklist: [],
}
const manualEvidence = (id: string): DraftEvidence => ({ id, page: null, quote: '', source: 'manual', confidence: 0, needs_review: true })
function existingDraft(data: ManagedProgramData): NoticeDraft {
  return { version: 1, status: 'draft', title: { ...manualEvidence('title'), value: data.posting.title },
    period: { ...manualEvidence('period'), value: { apply_start: data.posting.apply_start, apply_end: data.posting.apply_end } },
    guidance: { ...manualEvidence('guidance'), value: data.posting.guidance_text },
    required_docs: data.required_docs.map((slot) => ({ ...manualEvidence(`manual_document_${slot}`), slot_key: slot, label: data.slot_options.find((item) => item.key === slot)?.label || '제출 서류', required: true, type: 'document' })),
    criteria: [{ ...manualEvidence('manual_program_review'), type: 'checklist', label: '공고문 기준 확인', values: {} }], source_pages: [], warnings: [] }
}
export default function ProgramPreviewEditor({ postingId, onBack, onPostingChanged }: { postingId: number; onBack: () => void; onPostingChanged?: (posting: OfficerPosting) => void }) {
  const [data, setData] = useState<AnalyzedProgramData | null>(null)
  const [draft, setDraft] = useState<NoticeDraft | null>(null)
  const [savedDraft, setSavedDraft] = useState('')
  const [layoutDirty, setLayoutDirty] = useState(false)
  const [templateBusy, setTemplateBusy] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [page, setPage] = useState<number | null>(null)
  const [focusField, setFocusField] = useState<{ formId: number; key: string; nonce: number } | null>(null)
  const [attempt, setAttempt] = useState(0)
  const dirty = !!draft && savedDraft !== JSON.stringify(draft)
  useBeforeUnload(dirty || layoutDirty || busy || templateBusy)
  useEffect(() => {
    let current = true
    fetchProgramWorkspace(postingId).then((raw) => {
      if (!current) return
      const next = raw as AnalyzedProgramData
      const analysis = next.analysis || existingDraft(next)
      setData(next); setDraft(analysis); setSavedDraft(JSON.stringify(analysis)); setError(''); onPostingChanged?.(next.posting)
    }).catch((problem: unknown) => { if (current) setError(problem instanceof Error ? problem.message : '사업을 불러오지 못했습니다.') })
    return () => { current = false }
  }, [postingId, attempt, onPostingChanged])
  const readonly = busy || templateBusy || data?.posting.status !== 'draft'
  const save = async () => {
    if (!draft || !data || readonly) return
    setBusy(true); setError(''); setMessage('')
    try { const next = await saveProgramAnalysis(postingId, draft); const clean = next.analysis || draft; setData(next); setDraft(clean); setSavedDraft(JSON.stringify(clean)); onPostingChanged?.(next.posting); setMessage('작성 중으로 저장했습니다.') }
    catch (problem: unknown) { setError(problem instanceof Error ? problem.message : '저장하지 못했습니다.') }
    finally { setBusy(false) }
  }
  const transition = async (action: 'publish' | 'unpublish' | 'close') => {
    if (!data || busy || templateBusy) return
    setBusy(true); setError(''); setMessage('')
    try {
      if (action === 'unpublish') await unpublishProgram(postingId)
      else await (action === 'publish' ? publishPosting(postingId) : closePosting(postingId))
      setAttempt((value) => value + 1); setMessage(action === 'publish' ? '사업을 게시했습니다.' : action === 'unpublish' ? '게시를 취소했습니다. 내용을 수정할 수 있습니다.' : '사업을 마감했습니다.')
    } catch (problem: unknown) { setError(problem instanceof Error ? problem.message : '상태를 바꾸지 못했습니다.') }
    finally { setBusy(false) }
  }
  if (!data || !draft) return <main className="program-preview"><p role={error ? 'alert' : 'status'}>{error || '예시 페이지를 불러오고 있습니다.'}</p>{error && <button className="btn" onClick={() => setAttempt((value) => value + 1)}>다시 시도</button>}</main>
  const update = (next: NoticeDraft) => { setDraft(next); setMessage('') }
  const pending = pendingDraftItems(draft)
  const formPending = data.forms.flatMap((form) => Object.entries(form.layout.fields || {}).filter(([, field]) => field.needs_review !== false).map(([id, field]) => ({ id: `form-${form.id}-${id}`, formId: form.id, key: id, label: field.label || '서식 입력칸' })))
  const labels = new Map<string, string>([['title', '사업 제목'], ['period', '신청 기간'], ['guidance', '안내문'], ...draft.required_docs.map((item): [string, string] => [item.id, item.original_label || item.label]), ...draft.criteria.map((item): [string, string] => [item.id, item.label])])
  const blockers = [...(data.publish_blockers || []), ...(dirty ? ['수정한 내용을 저장해 주세요.'] : []), ...(layoutDirty ? ['서식 틀을 저장하고 확정해 주세요.'] : []), ...(pending.length ? [`확인할 항목이 ${pending.length}개 남았습니다.`] : [])]
  const confirm = (item: DraftEvidence) => {
    const mark = <T extends DraftEvidence>(value: T): T => value.id === item.id ? { ...value, needs_review: false } : value
    update({ ...draft, title: mark(draft.title), period: mark(draft.period), guidance: mark(draft.guidance), required_docs: draft.required_docs.map(mark), criteria: draft.criteria.map(mark) })
  }
  const evidence = (item: DraftEvidence) => <div className="program-preview__evidence">
    {item.quote && <blockquote>“{item.quote}”</blockquote>}{[...(item.basis_evidence ? [item.basis_evidence] : []), ...(item.table_evidence || []), ...(item.sources || [])].map((source) => <div key={source.id}><blockquote>“{source.quote}”</blockquote>{source.page && <button className="program-preview__source" onClick={() => setPage(source.page)}>근거 공고문 {source.page}쪽 보기</button>}</div>)}
    {item.page ? <button className="program-preview__source" type="button" onClick={() => setPage(item.page)}>공고문 {item.page}쪽 보기</button> : <small>담당자 직접 입력·확인</small>}
    <small>신뢰도 {Math.round(item.confidence * 100)}%</small><button className="btn" type="button" disabled={readonly || !item.needs_review} onClick={() => confirm(item)}>{item.needs_review ? '확인함' : '확인 완료'}</button>
  </div>
  const section = (id: string, title: string, content: ReactNode, pendingSection = false) => <section id={`preview-${id}`} className={`program-preview__section${pendingSection ? ' program-preview__section--pending' : ''}`}><h2>{title}</h2>{content}</section>
  const editDocument = (id: string, patch: Partial<DraftDocument>) => update({ ...draft, required_docs: draft.required_docs.map((item) => item.id === id ? { ...item, ...patch, needs_review: true } : item) })
  const editCriterion = (id: string, patch: Partial<DraftCriterion>) => update({ ...draft, criteria: draft.criteria.map((item) => item.id === id ? { ...item, ...patch, needs_review: true } : item) })
  return <main className="program-preview">
    <header className="program-preview__bar"><div><p className="program-preview__eyebrow">신청자 화면 예시</p><h1>내용을 확인하고 올려 주세요</h1><p>노란 항목은 담당자 확인이 필요합니다. 수정한 항목은 다시 확인해 주세요.</p></div><button className="btn" onClick={onBack} disabled={busy || dirty || layoutDirty}>사업 목록</button></header>
    {error && <p role="alert" className="program-preview__error">{error}</p>}{message && <p role="status" className="program-preview__saved">{message}</p>}
    {!!draft.warnings.length && <div className="program-preview__notice">{draft.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
    <div className="program-preview__layout"><div className="program-preview__page">
      <div className="program-preview__citizen-head"><strong>전북 청년정책</strong><span>온라인 신청</span></div>
      {section('title', '① 사업 제목과 신청 기간', <>
        <div><label>사업 제목<input id="preview-title-input" value={draft.title.value} maxLength={100} disabled={readonly} onChange={(event) => update({ ...draft, title: { ...draft.title, value: event.target.value, needs_review: true } })} /></label>{evidence(draft.title)}</div>
        <div id="preview-period"><div className="program-preview__dates"><label>신청 시작일<input type="date" value={draft.period.value.apply_start} disabled={readonly} onChange={(event) => update({ ...draft, period: { ...draft.period, value: { ...draft.period.value, apply_start: event.target.value }, needs_review: true } })} /></label><label>신청 종료일<input type="date" value={draft.period.value.apply_end} disabled={readonly} onChange={(event) => update({ ...draft, period: { ...draft.period, value: { ...draft.period.value, apply_end: event.target.value }, needs_review: true } })} /></label></div>{evidence(draft.period)}</div>
      </>, draft.title.needs_review || draft.period.needs_review)}
      {section('guidance', '② 안내문', <><label>신청자 안내문<textarea id="preview-guidance-input" value={draft.guidance.value} maxLength={20000} disabled={readonly} onChange={(event) => update({ ...draft, guidance: { ...draft.guidance, value: event.target.value, needs_review: true } })} /></label>{evidence(draft.guidance)}<div className="program-preview__guidance"><ProgramGuidance text={draft.guidance.value} /></div></>, draft.guidance.needs_review)}
      {section('forms', '③ 서식 (서명용)', <><p>원본 서식 위의 입력칸과 서명칸을 확인해 주세요.</p><ProgramTemplateEditor postingId={postingId} forms={data.forms} readOnly={readonly} onChanged={(next) => setData(next as AnalyzedProgramData)} onDirty={setLayoutDirty} onBusy={setTemplateBusy} focusField={focusField} /></>, formPending.length > 0)}
      {section('documents', '④ 제출 서류와 기준', <>
        <h3>제출 서류</h3>{draft.required_docs.map((item) => <div id={`preview-${item.id}`} key={item.id} className={`program-preview__item${item.needs_review ? ' program-preview__item--pending' : ''}`}>
          <label>서류 이름<input value={item.slot_key ? item.label : item.original_label || item.label} disabled={readonly} maxLength={200} onChange={(event) => editDocument(item.id, item.slot_key ? { label: event.target.value } : { label: '기타 서류', original_label: event.target.value })} /></label>
          <label>서류 종류<select value={item.slot_key || ''} disabled={readonly} onChange={(event) => { const slot = event.target.value; editDocument(item.id, slot ? { slot_key: slot, label: data.slot_options.find((option) => option.key === slot)?.label || item.label, original_label: undefined } : { slot_key: null, label: '기타 서류', original_label: item.original_label || item.label }) }}><option value="">기타 서류 · 담당자 확인</option>{data.slot_options.map((slot) => <option key={slot.key} value={slot.key}>{slot.label}</option>)}</select></label>
          <label className="program-preview__check"><input type="checkbox" checked={item.required} disabled={readonly} onChange={(event) => editDocument(item.id, { required: event.target.checked })} />필수 제출</label>
          {evidence(item)}<button className="btn" disabled={readonly} onClick={() => update({ ...draft, required_docs: draft.required_docs.filter((value) => value.id !== item.id) })}>서류 삭제</button>
        </div>)}<button className="btn" disabled={readonly} onClick={() => update({ ...draft, required_docs: [...draft.required_docs, { ...manualEvidence(`manual_doc_${Date.now()}`), slot_key: null, label: '기타 서류', required: true, type: 'document' }] })}>서류 추가</button>
        <h3>사업 기준</h3>{draft.criteria.map((item) => <div id={`preview-${item.id}`} key={item.id} className={`program-preview__item${item.needs_review ? ' program-preview__item--pending' : ''}`}>
          <label>기준 이름<input value={item.label} disabled={readonly} maxLength={240} onChange={(event) => editCriterion(item.id, { label: event.target.value })} /></label>
          <label>기준 종류<select value={item.type} disabled={readonly} onChange={(event) => editCriterion(item.id, { type: event.target.value, values: {}, engine_rule: null })}>{Object.entries(kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <span className="program-preview__rule-kind">{item.type === 'checklist' || !item.engine_rule ? '담당자 확인' : '자동 판정'}</span>
          {(valueFields[item.type] || []).map(([key, label, type]) => <label key={key}>{label}<input type={type} value={String(item.values[key] ?? '')} disabled={readonly} onChange={(event) => editCriterion(item.id, { values: { ...item.values, ...(item.type === 'issue_date' ? { mode: 'after_date' } : {}), [key]: type === 'number' ? event.target.value === '' ? undefined : Number(event.target.value) : event.target.value } })} /></label>)}
          {item.type === 'income' && <label>심사 대상 고지 월 (YYYY-MM, 쉼표로 구분)<input value={Array.isArray(item.values.premium_months) ? item.values.premium_months.join(', ') : ''} disabled={readonly} onChange={(event) => editCriterion(item.id, { values: { ...item.values, premium_months: event.target.value.split(/[,\s]+/).filter(Boolean) } })} /></label>}{evidence(item)}<button className="btn" disabled={readonly} onClick={() => update({ ...draft, criteria: draft.criteria.filter((value) => value.id !== item.id) })}>기준 삭제</button>
        </div>)}<button className="btn" disabled={readonly} onClick={() => update({ ...draft, criteria: [...draft.criteria, { ...manualEvidence(`manual_criterion_${Date.now()}`), type: 'checklist', label: '담당자 확인 항목', values: {}, engine_rule: null }] })}>기준 추가</button>
      </>, draft.required_docs.some((item) => item.needs_review) || draft.criteria.some((item) => item.needs_review))}
    </div><aside className="program-preview__review" aria-label="확인할 항목">
      <h2>확인할 항목 {pending.length + formPending.length}개</h2><ul>{pending.map((item) => <li key={item.id}><button onClick={() => document.getElementById(`preview-${item.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>{labels.get(item.id) || item.id}</button></li>)}{formPending.map((item) => <li key={item.id}><button disabled={layoutDirty || templateBusy} onClick={() => { setFocusField({ formId: item.formId, key: item.key, nonce: Date.now() }); document.getElementById('preview-forms')?.scrollIntoView({ behavior: 'smooth' }) }}>{item.label}</button></li>)}</ul>
      <p>{data.posting.status === 'draft' ? '작성 중' : data.posting.status === 'closed' ? '마감' : '게시됨'}</p>
      {data.posting.status === 'draft' ? <><button className="btn" disabled={readonly || layoutDirty} onClick={() => void save()}>작성 중 저장</button><button className="btn btn--primary" disabled={readonly || !!blockers.length} onClick={() => void transition('publish')}>올리기 (게시)</button>{!!blockers.length && <ul className="program-preview__blockers">{blockers.map((reason) => <li key={reason}>{reason}</li>)}</ul>}</> : <><button className="btn" disabled={busy} onClick={() => void transition('unpublish')}>게시 취소 · 수정하기</button>{data.posting.status === 'published' ? <button className="btn btn--danger" disabled={busy} onClick={() => void transition('close')}>마감하기</button> : <button className="btn" disabled={busy || !!blockers.length} onClick={() => void transition('publish')}>다시 게시</button>}</>}
    </aside></div>
    {page && data.posting.notice_url && <Modal title={`공고문 ${page}쪽`} onClose={() => setPage(null)}><PdfPages url={data.posting.notice_url} pageNo={page} width={720} /></Modal>}
  </main>
}
