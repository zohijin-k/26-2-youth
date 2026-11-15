import { useEffect, useRef, useState, type ReactNode } from 'react'
import { closePosting, publishPosting, type OfficerPosting } from '../../api.ts'
import { fetchProgramWorkspace, unpublishProgram, type ManagedProgramData } from '../../program-workspace-api.ts'
import { pendingDraftItems, saveProgramAnalysis, type AnalyzedProgramData, type DraftCriterion, type DraftDocument, type DraftEvidence, type NoticeDraft } from '../../notice-draft-api.ts'
import ProgramGuidance from '../../components/ProgramGuidance.tsx'
import PdfPages from '../../components/PdfPages.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import ProgramTemplateEditor from './ProgramTemplateEditor.tsx'
import { OfficerConfirm, OfficerDialog, OfficerDrawer, OfficerMenu } from './OfficerModern.tsx'
import { canStartPublication, evidencePresentation, officerLabel } from './officer-modern-model.ts'
import { publishReviewedProgram } from './officer-publication.ts'
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

function Evidence({ item, label, readOnly, onConfirm, onSource }: {
  item: DraftEvidence; label: string; readOnly: boolean; onConfirm: () => void; onSource: (page: number) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const sources = [item, ...(item.basis_evidence ? [item.basis_evidence] : []), ...(item.table_evidence || []), ...(item.sources || [])]
  const quotes = [...new Set(sources.map((source) => source.quote).filter(Boolean))]
  const presentation = evidencePresentation({ ...item, quote: quotes[0] })
  const page = sources.find((source) => source.page)?.page
  const evidenceId = `evidence-${item.id}`
  return <div className="program-preview__evidence">
    <div className="program-preview__evidence-actions">
      {presentation.chip && <span className="om-chip">{presentation.chip}</span>}
      <button type="button" className="om-text" aria-expanded={expanded} aria-controls={evidenceId} onClick={() => setExpanded((value) => !value)}>근거</button>
      <button type="button" className="btn program-preview__confirm" aria-label={`${label} 확인`} aria-pressed={!item.needs_review} disabled={readOnly || !item.needs_review}
        onClick={() => { setExpanded(false); onConfirm() }}>{item.needs_review ? '□ 확인' : '✓ 확인함'}</button>
    </div>
    {presentation.showPreview && !expanded && <p className="program-preview__quote-preview" title={quotes[0]}>{quotes[0]}</p>}
    <div id={evidenceId} hidden={!expanded} className="program-preview__evidence-full">
      {quotes.length ? quotes.map((quote) => <blockquote key={quote}>{quote}</blockquote>) : <p>근거 없이 직접 입력한 항목입니다.</p>}
      {!!page && <button className="om-text" type="button" onClick={() => onSource(page)}>공고문 {page}쪽 보기</button>}
    </div>
  </div>
}
interface Confirmation { title: string; description: string; label: string; perform: () => void }
export default function ProgramPreviewEditor({ postingId, onBack, onPostingChanged, focusHeadingOnLoad = false }: { postingId: number; onBack: () => void; onPostingChanged?: (posting: OfficerPosting) => void; focusHeadingOnLoad?: boolean }) {
  const mounted = useRef(true)
  const heading = useRef<HTMLHeadingElement>(null)
  const headingFocused = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [data, setData] = useState<AnalyzedProgramData | null>(null)
  const [draft, setDraft] = useState<NoticeDraft | null>(null)
  useEffect(() => {
    if (focusHeadingOnLoad && !headingFocused.current && heading.current) {
      heading.current.focus()
      headingFocused.current = true
    }
  }, [data, draft, focusHeadingOnLoad])
  const [savedDraft, setSavedDraft] = useState('')
  const [layoutDirty, setLayoutDirty] = useState(false)
  const [templateBusy, setTemplateBusy] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [failedAction, setFailedAction] = useState<'save' | 'publish' | 'unpublish' | 'close' | null>(null)
  const [publishReasons, setPublishReasons] = useState<string[]>([])
  const [page, setPage] = useState<number | null>(null)
  const [focusField, setFocusField] = useState<{ formId: number; key: string; nonce: number } | null>(null)
  const [editing, setEditing] = useState<Record<string, boolean>>({})
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null)
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
  const acceptSaved = (next: AnalyzedProgramData, fallback: NoticeDraft) => {
    if (!mounted.current) return
    const clean = next.analysis || fallback
    setData(next); setDraft(clean); setSavedDraft(JSON.stringify(clean)); onPostingChanged?.(next.posting)
  }
  const save = async () => {
    if (!draft || !data || readonly || layoutDirty) return
    setBusy(true); setError(''); setMessage(''); setFailedAction(null)
    try { const next = await saveProgramAnalysis(postingId, draft); if (mounted.current) { acceptSaved(next, draft); setMessage('작성 중으로 저장했습니다.') } }
    catch (problem: unknown) { if (mounted.current) { setError(problem instanceof Error ? problem.message : '저장하지 못했습니다.'); setFailedAction('save') } }
    finally { if (mounted.current) setBusy(false) }
  }
  const transition = async (action: 'publish' | 'unpublish' | 'close') => {
    if (!data || !draft || busy || templateBusy) return
    if (action === 'publish' && !canStartPublication({ pendingCount: pendingDraftItems(draft).length, formsConfirmed: data.forms.length > 0 && data.forms.every((form) => form.confirmed), layoutDirty })) return
    setBusy(true); setError(''); setMessage(''); setPublishReasons([]); setFailedAction(null)
    try {
      if (action === 'publish') {
        const result = await publishReviewedProgram({
          save: () => data.posting.status === 'draft' ? saveProgramAnalysis(postingId, draft) : Promise.resolve(),
          refresh: () => fetchProgramWorkspace(postingId) as Promise<AnalyzedProgramData>,
          publish: () => publishPosting(postingId),
          isCurrent: () => mounted.current,
        })
        if (!mounted.current) return
        acceptSaved(result.data, draft)
        if (!result.published) { setPublishReasons(result.blockers); return }
      } else if (action === 'unpublish') await unpublishProgram(postingId)
      else await closePosting(postingId)
      if (!mounted.current) return
      setAttempt((value) => value + 1)
      setMessage(action === 'publish' ? '사업을 게시했습니다.' : action === 'unpublish' ? '게시를 취소했습니다. 내용을 수정할 수 있습니다.' : '사업을 마감했습니다.')
    } catch (problem: unknown) { if (mounted.current) { setError(problem instanceof Error ? problem.message : '상태를 바꾸지 못했습니다.'); setFailedAction(action) } }
    finally { if (mounted.current) setBusy(false) }
  }
  if (!data || !draft) return <main className="om program-preview"><p role={error ? 'alert' : 'status'}>{error || '예시 페이지를 불러오고 있습니다.'}</p>{error && <button className="btn" onClick={() => setAttempt((value) => value + 1)}>다시 시도</button>}</main>
  const update = (next: NoticeDraft) => { setDraft(next); setMessage(''); setPublishReasons([]) }
  const pending = pendingDraftItems(draft)
  const formPending = data.forms.flatMap((form) => Object.entries(form.layout.fields || {}).filter(([, field]) => field.needs_review !== false).map(([id, field]) => ({ id: `form-${form.id}-${id}`, formId: form.id, key: id, label: field.label || '서식 입력칸' })))
  const unconfirmedForms = data.forms.filter((form) => !form.confirmed && !formPending.some((item) => item.formId === form.id))
  const formCount = formPending.length + unconfirmedForms.length + (data.forms.length ? 0 : 1)
  const remaining = pending.length + formCount
  const labels = new Map<string, string>([['title', '사업 제목'], ['period', '신청 기간'], ['guidance', '안내문'], ...draft.required_docs.map((item): [string, string] => [item.id, item.original_label || item.label]), ...draft.criteria.map((item): [string, string] => [item.id, item.label])])
  const canPublish = canStartPublication({ busy: busy || templateBusy, pendingCount: pending.length, formsConfirmed: data.forms.length > 0 && data.forms.every((form) => form.confirmed), layoutDirty, draftDirty: dirty })
  const jump = (id: string) => document.getElementById(`preview-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const confirm = (item: DraftEvidence) => {
    const mark = <T extends DraftEvidence>(value: T): T => value.id === item.id ? { ...value, needs_review: false } : value
    update({ ...draft, title: mark(draft.title), period: mark(draft.period), guidance: mark(draft.guidance), required_docs: draft.required_docs.map(mark), criteria: draft.criteria.map(mark), suggestions: draft.suggestions?.filter((suggestion) => suggestion.target_id !== item.id) })
  }
  const evidence = (item: DraftEvidence) => <Evidence key={item.id} item={item} label={labels.get(item.id) || '항목'} readOnly={readonly} onConfirm={() => confirm(item)} onSource={setPage} />
  const section = (id: string, title: string, content: ReactNode, pendingSection = false) => <section id={`preview-${id}`} className={`program-preview__section${pendingSection ? ' program-preview__section--pending' : ''}`}><h2>{title}</h2>{content}</section>
  const editDocument = (id: string, patch: Partial<DraftDocument>) => update({ ...draft, required_docs: draft.required_docs.map((item) => item.id === id ? { ...item, ...patch, needs_review: true } : item) })
  const editCriterion = (id: string, patch: Partial<DraftCriterion>) => update({ ...draft, criteria: draft.criteria.map((item) => item.id === id ? { ...item, ...patch, needs_review: true } : item) })
  const toggleEditor = (id: string) => setEditing((prior) => ({ ...prior, [id]: !prior[id] }))
  const remove = (kind: 'document' | 'criterion', item: DraftDocument | DraftCriterion) => setConfirmation({ title: `${kind === 'document' ? '서류' : '기준'} 삭제`, description: `“${item.label}” 항목을 삭제할까요?`, label: '삭제', perform: () => {
    update(kind === 'document' ? { ...draft, required_docs: draft.required_docs.filter((value) => value.id !== item.id) } : { ...draft, criteria: draft.criteria.filter((value) => value.id !== item.id) })
  } })
  const progress = [
    { id: 'title', label: '① 제목·기간', count: Number(draft.title.needs_review) + Number(draft.period.needs_review) },
    { id: 'guidance', label: '② 안내문', count: Number(draft.guidance.needs_review) },
    { id: 'forms', label: '③ 서식', count: formCount },
    { id: 'documents', label: '④ 서류·기준', count: [...draft.required_docs, ...draft.criteria].filter((item) => item.needs_review).length },
  ]
  const menuActions = data.posting.status === 'draft'
    ? [{ label: '작성 중 저장', disabled: readonly || layoutDirty, onSelect: () => void save() }]
    : [{ label: '게시 취소 · 수정하기', disabled: busy, onSelect: () => setConfirmation({ title: '게시 취소', description: '신청자에게 보이는 게시를 취소하고 내용을 수정할까요?', label: '게시 취소', perform: () => void transition('unpublish') }) },
      ...(data.posting.status === 'published' ? [{ label: '마감하기', danger: true, disabled: busy, onSelect: () => setConfirmation({ title: '사업 마감', description: '이 사업의 신청 접수를 마감할까요?', label: '마감', perform: () => void transition('close') }) }] : [])]
  return <main className="om program-preview">
    <header className="program-preview__bar">
      <OfficerDrawer postingId={postingId} current="settings" disabled={busy || dirty || layoutDirty} onList={onBack} />
      <div className="program-preview__heading"><h1 ref={heading} tabIndex={-1}>{draft.title.value || '새 사업'}</h1><span className="om-chip">{officerLabel(data.posting.status)}</span></div>
      <button className="btn btn--primary" disabled={!canPublish || data.posting.status === 'published'} onClick={() => void transition('publish')}>{busy ? '처리 중…' : data.posting.status === 'closed' ? '다시 게시' : '올리기(게시)'}</button>
      <OfficerMenu label="사업 더보기" actions={menuActions} disabled={busy || templateBusy} />
      <nav className="program-preview__progress" aria-label="편집 진행">
        {progress.map((item) => <button type="button" className="om-chip" key={item.id} onClick={() => jump(item.id)}>{item.label} {item.count ? item.count : '✓'}</button>)}
        <div className={`program-preview__remaining${remaining || layoutDirty ? ' is-pending' : ''}`}>
          {remaining === 0 && !layoutDirty ? <span className="om-chip om-chip--success" role="status">모두 확인함</span> : <OfficerMenu label={`남은 확인 ${remaining}개 보기`} actions={[
            ...pending.map((item) => ({ label: labels.get(item.id) || '확인할 항목', onSelect: () => jump(item.id) })),
            ...formPending.map((item) => ({ label: `${item.label} · 서식`, disabled: layoutDirty || templateBusy, onSelect: () => { setFocusField({ formId: item.formId, key: item.key, nonce: Date.now() }); jump('forms') } })),
            ...unconfirmedForms.map((form) => ({ label: `${form.file_name} · 서식 확정 필요`, onSelect: () => jump('forms') })),
            ...(!data.forms.length ? [{ label: '서식 PDF를 먼저 등록해 주세요', onSelect: () => jump('forms') }] : []),
            ...(layoutDirty ? [{ label: '수정한 서식을 확정해 주세요', onSelect: () => jump('forms') }] : []),
          ]}>남은 확인 {remaining}개 보기</OfficerMenu>}
        </div>
      </nav>
      {!!publishReasons.length && <ul className="program-preview__blockers" role="alert">{publishReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
    </header>
    <p className="program-preview__intro">신청자 화면 예시 · 항목을 고치면 다시 확인해 주세요.</p>
    {error && <p role="alert" className="program-preview__error">{error} <button className="om-text" disabled={busy || templateBusy} onClick={() => { if (failedAction === 'save') void save(); else if (failedAction) void transition(failedAction); else setAttempt((value) => value + 1) }}>다시 시도</button></p>}{message && <p role="status" className="program-preview__saved">{message}</p>}
    {(!!draft.warnings.length || !!draft.suggestions?.length) && <details className="program-preview__notice"><summary>추가 안내 {draft.warnings.length + (draft.suggestions?.length || 0)}개</summary>
      {draft.warnings.map((warning) => <p key={warning}>{warning}</p>)}
      {draft.suggestions?.map((suggestion, index) => <section key={`${suggestion.target_id}-${index}`} aria-label="제안 확인"><strong>{labels.get(suggestion.target_id) || '기준 확인'}</strong><blockquote>{suggestion.text || suggestion.quote}</blockquote>
        {suggestion.page && <button className="om-text" onClick={() => setPage(suggestion.page)}>공고문 {suggestion.page}쪽 보기</button>}
        {suggestion.type === 'guidance' && suggestion.text && <button className="btn" disabled={readonly} onClick={() => update({ ...draft, guidance: { ...draft.guidance, value: suggestion.text!, needs_review: true }, suggestions: draft.suggestions?.filter((_, at) => at !== index) })}>안내문에 반영</button>}
        <button className="om-text" onClick={() => jump(suggestion.target_id)}>항목 확인하기</button>
        <OfficerMenu label="제안 더보기" disabled={readonly} actions={[{ label: '제안 제외', danger: true, onSelect: () => setConfirmation({ title: '제안 제외', description: '이 제안을 제외할까요?', label: '제외', perform: () => update({ ...draft, suggestions: draft.suggestions?.filter((_, at) => at !== index) }) }) }]} />
      </section>)}
    </details>}
    <div className="program-preview__page">
      {section('title', '① 사업 제목과 신청 기간', <>
        <div><label>사업 제목<input id="preview-title-input" value={draft.title.value} maxLength={100} disabled={readonly} onChange={(event) => update({ ...draft, title: { ...draft.title, value: event.target.value, needs_review: true } })} /></label>{evidence(draft.title)}</div>
        <div id="preview-period"><div className="program-preview__dates"><label>신청 시작일<input type="date" value={draft.period.value.apply_start} disabled={readonly} onChange={(event) => update({ ...draft, period: { ...draft.period, value: { ...draft.period.value, apply_start: event.target.value }, needs_review: true } })} /></label><label>신청 종료일<input type="date" value={draft.period.value.apply_end} disabled={readonly} onChange={(event) => update({ ...draft, period: { ...draft.period, value: { ...draft.period.value, apply_end: event.target.value }, needs_review: true } })} /></label></div>{evidence(draft.period)}</div>
      </>, draft.title.needs_review || draft.period.needs_review)}
      {section('guidance', '② 안내문', <><label>신청자 안내문<textarea id="preview-guidance-input" value={draft.guidance.value} maxLength={20000} disabled={readonly} onChange={(event) => update({ ...draft, guidance: { ...draft.guidance, value: event.target.value, needs_review: true } })} /></label>{evidence(draft.guidance)}<details className="program-preview__guidance"><summary>안내문 미리보기</summary><ProgramGuidance text={draft.guidance.value} /></details></>, draft.guidance.needs_review)}
      {section('forms', '③ 서식 (서명용)', <ProgramTemplateEditor modern postingId={postingId} forms={data.forms} readOnly={readonly} onChanged={(next) => setData(next as AnalyzedProgramData)} onDirty={setLayoutDirty} onBusy={setTemplateBusy} focusField={focusField} />, formCount > 0)}
      {section('documents', '④ 제출 서류와 기준', <>
        <h3>제출 서류</h3>{draft.required_docs.map((item) => <article id={`preview-${item.id}`} key={item.id} className={`program-preview__item${item.needs_review ? ' program-preview__item--pending' : ''}`}>
          <div className="program-preview__item-head"><strong>{item.original_label || item.label}</strong><span className="om-chip">{item.slot_key ? '지정 서류' : '기타 서류'}</span>{item.required && <span className="om-chip">필수</span>}
            <button type="button" className="om-text" aria-expanded={!!editing[item.id]} aria-controls={`edit-${item.id}`} disabled={readonly} onClick={() => toggleEditor(item.id)}>고치기</button>
            <OfficerMenu label={`${item.original_label || item.label} 더보기`} disabled={readonly} actions={[{ label: '서류 삭제', danger: true, onSelect: () => remove('document', item) }]} />
          </div>
          <div id={`edit-${item.id}`} hidden={!editing[item.id]}>
            <label>서류 이름<input value={item.slot_key ? item.label : item.original_label || item.label} disabled={readonly} maxLength={200} onChange={(event) => editDocument(item.id, item.slot_key ? { label: event.target.value } : { label: '기타 서류', original_label: event.target.value })} /></label>
            <label>서류 종류<select value={item.slot_key || ''} disabled={readonly} onChange={(event) => { const slot = event.target.value; editDocument(item.id, slot ? { slot_key: slot, label: data.slot_options.find((option) => option.key === slot)?.label || item.label, original_label: undefined } : { slot_key: null, label: '기타 서류', original_label: item.original_label || item.label }) }}><option value="">기타 서류 · 담당자 확인</option>{data.slot_options.map((slot) => <option key={slot.key} value={slot.key}>{slot.label}</option>)}</select></label>
            <label className="program-preview__check"><input type="checkbox" checked={item.required} disabled={readonly} onChange={(event) => editDocument(item.id, { required: event.target.checked })} />필수 제출</label>
          </div>{evidence(item)}
        </article>)}<button className="om-text" disabled={readonly} onClick={() => { const id = `manual_doc_${Date.now()}`; setEditing((prior) => ({ ...prior, [id]: true })); update({ ...draft, required_docs: [...draft.required_docs, { ...manualEvidence(id), slot_key: null, label: '기타 서류', required: true, type: 'document' }] }) }}>서류 추가</button>
        <h3>사업 기준</h3>{draft.criteria.map((item) => <article id={`preview-${item.id}`} key={item.id} className={`program-preview__item${item.needs_review ? ' program-preview__item--pending' : ''}`}>
          <div className="program-preview__item-head"><strong>{item.label}</strong><span className="om-chip">{officerLabel(item.type, '담당자 확인')}</span>
            <button type="button" className="om-text" aria-expanded={!!editing[item.id]} aria-controls={`edit-${item.id}`} disabled={readonly} onClick={() => toggleEditor(item.id)}>고치기</button>
            <OfficerMenu label={`${item.label} 더보기`} disabled={readonly} actions={[{ label: '기준 삭제', danger: true, onSelect: () => remove('criterion', item) }]} />
          </div>
          <div id={`edit-${item.id}`} hidden={!editing[item.id]}>
            <label>기준 이름<input value={item.label} disabled={readonly} maxLength={240} onChange={(event) => editCriterion(item.id, { label: event.target.value })} /></label>
            <label>기준 종류<select value={item.type} disabled={readonly} onChange={(event) => editCriterion(item.id, { type: event.target.value, values: {}, engine_rule: null })}>{Object.entries(kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <span className="om-chip">{item.type === 'checklist' || !item.engine_rule ? '담당자 확인' : '자동 판정'}</span>
            {(valueFields[item.type] || []).map(([key, label, type]) => <label key={key}>{label}<input type={type} value={String(item.values[key] ?? '')} disabled={readonly} onChange={(event) => editCriterion(item.id, { values: { ...item.values, ...(item.type === 'issue_date' ? { mode: 'after_date' } : {}), [key]: type === 'number' ? event.target.value === '' ? undefined : Number(event.target.value) : event.target.value } })} /></label>)}
            {item.type === 'income' && <label>심사 대상 고지 월 (연도-월, 쉼표로 구분)<input value={Array.isArray(item.values.premium_months) ? item.values.premium_months.join(', ') : ''} disabled={readonly} onChange={(event) => editCriterion(item.id, { values: { ...item.values, premium_months: event.target.value.split(/[,\s]+/).filter(Boolean) } })} /></label>}
          </div>{evidence(item)}
        </article>)}<button className="om-text" disabled={readonly} onClick={() => { const id = `manual_criterion_${Date.now()}`; setEditing((prior) => ({ ...prior, [id]: true })); update({ ...draft, criteria: [...draft.criteria, { ...manualEvidence(id), type: 'checklist', label: '담당자 확인 항목', values: {}, engine_rule: null }] }) }}>기준 추가</button>
      </>, draft.required_docs.some((item) => item.needs_review) || draft.criteria.some((item) => item.needs_review))}
    </div>
    {!!page && data.posting.notice_url && <OfficerDialog title={`공고문 ${page}쪽`} onClose={() => setPage(null)}><PdfPages url={data.posting.notice_url} pageNo={page} width={720} /></OfficerDialog>}
    {confirmation && <OfficerConfirm title={confirmation.title} confirmLabel={confirmation.label} onClose={() => setConfirmation(null)} onConfirm={() => { confirmation.perform(); setConfirmation(null) }}>{confirmation.description}</OfficerConfirm>}
  </main>
}
