/**
 * 반려 처리 페이지 — 심사 화면에서 반려를 누르면 여기로 온다.
 *
 * 위에서 아래로: 반려 사유 고르기(이 건의 확인 필요 항목) → 신청자에게 보낼 안내(고른 사유가
 * 한 줄씩 들어가고 고칠 수 있다) → 내부 메모 → 반려 확정. 안내는 신청자 마이페이지에
 * 그대로 나가고, 내부 메모는 나가지 않는다.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { fetchApplicationReasons } from '../../api.ts'
import { NOTICE_MAX, NOTICE_INTRO, reasonLines, toggleReason } from './reject-notice.ts'
import { OfficerConfirm } from './OfficerModern.tsx'
import { useOfficerDraftGuard } from './useReviewDraft.ts'
import { reviewSaveError } from './review-save.ts'
import { matchesReviewSave, type ReviewSnapshot } from './review-draft.ts'
import './reject-application.css'

export interface RejectSummary { name: string; application_no: string; program_name?: string }

interface Props {
  applicationId: number
  role: string
  /** 머리에 보일 신청자·신청번호. 부모가 이미 읽은 값이 없으면 `load`로 읽는다. */
  load: () => Promise<RejectSummary>
  /** 사업 기준처럼 서류 밖에서 온 확인 필요 사유. */
  extraReasons?: () => Promise<string[]>
  onCancel: () => void
  onSubmit: (notice: string, memo: string, expectedRevision: number) => Promise<void>
  verify: () => Promise<ReviewSnapshot>
  onSaved: () => void
}

