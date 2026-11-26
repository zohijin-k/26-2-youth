/** Youth employment package applicant flow; original forms and rules come from the API. */

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import {
  createApplication,
  fetchApplication,
  fetchApplicationConsents,
  fetchFinalCheck,
  fetchPrograms,
  fetchStatus,
  fetchSubsidyItems,
  patchApplication,
  postConsents,
  postSelfCheck,
  type Blocker,
  type ConsentPayload,
  type Identity,
  type Program,
  type SelfCheckResult,
  type SubmitResult,
  type SubsidyState,
} from '../../api.ts'
import SaveStatus from '../../components/SaveStatus.tsx'
import useSaveBeforeLeave from '../../hooks/useSaveBeforeLeave.ts'
import { mutationError } from '../../lib/applicant-mutation.ts'
import DocumentUpload from './DocumentUpload.tsx'
import FinalCheck from './FinalCheck.tsx'
import MissingItems from './MissingItems.tsx'
import IdentityCheck from './IdentityCheck.tsx'
import MyPage from './MyPage.tsx'
import SubsidyItems from './SubsidyItems.tsx'
import PdfFormsWorkspace, { ApplicantFormsBulkMenu } from '../../forms/PdfFormsWorkspace.tsx'
import { EMPTY_CONSENT, type ConsentValue } from '../../forms/consent-model.ts'
import { CONSENT_OPTIONS } from '../../forms/consent-model.ts'
import { savableEmail, withSavableEmail } from '../../forms/email.ts'
import { EMPTY_FORM1, type Form1Value } from '../../forms/form1-model.ts'
import type { SelfCheckAnswers } from '../../forms/form2-model.ts'
import { currentParams, routeUrl } from '../../navigation-url.ts'
import Icon from '../../components/Icon.tsx'
import Notice from '../../components/Notice.tsx'
import Spinner from '../../components/Spinner.tsx'
import useDocumentTitle from '../../hooks/useDocumentTitle.ts'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import { friendlyError } from '../../lib/error-copy.ts'
import { readReceiptSteps } from '../../lib/receipt-steps.ts'
import { formatDateTime } from '../../lib/format.ts'
import { ACTIVE_APPLICATION_KEY, createIdentitySession } from '../../lib/identity-session.ts'
import { YOUTH_PROGRAM as YOUTH_PROGRAM_CODE } from '../../program-scope.ts'
import './apply-flow.css'

type Stage =
  | 'identity'
  | 'forms'
  | 'subsidy'
  | 'upload'
  | 'final'
  | 'complete'
  | 'mypage'


function savedPage(): { appId: number; stage: Stage; previous: Stage } | null {
  const params = currentParams()
  const route = /^\/apply\/([a-z]+)\/?$/.exec(window.location.pathname)
  const stage = route?.[1] as Stage
  const previous = params.get('from') as Stage
  const stages: Stage[] = ['identity', 'forms', 'subsidy', 'upload', 'final', 'complete', 'mypage']
  const removedEntry = params.get('mode') === 'officer' || params.get('program') === 'double_savings' || [...params.keys()].some((key) => key.startsWith('o_'))
  const nextStage = stages.includes(stage) && !removedEntry ? stage : 'identity'
  try {
    const savedId = window.sessionStorage.getItem(ACTIVE_APPLICATION_KEY)
    if (!savedId || !/^[1-9]\d*$/.test(savedId)) return null
    const appId = Number(savedId)
    if (!Number.isSafeInteger(appId)) return null
    return { appId, stage: nextStage, previous: stages.includes(previous) ? previous : 'identity' }
  } catch {
    return null
  }
}

type Step = { key: 'identity' | 'forms' | 'upload' | 'final'; label: string }
type StepperProgress = { completed: number; total: number }
const APPLY_STEPS: Step[] = [
  { key: 'identity', label: '본인인증' },
  { key: 'forms', label: '서식 작성' },
  { key: 'upload', label: '서류 업로드' },
  { key: 'final', label: '확인 및 제출' },
]

/** 신청서의 성명·생년월일을 본인인증 값으로 덮는다 (서버도 같은 규칙으로 잠근다). */
function lockIdentity(form: Form1Value, identity: Identity | null): Form1Value {
  if (!identity) return form
  const [y, m, d] = identity.birth.split('-')
  return { ...form, accountHolder: form.accountHolder || identity.name, name: identity.name, birth: { y, m: String(Number(m)), d: String(Number(d)) } }
}

