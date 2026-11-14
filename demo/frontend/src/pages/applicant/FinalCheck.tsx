/** Submission precheck: show missing items and their edit links without exposing scores. */

import { useEffect, useState } from 'react'

import {
  fetchFinalCheck,
  submitApplication,
  type Blocker,
  type FinalCheck as FinalCheckData,
  type SubmitResult,
} from '../../api.ts'
import FileLink from '../../components/ApplicantFileLink.tsx'
import StatusBadge from '../../components/ApplicantStatusBadge.tsx'
import { Skeleton, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import ConfirmDialog from '../../components/ConfirmDialog.tsx'
import Notice from '../../components/Notice.tsx'
import Spinner from '../../components/Spinner.tsx'
import useBeforeUnload from '../../hooks/useBeforeUnload.ts'
import { friendlyError } from '../../lib/error-copy.ts'
import { formatDate } from '../../lib/format.ts'
import './final-check.css'

/** 남은 항목을 어느 화면에서 고치는지 기준으로 묶는다. 순서는 신청 순서대로. */
type ApplicantStage = 'forms' | 'subsidy' | 'upload'

const BLOCKER_GROUPS: { goto: ApplicantStage; title: string; action: string }[] = [
  { goto: 'forms', title: '신청 서식', action: '서식 작성으로' },
  { goto: 'subsidy', title: '지원 항목', action: '지원 항목으로' },
  { goto: 'upload', title: '서류', action: '서류 업로드로' },
]

function applicantStage(goto: Blocker['goto']): ApplicantStage {
  return goto === 'form1' || goto === 'consent' ? 'forms' : goto
}

export default function FinalCheck({
  applicationId,
  onSubmitted,
  onBack,
  onGoto,
}: {
  applicationId: number
  onSubmitted: (result: SubmitResult) => void
  onBack: () => void
  /** 남은 항목을 고치러 해당 단계로 간다 */
  onGoto: (stage: ApplicantStage) => void
}) {
  const [data, setData] = useState<FinalCheckData | null>(null)
  const [busy, setBusy] = useState(false)
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
    setConfirming(false)
    setBusy(true)
    setError('')
    try {
      onSubmitted(await submitApplication(applicationId))
    } catch (e: unknown) {
      setError(friendlyError(e, '신청 내용을 확인하지 못했습니다. 다시 시도해 주세요.'))
      fetchFinalCheck(applicationId).then(setData).catch(() => undefined)
    } finally {
      setBusy(false)
    }
  }

  if (error && !data) return <Notice tone="danger" role="alert">{error}<button type="button" className="btn" onClick={() => { setError(''); setReload((value) => value + 1) }}>다시 시도하기</button></Notice>
  if (!data) return showSkeleton ? (
    <Skeleton className="fcheck fcheck__skeleton">
      <section className="fcheck__todo"><h3>제출 전에 채워야 할 항목 <span><SkeletonLine width="30px" /></span></h3><ul>{['신청 서식', '지원 항목', '서류'].map((label) => <li key={label}><span className="fcheck__todo-title">{label}</span><span className="fcheck__todo-items"><SkeletonLine width="74%" /></span><button type="button" className="btn btn--small" disabled aria-disabled="true">확인하기</button></li>)}</ul></section>
      <section className="fcheck__box"><h3>신청하신 지원 항목과 지급 예정액</h3><table className="fcheck__docs"><thead><tr><th>항목</th><th>영수증 금액</th><th>지급 예정액</th><th>계산 근거</th></tr></thead><tbody>{[0, 1, 2].map((row) => <tr key={row}>{[0, 1, 2, 3].map((col) => <td data-label="항목" key={col}><SkeletonLine width={col === 3 ? '88%' : '64%'} /></td>)}</tr>)}</tbody></table></section>
      <section className="fcheck__box"><h3>작성하신 내용</h3><dl className="fcheck__summary">{[0, 1, 2, 3, 4, 5].map((row) => <div key={row}><dt><SkeletonLine width="76%" /></dt><dd><SkeletonLine width="88%" /></dd></div>)}</dl></section>
      <section className="fcheck__box"><h3>제출 서류 판독 결과</h3><table className="fcheck__docs"><thead><tr><th>파일</th><th>판독된 서류</th><th>발급일 입력값</th><th>판정</th><th>사유</th></tr></thead><tbody>{[0, 1, 2, 3].map((row) => <tr key={row}>{[0, 1, 2, 3, 4].map((col) => <td data-label="파일" key={col}><SkeletonLine width={col === 4 ? '84%' : '60%'} /></td>)}</tr>)}</tbody></table></section>
      <div className="flow__actions"><button type="button" className="btn" disabled aria-disabled="true">이전</button><button type="button" className="btn btn--primary" disabled aria-disabled="true">최종 제출</button></div>
    </Skeleton>
  ) : null

  return (
    <div className="fcheck">
      <h2>확인 및 제출</h2>
      {attempted && !data.can_submit && <Notice tone="warning" role="alert" title={`남은 항목 ${data.blockers.length}건을 확인해 주세요.`}><a href="#fcheck-todo">보완할 항목으로 이동하기</a></Notice>}
      {data.first_come && (
        <section className="fcheck__queue">
          <h3>이 사업은 선착순입니다</h3>
          <p>
            {data.first_come.notice} 지금 제출하시면{' '}
            <strong>{data.first_come.position}번째</strong>로 접수됩니다.
          </p>
        </section>
      )}

      {data.warnings.length > 0 && !data.already_submitted && (
        <div className="fcheck__warn">
          {data.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {!data.already_submitted && data.blockers.length > 0 && (
        <section className="fcheck__todo" aria-labelledby="fcheck-todo">
          <h3 id="fcheck-todo" tabIndex={-1}>
            제출 전에 채워야 할 항목 <span>{data.blockers.length}건</span>
          </h3>
          <ul>
            {BLOCKER_GROUPS.map((g) => {
              const items = data.blockers.filter((b) => applicantStage(b.goto) === g.goto)
              if (items.length === 0) return null
              return (
                <li key={g.goto}>
                  <span className="fcheck__todo-title">{g.title}</span>
                  <span className="fcheck__todo-items">
                    {items.map((b) => (
                      <span key={`${b.kind}-${b.target}`} title={b.message}>
                        {b.kind === 'eligibility' ? `${b.label}: ${b.message}` : b.label}
                      </span>
                    ))}
                  </span>
                  <button type="button" className="btn btn--small" onClick={() => onGoto(g.goto)}>
                    {g.action}
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {data.subsidy && data.subsidy.lines.length > 0 && (
        <section className="fcheck__box">
          <h3>신청하신 지원 항목과 지급 예정액</h3>
          <table className="fcheck__docs">
            <thead>
              <tr>
                <th>항목</th>
                <th>영수증 금액</th>
                <th>지급 예정액</th>
                <th>계산 근거</th>
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
                  <td data-label="계산 근거">{line.calculation}</td>
                </tr>
              ))}
              <tr>
                <th colSpan={2}>합계</th>
                <td data-label="지급 예정액" colSpan={2}>
                  <strong>
                    {data.subsidy.total_granted.toLocaleString('ko-KR')}원
                  </strong>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      <section className="fcheck__box">
        <h3>작성하신 내용</h3>
        <dl className="fcheck__summary">
          {data.form_summary.map((f) => (
            <div key={f.label}>
              <dt>{f.label}</dt>
              <dd className={f.value ? undefined : 'is-empty'}>{f.value || '미입력'}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="fcheck__box">
        <h3>제출 서류 판독 결과</h3>
        {data.documents.length === 0 ? (
          <p className="fcheck__empty">아직 올린 서류가 없습니다.</p>
        ) : (
          <table className="fcheck__docs">
            <thead>
              <tr>
                <th>파일</th>
                <th>판독된 서류</th>
                <th>발급일 입력값</th>
                <th>판정</th>
                <th>사유</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((d) => {
                const status = d.status ?? 'NEEDS_REVIEW'
                return (
                  <tr key={d.document_id}>
                    <td data-label="파일">
                      <FileLink url={d.file_url} name={d.file_name} format={d.file_format} />
                    </td>
                    <td data-label="판독된 서류">{d.detected_doc_type ?? '미판별'}</td>
                    <td data-label="발급일 입력값">{d.declared_issue_date ? formatDate(d.declared_issue_date) : '-'}</td>
                    <td data-label="판정">
                      <StatusBadge status={status} audience="applicant" />
                    </td>
                    <td data-label="사유" className={d.findings.length ? 'fcheck__reason' : 'fcheck__none'}>
                      {d.findings.map((f) => f.message).join(' / ') || '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>

      {error && <p className="fcheck__error" role="alert">{error}</p>}

      <div className="flow__actions">
        <button type="button" className="btn" onClick={onBack}>
          이전
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={data.already_submitted || busy}
          onClick={() => {
            setAttempted(true)
            if (!data.can_submit) { document.getElementById('fcheck-todo')?.focus(); return }
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
