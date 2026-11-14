/**
 * 새 사업 올리기 — 사업명·접수 기간·공고문 PDF·서식 PDF로 사업을 만든다.
 *
 * 만든 사업은 작성 중 상태다. 게시하기 전에는 신청자 화면에 나오지 않는다.
 * 칸마다 서버와 같은 규칙으로 먼저 확인하고, 서버가 돌려준 문장은 저장 버튼 옆에
 * 그대로 보여 준다. 칸 이름은 서버 문장이 쓰는 이름(사업명·접수 시작일·접수 종료일·
 * 공고문 PDF·서식 PDF)과 같게 둔다.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { createPosting, type OfficerPosting } from '../../api.ts'
import './officer.css'
import './new-program.css'

interface Props {
  onCancel: () => void
  onCreated: (posting: OfficerPosting) => void
}

const MAX_TITLE = 100
/** 날짜 입력은 연도 다섯 자리 이상도 받을 수 있다. 서버 형식(YYYY-MM-DD)만 통과시킨다. */
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/
const MAX_DAY = '9999-12-31'
const MAX_FILE_BYTES = 20 * 1024 * 1024

type Field = 'title' | 'apply_start' | 'apply_end' | 'notice_pdf' | 'forms_pdf'
const FIELDS: Field[] = ['title', 'apply_start', 'apply_end', 'notice_pdf', 'forms_pdf']

/** 고른 파일. `pdf`는 파일 머리글을 읽어 본 결과이고, 읽는 동안은 null이다. */
type Picked = { file: File; pdf: boolean | null }

/** 서버와 같은 기준: 파일이 `%PDF-`로 시작해야 한다. */
async function startsAsPdf(file: File): Promise<boolean> {
  try {
    return (await file.slice(0, 5).text()) === '%PDF-'
  } catch {
    return false
  }
}

function fileError(picked: Picked | null, label: string): string {
  if (!picked) return `${label} 파일을 선택해 주세요.`
  if (picked.pdf === false) return 'PDF 파일만 올릴 수 있습니다.'
  if (picked.file.size > MAX_FILE_BYTES) return '파일 크기는 20MB 이하여야 합니다.'
  return ''
}

function megabytes(size: number): string {
  return `${(size / (1024 * 1024)).toFixed(size < 1024 * 1024 ? 2 : 1)}MB`
}

