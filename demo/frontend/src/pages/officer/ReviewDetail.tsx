/**
 * 분할 심사 뷰 — 좌 55% 원본 / 우 45% AI 판독 결과 (R4.2).
 *
 * 이 화면의 차별점은 **판정 근거와 원본 위치가 이어져 있다**는 것이다. 심사표
 * 항목이나 판독 필드를 클릭하면 좌측 뷰어가 해당 서류의 해당 좌표로 스크롤하고
 * 그 자리를 하이라이트한다 (R4.3). "소득분위 초과"라고만 쓰면 담당자는 결국 원본
 * 파일을 찾아 헤맨다.
 *
 * 화면 어디에도 파일을 내려받는 버튼이 없다 (R4.1).
 */

import { useMemo, useState, type ReactNode } from 'react'

import {
  fetchReviewDetail,
  postDecision,
  type BBox,
  type DecisionKey,
  type FormExport,
  type OfficerDocument,
  type ReviewDetailData,
} from '../../api.ts'
import StatusBadge from '../../components/StatusBadge.tsx'
import { Skeleton, SkeletonBlock, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import DocumentViewer from './DocumentViewer.tsx'
import { dotClass } from './format.ts'
import { useReviewDraft } from './useReviewDraft.ts'
import ReviewSaveStatus from './ReviewSaveStatus.tsx'
import { reviewSaveError } from './review-save.ts'
import { fieldDisplay, primaryReason, reasonDisplay, type ReasonLike } from './reason-labels.ts'

interface Props {
  applicationId: number
  role: string
  onBack: () => void
  /** 반려는 여기서 바로 처리하지 않고 반려 페이지로 넘긴다. */
  onReject: () => void
  /** 판단이 기록되면 목록을 다시 읽어야 한다. */
  onDecided: () => void
  /**
   * 열자마자 띄울 서류의 슬롯 키. 목록의 서류 칸을 눌러 들어온 경우에 온다.
   *
   * 없거나 그 슬롯의 서류가 없으면 지금까지처럼 첫 서류를 연다 — 행을 눌러
   * 들어온 경로와 같다.
   */
  initialSlotKey?: string | null
}

/**
 * 작성 서식을 업로드 서류와 같은 모양으로 감싼다 (P7 / R9.3).
 *
 * 뷰어는 `file_url`만 있으면 되므로 판독 결과 자리는 비운다. 서식은 신청자가 화면에
 * 입력한 값이라 판독할 것이 없다. 음수 id를 쓰는 이유는 업로드 서류 id와 섞이지
 * 않게 하기 위해서다 — 탭을 옮길 때 뷰어가 쪽수를 되돌리는 기준이 id다.
 */
function asViewerDoc(form: FormExport, index: number): OfficerDocument {
  return {
    document_id: -(index + 1),
    slot_key: `form:${form.form_no}`,
    label: form.label,
    expected_doc_type: null,
    detected_doc_type: null,
    status: null,
    findings: [],
    file_url: form.file_url,
    file_name: form.file_name,
    file_format: 'pdf',
    page_index: null,
    extracted: {},
    bboxes: {},
    ocr_confidence: null,
    ocr_tier: null,
    ocr_engine: null,
    ocr_fallback_reason: null,
    ocr_quality_note: null,
    declared_issue_date: null,
    uploaded_at: '',
  }
}

interface Focus {
  documentId: number
  bbox: BBox | null
  label: string
}

/**
 * 열자마자 띄울 서류.
 *
 * 목록에서 "초본" 칸을 눌러 들어왔으면 초본이 떠야 한다. 그 슬롯이 없으면
 * (안 낸 서류를 어떻게든 눌렀거나 목록과 상세가 어긋난 경우) 첫 서류로 떨어진다.
 */
function pickInitialDoc(
  detail: ReviewDetailData,
  slotKey: string | null | undefined,
): number | null {
  const wanted = slotKey ? detail.documents.find((d) => d.slot_key === slotKey) : undefined
  return (wanted ?? detail.documents[0])?.document_id ?? null
}

export default function ReviewDetail(props: Props) {
  // A draft and every pending response belong to exactly one application and role.
  return <ReviewDetailContent key={`${props.applicationId}:${props.role}`} {...props} />
}

function ReviewDetailContent({
  applicationId,
  role,
  onBack,
  onDecided,
  onReject,
  initialSlotKey,
}: Props) {
  const draft = useReviewDraft({
    load: () => fetchReviewDetail(applicationId, role),
    write: (decision, memo, expectedRevision) => postDecision(applicationId, { role, decision: decision as DecisionKey, memo, expected_revision: expectedRevision }),
    errorText: reviewSaveError, onSaved: onDecided,
  })
  const { data: detail, memo, busy: saving, loadError: error, editor } = draft
  const [activeDocId, setActiveDocId] = useState<number | null>(null)
  /** 작성 서식 탭이 켜져 있으면 서식 번호. 업로드 서류 탭을 누르면 꺼진다. */
  const [activeForm, setActiveForm] = useState<string | null>(null)
  const [focus, setFocus] = useState<Focus | null>(null)
  const showSkeleton = useDelayedFlag(!detail && !error)

  const activeDoc: OfficerDocument | null = useMemo(() => {
    if (!detail) return null
    return (
      detail.documents.find((d) => d.document_id === (activeDocId ?? pickInitialDoc(detail, initialSlotKey))) ?? null
    )
  }, [detail, activeDocId, initialSlotKey])

  if (error) return <div><button type="button" className="review__back" onClick={onBack}>← 접수 목록</button><p className="officer__error" role="alert">{error} <button type="button" className="btn" onClick={() => void editor.check()}>다시 시도</button></p></div>
  if (!detail) return showSkeleton ? (
    <Skeleton className="review__skeleton">
      <div className="review__head review__skeleton-header">
        <button type="button" className="review__back" disabled aria-disabled="true">← 접수 목록</button>
        <span>접수번호 <SkeletonLine width="94px" /></span><span>신청자 <SkeletonLine width="118px" /></span><span>지역 <SkeletonLine width="88px" /></span><span>접수 <SkeletonLine width="124px" /></span>
      </div>
      <div className="review__skeleton-split">
        <div className="review__left review__skeleton-left"><nav className="review__tabs review__skeleton-tabs">{Array.from({ length: 5 }, (_, i) => <button key={i} type="button" className="review__tab" disabled aria-disabled="true"><SkeletonLine width="68%" /></button>)}</nav><SkeletonBlock className="review__skeleton-page" /></div>
        <div className="review__right review__skeleton-right">{['최종 판정', '지원 항목별 지급 내역', '자격요건 체크리스트', '제외대상 조회 결과', '판독 결과'].map((title, index) => <section className="panel" key={title}><h3 className="panel__title">{title}</h3><div className="panel__body review__skeleton-panel">{Array.from({ length: index === 1 ? 6 : index === 4 ? 5 : 3 }, (_, i) => <SkeletonLine key={i} width={i % 3 ? '82%' : '96%'} />)}</div></section>)}</div>
      </div>
    </Skeleton>
  ) : null

  const formIndex = detail.forms.findIndex((f) => f.form_no === activeForm)
  const viewingForm = formIndex >= 0 ? detail.forms[formIndex] : null
  const viewing = viewingForm ? asViewerDoc(viewingForm, formIndex) : activeDoc

  /** 판독 필드 → 좌측 원본의 해당 위치. */
  const focusField = (doc: OfficerDocument, field: string) => {
    const bbox = doc.bboxes[field]
    if (!bbox) return
    setActiveDocId(doc.document_id)
    setFocus({ documentId: doc.document_id, bbox, label: field })
  }


  /** 사유 → 그 서류 원본. */
  const openDoc = (documentId: number | null) => {
    if (documentId == null) return
    setActiveForm(null)
    setActiveDocId(documentId)
  }
  const primary = primaryReason(detail.ai.reasons)

  const highlight =
    !viewingForm && focus && focus.documentId === activeDoc?.document_id ? focus.bbox : null

  return (
    <div className="review">
      <header className="review__head">
        <button type="button" className="review__back" onClick={onBack}>
          ← 접수 목록
        </button>
        <span className="review__no">{detail.application_no}</span>
        {detail.criteria_version != null && <span className="review__criteria">적용 기준 v{detail.criteria_version}</span>}
        <strong className="review__name">{detail.name}</strong>
        {detail.identity && (
          <span
            className={
              detail.identity.verified ? 'review__id review__id--ok' : 'review__id review__id--none'
            }
          >
            {detail.identity.verified
              ? `본인인증 완료${detail.identity.method === 'demo' ? '(데모)' : ''}${
                  detail.identity.pledge_signed
                    ? detail.identity.pledge_kind === 'uploaded'
                      ? ' · 서약 서명(파일)'
                      : ' · 서약 서명'
                    : ''
                }`
              : '본인인증 없음'}
          </span>
        )}
        <span className="review__where">
          {detail.region} {detail.town}
        </span>
        <span className="review__when">접수 {detail.submitted_at ?? '-'}</span>
                {detail.ai.final_status && <StatusBadge status={detail.ai.final_status} />}
        <span className="review__spacer" />
        <span className="review__role">{detail.role.name} 화면</span>
      </header>

      <div className="review__split">
        {/* ---------------- 좌 55% 원본 ---------------- */}
        <section className="review__left">
          <nav className="review__tabs">
            {detail.documents.map((d) => (
              <button
                key={d.document_id}
                type="button"
                className={
                  !viewingForm && d.document_id === activeDoc?.document_id
                    ? 'review__tab review__tab--on'
                    : 'review__tab'
                }
                onClick={() => {
                  setActiveForm(null)
                  setActiveDocId(d.document_id)
                }}
              >
                <span className={dotClass(d.status)} />
                {d.label}
              </button>
            ))}
            {/* 작성 서식 탭 (P7). 업로드 서류와 나란히 두어 "올린 것"과 "쓴 것"을
                같은 자리에서 본다. 여기도 내려받는 경로는 없다 (R9.3). */}
            {detail.forms.map((f) => (
              <button
                key={f.form_no}
                type="button"
                className={
                  activeForm === f.form_no
                    ? 'review__tab review__tab--form review__tab--on'
                    : 'review__tab review__tab--form'
                }
                onClick={() => setActiveForm(f.form_no)}
              >
                <span className="review__tab-pen">✎</span>
                {f.public_form ?? f.title} 작성본
              </button>
            ))}
          </nav>
          {viewing ? <DocumentViewer
            doc={viewing}
            highlight={highlight}
            highlightLabel={focus?.label}
          /> : <p className="muted">확인할 원본 서류가 없습니다.</p>}
        </section>

        {/* ---------------- 우 45% 판독 결과 ---------------- */}
        <section className="review__right">
          <Panel title="최종 판정">
            <div className="verdict">
              {detail.ai.final_status && <StatusBadge status={detail.ai.final_status} />}
              <span className="verdict__action">{detail.ai.recommended_action}</span>
            </div>
            <ul className="verdict__stages">
              <li>1단계 서류 적합성: {detail.ai.stage1_status ?? '-'}</li>
              <li>2단계 통합 자격심사: {detail.ai.stage2_status ?? '-'}</li>
            </ul>
            {primary && (
              <div className="reasons__primary" role="note">
                <span className="reasons__primary-tag">우선 확인</span>
                <ReasonText reason={primary} docType={primary.doc_type}
                  onOpen={primary.document_id != null ? () => openDoc(primary.document_id ?? null) : undefined} />
              </div>
            )}
            {detail.ai.reasons.length > 0 ? (
              <ul className="reasons">
                {detail.ai.reasons.map((r, i) => (
                  <li key={i}>
                    <ReasonText reason={r} docType={r.doc_type}
                      onOpen={r.document_id != null ? () => openDoc(r.document_id ?? null) : undefined} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">부적합·확인필요 사유가 없습니다.</p>
            )}
          </Panel>

          {detail.supplement && (
            <Panel title={`서류 보완 기한 (${detail.supplement.days}일)`}>
              <div
                className={
                  detail.supplement.expired ? 'supplement supplement--over' : 'supplement'
                }
              >
                <span className="supplement__days">
                  {detail.supplement.expired
                    ? '기한 종료'
                    : `D-${detail.supplement.days_left}`}
                </span>
                <span className="supplement__deadline">
                  {detail.supplement.deadline.replace('T', ' ')}까지
                </span>
              </div>
              <p className="muted">{detail.supplement.notice}</p>
            </Panel>
          )}

          {detail.subsidy && detail.subsidy.lines.length > 0 && (
            <Panel title="지원 항목별 지급 내역">
              <table className="subsidy-view">
                <thead>
                  <tr>
                    <th>항목</th>
                    <th>영수증</th>
                    <th>지급액</th>
                    <th>근거</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.subsidy.lines.map((line) => (
                    <tr key={`${line.item_type}-${line.index}`}>
                      <td>{line.label}{line.linked_interview_index && <small className="subsidy__link-note">면접 {line.linked_interview_index}회차와 연결</small>}</td>
                      <td>
                        {line.actual_cost
                          ? line.receipt_amount === null
                            ? '미입력'
                            : `${line.receipt_amount.toLocaleString('ko-KR')}원`
                          : '불요'}
                      </td>
                      <td>
                        <strong>{line.granted_amount.toLocaleString('ko-KR')}원</strong>
                      </td>
                      <td className="muted">{line.calculation}</td>
                    </tr>
                  ))}
                  <tr>
                    <th colSpan={2}>합계</th>
                    <td colSpan={2}>
                      <strong>
                        {detail.subsidy.total_granted.toLocaleString('ko-KR')}원
                      </strong>
                    </td>
                  </tr>
                </tbody>
              </table>
            </Panel>
          )}

          <Panel title="자격요건 체크리스트">
            <ul className="checks">
              {detail.eligibility.map((e) => (
                <li key={e.key} className={e.ok ? 'checks__ok' : 'checks__no'}>
                  <span className="checks__mark">{e.ok ? '✓' : '✕'}</span>
                  <span>
                    <strong>{e.label}</strong>
                    <em>{e.basis}</em>
                  </span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="제외대상 조회 결과">
            <ul className="checks">
              {detail.exclusions.map((x, i) => (
                <li key={i} className={x.ok ? 'checks__ok' : 'checks__no'}>
                  <span className="checks__mark">{x.ok ? '✓' : '✕'}</span>
                  <span>
                    <strong>
                      {x.label} — {x.answer}
                    </strong>
                    <em>{x.source}</em>
                  </span>
                </li>
              ))}
            </ul>
          </Panel>

          {viewingForm && (
            <Panel title={`작성 서식 — ${viewingForm.label}`}>
              <p className="muted">
                신청자가 온라인으로 작성한 값을 원본 서식 PDF에 그대로 얹은 것입니다.
                항목 순서·표 구조·문구가 종이 서식과 같습니다.
              </p>

            </Panel>
          )}

          {activeDoc?.ocr_tier === 'manual_receipt' && <Panel title={`담당자 확인 대상 — ${activeDoc.label}`}>
            <p>결제영수증은 담당자가 원본과 신청 금액을 직접 확인합니다. 검토한 내용과 판단 근거는 아래 담당자 처리의 메모에 기록해 주세요.</p>
          </Panel>}
          {activeDoc && activeDoc.ocr_tier !== 'manual_receipt' && <Panel title={`판독 결과 — ${activeDoc.label}`}>
            <dl className="ocr">
              <dt>판별된 서류</dt>
              <dd>
                {activeDoc.detected_doc_type ?? '판별 실패'}
                {activeDoc.expected_doc_type &&
                  activeDoc.expected_doc_type !== activeDoc.detected_doc_type && (
                    <em> (요구: {activeDoc.expected_doc_type})</em>
                  )}
              </dd>
              <dt>판독 신뢰도</dt>
              <dd>
                {activeDoc.ocr_confidence === null
                  ? '-'
                  : `${Math.round(activeDoc.ocr_confidence * 100)}%`}{' '}
                <em>({activeDoc.ocr_tier})</em>
              </dd>
              {activeDoc.ocr_engine && (
                <>
                  <dt>판독 엔진</dt>
                  <dd>
                    {activeDoc.ocr_engine}
                    {activeDoc.ocr_quality_note && (
                      <em> · {activeDoc.ocr_quality_note}</em>
                    )}
                    {activeDoc.ocr_fallback_reason && (
                      <em> (대체 사유: {activeDoc.ocr_fallback_reason})</em>
                    )}
                  </dd>
                </>
              )}
              <dt>입력한 발급일</dt>
              <dd>{activeDoc.declared_issue_date ?? '-'}</dd>
            </dl>
            <ul className="fields">
              {Object.entries(activeDoc.extracted).map(([key, value]) => {
                const shown = fieldDisplay(key, value)
                return (
                <li key={key}>
                  <span className="fields__key">{shown.label}</span>
                  <span className="fields__value">
                    {shown.items.length > 1 ? <ul className="fields__items">{shown.items.map((item) => <li key={item}>{item}</li>)}</ul> : shown.items[0]}
                    {shown.diagnostic && <details className="reasons__audit"><summary>감사·진단 정보</summary><p>저장값: <code>{shown.diagnostic}</code></p></details>}
                  </span>
                  {activeDoc.bboxes[key] && (
                    <button
                      type="button"
                      className="fields__go"
                      onClick={() => focusField(activeDoc, key)}
                    >
                      원본 위치
                    </button>
                  )}
                </li>
              )})}
            </ul>
            {activeDoc.findings.length > 0 && (
              <ul className="reasons">
                {(activeDoc.finding_views ?? activeDoc.findings).map((f, i) => (
                  <li key={i}>
                    <ReasonText reason={f} />
                    {f.how_to_fix && <em> {f.how_to_fix}</em>}
                  </li>
                ))}
              </ul>
            )}
          </Panel>}

          <Panel title="담당자 처리">
            <p className="muted">
              {detail.role.name} · {detail.role.stage} — {detail.role.scope}
            </p>
            {detail.decision.decision && (
              <p className="decided">
                현재 처리 상태: <strong>{detail.decision.label}</strong>{' '}
                <em>{detail.decision.decided_at}</em>
              </p>
            )}
            <textarea
              className="memo"
              value={memo}
              rows={3}
              placeholder="담당자 메모 (판단 근거·확인 사항)"
              aria-label="담당자 메모"
              onChange={(e) => editor.edit(e.target.value)}
            />
            <ReviewSaveStatus editor={editor} state={draft} />
            {saving && <p role="status">처리 결과와 메모를 저장하고 있습니다.</p>}
            <div className="actions" aria-busy={saving}>
              {detail.role.actions.map((a) => (
                <button
                  key={a.key}
                  type="button"
                  className={`btn btn--${a.tone}`}
                  disabled={saving || draft.needsCheck}
                  onClick={() => (a.key === 'reject' ? onReject() : void editor.save(a.key))}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </Panel>
        </section>
      </div>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h3 className="panel__title">{title}</h3>
      <div className="panel__body">{children}</div>
    </section>
  )
}

/** 확인 사유 한 건: 분류 · 제목 · 설명. 내부 코드와 엔진 원문은 '감사·진단 정보'에 접어 둔다. */
function ReasonText({ reason, docType, onOpen }: { reason: ReasonLike; docType?: string | null; onOpen?: () => void }) {
  const view = reasonDisplay(reason)
  return (
    <>
      {view.category && <span className="reasons__category">{view.category}</span>}
      {view.title && <strong className="reasons__title">{view.title}</strong>}{view.title && ' '}
      {view.body}
      {docType && <em className="reasons__doc"> ({docType})</em>}
      {view.details.length > 0 && <ul className="reasons__details">{view.details.map((item) => <li key={item}>{item}</li>)}</ul>}
      {onOpen && <button type="button" className="reasons__open" onClick={onOpen}>원본 보기</button>}
      {view.diagnostics.length > 0 && (
        <details className="reasons__audit">
          <summary>감사·진단 정보</summary>
          {view.diagnostics.map((line) => <p key={line}>{line}</p>)}
        </details>
      )}
    </>
  )
}
