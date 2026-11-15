import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { OfficerPosting } from '../../api.ts'
import { analyzeProgram } from '../../notice-draft-api.ts'
import { OfficerDrawer } from './OfficerModern.tsx'
import './officer.css'
import './new-program.css'
import './officer-entry-modern.css'

const STEPS = ['올리기', '분석', '예시 페이지 수정', '게시']
const MAX_BYTES = 20 * 1024 * 1024
function fileSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.ceil(bytes / 1024))}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`
}
function fileProblem(files: File[]): string {
  // The server validates PDF content, encryption and page limits regardless of filename.
  if (files.some((file) => !file.size)) return '내용이 없는 파일입니다. 다시 선택해 주세요.'
  if (files.some((file) => file.size > MAX_BYTES)) return '파일당 20MB 이하인 PDF를 선택해 주세요.'
  return ''
}
function uniqueFiles(files: File[]): File[] {
  const seen = new Set<string>()
  return files.filter((file) => {
    const key = `${file.name}\u0000${file.size}\u0000${file.lastModified}`
    if (seen.has(key)) return false
    seen.add(key); return true
  })
}
export default function OneShotNewProgram({ onCancel, onCreated }: { onCancel: () => void; onCreated: (posting: OfficerPosting) => void }) {
  const [notice, setNotice] = useState<File | null>(null)
  const [forms, setForms] = useState<File[]>([])
  const [supplemental, setSupplemental] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [dragging, setDragging] = useState<'notice' | 'forms' | null>(null)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const noticeInput = useRef<HTMLInputElement>(null)
  const formsInput = useRef<HTMLInputElement>(null)
  const mock = new URLSearchParams(window.location.search).get('mock') === '1'
  useEffect(() => {
    if (!busy || startedAt === null) return
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [busy, startedAt])
  const choose = (kind: 'notice' | 'forms', incoming: File[]) => {
    if (busy || !incoming.length) return
    const next = kind === 'forms' ? uniqueFiles([...forms, ...incoming]) : incoming
    const problem = kind === 'notice' && incoming.length !== 1 ? '공고문 PDF는 1개만 선택해 주세요.'
      : next.length > 10 ? '서식 PDF는 10개까지 선택할 수 있습니다.' : fileProblem(incoming)
    if (problem) { setError(problem); return }
    if (kind === 'notice') setNotice(incoming[0])
    else setForms(next)
    setError('')
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!notice || !forms.length || busy) return
    setBusy(true); setError(''); setElapsed(0); setStartedAt(Date.now())
    try { const data = await analyzeProgram(notice, forms, supplemental); if (mounted.current) onCreated(data.posting) }
    catch (problem: unknown) { if (mounted.current) { setError(problem instanceof Error ? problem.message : '파일을 분석하지 못했습니다.'); setBusy(false) } }
  }
  const zone = (kind: 'notice' | 'forms', label: string, files: File[]) => {
    const input = kind === 'notice' ? noticeInput : formsInput
    return <div className={`om-upload-slot${dragging === kind ? ' is-dragging' : ''}`}
      onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(kind) }}
      onDragLeave={(event) => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setDragging(null) }}
      onDrop={(event) => { event.preventDefault(); setDragging(null); choose(kind, Array.from(event.dataTransfer.files)) }}>
      <input ref={input} id={kind === 'notice' ? 'program-notice' : 'program-forms'} type="file" accept="application/pdf,.pdf"
        multiple={kind === 'forms'} hidden disabled={busy} aria-label={label} onChange={(event) => {
          choose(kind, Array.from(event.target.files || [])); event.target.value = ''
        }} />
      <button type="button" className="om-upload-zone" disabled={busy} onClick={() => input.current?.click()}>
        <strong>{label}</strong><span>파일 선택 또는 여기로 끌어놓기</span><small>{kind === 'notice' ? 'PDF 1개' : 'PDF 1~10개'}</small>
      </button>
      {!!files.length && <ul className="om-upload-files" aria-label={`${label} 선택한 파일`}>{files.map((file, index) => <li key={`${file.name}-${file.size}-${file.lastModified}`} className="om-chip">
        <span>{file.name} · {fileSize(file.size)}</span><button type="button" className="om-upload-remove" disabled={busy} aria-label={`${file.name} 선택 취소`} onClick={() => {
          if (kind === 'notice') setNotice(null)
          else setForms((current) => current.filter((_, at) => at !== index))
        }}>✕</button>
      </li>)}</ul>}
    </div>
  }
  return <main className="om om-page om-entry-upload pnew one-shot-upload">
    <header className="om-head"><OfficerDrawer current="new" onList={onCancel} disabled={busy} /><h1 className="pnew__title">새 사업 올리기</h1></header>
    {mock ? <p className="om-notice">목업에서는 신청 목록과 심사 예시를 확인할 수 있습니다.</p> : <>
      <p className="om-subtle">공고문과 서식을 올린 뒤, 신청자가 볼 화면에서 내용을 확인합니다.</p>
      <ol className="om-upload-steps" aria-label="사업 게시 진행 단계">{STEPS.map((step, index) => <li key={step} className="om-chip" aria-current={index === (busy ? 1 : 0) ? 'step' : undefined}>{index + 1} {step}</li>)}</ol>
      <form className="om-card om-stack" onSubmit={(event) => void submit(event)}>
        <div className="om-upload-zones">{zone('notice', '공고문 PDF', notice ? [notice] : [])}{zone('forms', '서식 PDF', forms)}</div>
        <p className="om-subtle om-upload-limits">서식 1~10개 · 파일당 20MB·20쪽 이하 · 암호 없는 PDF</p>
        <label className="om-upload-supplemental" htmlFor="program-supplemental">부가 설명문 (선택)
          <textarea id="program-supplemental" maxLength={4000} rows={3} value={supplemental} disabled={busy} onChange={(event) => setSupplemental(event.target.value)} />
        </label>
        <small>{supplemental.length.toLocaleString('ko-KR')} / 4,000자 · 공고문에 덧붙일 공개 안내</small>
        {error && <p role="alert" className="om-notice">{error}</p>}
        {busy && <p role="status" className="om-notice">파일을 올리고 분석하고 있습니다. {elapsed}초 경과</p>}
        <div className="om-upload-actions"><button className="btn btn--primary" type="submit" disabled={busy || !notice || !forms.length}>{busy ? '분석 중…' : error ? '다시 시도' : '분석하기'}</button></div>
      </form>
    </>}
  </main>
}
