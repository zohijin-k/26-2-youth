/**
 * 서류 업로드 · 즉시 판정 (P2).
 *
 * 제출 전에 서류 상태를 확인하고 필요한 내용을 보완할 수 있도록 안내한다.
 * 그래서 이 화면의 전부는 "올리는 순간 알려준다"에 걸려 있다.
 *
 *   슬롯마다  [발급처 바로가기] [발급일 직접 입력] → [파일 업로드]
 *            발급일 입력을 받는 서류는 날짜를 다 적어야 파일을 고를 수 있다 (2차 검증의 기준값)
 *   업로드 즉시 확인 안내 + 해결 방법 + 재업로드 (R2.1·R2.2)
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import {
  deleteDocument,
  fetchChecklist,
  fetchInterviewFormFileOptions,
  uploadDocument,
  type Checklist,
  type DocRequirementRow,
  type UploadedDocument,
} from '../../api.ts'
import FilePreview from '../../components/ApplicantFilePreview.tsx'
import { Skeleton, SkeletonCard, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import Modal from '../../components/ApplicantModal.tsx'
import PdfPages from '../../components/PdfPages.tsx'
import StatusBadge from '../../components/ApplicantStatusBadge.tsx'
import { DateTriple } from '../../forms/FormSheet.tsx'
import { EMPTY_YMD, isCompleteYMD, ymdToISO, type YMD } from '../../forms/ymd.ts'
import ConfirmDialog from '../../components/ConfirmDialog.tsx'
import Icon from '../../components/Icon.tsx'
import MoreInfo from '../../components/MoreInfo.tsx'
import Notice from '../../components/Notice.tsx'
import ProgressBar from '../../components/ProgressBar.tsx'
import Spinner from '../../components/Spinner.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import { friendlyError } from '../../lib/error-copy.ts'
import { formatBytes, formatDate } from '../../lib/format.ts'
import { precheckFile, type PdfProbe } from '../../lib/file-precheck.ts'
import { estimateSeconds, rememberObservation, slowThresholdSec, type Observation } from '../../lib/upload-estimate.ts'
import { queueReducer, nextRunnable, slotItem, isActive, transferPercentage, type QueueItem } from './upload-queue.ts'
import { mutationError, slotChange } from '../../lib/applicant-mutation.ts'
import './document-upload.css'

const probePdf: PdfProbe = async (file) => {
  const pdfjs = await import('pdfjs-dist')
  const task = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) })
  try {
    const pdf = await task.promise
    const text = await (await pdf.getPage(1)).getTextContent()
    return { pages: pdf.numPages, hasText: text.items.some((part) => 'str' in part && part.str.trim().length > 0) }
  } finally { await task.destroy() }
}

function PendingFile({file, url, job, onCancel, onRetry}: { file: File; url: string; job?: QueueItem; onCancel?: () => void; onRetry?: () => void }) {
  const [now, setNow] = useState(() => Date.now())
  const status = job?.status
  useEffect(() => {
    if (!status || !['sending', 'reading'].includes(status)) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [status])
  const elapsed = Math.max(0, Math.floor((now - (job?.sentAt ?? job?.startedAt ?? now)) / 1000))
  const reading = job?.status === 'reading'
  const percentage = job ? transferPercentage(job) : null
  const slow = reading && elapsed > slowThresholdSec(job.estimateSec)
  const label = !job ? '파일을 확인하고 있습니다.' : job.status === 'queued' ? '대기 중' : job.status === 'failed' ? '올리지 못했습니다.' : reading ? '서류를 읽고 확인하고 있습니다.' : '파일을 보내고 있습니다.'
  return <div className="upload-pending">
    <div className="upload-pending__file">
      {file.name.toLowerCase().endsWith('.pdf') ? <PdfPages url={url} width={56} maxPages={1} maxHeight={76} /> : <img src={url} alt="선택한 서류 미리보기" />}
      <div><strong>{file.name}</strong><p>{formatBytes(file.size)}</p></div>
    </div>
    <p>{job?.status !== 'failed' && job?.status !== 'queued' && <Spinner />} {label}</p>
    {job?.status === 'sending' && <><ProgressBar indeterminate={percentage === null} value={job.sent} max={job.total} label="파일 전송" />{percentage !== null && <p>{percentage}% 전송</p>}</>}
    {reading && <><ProgressBar indeterminate label="서류 자동 확인" /><p>{elapsed}초 경과 · 분석이 끝나면 결과를 표시합니다.</p></>}
    {slow && <Notice tone="warning">평소보다 오래 걸리고 있습니다. 창을 닫지 말고 기다려 주세요.</Notice>}
    {job?.error && <Notice tone="danger">{job.error}<p>이 화면을 떠나면 파일을 다시 선택해야 합니다. 서버의 서류 상태를 먼저 확인해 주세요.</p></Notice>}
    {job?.hint && <p>{job.hint}</p>}
    {onCancel && <button type="button" className="btn btn--small" onClick={onCancel}>대기 취소하기</button>}
    {onRetry && <button type="button" className="btn btn--small" onClick={onRetry}>서버 상태 확인 후 재시도</button>}
  </div>
}


/**
 * 판정 도장. 서류 접수 때 찍는 도장처럼 결과를 한 번에 보여준다.
 * 슬롯 머리 오른쪽에 하나만 둔다 — 상태를 여러 곳에서 반복하지 않는다.
 */
