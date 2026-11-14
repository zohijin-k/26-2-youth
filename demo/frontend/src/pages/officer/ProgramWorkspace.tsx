/**
 * 사업 작업 공간 — `/officer/programs/:id...`.
 *
 * 기본 사업(규칙이 연결된 사업)은 기존 접수 목록·심사 화면을 그대로 올린다.
 * 그 밖의 사업은 요약 화면이다: 기간과 상태, 올린 PDF 두 개, 게시·마감·삭제.
 * PDF는 서버가 응답에 넣어 준 주소로만 연다.
 *
 * `target`이 'builtin'이면 리뉴얼 전 주소로 들어온 것이다. 목록에서 기본 사업을
 * 찾고, 콘솔을 올리기 **전에** 주소를 작업 공간 주소로 옮긴다 (콘솔은 마운트될 때
 * 주소를 읽는다).
 */
import { useEffect, useRef, useState } from 'react'

import {
  closePosting,
  deletePosting,
  fetchOfficerPosting,
  fetchOfficerPostings,
  isNotFound,
  publishPosting,
  type OfficerPosting,
} from '../../api.ts'
import FilePreview from '../../components/FilePreview.tsx'
import Modal from '../../components/Modal.tsx'
import { Skeleton, SkeletonBlock, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import { formatDayTime, formatPeriod } from '../../posting-format.ts'
import OfficerConsole from './OfficerConsole.tsx'
import ManagedProgramWorkspace from './ManagedProgramWorkspace.tsx'
import { fetchProgramWorkspace } from '../../program-workspace-api.ts'
import './officer.css'
import './program-workspace.css'

interface Props {
  target: number | 'builtin'
  /** 목록이나 새 사업 화면에서 이미 받은 값. 있으면 빈 화면 없이 바로 그린다. */
  initialPosting?: OfficerPosting
  onBuiltinFound: (postingId: number) => void
  onBack: () => void
  /** 사업이 없어졌을 때(삭제했거나 기본 사업이 없음). 목록으로 바꿔 끼운다. */
  onGone: () => void
}

type Action = 'publish' | 'close' | 'remove'

const ACTION_COPY: Record<Action, { title: string; body: string; confirm: string; tone: 'primary' | 'danger' }> = {
  publish: {
    title: '사업 게시',
    body: '이 사업을 게시합니다. 게시하면 신청자 화면의 사업 찾기에 바로 표시됩니다.',
    confirm: '게시하기',
    tone: 'primary',
  },
  close: {
    title: '사업 마감',
    body: '이 사업을 마감합니다. 신청자 화면에 마감으로 표시되고 새 신청을 받지 않습니다.',
    confirm: '마감하기',
    tone: 'danger',
  },
  remove: {
    title: '작성 중인 사업 삭제',
    body: '이 사업과 올린 PDF를 삭제합니다. 삭제하면 되돌릴 수 없습니다.',
    confirm: '삭제',
    tone: 'danger',
  },
}

/** 지금 신청자에게 어떻게 보이는지 한 문장. */
function stateSentence(posting: OfficerPosting): string {
  if (posting.status === 'draft') return '작성 중인 사업입니다. 게시하기 전에는 신청자에게 보이지 않습니다.'
  if (posting.status === 'closed') return '마감한 사업입니다. 신청자 화면에 마감으로 표시됩니다.'
  if (posting.phase === 'upcoming') return '게시된 사업입니다. 접수 시작일 전이라 신청자 화면에 접수 예정으로 표시됩니다.'
  if (posting.phase === 'closed') return '게시된 사업입니다. 접수 기간이 끝나 신청자 화면에 마감으로 표시됩니다.'
  return '게시된 사업입니다. 신청자 화면에 접수 중으로 표시됩니다.'
}

/** 방금 본 사업. 뒤로·앞으로 이동으로 화면이 다시 올라올 때 빈 화면을 건너뛴다. */
let lastPosting: OfficerPosting | null = null

export default function ProgramWorkspace({ target, initialPosting, onBuiltinFound, onBack, onGone }: Props) {
  const [posting, setPosting] = useState<OfficerPosting | null>(
    () => initialPosting ?? (typeof target === 'number' && lastPosting?.id === target ? lastPosting : null),
  )
  const [problem, setProblem] = useState<'' | 'missing' | 'failed'>('')
  const [attempt, setAttempt] = useState(0)
  const [viewing, setViewing] = useState<'notice' | 'forms' | null>(null)
  const [asking, setAsking] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [managed, setManaged] = useState(false)
  useEffect(() => {
    if (!posting || posting.builtin) return
    let active = true
    fetchProgramWorkspace(posting.id).then((workspace) => {
      if (active) setManaged(workspace.managed)
    }).catch(() => { /* Legacy posting overview remains available. */ })
    return () => { active = false }
  }, [posting])
  const showSkeleton = useDelayedFlag(posting === null && !problem)

  // 그려 둔 사업을 기억한다. 아래의 불러오기보다 먼저 돌아야 한다.
  useEffect(() => {
    if (posting) lastPosting = posting
  }, [posting])

  // 게시·마감·삭제를 시작하면 값이 오른다. 그 전에 보낸 조회 응답이 늦게 와서 새 상태를 덮지 않게 한다.
  const actions = useRef(0)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  // 확인 창을 닫으면 창을 연 버튼으로 초점을 돌려놓는다.
  const trigger = useRef<HTMLElement | null>(null)

  useEffect(() => {
    let active = true
    const started = actions.current
    const load = typeof target === 'number'
      ? fetchOfficerPosting(target)
      : fetchOfficerPostings().then((items) => items.find((item) => item.builtin) ?? null)
    load
      .then((found) => {
        if (!active || started !== actions.current) return
        if (!found) {
          onGone()
          return
        }
        if (target === 'builtin') onBuiltinFound(found.id)
        setPosting(found)
      })
      .catch((error: unknown) => {
        if (!active) return
        if (isNotFound(error)) {
          lastPosting = null
          setPosting(null)
          setProblem('missing')
          return
        }
        // 이미 그려 둔 화면이 있으면 새로 고침 실패로 화면을 가리지 않는다.
        if (typeof target !== 'number' || lastPosting?.id !== target) setProblem('failed')
      })
    return () => { active = false }
  }, [target, attempt, onBuiltinFound, onGone])

  const backButton = (
    <button type="button" className="pwork__back" onClick={onBack}>사업 목록</button>
  )

  if (problem) {
    return (
      <main className="pwork pwork--page">
        <nav className="pwork__bar" aria-label="사업 작업 공간">{backButton}</nav>
        <div className="pwork__notice" role="alert">
          {problem === 'missing' ? (
            <>
              <strong>사업을 찾을 수 없습니다.</strong>
              <span>삭제됐거나 주소가 바뀌었을 수 있습니다.</span>
            </>
          ) : (
            <>
              <strong>사업 정보를 불러오지 못했습니다.</strong>
              <button
                type="button"
                className="btn"
                onClick={() => { setProblem(''); setAttempt((value) => value + 1) }}
              >
                다시 시도
              </button>
            </>
          )}
        </div>
      </main>
    )
  }

  if (posting === null) {
    return (
      <main className="pwork pwork--page">
        <nav className="pwork__bar" aria-label="사업 작업 공간">{backButton}</nav>
        {showSkeleton && (
          <Skeleton label="사업 정보를 불러오는 중">
            <div className="pwork__head">
              <SkeletonLine width="64px" />
              <SkeletonLine width="320px" className="pwork__skeleton-title" />
              <SkeletonLine width="200px" />
            </div>
            <SkeletonBlock className="pwork__skeleton-block" />
          </Skeleton>
        )}
      </main>
    )
  }

  const chip = <span className={`pwork__chip pwork__chip--${posting.phase}`}>{posting.phase_label}</span>
  const period = formatPeriod(posting.apply_start, posting.apply_end)

  if (posting.builtin) {
    return (
      <div className="pwork pwork--console">
        <nav className="pwork__bar" aria-label="사업 작업 공간">
          {backButton}
          <strong className="pwork__bar-name">{posting.title}</strong>
          {chip}
          <span className="pwork__bar-period">접수 기간 {period}</span>
        </nav>
        <OfficerConsole basePath={`/officer/programs/${posting.id}`} />
      </div>
    )
  }

  if (managed) return <ManagedProgramWorkspace postingId={posting.id} onBack={onBack} />

  const run = async (action: Action) => {
    actions.current += 1
    setBusy(true)
    setActionError('')
    try {
      if (action === 'remove') {
        await deletePosting(posting.id)
        lastPosting = null
        if (mounted.current) onGone()
        return
      }
      // 게시·마감 응답이 곧 바뀐 사업이다. 다시 조회하다 실패해 성공을 실패로 보이게 하지 않는다.
      const changed = await (action === 'publish' ? publishPosting(posting.id) : closePosting(posting.id))
      if (!mounted.current) return
      setPosting(changed)
      setAsking(null)
      trigger.current?.focus()
    } catch (error: unknown) {
      if (!mounted.current) return
      setActionError(error instanceof Error ? error.message : String(error))
      // 다른 창에서 이미 바뀐 사업일 수 있다. 화면을 실제 상태로 맞춘다.
      fetchOfficerPosting(posting.id)
        .then((fresh) => { if (mounted.current) setPosting(fresh) })
        .catch(() => {})
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  const ask = (action: Action) => {
    trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setActionError('')
    setAsking(action)
  }
  const stopAsking = () => {
    if (busy) return
    setAsking(null)
    trigger.current?.focus()
  }

  const files = [
    { kind: 'notice' as const, label: '공고문 PDF', url: posting.has_notice ? posting.notice_url : null, name: posting.notice_file_name },
    { kind: 'forms' as const, label: '서식 PDF', url: posting.has_forms ? posting.forms_url : null, name: posting.forms_file_name },
  ]
  const filesReady = files.every((file) => file.url)
  const viewed = files.find((file) => file.kind === viewing)
  const copy = asking ? ACTION_COPY[asking] : null

  return (
    <main className="pwork pwork--page">
      <nav className="pwork__bar" aria-label="사업 작업 공간">{backButton}</nav>

      <header className="pwork__head">
        {chip}
        <h1 className="pwork__title">{posting.title}</h1>
        <p className="pwork__period">접수 기간 {period}</p>
      </header>

      <section className="pwork__state" aria-label="게시 상태">
        <p className="pwork__state-text">
          {stateSentence(posting)}
          {posting.status !== 'published' && !filesReady && ' 공고문 PDF와 서식 PDF가 모두 있어야 게시할 수 있습니다.'}
        </p>
        <div className="pwork__actions">
          {posting.status === 'draft' && (
            <button type="button" className="btn btn--danger" disabled={busy} onClick={() => ask('remove')}>삭제</button>
          )}
          {posting.status === 'published' ? (
            <button type="button" className="btn btn--danger" disabled={busy} onClick={() => ask('close')}>마감하기</button>
          ) : (
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy || !filesReady}
              onClick={() => ask('publish')}
            >
              {posting.status === 'closed' ? '다시 게시' : '게시하기'}
            </button>
          )}
        </div>
      </section>

      <div className="pwork__columns">
        <section className="panel">
          <h2 className="panel__title">사업 정보</h2>
          <div className="panel__body">
            <dl className="pwork__facts">
              <dt>접수 기간</dt>
              <dd>{period}</dd>
              <dt>상태</dt>
              <dd>{posting.phase_label}</dd>
              <dt>만든 때</dt>
              <dd>{formatDayTime(posting.created_at)}</dd>
              <dt>게시한 때</dt>
              <dd>{posting.published_at ? formatDayTime(posting.published_at) : '아직 게시하지 않았습니다'}</dd>
            </dl>
          </div>
        </section>

        <section className="panel">
          <h2 className="panel__title">올린 파일</h2>
          <div className="panel__body">
            <ul className="pwork__files">
              {files.map((file) => (
                <li key={file.kind}>
                  <span className="pwork__file-kind">{file.label}</span>
                  <span className="pwork__file-name">{file.url ? file.name || '이름 없는 파일' : '파일이 없습니다'}</span>
                  <button
                    type="button"
                    className="btn"
                    disabled={!file.url}
                    aria-label={`${file.label} 보기`}
                    onClick={() => setViewing(file.kind)}
                  >
                    보기
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="panel">
        <h2 className="panel__title">신청 목록</h2>
        <div className="panel__body">
          <p className="pwork__empty">
            <strong>접수된 신청이 없습니다.</strong>
            이 사업의 온라인 신청은 준비 중입니다.
          </p>
        </div>
      </section>

      {viewed?.url && (
        <FilePreview
          url={viewed.url}
          name={viewed.name || `${posting.title} ${viewed.label}`}
          kind="pdf"
          onClose={() => setViewing(null)}
        />
      )}

      {asking && copy && (
        <Modal
          title={copy.title}
          onClose={stopAsking}
          footer={(
            <>
              <button type="button" className="btn" disabled={busy} onClick={stopAsking} autoFocus>취소</button>
              <button
                type="button"
                className={`btn btn--${copy.tone}`}
                disabled={busy}
                onClick={() => void run(asking)}
              >
                {busy ? '처리 중' : asking === 'publish' && posting.status === 'closed' ? '다시 게시' : copy.confirm}
              </button>
            </>
          )}
        >
          <p className="pwork__confirm-name">{posting.title}</p>
          <p className="pwork__confirm-text">{copy.body}</p>
          {actionError && <p className="pwork__confirm-error" role="alert">{actionError}</p>}
        </Modal>
      )}
    </main>
  )
}
