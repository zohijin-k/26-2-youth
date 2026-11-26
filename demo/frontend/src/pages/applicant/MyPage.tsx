/**
 * 마이페이지 (계획서 3.1절 [7]).
 *
 *   · 진행 상태 5단계: 접수 → 서류검토 → 자격심사 → 선정심사 → 결과발표
 *   · 제출 서류 판독 결과 재확인
 *   · 동의 이력 (수기 서명 없이도 '누가 언제 무엇에 동의했는지'가 남는다)
 *
 * ⚠️ **심사 점수를 표시하지 않는다** (R5.3 / 공고문 "평가결과는 공개하지 않음").
 *    서버 응답(`/status`)에 애초에 점수가 없고, 이 화면도 점수를 계산하지 않는다.
 *    점수 표시를 추가해 달라는 요청이 오면 공고문 문구를 먼저 확인할 것.
 */

import { useEffect, useState } from 'react'

import { fetchStatus, type ApplicationStatus } from '../../api.ts'
import FileLink from '../../components/ApplicantFileLink.tsx'
import { Skeleton, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import Icon from '../../components/Icon.tsx'
import Notice from '../../components/Notice.tsx'
import { friendlyError } from '../../lib/error-copy.ts'
import { formatDateTime } from '../../lib/format.ts'
import './my-page.css'

export default function MyPage({ applicationId }: { applicationId: number }) {
  const [data, setData] = useState<ApplicationStatus | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const showSkeleton = useDelayedFlag(!data && !error)

  useEffect(() => {
    fetchStatus(applicationId)
      .then(setData)
      .catch((e: unknown) => setError(friendlyError(e, '신청 현황을 불러오지 못했습니다. 다시 시도해 주세요.')))
  }, [applicationId, attempt])

  if (error) return <Notice tone="danger" role="alert">{error}<button type="button" className="btn" onClick={() => { setError(''); setAttempt((value) => value + 1) }}>다시 시도하기</button></Notice>
  if (!data) return showSkeleton ? (
    <Skeleton className="mypage mypage__skeleton">
      <section className="mypage__head">
        <div><SkeletonLine width="240px" /><p>신청번호 <SkeletonLine width="110px" /> · 접수 <SkeletonLine width="140px" /></p></div>
        <p className="mypage__call">문의 <SkeletonLine width="100px" /></p>
      </section>
      <ol className="mypage__progress">
        {['접수', '서류검토', '자격심사', '선정심사', '결과발표'].map((label, index) => <li className="mpstep" key={label}><span className="mpstep__no">{index + 1}</span><span className="mpstep__label">{label}</span></li>)}
      </ol>
      <p className="mypage__notice"><SkeletonLine width="74%" /></p>
      <section className="mypage__box"><h3>신청한 지원 항목</h3><table className="mypage__docs"><thead><tr><th>항목</th><th>영수증 금액</th><th>지급 예정액</th></tr></thead><tbody>{[0, 1].map((row) => <tr key={row}>{[0, 1, 2].map((col) => <td data-label="항목" key={col}><SkeletonLine width="64%" /></td>)}</tr>)}</tbody></table></section>
      <section className="mypage__box"><h3>제출한 서류</h3><ul className="mypage__files">{[0, 1, 2].map((row) => <li key={row}><SkeletonLine width="48%" /></li>)}</ul></section>
      <section className="mypage__box"><h3>동의 이력</h3><table className="mypage__docs mypage__consents"><thead><tr><th>항목</th><th>동의 여부</th><th>일시</th></tr></thead><tbody>{[0, 1, 2].map((row) => <tr key={row}><td data-label="항목"><SkeletonLine width="70%" /></td><td data-label="동의 여부"><SkeletonLine width="60%" /></td><td data-label="일시"><SkeletonLine width="80%" /></td></tr>)}</tbody></table></section>
    </Skeleton>
  ) : null

  return (
    <div className="mypage">
      <section className="mypage__head">
        <div>
          <h2>{data.program_name}</h2>
          <p>
            신청번호 <strong>{data.application_no}</strong>
            {data.submitted_at && ` · 접수 ${formatDateTime(data.submitted_at)}`}
          </p>
        </div>
        {data.call_center && <p className="mypage__call">문의 <a href={`tel:${data.call_center.replace(/[^+0-9]/g, '')}`}>{data.call_center}</a></p>}
      </section>

      <ol className="mypage__progress">
        {data.progress.map((p, i) => (
          <li key={p.label} className={`mpstep mpstep--${p.state}`} aria-current={p.state === 'current' ? 'step' : undefined}>
            <span className="mpstep__no" aria-hidden="true">{p.state === 'done' ? <Icon name="check" size={16} /> : p.state === 'current' ? null : i + 1}</span>
            <span className="mpstep__label">{p.label}</span>{p.state !== 'todo' && <span className="mpstep__state">{p.state === 'current' ? '진행 중' : '완료'}</span>}
          </li>
        ))}
      </ol>

      {/* 반려는 다른 안내보다 먼저, 담당자가 쓴 사유 그대로 보인다. */}
      {data.rejection && (
        <Notice tone="danger" title="신청이 반려되었습니다" className="mypage__rejection" role="status">
          <p className="mypage__rejection-text">{data.rejection.notice || '담당자 확인 결과 반려되었습니다. 자세한 내용은 문의처로 연락해 주세요.'}</p>
          {data.rejection.decided_at && <p className="mypage__rejection-date">처리일 {formatDateTime(data.rejection.decided_at)}</p>}
        </Notice>
      )}

      {/* 심사 안내는 접지 않고 바로 보인다. 접수 순번은 혼란을 주므로 보이지 않는다(서버 안내 문구에도 순번이 있어 쓰지 않는다). */}
      {(data.result_notice || data.first_come?.quota != null) && (
        <Notice tone="info" title="심사 안내" className="mypage__guide">
          <ul>
            {data.result_notice && <li>{data.result_notice}</li>}
            {data.first_come?.quota != null && <li>총 지원규모 {data.first_come.quota.toLocaleString('ko-KR')}건</li>}
          </ul>
        </Notice>
      )}

      {/* 7일 보완 기한 카운트다운 (E12). 미보완 시 후순위자에게 자리가 넘어간다. */}
      {data.supplement && (
        <section
          className={
            data.supplement.expired
              ? 'mypage__supplement mypage__supplement--over'
              : 'mypage__supplement'
          }
        >
          <div className="mypage__countdown">
            <span className="mypage__days">
              {data.supplement.expired ? '기한 종료' : `D-${data.supplement.days_left}`}
            </span>
            <span>
              보완 기한 {formatDateTime(data.supplement.deadline)}
              {!data.supplement.expired && ` (약 ${data.supplement.hours_left}시간 남음)`}
            </span>
          </div>
          <p>{data.supplement.notice}</p>
          <p>보완할 서류는 따로 안내해 드립니다.</p>
        </section>
      )}

      {/* 항목별 지급 예정액. 점수와 달리 이 값은 신청자에게 보여 주는 것이 맞다. */}
      {data.subsidy && data.subsidy.lines.length > 0 && (
        <section className="mypage__box">
          <h3>신청한 지원 항목<span className="mypage__count">지급 예정 {data.subsidy.total_granted.toLocaleString('ko-KR')}원</span></h3>
          <table className="mypage__docs">
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
                  <strong>{data.subsidy.total_granted.toLocaleString('ko-KR')}원</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      <section className="mypage__box">
        <h3>제출한 서류<span className="mypage__count">{data.documents.length}건</span></h3>
        {/* 신청자에게는 낸 파일만 보여 준다. 자동 판독 결과(서류 종류·읽은 값·판정)는 보이지 않는다. 미비 서류는 담당자 확인 뒤 따로 안내한다. */}
        {data.documents.length === 0 ? <p className="mypage__empty">아직 제출한 서류가 없습니다.</p> : (
          <ul className="mypage__files">
            {data.documents.map((d) => (
              <li key={d.document_id}><FileLink url={d.file_url} name={d.file_name} format={d.file_format} /></li>
            ))}
          </ul>
        )}
      </section>

      <section className="mypage__box">
        <h3>동의 이력<span className="mypage__count">{data.consents.length}건</span></h3>
        {/* 다른 목록과 같은 표: 칸 위치가 글자 길이와 상관없이 줄마다 같고, 폰에서는 줄마다 이름표가 붙은 카드가 된다. */}
        {data.consents.length === 0 ? <p className="mypage__empty">아직 동의한 항목이 없습니다.</p> : (
          <table className="mypage__docs mypage__consents">
            <thead>
              <tr>
                <th>항목</th>
                <th>동의 여부</th>
                <th>일시</th>
              </tr>
            </thead>
            <tbody>
              {data.consents.map((c) => (
                <tr key={c.consent_type}>
                  <td data-label="항목">{c.label}</td>
                  <td data-label="동의 여부" className={c.agreed ? 'mypage__agreed' : 'mypage__declined'}>{c.agreed ? '동의함' : '동의하지 않음'}</td>
                  <td data-label="일시" className="mypage__time">
                    {formatDateTime(c.agreed_at)}
                    {c.signature_kind === 'electronic' && ' · 전자서명'}
                    {c.signature_kind === 'handwritten' && ' · 자필서명 스캔'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
