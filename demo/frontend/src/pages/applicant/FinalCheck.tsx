/** Submission precheck: show missing items and their edit links without exposing scores. */

import { useEffect, useState } from 'react'

import {
  fetchFinalCheck,
  type FinalCheck as FinalCheckData,
  type SubmitResult,
} from '../../api.ts'
import { Skeleton, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import ConfirmDialog from '../../components/ConfirmDialog.tsx'
import MoreInfo from '../../components/MoreInfo.tsx'
import MissingItems, { type ApplicantStage } from './MissingItems.tsx'
import Notice from '../../components/Notice.tsx'
import Spinner from '../../components/Spinner.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import { friendlyError } from '../../lib/error-copy.ts'
import useApplicantSubmission from '../../hooks/useApplicantSubmission.ts'
import './final-check.css'

export default function FinalCheck({
  applicationId,
  onSubmitted,
  onBack,
  onGoto,
  onPendingChange,
}: {
  applicationId: number
  onPendingChange?: (pending: boolean) => void
  onSubmitted: (result: SubmitResult) => void
  onBack: () => void
  /** 남은 항목을 고치러 해당 단계로 간다 */
  onGoto: (stage: ApplicantStage) => void
}) {
  const [data, setData] = useState<FinalCheckData | null>(null)
  const submission = useApplicantSubmission(applicationId, onSubmitted)
  const busy = submission.busy
  useEffect(() => { onPendingChange?.(busy); return () => onPendingChange?.(false) }, [busy, onPendingChange])
  const [confirming, setConfirming] = useState(false)
  const [attempted, setAttempted] = useState(false)
  const [reload, setReload] = useState(0)
  useBeforeUnload(busy)
  const [error, setError] = useState('')
  const showSkeleton = useDelayedFlag(!data && !error)

  useEffect(() => {
    fetchFinalCheck(applicationId)
      .then(setData)
      .catch((e: unknown) => setError(friendlyError(e, '신청 내용을 확인하지 못했습니다. 다시 시도해 주세요.')))
  }, [applicationId, reload])

  const submit = async () => {
    setConfirming(false); setError('')
    await submission.submit()
    fetchFinalCheck(applicationId).then(setData).catch(() => undefined)
  }

  if (error && !data) return <Notice tone="danger" role="alert">{error}<button type="button" className="btn" onClick={() => { setError(''); setReload((value) => value + 1) }}>다시 시도하기</button></Notice>
  if (!data) return showSkeleton ? (
    <Skeleton className="fcheck fcheck__skeleton">
      <section className="fcheck__box"><h3>신청한 지원 항목</h3><table className="fcheck__docs"><thead><tr><th>항목</th><th>영수증 금액</th><th>지급 예정액</th></tr></thead><tbody>{[0, 1, 2].map((row) => <tr key={row}>{[0, 1, 2].map((col) => <td data-label="항목" key={col}><SkeletonLine width="64%" /></td>)}</tr>)}</tbody></table></section>
      <section className="fcheck__box"><h3>작성한 내용 확인하기</h3><dl className="fcheck__summary">{[0, 1, 2, 3, 4, 5].map((row) => <div key={row}><dt><SkeletonLine width="76%" /></dt><dd><SkeletonLine width="88%" /></dd></div>)}</dl></section>
      <div className="flow__actions"><button type="button" className="btn" disabled aria-disabled="true">이전</button><button type="button" className="btn btn--primary" disabled aria-disabled="true">제출하기</button></div>
    </Skeleton>
  ) : null

  return (
    <div className="fcheck">
      <h2>확인 및 제출</h2>
      {/* 단계 표시로 미리 보러 온 경우: 아직 제출할 수 없다는 것만 한 줄로 알린다(남은 항목 목록은 제출을 눌렀을 때). */}
      {!data.can_submit && !data.already_submitted && !attempted && (
        <Notice tone="info" title="미리 보기 화면입니다.">서류 업로드까지 모두 마치면 여기서 제출할 수 있습니다.</Notice>
      )}

      {data.subsidy && data.subsidy.lines.length > 0 && (
        <MoreInfo variant="card" open summary="신청한 지원 항목" meta={`지급 예정 ${data.subsidy.total_granted.toLocaleString('ko-KR')}원`}>
          <table className="fcheck__docs">
            <thead>
              <tr>
                <th>항목</th>
                <th>영수증 금액</th>
                <th>지급 예정액</th>
              </tr>
            </thead>
            <tbody>
              {data.subsidy.lines.map((line) => (
                <tr key={`${line.item_type}-${line.index}`}>
                  <td data-label="항목">{line.label}{line.linked_interview_index && <small className="subsidy__link-note">면접 {line.linked_interview_index}회차와 연결</small>}</td>
                  <td data-label="영수증 금액">
                    {line.actual_cost
                      ? line.receipt_amount === null
                        ? '미입력'
                        : `${line.receipt_amount.toLocaleString('ko-KR')}원`
                      : '불요'}
                  </td>
                  <td data-label="지급 예정액">
                    <strong>{line.granted_amount.toLocaleString('ko-KR')}원</strong>
                  </td>
                </tr>
              ))}
              <tr>
                <th colSpan={2}>합계</th>
                <td data-label="지급 예정액">
                  <strong>
                    {data.subsidy.total_granted.toLocaleString('ko-KR')}원
                  </strong>
                </td>
              </tr>
            </tbody>
          </table>
        </MoreInfo>
      )}

      <MoreInfo variant="card" open summary="작성한 내용 확인하기" meta={data.form_summary.some((f) => !f.value) ? `미입력 ${data.form_summary.filter((f) => !f.value).length}개` : '모두 입력'}>
        <dl className="fcheck__summary">
          {data.form_summary.map((f) => (
            <div key={f.label}>
              <dt>{f.label}</dt>
              <dd className={f.value ? undefined : 'is-empty'}>{f.value || '미입력'}</dd>
            </div>
          ))}
        </dl>
      </MoreInfo>

      {(error || submission.error) && <Notice tone="danger" role="alert">{submission.error || error}{submission.unknown && <button type="button" className="btn" disabled={busy} onClick={() => void submission.check()}>접수 상태 다시 확인</button>}</Notice>}

      {/* 서류 업로드에서 이미 막으므로 평소에는 나오지 않는다. 새로고침 등으로 바로 들어와 제출을 눌렀을 때만 남은 항목을 보여 준다. */}
      {attempted && !data.can_submit && !data.already_submitted && (
        <MissingItems id="fcheck-todo" title="아직 제출할 수 없습니다. 아래 항목을 마쳐 주세요." blockers={data.blockers} onGoto={onGoto} />
      )}

      <div className="flow__actions">
        <button type="button" className="btn" disabled={busy} onClick={onBack}>
          이전
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={data.already_submitted || busy || submission.unknown}
          onClick={() => {
            setAttempted(true)
            if (!data.can_submit) { window.requestAnimationFrame(() => document.getElementById('fcheck-todo')?.focus()); return }
            setConfirming(true)
          }}
        >
          {busy && <Spinner />}{data.already_submitted
            ? '이미 제출된 신청입니다'
            : busy
              ? '제출하는 중'
              : data.can_submit
                ? '제출하기'
                : '제출하기'}
        </button>
      </div>
      {confirming && <ConfirmDialog title="신청서를 최종 제출하시겠습니까?" description="작성하신 내용과 서류를 확인해 주세요. 제출 후에는 수정할 수 없습니다." confirmLabel="제출하기" onCancel={() => setConfirming(false)} onConfirm={() => void submit()} size="md">
        <dl className="fact-list">{data.form_summary.filter((field) => field.value).map((field) => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl>
        <p>제출 서류 {data.documents.length}건</p>
      </ConfirmDialog>}
    </div>
  )
}
