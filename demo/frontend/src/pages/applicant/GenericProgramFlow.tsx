import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { createApplication, fetchApplication, fetchPosting, fetchStatus, patchApplication, type ApplicationRow, type Identity, type SubmitResult } from '../../api.ts'
import PdfFormsWorkspace, { ApplicantFormsBulkMenu } from '../../forms/PdfFormsWorkspace.tsx'
import { EMPTY_FORM1, type Form1Value } from '../../forms/form1-model.ts'
import { EMPTY_CONSENT } from '../../forms/consent-model.ts'
import IdentityCheck from './IdentityCheck.tsx'
import DocumentUpload from './DocumentUpload.tsx'
import FinalCheck from './FinalCheck.tsx'
import MyPage from './MyPage.tsx'
import Notice from '../../components/Notice.tsx'
import Spinner from '../../components/Spinner.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import useDocumentTitle from '../../hooks/useDocumentTitle.ts'
import { routeUrl } from '../../navigation-url.ts'
import { friendlyError } from '../../lib/error-copy.ts'
import { formatDateTime } from '../../lib/format.ts'
import './apply-flow.css'

type Stage = 'identity' | 'forms' | 'upload' | 'final' | 'complete' | 'mypage'
const STEPS = [{ key: 'identity', label: '본인인증' }, { key: 'forms', label: '서식 작성' }, { key: 'upload', label: '서류 업로드' }, { key: 'final', label: '확인 및 제출' }] as const
function requestedStage(): Stage {
  const value = window.location.pathname.split('/').at(-1)
  return ['identity','forms','upload','final','complete','mypage'].includes(value ?? '') ? value as Stage : 'identity'
}
function savedId(key: string): number | null {
  try { const value = Number(window.sessionStorage.getItem(key)); return Number.isSafeInteger(value) && value > 0 ? value : null } catch { return null }
}