/** 파일 형식 표시 (PDF·JPG·PNG). */
function fileKind(name: string): string {
  return (name.split('.').pop() ?? '').toUpperCase().slice(0, 4) || 'FILE'
}

function isPdf(doc: UploadedDocument): boolean {
  return (doc.file_format || doc.file_name).toLowerCase().endsWith('pdf')
}

function DocumentThumbnail({ doc, onClick }: { doc: UploadedDocument; onClick: () => void }) {
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)
  const pdf = isPdf(doc)
  const extension = fileKind(doc.file_name)
  const kind = extension === 'JPEG' ? 'JPG' : extension

  return (
    <button
      type="button"
      className="dresult__kind"
      onClick={onClick}
      aria-label={`${doc.file_name} 크게 보기`}
    >
      {!failed && (pdf ? (
        <PdfPages
          url={doc.file_url}
          width={56}
          maxHeight={76}
          maxPages={1}
          className={ready ? 'dresult__pages dresult__pages--ready' : 'dresult__pages'}
          onReady={() => setReady(true)}
          onError={() => setFailed(true)}
        />
      ) : (
        <img
          className="dresult__image"
          src={doc.file_url}
          alt=""
          onLoad={() => setReady(true)}
          onError={() => setFailed(true)}
        />
      ))}
      {(!ready || failed) && <span className="dresult__fallback">{kind}</span>}
      {ready && !failed && <span className="dresult__badge">{kind}</span>}
    </button>
  )
}

