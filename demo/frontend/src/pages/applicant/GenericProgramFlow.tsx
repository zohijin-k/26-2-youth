import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { createApplication, fetchApplication, fetchFinalCheck, fetchPosting, fetchStatus, patchApplication, type ApplicationRow, type Blocker, type Identity, type SubmitResult } from '../../api.ts'
import PdfFormsWorkspace, { ApplicantFormsBulkMenu } from '../../forms/PdfFormsWorkspace.tsx'
import { savableEmail, withSavableEmail } from '../../forms/email.ts'
import { EMPTY_FORM1, type Form1Value } from '../../forms/form1-model.ts'
import { EMPTY_CONSENT } from '../../forms/consent-model.ts'
import IdentityCheck from './IdentityCheck.tsx'
import DocumentUpload from './DocumentUpload.tsx'
import FinalCheck from './FinalCheck.tsx'
import MissingItems from './MissingItems.tsx'
import MyPage from './MyPage.tsx'
import SaveStatus, { type SavePhase } from '../../components/SaveStatus.tsx'
import useSaveBeforeLeave from '../../hooks/useSaveBeforeLeave.ts'
import { mutationError } from '../../lib/applicant-mutation.ts'
import Icon from '../../components/Icon.tsx'
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
  /** 단계 표시에서 "확인 및 제출"을 눌러 미리 볼 때, 누르기 전에 있던 화면. 정상 진행으로 왔으면 null. */
  const [peekFrom, setPeekFrom] = useState<Stage | null>(null)
  const [app, setApp] = useState<ApplicationRow | null>(null)
  const [title, setTitle] = useState('사업 신청')
  const [guidance, setGuidance] = useState('')
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState('')
  const [form, setForm] = useState<Form1Value>(EMPTY_FORM1)
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [saving, setSaving] = useState(false)
  const [savePhase, setSavePhase] = useState<SavePhase>('idle')
  const flushPending = useRef<Promise<void> | null>(null)
  const [workspaceBusy, setWorkspaceBusy] = useState(false)
  const [continuing, setContinuing] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)
  const [receipt, setReceipt] = useState<SubmitResult | null>(null)
  const [progress, setProgress] = useState({ completed: 0, total: 0 })
  const pendingCreate = useRef<Promise<ApplicationRow> | null>(null)
  const saveQueue = useRef<Promise<unknown>>(Promise.resolve())
  const latestForm = useRef(form)
  // 부분 저장에 실을 수 있는 마지막 이메일. 주소를 다 치기 전에는 이 값을 보낸다(withSavableEmail).
  const savableEmailRef = useRef('')
  const navigation = useSaveBeforeLeave(!receipt && (stage === 'forms' || !!saveError), () => flush(), uploadBusy || continuing || workspaceBusy)
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
        savableEmailRef.current = savableEmail(latestForm.current.email, '')
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
    setSaving(true); setSavePhase('saving'); setSaveError('')
    const form1 = withSavableEmail(value, savableEmailRef)
    const operation = saveQueue.current.catch(() => undefined).then(() => patchApplication(app.id, { form1 }))
    saveQueue.current = operation
    void operation.then(() => { if (saveQueue.current === operation) setSavePhase('saved') }).catch((problem: unknown) => { setSavePhase('failed'); setSaveError(mutationError(problem, '서식을 저장하지 못했습니다.')) }).finally(() => { if (saveQueue.current === operation) setSaving(false) })
  }
  const persist = async () => {
    if (!app) return
    setSaving(true)
    try { await saveQueue.current.catch(() => undefined); await patchApplication(app.id, { form1: latestForm.current }); setSaveError(''); setSavePhase('saved') }
    catch (problem: unknown) { setSavePhase('failed'); setSaveError(mutationError(problem, '서식을 저장하지 못했습니다.')); throw problem }
    finally { setSaving(false) }
  }
  function flush(): Promise<void> {
    if (flushPending.current) return flushPending.current
    setSavePhase('saving')
    const operation = persist().finally(() => { flushPending.current = null })
    flushPending.current = operation; return operation
  }
  const onProgress = useCallback((completed: number, total: number) => setProgress({ completed, total }), [])
  // 서류 업로드 → 최종 확인: 서버 기준으로 모두 채워졌을 때만 넘어간다. 서류가 바뀌면 남은 항목을 지우고 다시 확인한다.
  const [uploadState, setUploadState] = useState('')
  const onUploadProgress = useCallback((completed: number, total: number) => setUploadState(`${completed}/${total}`), [])
  const [finalGateResult, setFinalGate] = useState<{ upload: string; blockers: Blocker[] } | null>(null)
  const [gateChecking, setGateChecking] = useState(false)
  const [gateError, setGateError] = useState('')
  const finalGate = finalGateResult?.upload === uploadState ? finalGateResult.blockers : null
  const goToFinal = async () => {
    if (!app || gateChecking) return
    setGateChecking(true); setGateError('')
    try {
      const check = await fetchFinalCheck(app.id)
      if (check.can_submit || check.already_submitted) { setFinalGate(null); setPeekFrom(null); setStage('final'); return }
      setFinalGate({ upload: uploadState, blockers: check.blockers })
      window.requestAnimationFrame(() => document.getElementById('upload-gate')?.focus())
    } catch (problem: unknown) {
      setGateError(mutationError(problem, '제출할 수 있는지 확인하지 못했습니다. 입력과 파일은 이 화면에 남아 있습니다.'))
    } finally {
      setGateChecking(false)
    }
  }
  if (loading) return <div className="page" role="status"><Spinner /> 신청 화면을 불러오는 중입니다.</div>
  if (error) return <Notice tone="danger" role="alert">{error}<button className="btn" onClick={() => { setError(''); setLoading(true); setAttempt((value) => value + 1) }}>다시 시도</button></Notice>
  const stageIndex = (value: Stage) => value === 'identity' ? 0 : value === 'forms' ? 1 : value === 'upload' ? 2 : 3
  const current = stageIndex(stage)
  // 미리 보기 중이면 "어디까지 마쳤는지"는 누르기 전 화면 기준이다. 아직 안 한 단계를 완료로 보이지 않게 한다.
  const peeking = stage === 'final' && peekFrom !== null
  const reached = stage === 'final' && peekFrom !== null ? stageIndex(peekFrom) : current
  const stepComplete = (index: number) => !!receipt || index < reached
  const stepState = (index: number) => index === current ? (peeking ? '미리 보기' : '현재') : stepComplete(index) ? '완료' : peeking && index === reached ? '진행 중' : ''
  const canPreview = identity !== null && !receipt && !uploadBusy && current < 3
  const previewFinal = () => navigation.leave(() => { setPeekFrom(stage); setStage('final') })
  return <div className={`flow flow--active${stage === 'upload' ? ' flow--fluid' : ''}`}>
    {headerHost && app && createPortal(<div className="shell__application-controls"><span className="shell__application-number">신청번호 <strong>{app.application_no}</strong></span><button className="btn btn--small" disabled={uploadBusy} onClick={() => navigation.leave(() => setStage('mypage'))}>마이페이지</button></div>, headerHost)}
    <div className="headband"><div className="flow__overview"><header className="flow__head"><h1 className="sr-only">{title} 신청</h1></header><ol className="flow__stages" aria-label="신청 단계">{STEPS.map((step, index) => {
      const isCurrent = index === current
      const complete = stepComplete(index)
      const content = <><span className="flow__stage-no" aria-hidden="true">{complete && !isCurrent ? <Icon name="check" size={18} /> : !isCurrent ? index + 1 : null}</span><span className="flow__stage-copy"><span className="flow__stage-caption"><span>{index + 1}단계</span>{stepState(index) && <span className="flow__stage-status">{stepState(index)}</span>}</span><span className="flow__stage-label">{step.label}</span></span></>
      return <li key={step.key} className={isCurrent ? (peeking ? 'is-current is-preview' : 'is-current') : complete ? 'is-complete' : 'is-waiting'}>
        {index === 3 && canPreview
          ? <button type="button" className="flow__stage-content" onClick={previewFinal}>{content}</button>
          : <span className="flow__stage-content" aria-current={isCurrent ? 'step' : undefined}>{content}</span>}
      </li>
    })}</ol></div></div>
    {stage !== 'forms' && navigation.error && <Notice tone="danger" role="alert">{navigation.error}</Notice>}
    <div className="flow__body">
      {stage === 'identity' && <><IdentityCheck lead={<Notice tone="info">{guidance || '공고문을 확인한 뒤 본인인증을 진행해 주세요.'}</Notice>} appId={app?.id ?? null} ensureApplication={ensureApplication} identity={identity} onNext={() => setStage('forms')} onVerified={(verified, _mobile, applicationId) => {
        setIdentity(verified)
        void fetchApplication(applicationId).then((row) => { setApp(row); const value = { ...EMPTY_FORM1, ...row.form1_json } as Form1Value; setForm(value); latestForm.current = value; savableEmailRef.current = savableEmail(value.email, ''); setStage('forms') }).catch((problem: unknown) => setError(friendlyError(problem, '신청 내용을 불러오지 못했습니다.')))
      }} /></>}
      {stage === 'forms' && app && <><PdfFormsWorkspace saveStatus={<SaveStatus phase={saving || navigation.pending ? 'saving' : savePhase} />} generic applicationId={app.id} identity={identity} form1={form} answers={{}} consent={EMPTY_CONSENT} checkResult={null} onForm1={save} onAnswers={() => undefined} onConsent={() => undefined} onBusyChange={setWorkspaceBusy} onFlush={flush} onContinue={() => { if (continuing) return; setContinuing(true); void flush().then(() => setStage('upload')).catch(() => undefined).finally(() => setContinuing(false)) }} continuing={continuing || navigation.pending} error={navigation.error || saveError} readOnly={!!receipt} onProgress={onProgress} /><p className="field__hint">서식 {progress.completed} / {progress.total} 작성 완료</p></>}
      {stage === 'upload' && app && !receipt && <><DocumentUpload applicationId={app.id} onProgress={onUploadProgress} onPendingChange={setUploadBusy} />{gateError && <Notice tone="danger" role="alert">{gateError}</Notice>}{finalGate && <MissingItems id="upload-gate" title="아직 제출할 수 없습니다. 아래 항목을 모두 마쳐야 다음으로 넘어갑니다." blockers={finalGate} current="upload" onGoto={(next) => { setFinalGate(null); setStage(next === 'subsidy' ? 'forms' : next) }} />}<div className="flow__actions"><button className="btn" disabled={uploadBusy} onClick={() => setStage('forms')}>이전</button><button className="btn btn--primary" disabled={uploadBusy} aria-busy={gateChecking || undefined} onClick={() => void goToFinal()}>{gateChecking && <Spinner />}최종 확인으로</button></div></>}
      {stage === 'final' && app && <FinalCheck onPendingChange={setUploadBusy} applicationId={app.id} onBack={() => setStage(peeking && peekFrom ? peekFrom : 'upload')} onGoto={(next) => setStage(next === 'subsidy' ? 'forms' : next)} onSubmitted={(result) => { setReceipt(result); setStage('complete') }} />}
      {stage === 'complete' && receipt && app && <section className="flow-block flow-block--ok"><h2>신청이 접수되었습니다</h2><p>신청번호 <strong>{receipt.application_no}</strong></p>{receipt.submitted_at && <p>접수 일시 {formatDateTime(receipt.submitted_at)}</p>}<p>담당자가 공고문을 기준으로 제출 내용을 확인합니다.</p><ApplicantFormsBulkMenu applicationId={app.id} /><button className="btn btn--primary" onClick={() => navigation.leave(() => setStage('mypage'))}>마이페이지</button></section>}
      {stage === 'mypage' && app && <><MyPage applicationId={app.id} /><div className="flow__actions"><button className="btn" onClick={() => setStage(receipt ? 'complete' : identity ? 'forms' : 'identity')}>신청 화면으로</button></div></>}
    </div>
  </div>
}
