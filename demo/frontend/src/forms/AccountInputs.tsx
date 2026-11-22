import { useEffect, useRef, useState } from 'react'
import { fetchChecklist, uploadDocument, type Identity, type UploadedDocument } from '../api.ts'
import FilePreview from '../components/ApplicantFilePreview.tsx'
import Icon from '../components/Icon.tsx'
import MoreInfo from '../components/MoreInfo.tsx'
import Spinner from '../components/Spinner.tsx'
import { mutationError, slotChange } from '../lib/applicant-mutation.ts'
import ConfirmDialog from '../components/ConfirmDialog.tsx'
import ProgressBar from '../components/ProgressBar.tsx'
import useBeforeUnload from '../hooks/useBeforeUnload.ts'
import type { Form1Value } from './form1-model.ts'

export default function AccountInputs({ applicationId, identity, value, onChange, onFlush, readOnly, onBusyChange }: {
  applicationId: number; identity: Identity | null; value: Form1Value
  onChange: (value: Form1Value) => void; onFlush: () => Promise<void>; readOnly: boolean
  onBusyChange: (busy: boolean) => void
}) {
  const [file, setFile] = useState<UploadedDocument | null>(null)
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const candidate = useRef<File | null>(null)
  const before = useRef<number | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [confirmRetry, setConfirmRetry] = useState(false)
  const [phase, setPhase] = useState<'saving' | 'sending' | 'reading' | null>(null)
  const [progress, setProgress] = useState<{sent: number; total: number} | null>(null)
  useBeforeUnload(busy || uncertain)
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
    return () => { mounted.current = false; controller.current?.abort(); onBusyChange(false) }
  }, [applicationId, onBusyChange])
  const accept = (uploaded: UploadedDocument) => {
    setFile(uploaded); setUncertain(false); candidate.current = null
    onChange({ ...current.current, bankbookFileName: uploaded.file_name })
  }
  const pickFile = async (picked: File | undefined, explicitRetry = false) => {
    if (!picked || lock.current || (uncertain && !explicitRetry)) return
    setError('')
    if (!/\.(pdf|jpe?g|png)$/i.test(picked.name) || !picked.size) {
      setError('내용이 있는 PDF·JPG·PNG 통장 사본을 선택해 주세요.'); return
    }
    if (picked.size > 20 * 1024 * 1024) { setError('통장 사본은 20MB 이하로 올려 주세요.'); return }
    candidate.current = picked; before.current = file?.document_id ?? null
    lock.current = true; setBusy(true); onBusyChange(true); setPhase('saving'); setProgress(null)
    let posted = false
    const abort = new AbortController(); controller.current = abort
    try {
      await onFlush()
      if (!mounted.current) return
      setPhase('sending'); posted = true
      const uploaded = await uploadDocument(applicationId, 'bank_account', picked, '', {
        signal: abort.signal,
        onProgress: (sent, total) => { if (mounted.current) setProgress({sent, total}) },
        onSent: () => { if (mounted.current) setPhase('reading') },
      })
      if (mounted.current) accept(uploaded)
    } catch (problem: unknown) {
      if (mounted.current) { setUncertain(posted); setError(mutationError(problem, '통장 사본의 처리 결과를 확인하지 못했습니다. 서버 상태를 먼저 확인해 주세요.')) }
    } finally {
      lock.current = false; controller.current = null
      if (mounted.current) { setBusy(false); setPhase(null); onBusyChange(false) }
    }
  }
  const reconcile = async () => {
    if (lock.current) return
    lock.current = true; setBusy(true); onBusyChange(true)
    try {
      const checklist = await fetchChecklist(applicationId)
      if (!mounted.current) return
      const documents = checklist.items.find((item) => item.slot_key === 'bank_account')?.documents ?? []
      if (slotChange(before.current, documents) === 'changed') {
        accept(documents[0]); setError('서버의 통장 사본이 변경되었습니다. 원본을 확인해 주세요. 파일은 다시 전송하지 않았습니다.')
      } else if (uncertain && candidate.current) setConfirmRetry(true)
      else { setFile(documents[0] ?? null); setError('') }
    } catch (problem: unknown) { if (mounted.current) setError(mutationError(problem, '첨부 상태를 확인하지 못했습니다. 다시 확인해 주세요.')) }
    finally { lock.current = false; if (mounted.current) { setBusy(false); onBusyChange(false) } }
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
          {!readOnly && <input id="bankbook-file" type="file" className="sr-only" accept=".pdf,.jpg,.jpeg,.png" disabled={busy || uncertain} aria-labelledby="bankbook-label" aria-describedby="bankbook-hint" onChange={(event) => { const picked = event.target.files?.[0]; event.target.value = ''; void pickFile(picked) }} />}
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
    {phase && <div role="status" aria-live="polite"><p>{phase === 'saving' ? '작성한 내용을 저장하고 있습니다.' : phase === 'reading' ? '서류를 읽고 확인하고 있습니다. 분석이 끝나면 결과를 표시합니다.' : '파일을 보내고 있습니다.'}</p><ProgressBar label={phase === 'sending' ? '통장 사본 전송' : '통장 사본 처리 대기'} indeterminate={phase !== 'sending' || !progress} value={progress?.sent} max={progress?.total} /></div>}
    {(uncertain || error) && <button type="button" className="btn" disabled={busy} onClick={() => void reconcile()}>통장 사본 서버 상태 확인</button>}
    {confirmRetry && <ConfirmDialog title="통장 사본을 다시 전송하시겠습니까?" description="서버 목록을 확인했습니다. 다시 전송하면 기존 서류가 교체될 수 있습니다. 원본을 먼저 확인해 주세요." confirmLabel="같은 파일 다시 전송" onCancel={() => setConfirmRetry(false)} onConfirm={() => { setConfirmRetry(false); const picked = candidate.current; setUncertain(false); if (picked) void pickFile(picked, true) }} />}
    {error && <p className="field__error" role="alert"><Icon name="alertCircle" size={18} /><span>{error}</span></p>}
    {viewing && file && <FilePreview url={file.file_url} name={file.file_name} kind={file.file_format === 'pdf' ? 'pdf' : 'image'} onClose={() => setViewing(false)} />}
  </section>
}
