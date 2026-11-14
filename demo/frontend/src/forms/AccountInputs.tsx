import { useEffect, useRef, useState } from 'react'
import { fetchChecklist, uploadDocument, type Identity, type UploadedDocument } from '../api.ts'
import FilePreview from '../components/ApplicantFilePreview.tsx'
import Spinner from '../components/Spinner.tsx'
import { friendlyError } from '../lib/error-copy.ts'
import type { Form1Value } from './form1-model.ts'

export default function AccountInputs({ applicationId, identity, value, onChange, onFlush, readOnly, onBusyChange }: {
  applicationId: number; identity: Identity | null; value: Form1Value
  onChange: (value: Form1Value) => void; onFlush: () => Promise<void>; readOnly: boolean
  onBusyChange: (busy: boolean) => void
}) {
  const [file, setFile] = useState<UploadedDocument | null>(null)
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState(false)
  const [error, setError] = useState('')
  const current = useRef(value)
  useEffect(() => { current.current = value }, [value])
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    fetchChecklist(applicationId).then((checklist) => {
      if (mounted.current) setFile(checklist.items.find((item) => item.slot_key === 'bank_account')?.documents[0] ?? null)
    }).catch(() => { if (mounted.current) setError('통장 사본 첨부 상태를 불러오지 못했습니다. 다시 확인해 주세요.') })
    return () => { mounted.current = false }
  }, [applicationId])
  const pickFile = async (picked: File | undefined) => {
    if (!picked || busy) return
    setError('')
    if (!/\.(pdf|jpe?g|png)$/i.test(picked.name) || !picked.size) {
      setError('내용이 있는 PDF·JPG·PNG 통장 사본을 선택해 주세요.'); return
    }
    if (picked.size > 20 * 1024 * 1024) { setError('통장 사본은 20MB 이하로 올려 주세요.'); return }
    setBusy(true)
    onBusyChange(true)
    try {
      await onFlush()
      const uploaded = await uploadDocument(applicationId, 'bank_account', picked, '')
      if (!mounted.current) return
      setFile(uploaded)
      onChange({ ...current.current, bankbookFileName: uploaded.file_name })
    } catch (problem: unknown) {
      if (mounted.current) setError(friendlyError(problem, '통장 사본을 올리지 못했습니다. 다시 시도해 주세요.'))
    } finally {
      if (mounted.current) { setBusy(false); onBusyChange(false) }
    }
  }
  const holderMismatch = !!identity && !!value.accountHolder.trim() && value.accountHolder.replace(/\s/g, '') !== identity.name.replace(/\s/g, '')
  return <section className="pdf-forms__selfcheck" id="workspace-account" aria-busy={busy}>
    <h3>입금 받을 계좌</h3>
    <p>지원금은 본인 명의 계좌로만 지급됩니다. 예금주와 계좌번호가 보이는 통장 사본을 첨부해 주세요.</p>
    <div className="field"><label className="field__label" htmlFor="account-holder">예금주 <span className="field__req">필수</span></label>
      <input id="account-holder" className="input" autoComplete="name" value={value.accountHolder} disabled={readOnly || busy} aria-invalid={holderMismatch || undefined} aria-describedby={holderMismatch ? 'account-holder-error' : undefined} onChange={(event) => onChange({ ...value, accountHolder: event.target.value })} />
      {holderMismatch && <p className="field__error" id="account-holder-error" role="alert">지원금은 본인 명의 계좌로만 지급됩니다. 예금주를 본인인증 성명과 같게 입력해 주세요.</p>}
    </div>
    <div className="field"><span className="field__label">통장 사본 <span className="field__req">필수</span></span>
      <p>{file?.file_name || value.bankbookFileName || '첨부한 파일이 없습니다.'}</p>
      {!readOnly && <label className="btn" htmlFor="bankbook-file">{busy ? <><Spinner /> 올리는 중…</> : file ? '다른 파일 선택' : '통장 사본 선택'}</label>}
      {!readOnly && <input id="bankbook-file" type="file" className="sr-only" accept=".pdf,.jpg,.jpeg,.png" disabled={busy} onChange={(event) => { const picked = event.target.files?.[0]; event.target.value = ''; void pickFile(picked) }} />}
      {file && <button className="btn" type="button" onClick={() => setViewing(true)}>통장 사본 미리보기</button>}
      <p className="field__hint">PDF·JPG·PNG, 20MB 이하. 첨부 파일은 담당자가 원본으로 확인합니다.</p>
    </div>
    {error && <p className="field__error" role="alert">{error}</p>}
    {viewing && file && <FilePreview url={file.file_url} name={file.file_name} kind={file.file_format === 'pdf' ? 'pdf' : 'image'} onClose={() => setViewing(false)} />}
  </section>
}