export default function RejectApplication({ applicationId, role, load, extraReasons, onCancel, onSubmit, verify, onSaved }: Props) {
  const [summary, setSummary] = useState<RejectSummary | null>(null)
  const [reasons, setReasons] = useState<string[] | null>(null)
  const [picked, setPicked] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const [memo, setMemo] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const baseline = useRef<ReviewSnapshot | null>(null)
  const lock = useRef(false)
  const live = useRef(true)
  const [needsCheck, setNeedsCheck] = useState(false)
  const [latest, setLatest] = useState<ReviewSnapshot | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  useOfficerDraftGuard(!confirmed && (!!notice || !!memo || busy || needsCheck))
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])
  const heading = useRef<HTMLHeadingElement>(null)
  const uid = useId()
  useEffect(() => {
    let current = true
    Promise.all([load(), fetchApplicationReasons(applicationId, role), extraReasons ? extraReasons() : Promise.resolve([]), verify()])
      .then(([info, data, extra, snapshot]) => { if (current) { if (!baseline.current) baseline.current = snapshot; setSummary(info); setReasons(reasonLines(data, extra)); setError('') } })
      .catch((problem: unknown) => { if (current) setError(problem instanceof Error ? problem.message : '반려할 신청 정보를 불러오지 못했습니다.') })
    return () => { current = false }
  }, [applicationId, role, load, extraReasons, verify, attempt])
  useEffect(() => { if (summary) heading.current?.focus() }, [summary])
  const pick = (reason: string, on: boolean) => {
    setPicked((prior) => on ? [...prior, reason] : prior.filter((value) => value !== reason))
    setNotice((prior) => toggleReason(prior, reason, on))
  }
  const ready = !!notice.trim() && notice.length <= NOTICE_MAX && !busy && !needsCheck
  const submit = async () => {
    if (lock.current || !ready) return
    lock.current = true
    setBusy(true); setError('')
    const sentMemo = memo.trim() || notice.trim()
    try {
      const before = await verify()
      if (!live.current) return
      if (baseline.current && JSON.stringify([before.revision, before.decision]) !== JSON.stringify([baseline.current.revision, baseline.current.decision])) {
        setLatest(before); setNeedsCheck(true); setError('저장 전 서버의 심사 결과가 달라졌습니다. 입력은 유지됩니다. 서버 상태를 확인해 주세요.'); return
      }
      if (!baseline.current?.revision) throw new Error('심사 버전 없음')
      const expectedRevision = baseline.current.revision
      await onSubmit(notice.trim(), sentMemo, expectedRevision)
      const saved = await verify()
      if (!live.current) return
      if (!matchesReviewSave(saved, { decision: 'reject', memo: sentMemo, expectedRevision })) throw new Error('저장 결과 불일치')
      setConfirmed(true)
      onSaved()
    } catch (problem: unknown) {
      if (live.current) {
        setNeedsCheck(true); setError(reviewSaveError(problem))
        try { const current = await verify(); if (live.current) setLatest(current) } catch { /* Keep input and gate closed. */ }
      }
    } finally { lock.current = false; if (live.current) setBusy(false) }
  }
  const check = async () => {
    if (lock.current) return
    lock.current = true; setBusy(true)
    try {
      const latest = await verify()
      if (!live.current) return
      if (latest.decision.decision === 'reject') {
        setError('서버에 반려 결과가 있습니다. 입력은 유지됩니다. 공개 반려 안내는 이 조회에서 확인할 수 없으므로 자동 재전송하지 않습니다. 심사 화면에서 결과를 확인해 주세요.')
      } else { setError('서버의 현재 심사 상태를 확인했습니다. 최신 메모와 작성 중인 입력을 비교한 뒤 재검토를 확인해 주세요.') }
      setLatest(latest)
    } catch (problem) { if (live.current) setError(reviewSaveError(problem)) }
    finally { lock.current = false; if (live.current) setBusy(false) }
  }

  return <main className="om om-page reject-page">
    <button type="button" className="om-text reject-page__back" disabled={busy} onClick={onCancel}>← 심사 화면으로</button>
    {!summary ? <p className={error ? 'om-notice' : undefined} role={error ? 'alert' : 'status'}>{error || '반려할 신청 정보를 불러오는 중입니다.'}
      {error && <> <button type="button" className="om-text" onClick={() => { setError(''); setAttempt((value) => value + 1) }}>다시 시도</button></>}</p> : <>
      <header className="reject-page__head">
        {summary.program_name && <p className="om-subtle">{summary.program_name}</p>}
        <h1 ref={heading} tabIndex={-1}>반려 처리</h1>
        <p>{summary.name} · {summary.application_no}</p>
      </header>
      <section className="om-card reject-page__section" aria-labelledby={`${uid}-reasons`}>
        <h2 id={`${uid}-reasons`}>① 반려 사유 고르기</h2>
        <p className="om-subtle">이 신청의 확인 필요 항목입니다. 고른 사유가 신청자 안내에 한 줄씩 들어갑니다.</p>
        {reasons && reasons.length ? <ul className="reject-page__reasons">{reasons.map((reason) => <li key={reason}>
          <label><input type="checkbox" checked={picked.includes(reason)} disabled={busy} onChange={(event) => pick(reason, event.target.checked)} />{reason}</label>
        </li>)}</ul> : <p className="reject-page__empty">기록된 확인 필요 항목이 없습니다. 아래에 반려 사유를 직접 써 주세요.</p>}
      </section>
      <section className="om-card reject-page__section" aria-labelledby={`${uid}-notice`}>
        <h2 id={`${uid}-notice`}>② 신청자에게 보낼 반려 안내</h2>
        <label htmlFor={`${uid}-notice-input`} className="om-subtle">신청자 마이페이지에 그대로 보입니다. 내용을 고칠 수 있습니다.</label>
        <textarea id={`${uid}-notice-input`} className="reject-page__notice" rows={7} maxLength={NOTICE_MAX} value={notice} disabled={busy}
          placeholder={`${NOTICE_INTRO}\n- 반려 사유를 적어 주세요.`} onChange={(event) => setNotice(event.target.value)} aria-required="true" />
        <p className="om-subtle reject-page__count">{notice.length.toLocaleString('ko-KR')} / {NOTICE_MAX.toLocaleString('ko-KR')}자</p>
      </section>
      <section className="om-card reject-page__section" aria-labelledby={`${uid}-memo`}>
        <h2 id={`${uid}-memo`}>③ 내부 메모 <span className="om-subtle">(선택 · 신청자에게 보이지 않음)</span></h2>
        <textarea aria-labelledby={`${uid}-memo`} rows={3} maxLength={2000} value={memo} disabled={busy} onChange={(event) => setMemo(event.target.value)} />
      </section>
      {error && <p className="om-notice" role="alert">{error}</p>}
      {needsCheck && latest && <section aria-label="최신 심사 상태">
        <h2>서버에 저장된 심사 결과와 메모 · 버전 {latest.revision}</h2>
        <p>{latest.decision.label ?? latest.decision.decision ?? '미처리'}</p>
        <blockquote style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{latest.decision.memo || '저장된 메모 없음'}</blockquote>
        <p>작성 중인 내부 메모와 반려 안내는 입력란에 유지됩니다. 최신 상태와 비교해 주세요.</p>
        <button type="button" className="btn" disabled={busy || latest.decision.decision === 'reject'} onClick={() => { baseline.current = latest; setLatest(null); setNeedsCheck(false); setError('최신 상태를 재검토했습니다. 입력을 확인한 뒤 반려를 명시적으로 다시 요청할 수 있습니다.') }}>최신 심사 상태를 확인했습니다 · 입력 유지</button>
      </section>}
      {needsCheck && <button type="button" className="btn" disabled={busy} onClick={() => void check()}>서버 상태 확인</button>}
      <div className="reject-page__actions">
        <button type="button" className="btn" disabled={busy} onClick={onCancel}>취소</button>
        <button type="button" className="btn btn--primary" disabled={!ready} onClick={() => setConfirming(true)}>{busy ? '처리 중…' : '반려 확정'}</button>
      </div>
    </>}
    {confirming && <OfficerConfirm title="반려 확정" confirmLabel="반려" busy={busy} onClose={() => setConfirming(false)} onConfirm={() => { setConfirming(false); void submit() }}>
      {summary?.name}님의 신청을 반려할까요? 아래 안내가 신청자 마이페이지에 표시됩니다.
      <blockquote className="reject-page__preview">{notice.trim()}</blockquote>
    </OfficerConfirm>}
  </main>
}