export default function GenericProgramFlow({ postingId, headerHost }: { postingId: number; headerHost: HTMLElement | null }) {
  const code = `posting_${postingId}`
  const storageKey = `applicant.program.${postingId}`
  const [stage, setStage] = useState<Stage>(requestedStage)
  const [app, setApp] = useState<ApplicationRow | null>(null)
  const [title, setTitle] = useState('사업 신청')
  const [guidance, setGuidance] = useState('')
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState('')
  const [form, setForm] = useState<Form1Value>(EMPTY_FORM1)
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [saving, setSaving] = useState(false)
  const [continuing, setContinuing] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)
  const [receipt, setReceipt] = useState<SubmitResult | null>(null)
  const [progress, setProgress] = useState({ completed: 0, total: 0 })
  const pendingCreate = useRef<Promise<ApplicationRow> | null>(null)
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve())
  const latestForm = useRef(form)
  useBeforeUnload(saving || continuing || !!saveError || uploadBusy)
  useDocumentTitle(`${title} 신청`)

  useEffect(() => {
    let active = true
    const restore = async () => {
      let restored: ApplicationRow | null = null
      const id = savedId(storageKey)
      if (id) {
        try { const row = await fetchApplication(id); if (row.program_code === code) restored = row }
        catch (problem) { if (!(problem instanceof Error) || !/404/.test(problem.message)) throw problem }
      }
      if (!active) return
      if (restored) {
        const response = await fetch(`/api/applications/${restored.id}/program`)
        if (!response.ok) throw new Error('신청한 사업 정보를 불러오지 못했습니다.')
        const metadata = await response.json() as { title: string; guidance_text: string }
        if (!active) return
        setTitle(metadata.title); setGuidance(metadata.guidance_text)
        setApp(restored); setForm({ ...EMPTY_FORM1, ...restored.form1_json } as Form1Value)
        latestForm.current = { ...EMPTY_FORM1, ...restored.form1_json } as Form1Value
        setIdentity(restored.identity_json?.name ? restored.identity_json as Identity : null)
        if (restored.status !== 'draft') {
          const status = await fetchStatus(restored.id)
          if (!active) return
          setReceipt({ application_no: status.application_no, submitted_at: status.submitted_at,
            status: status.status, message: '신청이 접수되었습니다.', next_steps: ['담당자가 공고문을 기준으로 제출 내용을 확인합니다.'], first_come: null, supplement: null, subsidy: null, notice: status.result_notice })
          setStage(requestedStage() === 'mypage' ? 'mypage' : 'complete')
        } else if (!restored.identity_json?.name) setStage('identity')
      } else {
        const posting = await fetchPosting(postingId)
        if (!active) return
        if (!posting.can_apply) throw new Error('현재 신청할 수 없는 사업입니다. 사업 안내에서 신청 기간을 확인해 주세요.')
        setTitle(posting.title); setGuidance(posting.guidance_text); setStage('identity')
      }
    }
    void restore().catch((problem: unknown) => { if (active) setError(friendlyError(problem, '신청 화면을 불러오지 못했습니다.')) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [code, storageKey, postingId, attempt])

  useEffect(() => {
    if (!loading) { routeUrl(`/apply/programs/${postingId}/${stage}`, {}, true); window.scrollTo({ top: 0 }) }
  }, [stage, postingId, loading])

  const ensureApplication = async () => {
    if (app) return app.id
    if (!pendingCreate.current) pendingCreate.current = createApplication(code).then((created) => {
      try { window.sessionStorage.setItem(storageKey, String(created.id)) } catch { /* The current flow can continue in memory. */ }
      setApp(created)
      return created
    }).catch((problem: unknown) => { pendingCreate.current = null; throw problem })
    return (await pendingCreate.current).id
  }
  const save = (value: Form1Value) => {
    latestForm.current = value; setForm(value)
    if (!app) return
    setSaving(true); setSaveError('')
    const operation = saveQueue.current.catch(() => undefined).then(() => patchApplication(app.id, { form1: value }))
    saveQueue.current = operation
    void operation.catch((problem: unknown) => setSaveError(friendlyError(problem, '서식을 저장하지 못했습니다.'))).finally(() => { if (saveQueue.current === operation) setSaving(false) })
  }
  const flush = async () => {
    if (!app) return
    setSaving(true)
    try { await saveQueue.current.catch(() => undefined); await patchApplication(app.id, { form1: latestForm.current }); setSaveError('') }
    catch (problem: unknown) { setSaveError(friendlyError(problem, '서식을 저장하지 못했습니다.')); throw problem }
    finally { setSaving(false) }
  }
  const onProgress = useCallback((completed: number, total: number) => setProgress({ completed, total }), [])
  if (loading) return <div className="page" role="status"><Spinner /> 신청 화면을 불러오는 중입니다.</div>
  if (error) return <Notice tone="danger" role="alert">{error}<button className="btn" onClick={() => { setError(''); setLoading(true); setAttempt((value) => value + 1) }}>다시 시도</button></Notice>
  const current = stage === 'identity' ? 0 : stage === 'forms' ? 1 : stage === 'upload' ? 2 : 3
  return <div className={`flow flow--active${stage === 'upload' ? ' flow--fluid' : ''}`}>
    {headerHost && app && createPortal(<div className="shell__application-controls"><span className="shell__application-number">신청번호 <strong>{app.application_no}</strong></span><button className="btn btn--small" disabled={uploadBusy} onClick={() => setStage('mypage')}>마이페이지</button></div>, headerHost)}
    <div className="headband"><div className="flow__overview"><header className="flow__head"><h1>{title} 신청</h1></header><ol className="flow__stages" aria-label="신청 단계">{STEPS.map((step, index) => <li key={step.key} className={index === current ? 'is-current' : index < current ? 'is-complete' : 'is-waiting'}><span className="flow__stage-content" aria-current={index === current ? 'step' : undefined}><span className="flow__stage-no">{index + 1}</span><span className="flow__stage-copy"><span className="flow__stage-caption">{index + 1}단계</span><span className="flow__stage-label">{step.label}</span></span></span></li>)}</ol></div></div>
    <div className={`flow__body${stage === 'forms' ? ' flow__body--wide' : ''}`}>
      {stage === 'identity' && <><Notice tone="info">{guidance || '공고문을 확인한 뒤 본인인증을 진행해 주세요.'}</Notice><IdentityCheck appId={app?.id ?? null} ensureApplication={ensureApplication} identity={identity} onNext={() => setStage('forms')} onVerified={(verified, _mobile, applicationId) => {
        setIdentity(verified)
        void fetchApplication(applicationId).then((row) => { setApp(row); const value = { ...EMPTY_FORM1, ...row.form1_json } as Form1Value; setForm(value); latestForm.current = value; setStage('forms') }).catch((problem: unknown) => setError(friendlyError(problem, '신청 내용을 불러오지 못했습니다.')))
      }} /></>}
      {stage === 'forms' && app && <><p className="flow__save" role="status">{saving ? '저장 중…' : saveError || '입력한 내용이 자동 저장됩니다.'}</p><PdfFormsWorkspace generic applicationId={app.id} identity={identity} form1={form} answers={{}} consent={EMPTY_CONSENT} checkResult={null} onForm1={save} onAnswers={() => undefined} onConsent={() => undefined} onFlush={flush} onContinue={() => { if (continuing) return; setContinuing(true); void flush().then(() => setStage('upload')).catch(() => undefined).finally(() => setContinuing(false)) }} continuing={continuing} error={saveError} readOnly={!!receipt} onProgress={onProgress} /><p className="field__hint">서식 {progress.completed} / {progress.total} 작성 완료</p></>}
      {stage === 'upload' && app && <><DocumentUpload applicationId={app.id} onProgress={() => undefined} onPendingChange={setUploadBusy} /><div className="flow__actions"><button className="btn" disabled={uploadBusy} onClick={() => setStage('forms')}>이전</button><button className="btn btn--primary" disabled={uploadBusy} onClick={() => setStage('final')}>최종 확인으로</button></div></>}
      {stage === 'final' && app && <FinalCheck applicationId={app.id} onBack={() => setStage('upload')} onGoto={(next) => setStage(next === 'subsidy' ? 'forms' : next)} onSubmitted={(result) => { setReceipt(result); setStage('complete') }} />}
      {stage === 'complete' && receipt && app && <section className="flow-block flow-block--ok"><h2>신청이 접수되었습니다</h2><p>신청번호 <strong>{receipt.application_no}</strong></p>{receipt.submitted_at && <p>접수 일시 {formatDateTime(receipt.submitted_at)}</p>}<p>담당자가 공고문을 기준으로 제출 내용을 확인합니다.</p><ApplicantFormsBulkMenu applicationId={app.id} /><button className="btn btn--primary" onClick={() => setStage('mypage')}>마이페이지</button></section>}
      {stage === 'mypage' && app && <><MyPage applicationId={app.id} /><div className="flow__actions"><button className="btn" onClick={() => setStage(receipt ? 'complete' : identity ? 'forms' : 'identity')}>신청 화면으로</button></div></>}
    </div>
  </div>
}