function DocumentResult({
  doc,
  onRetry,
}: {
  doc: UploadedDocument
  onRetry: () => void
}) {
  const [viewing, setViewing] = useState(false)
  const status = doc.status ?? 'NEEDS_REVIEW'
  const extracted = Object.entries(doc.extracted)
  return (
    <div className={`dresult dresult--${status.toLowerCase()}`}>
      <div className="dresult__file">
        <DocumentThumbnail key={doc.file_url} doc={doc} onClick={() => setViewing(true)} />
        <div className="dresult__body">
          <button type="button" className="dresult__name" onClick={() => setViewing(true)}>
            {doc.file_name}
          </button>
          {extracted.length > 0 && (
            <dl className="dextract">
              {extracted.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          )}
          {/* 확인이 필요한 경우에만 판독된 서류 종류를 함께 보여준다 */}
          {status !== 'PASS' && doc.detected_doc_type && (
            <span className="dresult__detected">읽은 서류 종류: {doc.detected_doc_type}</span>
          )}

        </div>
        <div className="dresult__actions">
          <button type="button" className="btn btn--small" onClick={() => setViewing(true)}>
            미리보기
          </button>
          <button type="button" className="btn btn--small dresult__retry" onClick={onRetry}>
            다시 올리기
          </button>
        </div>
      </div>
      {viewing && (
        <FilePreview
          url={doc.file_url}
          name={doc.file_name}
          kind={(doc.file_format || doc.file_name).toLowerCase().endsWith('pdf') ? 'pdf' : 'image'}
          onClose={() => setViewing(false)}
        />
      )}

      {status !== 'PASS' && <p className="dresult__automatic">{status === 'FAIL' ? '자동 확인 결과입니다. 사유와 해결 방법을 확인한 뒤 다시 올려 주세요.' : '자동 확인 결과입니다. 담당자 확인이 필요한 서류입니다.'}</p>}
      {doc.findings.map((f) => (
        <div key={f.code} className="dfinding">
          <p className="dfinding__msg">{f.message}</p>
          {f.how_to_fix && <p className="dfinding__fix">{f.how_to_fix}</p>}
          {f.link && (
            <a className="dfinding__link" href={f.link} target="_blank" rel="noreferrer">
              발급처 바로가기 <Icon name="external" size={16} />
            </a>
          )}
        </div>
      ))}
    </div>
  )
}

/** 카드에서 접어 둔 요건 설명 · 체크포인트. "서류 안내 보기"를 눌러야 펼쳐진다. 발급처 링크는
    카드에 남겨 새 창으로 바로 열리게 한다 — 접힌 안내 안에 숨기지 않는다. */
function SlotInfo({ item }: { item: DocRequirementRow }) {
  return (
    <>
      <div className="dinfo__section">
        <h4>올리는 방법</h4>
        <p>받는 형식: {item.accept.map((format) => format.toUpperCase()).join(' · ')}. 발급처의 PDF를 권장합니다. 촬영할 때는 서류 전체가 밝고 선명하게 나오도록 해 주세요.</p>
      </div>
      {item.doc_type_choices.length > 1 && (
        <div className="dinfo__section">
          <h4>인정되는 서류</h4>
          <p>{item.doc_type_choices.join(' 또는 ')} 중 하나만 올리면 됩니다.</p>
        </div>
      )}
      {item.required_fields.length > 0 && (
        <div className="dinfo__section">
          <h4>반드시 있어야 하는 표기</h4>
          <p>{item.required_fields.join('·')} 표기가 반드시 있어야 인정됩니다.</p>
        </div>
      )}
      {item.notes.length > 0 && (
        <div className="dinfo__section">
          <h4>안내</h4>
          {item.notes.map((n) => (
            <p key={n}>※ {n}</p>
          ))}
        </div>
      )}
      {item.alternatives.length > 0 && (
        <div className="dinfo__section">
          <h4>대체 가능</h4>
          {item.alternatives.map((n) => (
            <p key={n} className="dinfo__alt">
              {n}
            </p>
          ))}
        </div>
      )}
      {item.warnings.length > 0 && (
        <div className="dinfo__section caution">
          <h4><Icon name="alert" size={18} />자주 틀리는 부분</h4>
          <ul className="dinfo__warn">
            {item.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}

function SlotCard({
  item,
  applicationId,
  job,
  problem,
  onCancel,
  onSameFile,
  declared,
  onDeclaredChange,
  onPick,
  onRetry,
}: {
  item: DocRequirementRow
  applicationId: number
  job: QueueItem | null
  problem?: string
  onCancel: () => void
  onSameFile: () => void
  declared: YMD
  onDeclaredChange: (v: YMD) => void
  onPick: (file: File) => Promise<void>
  onRetry: (doc: UploadedDocument) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [interviewFormOpen, setInterviewFormOpen] = useState(false)
  const [interviewPdfReady, setInterviewPdfReady] = useState(false)
  const [interviewHwp, setInterviewHwp] = useState<string | null>(null)
  const [preparing, setPreparing] = useState<{file: File; url: string} | null>(null)
  const [dateAttempted, setDateAttempted] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const previousStatus = useRef('')
  useEffect(() => {
    const status = preparing ? 'checking' : job?.status ?? (item.documents.length ? 'complete' : problem ? 'failed' : '')
    if (status === previousStatus.current) return
    previousStatus.current = status
    const text: Record<string, string> = { checking: '파일을 확인하고 있습니다.', queued: '대기 중입니다.', sending: '파일을 보내기 시작했습니다.', reading: '', failed: '파일을 올리지 못했습니다.', complete: '서류 자동 확인을 마쳤습니다.' }
    setAnnouncement(`${item.label} ${status === 'checking' ? '파일을 확인하고 있습니다.' : text[status] ?? ''}`)
  }, [preparing, job?.status, item.label, item.documents.length, problem])
  useEffect(() => () => { if (preparing) URL.revokeObjectURL(preparing.url) }, [preparing])
  const doc = item.documents[0]
  const status = doc?.status ?? null
  // 발급일 직접 입력이 있는 서류는 날짜를 먼저 받아야 업로드 즉시 2차 검증을 할 수 있다.
  const dateReady = !item.check_declared_date || isCompleteYMD(declared)
  const issueISO = isCompleteYMD(declared) ? ymdToISO(declared) : ''
  const current = new Date()
  const todayISO = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`
  const basisLabel = item.date_basis_label || '발급일'
  const dateWarning = issueISO && issueISO > todayISO
    ? `${basisLabel}이 오늘 이후입니다. 다시 확인해 주세요.`
    : issueISO && item.min_issue_date && issueISO < item.min_issue_date
      ? `이 사업은 ${formatDate(item.min_issue_date)} 이후 ${basisLabel}만 인정합니다. 서류를 확인해 주세요.`
      : ''

  useEffect(() => {
    if (!/^(interview|suit)_\d+_confirmation$/.test(item.slot_key)) return
    let alive = true
    fetchInterviewFormFileOptions(applicationId).then((options) => {
      if (alive) setInterviewHwp(options.hwp)
    }).catch(() => { if (alive) setInterviewHwp(null) })
    return () => { alive = false }
  }, [applicationId, item.slot_key])

  return (
    <li
      className={`dslot dslot--${status ? status.toLowerCase() : 'empty'}`}
      id={`slot-${item.slot_key}`}
    >
      <div className="dslot__head">
        <div className="dslot__title">
          <span className="dslot__label">{item.label}</span>
          {item.required && <span className="field__req">필수</span>}
        </div>
        <div className="dslot__head-meta">
          {status ? (
            <StatusBadge status={status} audience="applicant" />
          ) : null}
          {!status && item.issuer_url && (
            <a className="dslot__issuer" href={item.issuer_url} target="_blank" rel="noreferrer">
              {item.issuer}에서 발급받기 <Icon name="external" size={16} />
            </a>
          )}
        </div>
      </div>

      <p className="dslot__criteria">{item.issue_rule_label}{item.notes.filter((note) => note.startsWith('조회기간에 ') || note.startsWith('최근 ')).map((note) => ` · ${note}`).join('')}</p>
      <MoreInfo summary="서류 안내 보기" className="dslot__more"><SlotInfo item={item} /></MoreInfo>

      {/^(interview|suit)_\d+_confirmation$/.test(item.slot_key) && (
        <details className="dslot__files-menu"><summary className="btn btn--small">면접확인서 양식</summary>
          <a href={`/api/applications/${applicationId}/forms/files/job_interview_confirmation/blank.pdf`}>빈 서식 PDF</a>
          {interviewHwp && <a href={interviewHwp}>원본 HWP</a>}
          <button type="button" className="btn btn--small" onClick={() => { setInterviewPdfReady(false); setInterviewFormOpen(true) }}>미리보기</button>
        </details>
      )}

      {/* 올리기 전: 발급일 → 파일 업로드. 올린 뒤에는 결과만 남긴다. */}
      {!doc && !job && !preparing && (
        <div className="dslot__action">
          <input
            ref={input}
            className="dslot__file"
            type="file"
            accept={item.accept.map((f) => `.${f}`).join(',')}
            aria-label={`${item.label} 파일 선택`}
            onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ''
              if (!file) return
              setPreparing({ file, url: URL.createObjectURL(file) })
              void onPick(file).finally(() => setPreparing(null))
            }}
          />
          {item.check_declared_date && (
            <fieldset className="dslot__declared" onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node) && Object.values(declared).some(Boolean)) setDateAttempted(true)
            }}>
              <legend className="dslot__declared-label">서류에 적힌 {basisLabel}<span className="field__req">필수</span></legend>
              <DateTriple value={declared} onChange={onDeclaredChange} ariaPrefix={item.label} describedBy={`slot-${item.slot_key}-date-hint`} invalid={dateAttempted && !dateReady} />
              <p id={`slot-${item.slot_key}-date-hint`} className="dslot__gate" role={dateAttempted && !dateReady ? 'alert' : undefined}>
                {dateReady ? `서류에 적힌 ${basisLabel}과 같은지 확인해 주세요.` : `${basisLabel}을 모두 입력하면 파일을 고를 수 있습니다.`}
              </p>
            </fieldset>
          )}
          {dateWarning && <p className="dslot__date-warning" role="status">{dateWarning}</p>}
          <button
            type="button"
            className="btn dslot__upload"
            onClick={() => { setDateAttempted(true); if (dateReady) input.current?.click(); else document.querySelector<HTMLElement>(`#slot-${item.slot_key} .form-date input`)?.focus() }}
          >
            <Icon name="upload" />
            파일 선택
          </button>
        </div>
      )}

      {preparing && <PendingFile file={preparing.file} url={preparing.url} />}
      {!preparing && job && <PendingFile file={job.file} url={job.previewUrl} job={job} onCancel={job.status === 'queued' ? onCancel : undefined} onRetry={job.status === 'failed' ? onSameFile : undefined} />}
      {!preparing && !job && problem && <Notice tone="danger" role="alert">{problem}</Notice>}
      <p className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</p>
      {doc && <DocumentResult doc={doc} onRetry={() => onRetry(doc)} />}
      {interviewFormOpen && (
        <Modal
          title="면접확인서 양식 보기"
          onClose={() => setInterviewFormOpen(false)}
          variant="printable-viewer"
          footer={<button type="button" className="btn btn--primary" disabled={!interviewPdfReady} onClick={() => window.print()}>인쇄</button>}
        >
          <div className="dupload__form-preview">
            <p>신청자 정보가 미리 들어 있습니다. 회사에서 면접 내용과 확인 서명을 작성합니다.</p>
            <img
              className="dupload__form-page"
              src={`/api/applications/${applicationId}/forms/job_interview_confirmation/pages/1.png?preview=true`}
              alt="면접확인서 양식"
              onLoad={() => setInterviewPdfReady(true)}
              onError={() => setInterviewPdfReady(false)}
            />
          </div>
        </Modal>
      )}
    </li>
  )
}

export default function DocumentUpload({applicationId, onProgress, onPendingChange}: {
  applicationId: number
  onProgress: (uploaded: number, total: number) => void
  onPendingChange: (pending: boolean) => void
}) {
  const [checklist, setChecklist] = useState<Checklist | null>(null)
  const [declared, setDeclared] = useState<Record<string, YMD>>({})
  const [queue, dispatch] = useReducer(queueReducer, [])
  const [problems, setProblems] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [reconciling, setReconciling] = useState(false)
  const [retryConfirm, setRetryConfirm] = useState<QueueItem | null>(null)
  const [recoveryNotice, setRecoveryNotice] = useState('')
  const recoveryLock = useRef(false)
  const attempts = useRef(new Map<string, number | null>())
  const dirty = useRef(false)
  const [removeTarget, setRemoveTarget] = useState<UploadedDocument | null>(null)
  const [preparingCount, setPreparingCount] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const showChecklistSkeleton = useDelayedFlag(!checklist && !error)
  const observation = useRef<Observation[]>([])
  const revision = useRef(0)
  const request = useRef<AbortController | null>(null)
  const epoch = useRef(0)
  const urls = useRef(new Set<string>())
  const active = isActive(queue) || preparingCount > 0 || deleting || reconciling
  useBeforeUnload(active || queue.some((item) => item.status === 'failed'))
  useEffect(() => { onPendingChange(active); return () => onPendingChange(false) }, [active, onPendingChange])
  useEffect(() => {
    epoch.current += 1
    const ownedUrls = urls.current
    return () => { epoch.current += 1; request.current?.abort(); request.current = null; for (const url of ownedUrls) URL.revokeObjectURL(url); ownedUrls.clear() }
  }, [])
  useEffect(() => {
    let alive = true
    fetchChecklist(applicationId).then((next) => { if (alive) setChecklist(next) }).catch((error: unknown) => { if (alive) setError(friendlyError(error, '서류 목록을 불러오지 못했습니다. 다시 시도해 주세요.')) })
    return () => { alive = false }
  }, [applicationId, attempt])
  useEffect(() => { if (checklist) onProgress(checklist.upload_done, checklist.upload_total) }, [checklist, onProgress])

  const refresh = useCallback(() => {
    const current = revision.current
    const generation = epoch.current
    return fetchChecklist(applicationId).then((next) => { if (epoch.current === generation && revision.current === current) setChecklist(next) })
  }, [applicationId])

  useEffect(() => {
    const item = nextRunnable(queue)
    if (!item || request.current || recoveryLock.current) return
    const controller = new AbortController()
    request.current = controller
    const generation = epoch.current
    revision.current += 1; dirty.current = true
    attempts.current.set(item.id, checklist?.items.find((row) => row.slot_key === item.slotKey)?.documents[0]?.document_id ?? null)
    let sentAt: number | null = null
    dispatch({ type: 'start', id: item.id, now: Date.now() })
    uploadDocument(applicationId, item.slotKey, item.file, item.declared, {
      signal: controller.signal,
      onProgress: (sent, total) => { if (epoch.current === generation) dispatch({ type: 'progress', id: item.id, sent, total }) },
      onSent: () => { if (epoch.current !== generation) return; sentAt = Date.now(); dispatch({ type: 'sent', id: item.id, now: sentAt }) },
    }).then((doc) => {
      if (epoch.current !== generation) return
      revision.current += 1
      setChecklist((current) => {
        if (!current) return current
        const items = current.items.map((row) => row.slot_key === doc.slot_key ? { ...row, documents: [doc] } : row)
        return { ...current, items, upload_done: items.filter((row) => row.upload && row.documents.length > 0).length }
      })
      if (sentAt !== null) observation.current = rememberObservation(observation.current, { kind: item.kind, pages: item.pages ?? 1, ms: Date.now() - sentAt })
      request.current = null
      dispatch({ type: 'succeed', id: item.id })
      URL.revokeObjectURL(item.previewUrl); urls.current.delete(item.previewUrl)

    }).catch((error: unknown) => {
      if (epoch.current !== generation) return
      request.current = null
      dispatch({ type: 'fail', id: item.id, now: Date.now(), error: mutationError(error, '응답을 확인하지 못했습니다. 서버 상태를 먼저 확인해 주세요.') })
    })
  }, [queue, applicationId, refresh, checklist?.items])

  useEffect(() => {
    if (active || request.current || !dirty.current) return
    dirty.current = false
    void refresh().catch(() => setError('최신 서류 목록을 확인하지 못했습니다. 목록을 다시 확인해 주세요.'))
  }, [active, refresh])

  const reconcileUpload = async (job: QueueItem) => {
    if (recoveryLock.current || request.current || isActive(queue) || deleting || preparingCount > 0) return
    recoveryLock.current = true; setReconciling(true); setRecoveryNotice('서버의 현재 서류 상태를 확인하고 있습니다.')
    const generation = epoch.current; revision.current += 1
    try {
      const next = await fetchChecklist(applicationId)
      if (generation !== epoch.current) return
      setChecklist(next)
      const row = next.items.find((item) => item.slot_key === job.slotKey)
      if (!row || slotChange(attempts.current.get(job.id) ?? null, row.documents) === 'changed') {
        dispatch({ type: 'clearSlot', slotKey: job.slotKey }); attempts.current.delete(job.id)
        URL.revokeObjectURL(job.previewUrl); urls.current.delete(job.previewUrl)
        setRecoveryNotice('서버의 서류 상태가 변경되었습니다. 원본과 결과를 확인해 주세요. 파일은 다시 전송하지 않았습니다.')
      } else { setRecoveryNotice('서버 목록을 확인했습니다. 재전송 전에 안내를 확인해 주세요.'); setRetryConfirm(job) }
    } catch (problem: unknown) { if (generation === epoch.current) setRecoveryNotice(mutationError(problem, '서버 상태를 확인하지 못했습니다. 재전송하지 않았습니다. 잠시 후 다시 확인해 주세요.')) }
    finally { recoveryLock.current = false; if (generation === epoch.current) setReconciling(false) }
  }

  const upload = async (item: DocRequirementRow, file: File) => {
    const failed = slotItem(queue, item.slot_key)
    if (failed?.status === 'failed') { void reconcileUpload(failed); return }
    const generation = epoch.current
    setPreparingCount((count) => count + 1)
    setProblems((current) => ({ ...current, [item.slot_key]: '' }))
    try {
      const checked = await precheckFile(file, probePdf)
      if (epoch.current !== generation) { if (checked.ok) URL.revokeObjectURL(checked.previewUrl); return }
      if (!checked.ok) { setProblems((current) => ({ ...current, [item.slot_key]: checked.message })); return }
      urls.current.add(checked.previewUrl)
      dispatch({ type: 'enqueue', now: Date.now(), item: {
        id: crypto.randomUUID(), slotKey: item.slot_key, file, declared: ymdToISO(declared[item.slot_key] ?? EMPTY_YMD),
        previewUrl: checked.previewUrl, kind: checked.kind, pages: checked.pages, hint: checked.hint,
        estimateSec: estimateSeconds(checked.kind, checked.pages, observation.current),
      } })
    } finally { if (epoch.current === generation) setPreparingCount((count) => count - 1) }
  }
  const remove = async () => {
    if (!removeTarget || deleting) return
    const doc = removeTarget
    setRemoveTarget(null); setDeleting(true)
    try { await deleteDocument(applicationId, doc.document_id); revision.current += 1; await refresh() }
    catch (error: unknown) {
      const message = friendlyError(error, '서류를 삭제하지 못했습니다. 다시 시도해 주세요.')
      if (checklist?.items.some((item) => item.slot_key === doc.slot_key)) setProblems((current) => ({ ...current, [doc.slot_key]: message }))
      else setError(message)
    }
    finally { setDeleting(false) }
  }
  if (error && !checklist) return <Notice tone="danger" role="alert" title="서류 목록을 불러오지 못했습니다.">{error}<button type="button" className="btn btn--small" onClick={() => { setError(''); setAttempt((value) => value + 1) }}>다시 시도하기</button></Notice>
  if (!checklist) return showChecklistSkeleton ? (
    <Skeleton className="dupload__skeleton-list">
      {Array.from({ length: 5 }, (_, index) => (
        <SkeletonCard key={index} className="dupload__skeleton-slot">
          <SkeletonLine width="38%" />
          <SkeletonLine width="78%" />
          <SkeletonLine width="54%" />
        </SkeletonCard>
      ))}
    </Skeleton>
  ) : null

  const uploadItems = checklist.items.filter((i) => i.upload)
  const onlineItems = checklist.items.filter((i) => !i.upload)

  return (
    <div className="dupload">
      <h2>서류 업로드</h2>
      <div className="dupload__progress">
        <span className="dupload__count">제출 서류 <strong>{checklist.upload_done}</strong> / {checklist.upload_total}</span>
        {checklist.program.has_subsidy_items && (
          <span className="dupload__progress-hint">고른 지원 항목에 따라 목록이 바뀝니다.</span>
        )}
        <ProgressBar value={checklist.upload_done} max={checklist.upload_total || 1} label="제출 서류" />
      </div>

      <ul className="dslots">
        {uploadItems.map((item) => (
          <SlotCard
            key={item.slot_key}
            item={item}
            applicationId={applicationId}
            job={slotItem(queue, item.slot_key)}
            problem={problems[item.slot_key]}
            onCancel={() => { const job = slotItem(queue, item.slot_key); if (job?.status === 'queued') { dispatch({type: 'cancel', id: job.id}); URL.revokeObjectURL(job.previewUrl); urls.current.delete(job.previewUrl) } }}
            onSameFile={() => { const job = slotItem(queue, item.slot_key); if (job) void reconcileUpload(job) }}
            declared={declared[item.slot_key] ?? EMPTY_YMD}
            onDeclaredChange={(value) => setDeclared((current) => ({ ...current, [item.slot_key]: value }))}
            onPick={(file) => upload(item, file)}
            onRetry={setRemoveTarget}
          />
        ))}
      </ul>

      {onlineItems.length > 0 && (
        <MoreInfo summary="올리지 않아도 되는 서류" meta={`${onlineItems.length}건`} className="dupload__online">
          <ul>
            {onlineItems.map((i) => (
              <li key={i.slot_key}>
                <strong>{i.label}</strong> — {i.fulfilled_by}(으)로 대체되었습니다.
              </li>
            ))}
          </ul>
        </MoreInfo>
      )}

      {checklist.unassigned.length > 0 && (
        <section className="dupload__unassigned">
          <h3>배정되지 않은 페이지</h3>
          <ul>
            {checklist.unassigned.map((d) => (
              <li key={d.document_id}>
                {d.file_name}
                {d.page_index !== null && ` (${d.page_index + 1}쪽)`} —{' '}
                {d.detected_doc_type ?? '서류 종류 미판별'}
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => setRemoveTarget(d)}
                >
                  삭제
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {recoveryNotice && <Notice tone="info" role="status">{recoveryNotice}</Notice>}
      {retryConfirm && <ConfirmDialog title="서버 상태를 확인했습니다. 다시 전송하시겠습니까?" description="이전 요청의 응답은 확인되지 않았습니다. 다시 전송하면 기존 서류가 교체될 수 있습니다. 서버의 원본을 먼저 확인해 주세요." confirmLabel="같은 파일 다시 전송" onCancel={() => setRetryConfirm(null)} onConfirm={() => { const job = retryConfirm; setRetryConfirm(null); dispatch({ type: 'retry', id: job.id, now: Date.now() }) }}><button type="button" className="btn" onClick={() => {
        const job = retryConfirm; setRetryConfirm(null); dispatch({ type: 'clearSlot', slotKey: job.slotKey })
        URL.revokeObjectURL(job.previewUrl); urls.current.delete(job.previewUrl)
        setRecoveryNotice('다른 파일을 선택해 주세요. 서버에 저장된 원본은 먼저 확인해 주세요.')
      }}>다른 파일 선택</button></ConfirmDialog>}
      {error && <Notice tone="danger" role="alert">{error}<button type="button" className="btn btn--small" onClick={() => void refresh().then(() => setError('')).catch(() => setError('목록을 불러오지 못했습니다. 다시 시도해 주세요.'))}>목록 다시 확인하기</button></Notice>}
      {removeTarget && <ConfirmDialog title="이 서류를 삭제하시겠습니까?" description="삭제한 서류는 다시 올려야 합니다." confirmLabel="서류 삭제하기" tone="danger" onCancel={() => setRemoveTarget(null)} onConfirm={() => void remove()}><p>{removeTarget.file_name}</p></ConfirmDialog>}
    </div>
  )
}
