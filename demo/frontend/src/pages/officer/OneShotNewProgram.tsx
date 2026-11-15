import { useState, type FormEvent } from 'react'
import type { OfficerPosting } from '../../api.ts'
import { analyzeProgram } from '../../notice-draft-api.ts'
import './officer.css'
import './new-program.css'
import './program-preview.css'

export default function OneShotNewProgram({ onCancel, onCreated }: { onCancel: () => void; onCreated: (posting: OfficerPosting) => void }) {
  const [notice, setNotice] = useState<File | null>(null)
  const [forms, setForms] = useState<File[]>([])
  const [supplemental, setSupplemental] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const mock = new URLSearchParams(window.location.search).get('mock') === '1'
  if (mock) return <main className="pnew one-shot-upload"><h1 className="pnew__title">합성 목업</h1><p>목업에서는 신청 목록과 심사 예시를 확인할 수 있습니다.</p><button className="btn" onClick={onCancel}>사업 목록</button></main>
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!notice || !forms.length || busy) return
    setBusy(true); setError('')
    try { const data = await analyzeProgram(notice, forms, supplemental); onCreated(data.posting) }
    catch (problem: unknown) { setError(problem instanceof Error ? problem.message : '파일을 분석하지 못했습니다.'); setBusy(false) }
  }
  return <main className="pnew one-shot-upload"><button className="pnew__back" onClick={onCancel} disabled={busy}>사업 목록</button>
    <p className="program-preview__eyebrow">올리기 → 분석 → 예시 페이지 수정 → 게시</p><h1 className="pnew__title">새 사업 올리기</h1>
    <p className="pnew__lead">공고문과 서식을 한 번에 올려 주세요. 초안을 확인하고 신청자가 볼 화면에서 직접 수정합니다.</p>
    <form className="pnew__form" onSubmit={(event) => void submit(event)}>
      <label className="pnew__field">공고문 PDF<input id="program-notice" className="pnew__input" type="file" accept="application/pdf,.pdf" required disabled={busy} onChange={(event) => setNotice(event.target.files?.[0] || null)} /></label>
      <label className="pnew__field">서식 PDF (여러 개 가능)<input id="program-forms" className="pnew__input" type="file" accept="application/pdf,.pdf" multiple required disabled={busy} onChange={(event) => setForms(Array.from(event.target.files || []))} /></label>
      <p className="pnew__note">서식 1~10개, 파일당 20MB·20쪽 이하, 암호 없는 PDF를 올려 주세요.</p>
      {!!forms.length && <ul>{forms.map((file, index) => <li key={index}>{file.name}</li>)}</ul>}
      <label className="pnew__field">부가 설명문 (선택)<textarea id="program-supplemental" className="pnew__input" maxLength={4000} value={supplemental} disabled={busy} onChange={(event) => setSupplemental(event.target.value)} /></label>
      <p className="pnew__note">{supplemental.length} / 4,000자 · 공고문에 덧붙일 공개 안내를 입력해 주세요.</p>
      {error && <p role="alert" className="pnew__server-error">{error}</p>}
      <div className="pnew__actions"><button className="btn" type="button" onClick={onCancel} disabled={busy}>취소</button><button className="btn btn--primary" type="submit" disabled={busy || !notice || !forms.length}>{busy ? '공고문과 서식을 분석하고 있습니다…' : '분석하기'}</button></div>
    </form></main>
}
