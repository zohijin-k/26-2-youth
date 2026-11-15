/** Existing posting creation screen, extended with the managed form workflow. */
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { createPosting, type OfficerPosting } from '../../api.ts'
import { fetchDocumentSlotOptions, type DocumentSlotOption } from '../../program-workspace-api.ts'
import ProgramStages from './ProgramStages.tsx'
import './officer.css'
import './new-program.css'
import './managed-program.css'

interface Props {
  onCancel: () => void
  onCreated: (posting: OfficerPosting) => void
}

type Field = 'title' | 'apply_start' | 'apply_end' | 'notice_pdf' | 'forms_pdf'
type Picked = { file: File; pdf: boolean | null }
const FIELDS: Field[] = ['title', 'apply_start', 'apply_end', 'notice_pdf', 'forms_pdf']
const MAX_TITLE = 100
const MAX_FILE_BYTES = 20 * 1024 * 1024
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

async function startsAsPdf(file: File): Promise<boolean> {
  try { return (await file.slice(0, 5).text()) === '%PDF-' } catch { return false }
}

function fileError(picked: Picked | undefined, label: string): string {
  if (!picked) return `${label} 파일을 선택해 주세요.`
  if (!picked.file.size || picked.pdf === false) return '내용이 있는 PDF 파일만 올릴 수 있습니다.'
  if (picked.file.size > MAX_FILE_BYTES) return '파일 크기는 20MB 이하여야 합니다.'
  return ''
}

