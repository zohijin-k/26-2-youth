import { useEffect, useRef, useState, type PointerEvent } from 'react'

import {
  confirmProgramForm, draftProgramForm, saveProgramForm,
  type AutofillSource, type FieldKind, type ManagedFormField, type ManagedFormLayout,
  type ManagedProgramData, type ManagedProgramForm,
} from '../../program-workspace-api.ts'
import { boundedBox, boxPercent, movedBox, type PdfBox } from '../../lib/form-box.ts'

const KIND_LABELS: Record<FieldKind, string> = { text: '문자', number: '숫자·금액', date: '날짜', check: '체크', radio: '하나 선택', signature: '서명' }
const SOURCE_LABELS: Record<AutofillSource, string> = { name: '본인인증 성명', birth: '본인인증 생년월일', mobile: '본인인증 연락처', phone: '본인인증 연락처', address: '주소', email: '이메일' }
const fieldKind = (field: ManagedFormField): FieldKind => field.field_type || (field.type === 'image' ? 'signature' : field.type)
const pageUrl = (postingId: number, formId: number, page: number) => `/api/officer/postings/${postingId}/workspace/forms/${formId}/pages/${page}.png`

interface Props {
  postingId: number
  forms: ManagedProgramForm[]
  readOnly: boolean
  onChanged: (data: ManagedProgramData) => void
  onDirty: (dirty: boolean) => void
  onBusy: (busy: boolean) => void
  focusField?: { formId: number; key: string; nonce: number } | null
}

type Drag = { mode: 'new' | 'move' | 'resize'; key: string; x: number; y: number; box: PdfBox }