export default function ApplyFlow({ headerHost }: { headerHost: HTMLElement | null }) {
  const [initialPage] = useState(savedPage)
  const [applicationSession] = useState(() => createIdentitySession({
    programCode: YOUTH_PROGRAM_CODE, storage: () => window.sessionStorage,
    load: fetchApplication, create: createApplication,
  }))
  const initialUrlWrite = useRef(true)
  const [restoring, setRestoring] = useState(true)
  const [startupAttempt, setStartupAttempt] = useState(0)
  const [program, setProgram] = useState<Program | null>(null)
  const [appId, setAppId] = useState<number | null>(null)
  const [appNo, setAppNo] = useState('')
  const [stage, setStage] = useState<Stage>('identity')
  const [stageBeforeMypage, setStageBeforeMypage] = useState<Stage>('identity')
  const [error, setError] = useState('')
  const [identity, setIdentity] = useState<Identity | null>(null)

  const [answers, setAnswers] = useState<SelfCheckAnswers>({})
  const [checkResult, setCheckResult] = useState<SelfCheckResult | null>(null)

  const [form1, setForm1] = useState<Form1Value>(EMPTY_FORM1)

  const [consent, setConsent] = useState<ConsentValue>(EMPTY_CONSENT)
  const [consentDirty, setConsentDirty] = useState(false)
  const saveFailed = useRef(false)

  const [submitted, setSubmitted] = useState<SubmitResult | null>(null)
  /** 지원 항목이 바뀌면 업로드 화면의 체크리스트를 다시 읽게 하는 키. */
  const [checklistKey, setChecklistKey] = useState(0)
  const [selectedSubsidyTypes, setSelectedSubsidyTypes] = useState(0)
  const [workspaceBusy, setWorkspaceBusy] = useState(false)
  const [formContinuing, setFormContinuing] = useState(false)
  const [formError, setFormError] = useState('')
  const [selectionAttempted, setSelectionAttempted] = useState(false)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'failed'>('idle')
  const pendingSaves = useRef(0)
  const stageHeading = useRef<HTMLHeadingElement>(null)
  const stageNames: Record<Stage, string> = { identity: '본인인증', forms: '서식 작성', subsidy: '지원 항목 선택', upload: '서류 업로드', final: '확인 및 제출', complete: '접수 완료', mypage: '마이페이지' }
  useDocumentTitle(`${stageNames[stage]} | ${program?.name ?? '전북청년 취업지원패키지'} 신청`)
  useBeforeUnload(saveState === 'saving' || saveState === 'failed' || formContinuing || consentDirty)
  useEffect(() => {
    if (restoring) return
    window.scrollTo({ top: 0 })
    stageHeading.current?.focus()
  }, [stage, restoring])
  const [formProgress, setFormProgress] = useState<StepperProgress>({ completed: 0, total: 0 })
  const [uploadPending, setUploadPending] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<StepperProgress>({ completed: 0, total: 0 })
  /** 서류 업로드에서 다음으로 가기 전 서버가 알려 준 남은 항목. 서류를 더 올리면 지우고 다시 확인한다. */
  /** 단계 표시에서 "확인 및 제출"을 눌러 미리 볼 때, 누르기 전에 있던 화면. 정상 진행으로 왔으면 null. */
  const [peekFrom, setPeekFrom] = useState<Stage | null>(null)
  const [finalGateResult, setFinalGate] = useState<{ upload: string; blockers: Blocker[] } | null>(null)
  const [gateChecking, setGateChecking] = useState(false)
  const [gateError, setGateError] = useState('')
  const uploadState = `${uploadProgress.completed}/${uploadProgress.total}`
  const finalGate = finalGateResult?.upload === uploadState ? finalGateResult.blockers : null
  const saveQueue = useRef<Promise<void>>(Promise.resolve())
  // 부분 저장에 실을 수 있는 마지막 이메일. 주소를 다 치기 전에는 이 값을 보낸다(withSavableEmail).
  const savableEmailRef = useRef('')
  const flushPending = useRef<Promise<void> | null>(null)
  const [flushing, setFlushing] = useState(false)
  const navigation = useSaveBeforeLeave(!submitted && (stage === 'forms' || saveState === 'failed' || consentDirty), () => flushForms(), uploadPending || formContinuing || workspaceBusy)

  useEffect(() => {
    let active = true
    if (!initialPage || initialPage.stage === 'identity') routeUrl('/apply/identity', {}, true)
    const restore = async () => {
      try {
        const programs = await fetchPrograms()
        if (!active) return
        const picked = programs.find((item) => item.code === YOUTH_PROGRAM_CODE)
        if (!picked) throw new Error('청년 취업지원패키지 설정을 불러오지 못했습니다.')
        setProgram(picked)
        const application = await applicationSession.restore()
        if (!active) return
        if (!application) {
          setAppId(null)
          setAppNo('')
          return
        }
        const restored = true
        const [consents, status, subsidy] = await Promise.all([
          fetchApplicationConsents(application.id), fetchStatus(application.id), fetchSubsidyItems(application.id),
        ])
        if (!active) return
        setAppId(application.id)
        setAppNo(application.application_no)
        const savedIdentity = application.identity_json
        setIdentity(savedIdentity?.name && savedIdentity.birth ? savedIdentity as Identity : null)
        const restoredForm1 = lockIdentity({ ...EMPTY_FORM1, ...application.form1_json } as Form1Value, savedIdentity?.name && savedIdentity.birth ? savedIdentity as Identity : null)
        setForm1(restoredForm1)
        savableEmailRef.current = savableEmail(restoredForm1.email, '')
        setAnswers(application.self_check_json as SelfCheckAnswers)
        setSelectedSubsidyTypes(subsidy.selections.length)
        const consentValue = (type: string) => {
          const item = consents.find((row) => row.consent_type === type)
          return item ? CONSENT_OPTIONS[item.agreed ? 0 : 1] : ''
        }
        setConsent({ privacy: consentValue('privacy'), thirdParty: consentValue('third_party') })
        if (status.status !== 'draft') {
          let nextSteps: string[] = []
          try { nextSteps = readReceiptSteps(window.sessionStorage.getItem(`applicant.receiptSteps.${application.id}`)) } catch { /* Receipt still uses the current server status. */ }
          setSubmitted({ application_no: status.application_no, submitted_at: status.submitted_at,
            status: status.status, message: '신청이 완료되었습니다.', next_steps: nextSteps,
            first_come: status.first_come, supplement: status.supplement, subsidy: status.subsidy, notice: status.result_notice })
        }
        const requestedStage = restored && initialPage ? initialPage.stage : 'identity'
        // 제출을 마친 신청은 서류 업로드 화면(자동 판독 결과가 보이는 곳)을 열지 않고 접수증으로 보낸다.
        setStage(requestedStage === 'complete' && status.status === 'draft' ? 'final'
          : requestedStage === 'upload' && status.status !== 'draft' ? 'complete' : requestedStage)
        setStageBeforeMypage(restored && initialPage ? initialPage.previous : 'identity')
      } catch (error: unknown) {
        if (active) setError(friendlyError(error, '신청 화면을 불러오지 못했습니다. 다시 시도해 주세요.'))
      } finally {
        if (active) setRestoring(false)
      }
    }
    void restore()
    return () => { active = false }
  }, [initialPage, startupAttempt, applicationSession])

  useEffect(() => {
    if (restoring) return
    try {
      if (appId !== null) window.sessionStorage.setItem(ACTIVE_APPLICATION_KEY, String(appId))
    } catch {
      // Continue in memory when tab storage is unavailable; refresh returns to identity verification.
    }
    if (appId === null) {
      routeUrl('/apply/identity', {}, true)
    } else {
      routeUrl(`/apply/${stage}`, stage === 'mypage' ? { from: stageBeforeMypage } : {}, initialUrlWrite.current)
    }
    initialUrlWrite.current = false
  }, [appId, stage, stageBeforeMypage, restoring])

  const reportFormProgress = useCallback((completed: number, total: number) => {
    setFormProgress({ completed, total })
  }, [])
  const reportUploadProgress = useCallback((completed: number, total: number) => {
    setUploadProgress({ completed, total })
  }, [])

  const save = (body: { form1?: unknown; self_check?: unknown }, targetId = appId): Promise<void> => {
    if (targetId === null) return Promise.resolve()
    pendingSaves.current += 1
    setSaveState('saving')
    const next = saveQueue.current.catch(() => undefined).then(() => patchApplication(targetId, body)).then(() => {
      pendingSaves.current -= 1
      if (pendingSaves.current === 0) setSaveState(saveFailed.current ? 'failed' : 'saved')
    })
    saveQueue.current = next.catch(() => {
      saveFailed.current = true
      pendingSaves.current -= 1
      setSaveState('failed')
    })
    return saveQueue.current
  }

  const persistForms = async () => {
    if (appId === null) return
    setSaveState('saving')
    try {
      await saveQueue.current
      await patchApplication(appId, { form1, self_check: answers })
      const values: ConsentPayload[] = [
        { consent_type: 'privacy', agreed: consent.privacy === '동의함' },
        { consent_type: 'third_party', agreed: consent.thirdParty === '동의함' },
      ]
      await postConsents(appId, values.filter((item) => {
        const selected = item.consent_type === 'privacy' ? consent.privacy : consent.thirdParty
        return selected === '동의함' || selected === '동의하지 않음'
      }))
      saveFailed.current = false
      setConsentDirty(false)
      setSaveState('saved')
    } catch (error: unknown) {
      saveFailed.current = true
      setSaveState('failed')
      throw error
    }
  }

  function flushForms(): Promise<void> {
    if (flushPending.current) return flushPending.current
    setFlushing(true)
    const operation = persistForms().catch((problem: unknown) => {
      setFormError(mutationError(problem, '서식을 저장하지 못했습니다. 입력을 확인한 뒤 다시 저장해 주세요.')); throw problem
    }).finally(() => { flushPending.current = null; setFlushing(false) })
    flushPending.current = operation
    return operation
  }

  const continueFromForms = async () => {
    if (appId === null || program === null || formContinuing) return
    setFormContinuing(true)
    setFormError('')
    try {
      await flushForms()
      const payload = Object.fromEntries(Object.entries(answers).filter(([, v]) => v)) as Record<string, string>
      const result = await postSelfCheck(appId, payload)
      setCheckResult(result)
      if (!result.eligible) return
      if (!consentReady) {
        setFormError('필수 동의와 서명을 모두 마쳐 주세요.')
        return
      }
      await postConsents(appId, [
        { consent_type: 'privacy', agreed: consent.privacy === '동의함' },
        { consent_type: 'third_party', agreed: consent.thirdParty === '동의함' },
      ])
      setConsentDirty(false)
      setStage('subsidy')
    } catch (e: unknown) {
      setFormError(friendlyError(e, '서식을 저장하지 못했습니다. 다시 시도해 주세요.'))
    } finally {
      setFormContinuing(false)
    }
  }

  /** 서류 업로드 → 확인 및 제출. 서버 기준으로 모두 채워졌을 때만 넘어가고, 아니면 남은 항목을 그 자리에서 보여 준다. */
  const goToFinal = async () => {
    if (appId === null || gateChecking) return
    setGateChecking(true)
    setGateError('')
    try {
      const check = await fetchFinalCheck(appId)
      if (check.can_submit || check.already_submitted) {
        setFinalGate(null)
        setPeekFrom(null)
        setStage('final')
        return
      }
      setFinalGate({ upload: uploadState, blockers: check.blockers })
      window.requestAnimationFrame(() => document.getElementById('upload-gate')?.focus())
    } catch (e: unknown) {
      setGateError(friendlyError(e, '제출할 수 있는지 확인하지 못했습니다. 다시 시도해 주세요.'))
    } finally {
      setGateChecking(false)
    }
  }

  /** 최종 확인의 수정 링크는 이미 도달한 단계로만 돌아가게 한다. */
  const jumpTo = (next: Stage) => {
    if (next === stage) return
    if (next === 'identity' && identity !== null) return
    navigation.leave(() => { setStage(next); window.scrollTo({ top: 0 }) })
  }

  if (restoring) return <div className="page" role="status"><Spinner /> 신청 화면을 불러오는 중입니다.</div>
  if (error) return <div className="flow"><p className="flow-error" role="alert">{error}</p><button type="button" className="btn" onClick={() => { setError(''); setRestoring(true); setStartupAttempt((attempt) => attempt + 1) }}>다시 시도</button></div>

  if (program === null) return <p className="flow">신청 화면을 불러오는 중입니다...</p>
  const consentReady = consent.privacy === '동의함' && consent.thirdParty === '동의함'

  const submittedDone = submitted !== null
  const uploadComplete = uploadProgress.total > 0 && uploadProgress.completed >= uploadProgress.total
  const viewedStage = stage === 'mypage' && !submittedDone ? stageBeforeMypage : stage
  const currentIndex = viewedStage === 'identity' ? 0
    : viewedStage === 'forms' || viewedStage === 'subsidy' ? 1
      : viewedStage === 'upload' ? 2 : 3

  const openMyPage = () => navigation.leave(() => {
    if (stage !== 'mypage') setStageBeforeMypage(stage)
    setStage('mypage')
    window.scrollTo({ top: 0 })
  })

  /** 단계 표시 아래 "N단계 · 상태 · 진행 수"의 상태와 진행 수. */
  // 미리 보기 중이면 "어디까지 마쳤는지"는 누르기 전 단계를 기준으로 한다. 아직 안 한 단계를 완료로 보이지 않게 한다.
  const peeking = stage === 'final' && peekFrom !== null
  const stageIndex = (s: Stage) => s === 'identity' ? 0 : s === 'forms' || s === 'subsidy' ? 1 : s === 'upload' ? 2 : 3
  const reachedIndex = stage === 'final' && peekFrom !== null ? stageIndex(peekFrom) : currentIndex
  const stepComplete = (index: number) => submittedDone || index < reachedIndex || (index === 2 && uploadComplete)

  const stepStatus = (index: number): { state: string; count: string } => {
    if (submittedDone) return { state: index === 3 ? '접수 완료' : '완료', count: '' }
    const progress = index === 1 ? formProgress : index === 2 ? uploadProgress : null
    const count = progress && progress.total > 0 ? `${progress.completed} / ${progress.total}` : ''
    if (index === currentIndex) return { state: peeking ? '미리 보기' : '현재', count }
    if (stepComplete(index)) return { state: '완료', count: index === 2 ? count : '' }
    // 아직 오지 않은 단계는 상태 글자 없이 번호만 둔다.
    return { state: peeking && index === reachedIndex ? '진행 중' : '', count }
  }

  /** 단계 표시에서 갈 수 있는 곳: 이미 거친 단계, 다녀간 서류 업로드, 그리고 "확인 및 제출" 미리 보기. */
  const stepReachable = (index: number) => !uploadPending && !submittedDone && stage !== 'mypage' && index !== 0 && index !== currentIndex &&
    (index <= reachedIndex || (index === 2 && uploadProgress.total > 0) || (index === 3 && identity !== null))

  const stepperNavigate = (index: number) => {
    if (!stepReachable(index)) return
    navigation.leave(() => { if (index === 3) setPeekFrom(stage); setStage(index === 1 ? 'forms' : index === 2 ? 'upload' : 'final'); window.scrollTo({ top: 0 }) })
  }

  /** 신청서 저장. 본인인증을 마쳤으면 성명·생년월일은 인증 값으로 고정된다. */
  const onForm1 = (next: Form1Value) => {
    const locked = lockIdentity(next, identity)
    setForm1(locked)
    save({ form1: withSavableEmail(locked, savableEmailRef) })
  }

  return (
    <div className={`flow flow--active${stage === 'upload' ? ' flow--fluid' : ''}`}>
      {stage !== 'forms' && navigation.error && <Notice tone="danger" role="alert">{navigation.error}</Notice>}
      {headerHost && appId !== null && createPortal(
        <div className="shell__application-controls">
          <span className="shell__application-number">신청번호 <strong>{appNo || '발급 중…'}</strong></span>
          <button type="button" className="btn btn--small" onClick={openMyPage} disabled={stage === 'mypage' || uploadPending}>마이페이지</button>
        </div>, headerHost,
      )}
      <div className="headband"><div className="flow__overview">
        <header className="flow__head flow__head--compact">
          {/* 화면에는 보이지 않는 제목. 단계가 바뀌면 여기로 포커스가 와서 화면 읽기 프로그램이 읽는다. */}
          <h1 ref={stageHeading} tabIndex={-1} className="sr-only">{program.name} 신청 · {stageNames[stage]}</h1>
          {program.is_first_come && <span className="flow__submission-order">선착순 접수</span>}
        </header>
        <ol className="flow__stages" aria-label="신청 단계">
          {APPLY_STEPS.map(({ key, label }, i) => {
            const complete = stepComplete(i)
            const current = i === currentIndex
            const canNavigate = stepReachable(i)
            const { state, count } = stepStatus(i)
            return (
            <li
              key={key}
              className={current ? (peeking ? 'is-current is-preview' : 'is-current') : complete ? 'is-complete' : 'is-waiting'}
            >
              {(() => {
                const content = <>
                  <span className="flow__stage-no" aria-hidden="true">{complete && !current ? <Icon name="check" size={18} /> : !current ? i + 1 : null}</span>
                  <span className="flow__stage-copy">
                    <span className="flow__stage-caption">
                      <span>{i + 1}단계</span>
                      {state && <span className="flow__stage-status">{state}</span>}
                      {count && <span className="flow__stage-count">{count}</span>}
                    </span>
                    <span className="flow__stage-label">{label}</span>
                  </span>
                </>
                return canNavigate
                  ? <button type="button" className="flow__stage-content" aria-current={current ? 'step' : undefined} onClick={() => stepperNavigate(i)}>{content}</button>
                  : <span className="flow__stage-content" aria-current={current ? 'step' : undefined}>{content}</span>
              })()}
            </li>
            )
          })}
        </ol>
      </div></div>
      <div className="flow__body">

      {/* ── 본인인증 (데모) ── */}
      {stage === 'identity' && (
        <IdentityCheck
          appId={appId}
          ensureApplication={async () => {
            const application = await applicationSession.ensure()
            setAppId(application.id)
            setAppNo(application.application_no)
            return application.id
          }}
          identity={identity}
          onVerified={(verified, mobile, verifiedAppId) => {
            setIdentity(verified)
            const locked = lockIdentity({ ...form1, mobile }, verified)
            setForm1(locked)
            save({ form1: withSavableEmail(locked, savableEmailRef) }, verifiedAppId)
            setStage('forms')
            window.scrollTo({ top: 0 })
          }}
          onNext={() => setStage('forms')}
        />
      )}

      {/* ── [1] 자가진단 ── */}
      {stage === 'forms' && appId !== null && (
        <PdfFormsWorkspace
          key={`${appId}:${program.code}:${!!submitted}`}
          applicationId={appId}
          identity={identity}
          form1={form1}
          answers={answers}
          consent={consent}
          checkResult={checkResult}
          onForm1={onForm1}
          onAnswers={(next) => { setAnswers(next); setCheckResult(null); save({ self_check: next }) }}
          onConsent={(next) => { setConsent(next); setConsentDirty(true) }}
          onBusyChange={setWorkspaceBusy}
          onFlush={flushForms}
          onChangedSubsidy={(state) => { setSelectedSubsidyTypes(state.selections.length); setChecklistKey((key) => key + 1) }}
          onContinue={() => void continueFromForms()}
          continuing={formContinuing || flushing || navigation.pending}
          error={navigation.error || formError}
          readOnly={!!submitted}
          onProgress={reportFormProgress}
          saveStatus={<SaveStatus phase={flushing || navigation.pending ? 'saving' : saveState} dirty={consentDirty} />}
        />
      )}

      {/* ── [4] 지원 항목 (취업지원패키지) ── */}
      {stage === 'subsidy' && appId !== null && (
        <>
          <SubsidyItems
            applicationId={appId}
            onChanged={(state: SubsidyState) => {
              setSelectedSubsidyTypes(state.selections.length)
              setChecklistKey((k) => k + 1)
            }}
          />
          <div className="flow__actions">
            <button type="button" className="btn" onClick={() => setStage('forms')}>
              이전
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => { setSelectionAttempted(true); if (selectedSubsidyTypes > 0) setStage('upload'); else window.requestAnimationFrame(() => document.getElementById('subsidy-missing')?.focus()) }}
            >
              서류 업로드로
            </button>
          </div>
          {selectionAttempted && selectedSubsidyTypes === 0 && <Notice id="subsidy-missing" tabIndex={-1} tone="warning" role="alert" title="지원 항목 1건을 선택해 주세요."><a href="#subsidy-items">지원 항목 선택으로 이동하기</a></Notice>}
        </>
      )}

      {/* ── [5] 서류 업로드 ── */}
      {stage === 'upload' && appId !== null && !submitted && (
        <>
          {identity === null && (
            <div className="flow-block flow-block--warn">
              <strong>본인인증 전입니다.</strong>
              <p>
                지금 올리는 서류는 본인 명의인지 대조하지 않습니다.{' '}
                <button type="button" className="btn btn--small" onClick={() => jumpTo('identity')}>
                  본인인증 하러 가기
                </button>
              </p>
            </div>
          )}
          <DocumentUpload key={checklistKey} applicationId={appId} onProgress={reportUploadProgress} onPendingChange={setUploadPending} />
          <p className="field__hint" role="status">{uploadPending ? '선택하신 파일을 처리하고 있습니다. 다른 칸의 파일을 선택하며 기다릴 수 있습니다.' : ''}</p>
          {finalGate && <MissingItems id="upload-gate" title="아직 제출할 수 없습니다. 아래 항목을 모두 마쳐야 다음으로 넘어갑니다." blockers={finalGate} current="upload" onGoto={(next) => { setFinalGate(null); jumpTo(next) }} />}
          {gateError && <Notice tone="danger" role="alert">{gateError}</Notice>}
          <div className="flow__actions">
            <button
              type="button"
              className="btn"
              disabled={uploadPending}
              onClick={() => setStage('subsidy')}
            >
              이전
            </button>
            <button type="button" className={gateChecking ? 'btn btn--primary btn--busy' : 'btn btn--primary'} disabled={uploadPending} aria-busy={gateChecking || undefined} onClick={() => void goToFinal()}>
              {gateChecking && <Spinner />}제출 전 최종 확인
            </button>
          </div>
        </>
      )}

      {/* ── [6] 제출 전 최종 확인 ── */}
      {stage === 'final' && appId !== null && (
        <>
          <FinalCheck
            onPendingChange={setUploadPending}
            applicationId={appId}
            onSubmitted={(result) => {
              setSubmitted(result)
              try { window.sessionStorage.setItem(`applicant.receiptSteps.${appId}`, JSON.stringify(result.next_steps)) } catch { /* A storage-disabled browser shows current status on refresh. */ }
              setStage('complete')
              window.scrollTo({ top: 0 })
            }}
            onBack={() => jumpTo(peeking && peekFrom ? peekFrom : 'upload')}
            onGoto={jumpTo}
          />
        </>
      )}

      {/* ── 제출 완료 ── */}
      {stage === 'complete' && submitted && appId !== null && (
        <>
          <section className="receipt card" aria-labelledby="receipt-title">
            <header className="receipt__head"><Icon name="checkCircle" size={32} /><h2 id="receipt-title">신청이 접수되었습니다</h2></header>
            <dl className="fact-list">
              <div><dt>신청번호</dt><dd className="receipt__number">{submitted.application_no}</dd></div>
              {submitted.submitted_at && <div><dt>접수 일시</dt><dd>{formatDateTime(submitted.submitted_at)}</dd></div>}
              <div><dt>사업명</dt><dd>{program.name}</dd></div>
              {submitted.first_come && <div><dt>접수 순번</dt><dd>{submitted.first_come.position}번</dd></div>}
              {submitted.subsidy && submitted.subsidy.lines.length > 0 && <div><dt>지급 예정액</dt><dd>{submitted.subsidy.total_granted.toLocaleString('ko-KR')}원</dd></div>}
            </dl>
            {submitted.next_steps.length > 0 && <><h3>다음 절차</h3><ol>{submitted.next_steps.map((step) => <li key={step}>{step}</li>)}</ol></>}
            {submitted.notice && <p>{submitted.notice}</p>}
            <ApplicantFormsBulkMenu applicationId={appId} refreshKey={1} />
            <div className="flow__actions"><button type="button" className="btn" onClick={() => window.print()}><Icon name="printer" />접수증 인쇄하기</button><button type="button" className="btn btn--primary" onClick={openMyPage}>마이페이지 열기</button></div>
          </section>
        </>
      )}

      {stage === 'mypage' && appId !== null && (
        <>
          <div className="flow__mypage-return">
            <button type="button" className="btn" onClick={() => setStage(stageBeforeMypage)}>신청 화면으로 돌아가기</button>
          </div>
          <MyPage applicationId={appId} />
        </>
      )}
      </div>
    </div>
  )
}