export default function NewProgram({ onCancel, onCreated }: Props) {
  const [title, setTitle] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [notice, setNotice] = useState<Picked[]>([])
  const [forms, setForms] = useState<Picked[]>([])
  const [slots, setSlots] = useState<DocumentSlotOption[] | null>(null)
  const [slotError, setSlotError] = useState('')
  const [slotAttempt, setSlotAttempt] = useState(0)
  const [requiredDocs, setRequiredDocs] = useState<string[]>([])
  const [guidance, setGuidance] = useState('')
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({})
  const [tried, setTried] = useState(false)
  const [sending, setSending] = useState(false)
  const [serverError, setServerError] = useState('')
  const mounted = useRef(true)
  const fileVersions = useRef({ notice_pdf: 0, forms_pdf: 0 })
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    let active = true
    fetchDocumentSlotOptions().then((items) => { if (active) { setSlots(items); setSlotError('') } })
      .catch(() => { if (active) setSlotError('제출 서류 목록을 불러오지 못했습니다.') })
    return () => { active = false }
  }, [slotAttempt])

  const titleLength = [...title.trim()].length
  const errors: Record<Field, string> = {
    title: !titleLength ? '사업명을 입력해 주세요.' : titleLength > MAX_TITLE ? '사업명은 100자 이하로 입력해 주세요.' : '',
    apply_start: !start ? '접수 시작일을 선택해 주세요.' : !ISO_DAY.test(start) ? '접수 시작일을 연도 네 자리로 선택해 주세요.'
      : end && start > end ? '접수 시작일은 접수 종료일보다 늦을 수 없습니다.' : '',
    apply_end: !end ? '접수 종료일을 선택해 주세요.' : !ISO_DAY.test(end) ? '접수 종료일을 연도 네 자리로 선택해 주세요.' : '',
    notice_pdf: fileError(notice[0], '공고문 PDF'),
    forms_pdf: forms.length > 10 ? '서식 PDF는 10개 이하로 올려 주세요.'
      : forms.map((picked) => fileError(picked, '서식 PDF')).find(Boolean) || (!forms.length ? '서식 PDF 파일을 1개 이상 선택해 주세요.' : ''),
  }
  const checking = [...notice, ...forms].some((item) => item.pdf === null)
  const shown = (field: Field) => tried || touched[field] ? errors[field] : ''
  const touch = (field: Field) => setTouched((previous) => ({ ...previous, [field]: true }))
  const pick = (field: 'notice_pdf' | 'forms_pdf', files: FileList | null) => {
    touch(field)
    setServerError('')
    const version = ++fileVersions.current[field]
    const selected = Array.from(files || [])
    const set = field === 'notice_pdf' ? setNotice : setForms
    set(selected.map((file) => ({ file, pdf: null })))
    void Promise.all(selected.map(async (file) => ({ file, pdf: await startsAsPdf(file) }))).then((items) => {
      if (mounted.current && fileVersions.current[field] === version) set(items)
    })
  }
  const fieldProps = (field: Field) => ({
    id: `pnew-${field}`, className: `pnew__input${shown(field) ? ' pnew__input--invalid' : ''}`,
    'aria-invalid': !!shown(field) || undefined, 'aria-describedby': `pnew-${field}-note`, disabled: sending,
  })
  const note = (field: Field, hint: string) => <p id={`pnew-${field}-note`} className={`pnew__note${shown(field) ? ' pnew__note--error' : ''}`} role={shown(field) ? 'alert' : undefined}>{shown(field) || hint}</p>
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (sending || checking || !slots) return
    setTried(true)
    const first = FIELDS.find((field) => errors[field])
    if (first) { document.getElementById(`pnew-${first}`)?.focus(); return }
    setSending(true)
    setServerError('')
    createPosting({ title: title.trim(), apply_start: start, apply_end: end,
      notice_pdf: notice[0].file, forms_pdf: forms[0].file, forms_pdfs: forms.slice(1).map((item) => item.file),
      required_docs: requiredDocs, guidance_text: guidance, workflow_version: 1,
    }).then((created) => { if (mounted.current) onCreated(created) })
      .catch((error: unknown) => {
        if (mounted.current) { setServerError(error instanceof Error ? error.message : '사업을 저장하지 못했습니다. 다시 시도해 주세요.'); setSending(false) }
      })
  }

  return <main className="pnew managed-program">
    <nav className="pnew__bar" aria-label="사업 목록으로"><button type="button" className="pnew__back" onClick={onCancel} disabled={sending}>사업 목록</button></nav>
    <h1 className="pnew__title">새 사업 올리기</h1>
    <ProgramStages />
    <p className="pnew__lead"><strong>작성 중</strong>으로 저장됩니다. 서식 틀을 확인하고 확정한 뒤 게시할 수 있습니다.</p>
    <form className="pnew__form" onSubmit={submit} noValidate>
      <div className="pnew__field"><label className="pnew__label" htmlFor="pnew-title">사업명</label>
        <input {...fieldProps('title')} type="text" value={title} autoComplete="off" onChange={(event) => { setTitle(event.target.value); setServerError('') }} onBlur={() => touch('title')} />
        {note('title', `신청자에게 보이는 이름입니다. ${titleLength} / 100자`)}
      </div>
      <div className="pnew__dates">
        <div className="pnew__field"><label className="pnew__label" htmlFor="pnew-apply_start">접수 시작일</label>
          <input {...fieldProps('apply_start')} type="date" value={start} max={end || '9999-12-31'} onChange={(event) => setStart(event.target.value)} onBlur={() => touch('apply_start')} />
          {note('apply_start', '이 날부터 신청을 받습니다.')}
        </div>
        <div className="pnew__field"><label className="pnew__label" htmlFor="pnew-apply_end">접수 종료일</label>
          <input {...fieldProps('apply_end')} type="date" value={end} min={start || undefined} max="9999-12-31" onChange={(event) => setEnd(event.target.value)} onBlur={() => touch('apply_end')} />
          {note('apply_end', '이 날까지 신청을 받습니다.')}
        </div>
      </div>
      <div className="pnew__field"><label className="pnew__label" htmlFor="pnew-notice_pdf">공고문 PDF</label>
        <input {...fieldProps('notice_pdf')} type="file" accept="application/pdf,.pdf" onChange={(event) => pick('notice_pdf', event.target.files)} />
        {note('notice_pdf', notice[0]?.file.name || 'PDF 1개, 20MB 이하. 암호가 없는 파일을 올려 주세요.')}
      </div>
      <div className="pnew__field"><label className="pnew__label" htmlFor="pnew-forms_pdf">서식 PDF</label>
        <input {...fieldProps('forms_pdf')} type="file" multiple accept="application/pdf,.pdf" onChange={(event) => pick('forms_pdf', event.target.files)} />
        {note('forms_pdf', '1개 이상, 최대 10개. 파일당 20MB·20쪽 이하이며 암호가 없어야 합니다.')}
        {forms.length > 0 && <ul className="managed-program__files">{forms.map((item, index) => <li key={index}>{item.file.name} · {(item.file.size / 1024 / 1024).toFixed(2)}MB</li>)}</ul>}
      </div>
      <fieldset className="managed-program__slots" disabled={sending}>
        <legend>제출 서류 선택</legend>
        {slots?.map((slot) => <label key={slot.key}><input type="checkbox" checked={requiredDocs.includes(slot.key)} onChange={(event) => setRequiredDocs((previous) => event.target.checked ? [...previous, slot.key] : previous.filter((key) => key !== slot.key))} />{slot.label}</label>)}
        {!slots && !slotError && <p className="pnew__note" role="status">제출 서류 목록을 불러오는 중입니다.</p>}
        {slotError && <p className="pnew__note pnew__note--error" role="alert">{slotError} <button type="button" className="btn" onClick={() => setSlotAttempt((value) => value + 1)}>다시 시도</button></p>}
        <p className="pnew__note">선택한 서류를 신청자가 업로드합니다. 온라인 작성 서식은 위에서 따로 올립니다.</p>
      </fieldset>
      <div className="pnew__field"><label className="pnew__label" htmlFor="pnew-guidance">안내 메시지</label>
        <textarea id="pnew-guidance" className="pnew__input" value={guidance} maxLength={20000} disabled={sending} onChange={(event) => setGuidance(event.target.value)} />
        <p className="pnew__note">신청자에게 보일 안내입니다. 저장한 뒤에도 수정할 수 있습니다.</p>
      </div>
      <div className="pnew__actions">
        {serverError && <p className="pnew__server-error" role="alert">{serverError}</p>}
        <button type="button" className="btn" onClick={onCancel} disabled={sending}>취소</button>
        <button type="submit" className="btn btn--primary" disabled={sending || checking || !slots}>{sending ? '저장 중' : '작성 중으로 저장'}</button>
      </div>
    </form>
  </main>
}