export default function ProgramTemplateEditor({ postingId, forms, readOnly, onChanged, onDirty, onBusy, focusField }: Props) {
  const [formId, setFormId] = useState<number | null>(focusField?.formId || forms[0]?.id || null)
  const form = forms.find((item) => item.id === formId) || forms[0]
  const [layout, setLayout] = useState<ManagedFormLayout>(form?.layout || {})
  const [dirty, setDirty] = useState(false)
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState('')
  const [tool, setTool] = useState<'select' | 'add'>('select')
  const [drawing, setDrawing] = useState<PdfBox | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const canvas = useRef<HTMLDivElement>(null)
  const drag = useRef<Drag | null>(null)
  const counter = useRef(0)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const revision = JSON.stringify(form?.layout || {})
  const revisionKey = `${form?.id}:${revision}`
  const [seenRevision, setSeenRevision] = useState(revisionKey)
  if (seenRevision !== revisionKey) {
    setSeenRevision(revisionKey)
    setLayout(JSON.parse(revision) as ManagedFormLayout)
    setDirty(false)
    setSelected('')
    setPage(0)
  }
  useEffect(() => { onDirty(dirty) }, [dirty, onDirty])
  useEffect(() => { onBusy(busy) }, [busy, onBusy])
  const [seenFocus, setSeenFocus] = useState(focusField)
  const [pendingFocus, setPendingFocus] = useState(focusField)
  if (seenFocus !== focusField) {
    setSeenFocus(focusField)
    setPendingFocus(focusField)
    if (focusField) setFormId(focusField.formId)
  }
  if (pendingFocus && form?.id === pendingFocus.formId) {
    setPendingFocus(null)
    const target = form.layout.fields?.[pendingFocus.key]
    if (target) { setSelected(pendingFocus.key); setPage(target.page) }
  }

  const fields = layout.fields || {}
  const entries = Object.entries(fields)
  const dimensions = layout.page_sizes?.[page]
  const pages = layout.page_sizes || []
  const current = fields[selected]
  const pending = entries.filter(([, field]) => field.needs_review !== false)
  const canConfirm = entries.length > 0 && pending.length === 0
  const disabled = readOnly || busy

  const replace = (next: ManagedFormLayout) => { setLayout(next); setDirty(true); setError('') }
  const change = (key: string, patch: Partial<ManagedFormField>) => {
    const field = fields[key]
    if (!field || disabled) return
    replace({ ...layout, fields: { ...fields, [key]: { ...field, ...patch, needs_review: patch.needs_review === false ? false : true } } })
  }
  const point = (event: PointerEvent) => {
    const rect = canvas.current!.getBoundingClientRect()
    return { x: Math.max(0, Math.min(dimensions!.width, (event.clientX - rect.left) / rect.width * dimensions!.width)),
      y: Math.max(0, Math.min(dimensions!.height, (event.clientY - rect.top) / rect.height * dimensions!.height)) }
  }
  const start = (event: PointerEvent<HTMLDivElement>, mode: Drag['mode'], key = '') => {
    if (disabled || !dimensions || event.button !== 0 || (mode === 'new' && tool !== 'add')) return
    event.preventDefault()
    event.stopPropagation()
    const at = point(event)
    drag.current = { mode, key, ...at, box: key ? [...fields[key].box] as PdfBox : [at.x, at.y, at.x, at.y] }
    canvas.current?.setPointerCapture(event.pointerId)
    if (mode === 'new') setDrawing([at.x, at.y, at.x, at.y])
    else setSelected(key)
  }
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const gesture = drag.current
    if (!gesture || !dimensions) return
    const at = point(event)
    if (gesture.mode === 'new') setDrawing(boundedBox([gesture.x, gesture.y, at.x, at.y], dimensions))
    else if (gesture.mode === 'move') change(gesture.key, { box: movedBox(gesture.box, at.x - gesture.x, at.y - gesture.y, dimensions) })
    else change(gesture.key, { box: boundedBox([gesture.box[0], gesture.box[1], at.x, at.y], dimensions) })
  }
  const end = (event: PointerEvent<HTMLDivElement>) => {
    const gesture = drag.current
    if (!gesture || !dimensions) return
    if (gesture.mode === 'new') {
      const at = point(event)
      const box = boundedBox([gesture.x, gesture.y, at.x, at.y], dimensions)
      if (box[2] - box[0] >= 4 && box[3] - box[1] >= 4 && entries.length < 500) {
        let key = `field_${form?.id || 0}_${++counter.current}`
        while (fields[key]) key = `field_${form?.id || 0}_${++counter.current}`
        replace({ ...layout, fields: { ...fields, [key]: { type: 'text', field_type: 'text', label: '새 입력칸', page, box, confidence: 1, required: false, needs_review: true, autofill_source: null } } })
        setSelected(key)
        setTool('select')
      }
    }
    drag.current = null
    setDrawing(null)
    if (canvas.current?.hasPointerCapture(event.pointerId)) canvas.current.releasePointerCapture(event.pointerId)
  }

  const run = async (action: 'draft' | 'save' | 'confirm') => {
    if (!form || disabled) return
    setBusy(true)
    setError('')
    try {
      let next: ManagedProgramData
      if (action === 'draft') next = await draftProgramForm(postingId, form.id)
      else {
        if (dirty || action === 'save') {
          next = await saveProgramForm(postingId, form.id, layout)
          if (action === 'save') {
            if (mounted.current) { onChanged(next); setDirty(false) }
            return
          }
        }
        next = await confirmProgramForm(postingId, form.id)
      }
      if (mounted.current) { onChanged(next); setDirty(false) }
    } catch (problem: unknown) {
      if (mounted.current) setError(problem instanceof Error ? problem.message : '서식 틀을 저장하지 못했습니다.')
    } finally { if (mounted.current) setBusy(false) }
  }
  const updateCoordinate = (index: number, value: string) => {
    if (!current || !dimensions || value === '') return
    const number = Number(value)
    if (!Number.isFinite(number)) return
    const box = [...current.box] as PdfBox
    box[index] = number
    change(selected, { box: boundedBox(box, dimensions) })
  }

  if (!form) return <p className="managed-program__notice">기본 정보에서 서식 PDF를 먼저 올려 주세요.</p>
  return <section className="template-editor" aria-label="서식 틀 확인 및 수정">
    <div className="template-editor__toolbar">
      <label>서식 <select value={form.id} disabled={busy || dirty} onChange={(event) => setFormId(Number(event.target.value))}>{forms.map((item) => <option key={item.id} value={item.id}>{item.file_name}{item.confirmed ? ' · 확정' : ' · 미확정'}</option>)}</select></label>
      <span role="status">{dirty ? '수정 중 · 미확정' : form.confirmed ? '틀 확정 완료' : '미확정'}</span>
      <button type="button" className="btn" disabled={disabled || dirty} onClick={() => void run('draft')}>{entries.length ? '자동 초안 다시 만들기' : '자동 초안 만들기'}</button>
      <button type="button" className="btn" disabled={disabled || !dirty} onClick={() => void run('save')}>틀 저장</button>
      <button type="button" className="btn btn--primary" disabled={disabled || !canConfirm || (!dirty && form.confirmed)} onClick={() => void run('confirm')}>틀 확정</button>
    </div>
    <p className="pnew__note">자동 초안은 담당자 확인이 필요합니다. 칸을 선택해 라벨·종류·필수를 고친 뒤 확인 완료를 눌러 주세요. 수정한 틀은 다시 확정해야 합니다.</p>
    {dirty && <p className="pnew__note">다른 서식을 열기 전에 틀을 저장해 주세요. <button type="button" className="btn" disabled={busy} onClick={() => { setLayout(form.layout); setDirty(false); setSelected('') }}>저장 전 수정 취소</button></p>}
    {error && <p className="pnew__server-error" role="alert">{error}</p>}
    <div className="template-editor__review" aria-label="확인 필요 입력칸"><strong>확인 필요 {pending.length}개</strong>
      {pending.length > 0 && <ul>{pending.map(([key, field]) => <li key={key}><button type="button" onClick={() => { setSelected(key); setPage(field.page) }}>{field.label || '입력칸'} · {field.page + 1}쪽</button></li>)}</ul>}
      {!entries.length && <p>자동 초안 없음 → 직접 추가. 쪽 위에서 끌어 입력칸을 만들 수 있습니다.</p>}
    </div>
    <div className="template-editor__layout">
      <div className="template-editor__document">
        <div className="template-editor__toolbar">
          <label>쪽 <select value={page} onChange={(event) => { setPage(Number(event.target.value)); setSelected('') }}>{pages.map((_, index) => <option key={index} value={index}>{index + 1} / {pages.length}</option>)}</select></label>
          <button type="button" className="btn" aria-pressed={tool === 'select'} onClick={() => setTool('select')}>칸 선택·이동</button>
          <button type="button" className="btn" aria-pressed={tool === 'add'} disabled={disabled || entries.length >= 500 || !dimensions} onClick={() => setTool('add')}>끌어서 새 칸 추가</button>
        </div>
        {dimensions ? <div ref={canvas} className={`template-editor__page${tool === 'add' ? ' is-drawing' : ''}`} style={{ aspectRatio: `${dimensions.width} / ${dimensions.height}` }} onPointerDown={(event) => start(event, 'new')} onPointerMove={move} onPointerUp={end} onPointerCancel={() => { drag.current = null; setDrawing(null) }}>
          <img src={pageUrl(postingId, form.id, page)} alt={`${form.file_name} ${page + 1}쪽`} draggable={false} />
          {entries.filter(([, field]) => field.page === page).map(([key, field]) => <div key={key} role="button" tabIndex={0} aria-label={`${field.label || '입력칸'}${field.needs_review !== false ? ' · 확인 필요' : ''}`} aria-pressed={selected === key} className={`template-editor__box${field.needs_review !== false ? ' needs-review' : ''}${selected === key ? ' is-selected' : ''}`} style={boxPercent(field.box, dimensions)} onPointerDown={(event) => start(event, 'move', key)} onClick={() => setSelected(key)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(key) } }}>
            <span>{field.label || KIND_LABELS[fieldKind(field)]}</span>
            {!disabled && selected === key && <div className="template-editor__resize" aria-hidden="true" onPointerDown={(event) => start(event, 'resize', key)} />}
          </div>)}
          {drawing && <span className="template-editor__box is-new" style={boxPercent(drawing, dimensions)} />}
        </div> : <p className="managed-program__notice">자동 초안을 만들면 PDF 쪽을 불러옵니다. 빈 서식도 직접 입력칸을 추가할 수 있습니다.</p>}
      </div>
      <aside className="template-editor__properties">
        <h3>입력칸 목록 <small>{entries.length}개</small></h3>
        <ul className="template-editor__field-list">{entries.map(([key, field]) => <li key={key}><button type="button" aria-pressed={selected === key} onClick={() => { setSelected(key); setPage(field.page) }}>{field.needs_review !== false ? '△ ' : '✓ '}{field.label || '입력칸'} <small>{field.page + 1}쪽 · {KIND_LABELS[fieldKind(field)]}</small></button></li>)}</ul>
        {current ? <fieldset disabled={disabled} className="template-editor__settings"><legend>선택한 칸 수정</legend>
          <label>라벨<input maxLength={200} value={current.label || ''} onChange={(event) => change(selected, { label: event.target.value })} /></label>
          <label>종류<select value={fieldKind(current)} onChange={(event) => { const field_type = event.target.value as FieldKind; change(selected, { field_type, type: field_type === 'signature' ? 'image' : field_type === 'check' || field_type === 'radio' ? 'check' : 'text' }) }}>{Object.entries(KIND_LABELS).map(([kind, label]) => <option key={kind} value={kind}>{label}</option>)}</select></label>
          <label className="template-editor__checkbox"><input type="checkbox" checked={!!current.required} onChange={(event) => change(selected, { required: event.target.checked })} />필수 입력</label>
          <label>자동 채움 출처<select value={current.autofill_source === 'phone' ? 'mobile' : current.autofill_source || ''} onChange={(event) => change(selected, { autofill_source: event.target.value as AutofillSource || null })}><option value="">없음</option>{Object.entries(SOURCE_LABELS).filter(([key]) => key !== 'phone').map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          {(fieldKind(current) === 'radio' || fieldKind(current) === 'check') && <label>선택 묶음 이름<input maxLength={80} value={current.group || ''} onChange={(event) => change(selected, { group: event.target.value })} /></label>}
          <div className="template-editor__coordinates">{['왼쪽', '위쪽', '오른쪽', '아래쪽'].map((label, index) => <label key={label}>{label}<input type="number" step="0.5" min={0} max={index % 2 ? dimensions?.height : dimensions?.width} value={Number(current.box[index].toFixed(2))} onChange={(event) => updateCoordinate(index, event.target.value)} /></label>)}</div>
          <p className="pnew__note">PDF 포인트 단위입니다. 상자를 끌어 이동하거나 오른쪽 아래 모서리로 크기를 바꿀 수 있습니다.</p>
          <button type="button" className="btn btn--primary" disabled={!current.label?.trim() || current.needs_review === false} onClick={() => change(selected, { needs_review: false })}>이 칸 확인 완료</button>
          <button type="button" className="btn btn--danger" onClick={() => { const next = { ...fields }; delete next[selected]; replace({ ...layout, fields: next }); setSelected('') }}>입력칸 삭제</button>
        </fieldset> : <p className="pnew__note">PDF 위의 칸이나 목록에서 수정할 칸을 선택해 주세요.</p>}
      </aside>
    </div>
  </section>
}

