/** Managed posting basics; form review and publication are added in the next stage. */
import { useEffect, useRef, useState, type FormEvent } from 'react'

import {
  fetchProgramWorkspace, replaceProgramFiles, saveProgramWorkspace,
  type ManagedProgramData, type ManagedProgramFields,
} from '../../program-workspace-api.ts'
import FilePreview from '../../components/FilePreview.tsx'
import ProgramStages from './ProgramStages.tsx'
import './new-program.css'
import './managed-program.css'

interface Props { postingId: number; onBack: () => void }
const emptyFields: ManagedProgramFields = { title: '', apply_start: '', apply_end: '', guidance_text: '', required_docs: [] }

export default function ManagedProgramWorkspace({ postingId, onBack }: Props) {
  const [data, setData] = useState<ManagedProgramData | null>(null)
  const [fields, setFields] = useState<ManagedProgramFields>(emptyFields)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<File | null>(null)
  const [forms, setForms] = useState<File[]>([])
  const [filesKey, setFilesKey] = useState(0)
  const [viewing, setViewing] = useState<{ url: string; name: string } | null>(null)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  useEffect(() => {
    let active = true
    fetchProgramWorkspace(postingId).then((next) => {
      if (!active) return
      setData(next)
      setFields({ title: next.posting.title, apply_start: next.posting.apply_start,
        apply_end: next.posting.apply_end, guidance_text: next.posting.guidance_text, required_docs: next.required_docs })
      setError('')
    }).catch((problem: unknown) => { if (active) setError(problem instanceof Error ? problem.message : '사업 정보를 불러오지 못했습니다.') })
    return () => { active = false }
  }, [postingId, attempt])

  const saveBasics = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setSaved('')
    setError('')
    try {
      const next = await saveProgramWorkspace(postingId, fields)
      if (mounted.current) { setData(next); setSaved('사업 기본 정보를 작성 중으로 저장했습니다.') }
    } catch (problem: unknown) {
      if (mounted.current) setError(problem instanceof Error ? problem.message : '사업 정보를 저장하지 못했습니다.')
    } finally { if (mounted.current) setBusy(false) }
  }

  const saveFiles = async () => {
    if (busy || (!notice && !forms.length)) return
    setBusy(true)
    setSaved('')
    setError('')
    try {
      const next = await replaceProgramFiles(postingId, notice, forms)
      if (!mounted.current) return
      setData(next)
      setNotice(null)
      setForms([])
      setFilesKey((key) => key + 1)
      setSaved('선택한 PDF 파일을 저장했습니다. 바뀐 서식은 틀을 다시 확인해야 합니다.')
    } catch (problem: unknown) {
      if (mounted.current) setError(problem instanceof Error ? problem.message : 'PDF 파일을 저장하지 못했습니다.')
    } finally { if (mounted.current) setBusy(false) }
  }

  const edit = (next: Partial<ManagedProgramFields>) => { setFields((previous) => ({ ...previous, ...next })); setSaved('') }
  const readonly = busy || data?.posting.status !== 'draft' || !data?.managed
  const posting = data?.posting

  return <main className="managed-program">
    <nav className="pnew__bar" aria-label="사업 작업 공간"><button type="button" className="pnew__back" onClick={onBack} disabled={busy}>사업 목록</button></nav>
    <h1 className="pnew__title">{posting?.title || '사업 정보'}</h1>
    <ProgramStages />
    {!data ? <div className="managed-program__notice" role={error ? 'alert' : 'status'}>{error || '사업 정보를 불러오는 중입니다.'}{error && <button type="button" className="btn" onClick={() => setAttempt((value) => value + 1)}>다시 시도</button>}</div> : <>
      <p className="pnew__lead"><strong>{posting?.phase_label}</strong> · 서식 틀을 모두 확인하고 확정한 뒤 게시할 수 있습니다.</p>
      {!data.managed && <p className="managed-program__notice">이전 방식으로 등록된 사업입니다. 새 사업 올리기에서 서식 작성이 가능한 사업을 등록해 주세요.</p>}
      {data.managed && posting?.status !== 'draft' && <p className="managed-program__notice">게시된 사업은 읽기 전용입니다. 게시를 취소한 뒤 기본 정보와 서식을 수정할 수 있습니다.</p>}
      <form className="pnew__form" onSubmit={(event) => void saveBasics(event)}>
        <div className="pnew__field"><label className="pnew__label" htmlFor="pedit-title">사업명</label>
          <input id="pedit-title" className="pnew__input" required maxLength={100} value={fields.title} disabled={readonly} onChange={(event) => edit({ title: event.target.value })} />
        </div>
        <div className="pnew__dates">
          <div className="pnew__field"><label className="pnew__label" htmlFor="pedit-start">접수 시작일</label>
            <input id="pedit-start" className="pnew__input" required type="date" value={fields.apply_start} max={fields.apply_end || '9999-12-31'} disabled={readonly} onChange={(event) => edit({ apply_start: event.target.value })} />
          </div>
          <div className="pnew__field"><label className="pnew__label" htmlFor="pedit-end">접수 종료일</label>
            <input id="pedit-end" className="pnew__input" required type="date" value={fields.apply_end} min={fields.apply_start || undefined} max="9999-12-31" disabled={readonly} onChange={(event) => edit({ apply_end: event.target.value })} />
          </div>
        </div>
        <fieldset className="managed-program__slots" disabled={readonly}><legend>제출 서류 선택</legend>
          {data.slot_options.map((slot) => <label key={slot.key}><input type="checkbox" checked={fields.required_docs.includes(slot.key)} onChange={(event) => edit({ required_docs: event.target.checked ? [...fields.required_docs, slot.key] : fields.required_docs.filter((key) => key !== slot.key) })} />{slot.label}</label>)}
          <p className="pnew__note">선택한 서류를 신청자 업로드 화면에 표시합니다.</p>
        </fieldset>
        <div className="pnew__field"><label className="pnew__label" htmlFor="pedit-guidance">안내 메시지</label>
          <textarea id="pedit-guidance" className="pnew__input" maxLength={20000} value={fields.guidance_text} disabled={readonly} onChange={(event) => edit({ guidance_text: event.target.value })} />
        </div>
        <div className="pnew__actions"><button type="submit" className="btn btn--primary" disabled={readonly}>{busy ? '저장 중' : '작성 중으로 저장'}</button></div>
      </form>
      <section className="pnew__form" aria-labelledby="pedit-files-title" style={{ marginTop: 16 }}>
        <h2 id="pedit-files-title" className="pnew__label">공고문·서식 PDF</h2>
        {posting?.notice_url && <div className="managed-program__existing"><strong>공고문</strong><span>{posting.notice_file_name}</span><button type="button" className="btn" onClick={() => setViewing({ url: posting.notice_url!, name: posting.notice_file_name || '공고문 PDF' })}>보기</button></div>}
        {data.forms.map((form) => <div className="managed-program__existing" key={form.id}><strong>서식</strong><span>{form.file_name}</span><button type="button" className="btn" onClick={() => setViewing({ url: form.file_url, name: form.file_name })}>보기</button></div>)}
        <div className="pnew__field"><label className="pnew__label" htmlFor="pedit-notice">공고문 바꾸기</label>
          <input key={`notice-${filesKey}`} id="pedit-notice" className="pnew__input" type="file" accept="application/pdf,.pdf" disabled={readonly} onChange={(event) => { setNotice(event.target.files?.[0] || null); setSaved('') }} />
        </div>
        <div className="pnew__field"><label className="pnew__label" htmlFor="pedit-forms">서식 PDF 전체 바꾸기</label>
          <input key={`forms-${filesKey}`} id="pedit-forms" className="pnew__input" type="file" multiple accept="application/pdf,.pdf" disabled={readonly} onChange={(event) => { setForms(Array.from(event.target.files || [])); setSaved('') }} />
          <p className="pnew__note">파일당 20MB, 서식은 파일당 20쪽 이하·최대 10개입니다. 서식을 바꾸면 기존 틀을 다시 확인합니다.</p>
        </div>
        <div className="pnew__actions"><button type="button" className="btn" disabled={readonly || (!notice && !forms.length)} onClick={() => void saveFiles()}>선택한 PDF 저장</button></div>
      </section>
      {error && <p className="pnew__server-error" role="alert" style={{ marginTop: 12 }}>{error}</p>}
      {saved && <p className="managed-program__saved" role="status">{saved}</p>}
    </>}
    {viewing && <FilePreview url={viewing.url} name={viewing.name} kind="pdf" onClose={() => setViewing(null)} />}
  </main>
}
