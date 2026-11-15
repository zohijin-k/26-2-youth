import { useEffect, useRef, useState } from 'react'
import { fetchChecklist, uploadDocument, type Identity, type UploadedDocument } from '../api.ts'
import FilePreview from '../components/ApplicantFilePreview.tsx'
import Icon from '../components/Icon.tsx'
import MoreInfo from '../components/MoreInfo.tsx'
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
  const fileName = file?.file_name || value.bankbookFileName
  return <section className="pdf-forms__card pdf-forms__account" id="workspace-account" aria-busy={busy}>
    <h3>입금 받을 계좌</h3>
    <p className="pdf-forms__lead">지원금은 본인 명의 계좌로만 지급됩니다.</p>
    <div className="field"><label className="field__label" htmlFor="account-holder">예금주<span className="field__req">필수</span></label>
      <input id="account-holder" className="input pdf-forms__short" autoComplete="name" value={value.accountHolder} disabled={readOnly || busy} aria-invalid={holderMismatch || undefined} aria-describedby={holderMismatch ? 'account-holder-error' : undefined} onChange={(event) => onChange({ ...value, accountHolder: event.target.value })} />
      {holderMismatch && <p className="field__error" id="account-holder-error" role="alert"><Icon name="alertCircle" size={18} /><span>예금주를 본인인증 성명과 같게 입력해 주세요.</span></p>}
    </div>
    <div className="field"><span className="field__label" id="bankbook-label">통장 사본<span className="field__req">필수</span></span>
      <div className={fileName ? 'pdf-forms__file' : 'pdf-forms__file is-empty'}>
        <span className="pdf-forms__file-name"><Icon name={fileName ? 'checkCircle' : 'file'} size={22} />{fileName || '아직 올리지 않았습니다'}</span>
        <span className="pdf-forms__file-actions">
          {file && <button className="btn" type="button" onClick={() => setViewing(true)}>미리보기</button>}
          {!readOnly && <input id="bankbook-file" type="file" className="sr-only" accept=".pdf,.jpg,.jpeg,.png" disabled={busy} aria-labelledby="bankbook-label" aria-describedby="bankbook-hint" onChange={(event) => { const picked = event.target.files?.[0]; event.target.value = ''; void pickFile(picked) }} />}
          {!readOnly && <label className="btn" htmlFor="bankbook-file">{busy ? <><Spinner /> 올리는 중…</> : <><Icon name="upload" />{fileName ? '다른 파일 선택' : '파일 선택'}</>}</label>}
        </span>
      </div>
      <p className="field__hint" id="bankbook-hint">PDF·JPG·PNG, 20MB 이하</p>
      <MoreInfo summary="통장 사본 안내 보기">
        <ul>
          <li>예금주와 계좌번호가 보이는 본인 명의 통장 사본을 올려 주세요.</li>
          <li>예금주는 본인인증 성명과 같아야 합니다.</li>
          <li>올린 파일은 담당자가 원본으로 확인합니다.</li>
        </ul>
      </MoreInfo>
    </div>
    {error && <p className="field__error" role="alert"><Icon name="alertCircle" size={18} /><span>{error}</span></p>}
    {viewing && file && <FilePreview url={file.file_url} name={file.file_name} kind={file.file_format === 'pdf' ? 'pdf' : 'image'} onClose={() => setViewing(false)} />}
  </section>
}