export default function NewProgram({ onCancel, onCreated }: Props) {
  const [title, setTitle] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [notice, setNotice] = useState<Picked | null>(null)
  const [forms, setForms] = useState<Picked | null>(null)
  /** 한 번이라도 손댄 칸. 손대기 전에는 빈 칸을 오류로 보이지 않는다. */
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({})
  const [tried, setTried] = useState(false)
  const [sending, setSending] = useState(false)
  const [serverError, setServerError] = useState('')

  const titleLength = [...title.trim()].length
  const errors: Record<Field, string> = {
    title: titleLength === 0 ? '사업명을 입력해 주세요.'
      : titleLength > MAX_TITLE ? `사업명은 ${MAX_TITLE}자 이하로 입력해 주세요.` : '',
    apply_start: !start ? '접수 시작일을 선택해 주세요.'
      : !ISO_DAY.test(start) ? '접수 시작일을 연도 네 자리로 다시 선택해 주세요.'
      : end && start > end ? '접수 시작일은 접수 종료일보다 늦을 수 없습니다.' : '',
    apply_end: !end ? '접수 종료일을 선택해 주세요.'
      : !ISO_DAY.test(end) ? '접수 종료일을 연도 네 자리로 다시 선택해 주세요.' : '',
    notice_pdf: fileError(notice, '공고문 PDF'),
    forms_pdf: fileError(forms, '서식 PDF'),
  }
  const shown = (field: Field) => (tried || touched[field] ? errors[field] : '')
  const touch = (field: Field) => setTouched((prev) => (prev[field] ? prev : { ...prev, [field]: true }))
  const checking = notice?.pdf === null || forms?.pdf === null

  const pick = (field: 'notice_pdf' | 'forms_pdf', file: File | undefined) => {
    const set = field === 'notice_pdf' ? setNotice : setForms
    touch(field)
    setServerError('')
    if (!file) {
      set(null)
      return
    }
    set({ file, pdf: null })
    void startsAsPdf(file).then((pdf) => {
      // 읽는 사이에 다른 파일을 골랐으면 버린다.
      set((current) => (current?.file === file ? { file, pdf } : current))
    })
  }

  // 저장 응답이 오기 전에 화면을 떠났으면 그 응답으로 주소나 화면을 바꾸지 않는다.
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (sending || checking) return
    setTried(true)
    const firstInvalid = FIELDS.find((field) => errors[field])
    if (firstInvalid || !notice || !forms) {
      if (firstInvalid) document.getElementById(`pnew-${firstInvalid}`)?.focus()
      return
    }
    setSending(true)
    setServerError('')
    createPosting({
      title: title.trim(),
      apply_start: start,
      apply_end: end,
      notice_pdf: notice.file,
      forms_pdf: forms.file,
    })
      .then((created) => { if (mounted.current) onCreated(created) })
      .catch((error: unknown) => {
        if (!mounted.current) return
        setServerError(error instanceof Error ? error.message : String(error))
        setSending(false)
      })
  }

  const fieldProps = (field: Field) => {
    const message = shown(field)
    return {
      id: `pnew-${field}`,
      className: message ? 'pnew__input pnew__input--invalid' : 'pnew__input',
      'aria-invalid': message ? true : undefined,
      'aria-describedby': `pnew-${field}-note`,
      disabled: sending,
    }
  }

  /** 칸 아래 한 줄. 오류가 있으면 오류가 도움말 자리를 차지한다. */
  const note = (field: Field, hint: string) => {
    const message = shown(field)
    return (
      <p
        id={`pnew-${field}-note`}
        className={message ? 'pnew__note pnew__note--error' : 'pnew__note'}
        role={message ? 'alert' : undefined}
      >
        {message || hint}
      </p>
    )
  }

  const fileHint = (picked: Picked | null, hint: string) =>
    picked ? `${picked.file.name} · ${megabytes(picked.file.size)}` : hint

  return (
    <main className="pnew">
      <nav className="pnew__bar" aria-label="사업 목록으로">
        <button type="button" className="pnew__back" onClick={onCancel} disabled={sending}>사업 목록</button>
      </nav>

      <h1 className="pnew__title">새 사업 올리기</h1>
      <p className="pnew__lead">
        <strong>작성 중</strong>으로 저장됩니다. 게시하기 전에는 신청자에게 보이지 않습니다.
      </p>

      <form className="pnew__form" onSubmit={submit} noValidate>
        <div className="pnew__field">
          <label className="pnew__label" htmlFor="pnew-title">사업명</label>
          <input
            {...fieldProps('title')}
            type="text"
            value={title}
            autoComplete="off"
            onChange={(event) => { setTitle(event.target.value); setServerError('') }}
            onBlur={() => touch('title')}
          />
          {note('title', `신청자에게 보이는 이름입니다. ${titleLength} / ${MAX_TITLE}자`)}
        </div>

        <div className="pnew__dates">
          <div className="pnew__field">
            <label className="pnew__label" htmlFor="pnew-apply_start">접수 시작일</label>
            <input
              {...fieldProps('apply_start')}
              type="date"
              value={start}
              max={end || MAX_DAY}
              onChange={(event) => { setStart(event.target.value); setServerError('') }}
              onBlur={() => touch('apply_start')}
            />
            {note('apply_start', '이 날부터 신청을 받습니다.')}
          </div>
          <div className="pnew__field">
            <label className="pnew__label" htmlFor="pnew-apply_end">접수 종료일</label>
            <input
              {...fieldProps('apply_end')}
              type="date"
              value={end}
              min={start || undefined}
              max={MAX_DAY}
              onChange={(event) => { setEnd(event.target.value); setServerError('') }}
              onBlur={() => touch('apply_end')}
            />
            {note('apply_end', '이 날까지 신청을 받습니다.')}
          </div>
        </div>

        <div className="pnew__field">
          <label className="pnew__label" htmlFor="pnew-notice_pdf">공고문 PDF</label>
          <input
            {...fieldProps('notice_pdf')}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => pick('notice_pdf', event.target.files?.[0])}
          />
          {note('notice_pdf', fileHint(notice, '신청자가 사업 안내에서 읽는 공고문입니다. PDF, 20MB 이하'))}
        </div>

        <div className="pnew__field">
          <label className="pnew__label" htmlFor="pnew-forms_pdf">서식 PDF</label>
          <input
            {...fieldProps('forms_pdf')}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => pick('forms_pdf', event.target.files?.[0])}
          />
          {note('forms_pdf', fileHint(forms, '신청자가 작성할 서식을 한 파일로 묶은 것입니다. PDF, 20MB 이하'))}
        </div>

        <div className="pnew__actions">
          {serverError && <p className="pnew__server-error" role="alert">{serverError}</p>}
          <button type="button" className="btn" onClick={onCancel} disabled={sending}>취소</button>
          <button type="submit" className="btn btn--primary" disabled={sending || checking}>
            {sending ? '저장 중' : '작성 중으로 저장'}
          </button>
        </div>
      </form>
    </main>
  )
}