export function ProgramFormPreview({ postingId, form }: { postingId: number; form: ManagedProgramForm }) {
  const [page, setPage] = useState(0)
  const dimensions = form.layout.page_sizes?.[page]
  return <section className="managed-program__preview-form">
    <h3>{form.file_name}</h3>
    {(form.layout.page_sizes?.length || 0) > 1 && <label>미리보기 쪽 <select value={page} onChange={(event) => setPage(Number(event.target.value))}>{form.layout.page_sizes?.map((_, index) => <option key={index} value={index}>{index + 1}쪽</option>)}</select></label>}
    {dimensions ? <div className="template-editor__page template-editor__page--preview" style={{ aspectRatio: `${dimensions.width} / ${dimensions.height}` }}>
      <img src={pageUrl(postingId, form.id, page)} alt={`${form.file_name} 신청자 서식 ${page + 1}쪽`} />
      {Object.entries(form.layout.fields || {}).filter(([, field]) => field.page === page).map(([key, field]) => <span key={key} className={`managed-program__preview-field managed-program__preview-field--${fieldKind(field)}`} style={boxPercent(field.box, dimensions)}>{fieldKind(field) === 'signature' ? '서명 입력' : fieldKind(field) === 'check' || fieldKind(field) === 'radio' ? '□' : `${field.label || '입력칸'}${field.required ? ' *' : ''}`}</span>)}
    </div> : <p className="pnew__note">서식 틀에서 초안을 만들고 입력칸을 확인해 주세요.</p>}
  </section>
}
