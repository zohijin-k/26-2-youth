/**
 * 사업 안내 — 사업 하나의 기간·안내문·공고문과 "신청하기".
 *
 * 이 화면도 신청 건을 만들지 않는다. "신청하기"를 누르면 서버가 준 주소
 * (`apply_path`)로 들어가고, 그때 신청 화면이 신청 건을 만든다.
 */
import { useEffect, useState } from 'react'

import { fetchPosting, isNotFound, type PublicPostingDetail } from '../../api.ts'
import FilePreview from '../../components/FilePreview.tsx'
import PdfPages from '../../components/PdfPages.tsx'
import { Skeleton, SkeletonBlock, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import { isPlainClick, routeHref } from '../../navigation-url.ts'
import { formatDay, formatPeriod } from '../../posting-format.ts'
import './program-info.css'

interface Props {
  postingId: number
  onBack: () => void
  onApply: (path: string) => void
}

/** 버튼 아래 한 줄. 신청할 수 없을 때는 그 이유다. */
function applyNote(posting: PublicPostingDetail): string {
  if (posting.can_apply) return '본인인증부터 시작합니다.'
  if (posting.phase === 'upcoming') return `${formatDay(posting.apply_start)}부터 신청할 수 있습니다.`
  if (posting.phase === 'closed') return '신청 기간이 끝났습니다.'
  return '이 사업의 온라인 신청은 준비 중입니다.'
}

/** 공고문 쪽 폭. 놓인 칸의 폭을 따라가되 20px 단위로만 바꿔 다시 그리는 횟수를 줄인다. */
function useBoxWidth(): [(element: HTMLDivElement | null) => void, number] {
  const [box, setBox] = useState<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    if (!box) return
    const measure = () => setWidth(Math.floor(box.clientWidth / 20) * 20)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(box)
    return () => observer.disconnect()
  }, [box])

  return [setBox, width]
}

export default function ProgramInfo({ postingId, onBack, onApply }: Props) {
  const [posting, setPosting] = useState<PublicPostingDetail | null>(null)
  const [problem, setProblem] = useState<'' | 'missing' | 'failed'>('')
  const [attempt, setAttempt] = useState(0)
  const [enlarged, setEnlarged] = useState(false)
  const [noticeBox, noticeWidth] = useBoxWidth()
  const showSkeleton = useDelayedFlag(posting === null && !problem)

  useEffect(() => {
    let active = true
    fetchPosting(postingId)
      .then((body) => { if (active) setPosting(body) })
      .catch((error: unknown) => { if (active) setProblem(isNotFound(error) ? 'missing' : 'failed') })
    return () => { active = false }
  }, [postingId, attempt])

  const back = (
    <a
      className="pinfo__back"
      href={routeHref('/')}
      onClick={(event) => {
        if (!isPlainClick(event)) return
        event.preventDefault()
        onBack()
      }}
    >
      사업 찾기
    </a>
  )

  if (problem) {
    return (
      <main className="pinfo">
        {back}
        <div className="pinfo__notice" role="alert">
          {problem === 'missing' ? (
            <>
              <strong>사업을 찾을 수 없습니다.</strong>
              <p>게시가 끝났거나 주소가 바뀌었을 수 있습니다.</p>
              <button type="button" className="pinfo__button" onClick={onBack}>사업 찾기로</button>
            </>
          ) : (
            <>
              <strong>사업 안내를 불러오지 못했습니다.</strong>
              <p>잠시 후 다시 시도해 주세요.</p>
              <button
                type="button"
                className="pinfo__button"
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
      <main className="pinfo">
        {back}
        {showSkeleton && (
          <Skeleton label="사업 안내를 불러오는 중">
            <div className="pinfo__head">
              <SkeletonLine width="56px" />
              <SkeletonLine width="min(420px, 80%)" className="pinfo__skeleton-title" />
              <SkeletonLine width="210px" />
            </div>
            <div className="pinfo__layout">
              <div className="pinfo__aside"><SkeletonBlock className="pinfo__skeleton-aside" /></div>
              <div className="pinfo__main"><SkeletonBlock className="pinfo__skeleton-main" /></div>
            </div>
          </Skeleton>
        )}
      </main>
    )
  }

  const noticeUrl = posting.has_notice ? posting.notice_url : null
  const paragraphs = posting.guidance_text.split(/\n\s*\n/).map((text) => text.trim()).filter(Boolean)
  // 쪽 둘레 여백과 스크롤 막대 자리를 뺀 폭. 좁은 화면은 둘레 여백이 작다.
  const pageWidth = Math.max(220, Math.min(860, noticeWidth - (noticeWidth < 480 ? 36 : 48)))

  return (
    <main className="pinfo">
      {back}

      <header className="pinfo__head">
        <span className={`pinfo__status pinfo__status--${posting.phase}`}>{posting.phase_label}</span>
        <h1 className="pinfo__title">{posting.title}</h1>
        <p className="pinfo__period">
          <span className="pinfo__period-label">신청 기간</span>
          {formatPeriod(posting.apply_start, posting.apply_end)}
        </p>
      </header>

      <div className="pinfo__layout">
        <aside className="pinfo__aside" aria-label="온라인 신청">
          <div className="pinfo__card pinfo__apply-card">
            <h2 className="pinfo__card-title">온라인 신청</h2>
            <button
              type="button"
              className="pinfo__apply"
              disabled={!posting.can_apply}
              aria-describedby="pinfo-apply-note"
              onClick={() => onApply(posting.apply_path ?? '/apply/identity')}
            >
              신청하기
            </button>
            <p className="pinfo__apply-note" id="pinfo-apply-note">{applyNote(posting)}</p>
          </div>
        </aside>

        <div className="pinfo__main">
          <section className="pinfo__card" aria-labelledby="pinfo-guidance-title">
            <h2 className="pinfo__card-title" id="pinfo-guidance-title">안내</h2>
            {paragraphs.length > 0 ? (
              <div className="pinfo__guidance">
                {paragraphs.map((text, index) => <p key={index}>{text}</p>)}
              </div>
            ) : (
              <p className="pinfo__quiet">
                {noticeUrl ? '등록된 안내문이 없습니다. 자세한 내용은 아래 공고문을 확인해 주세요.' : '등록된 안내문이 없습니다.'}
              </p>
            )}
          </section>

          {noticeUrl && (
            <section className="pinfo__card" aria-labelledby="pinfo-notice-title">
              <div className="pinfo__card-head">
                <h2 className="pinfo__card-title" id="pinfo-notice-title">공고문</h2>
                <button type="button" className="pinfo__button pinfo__button--small" onClick={() => setEnlarged(true)}>
                  크게 보기
                </button>
              </div>
              <div ref={noticeBox} className="pinfo__notice-box">
                <div className="pinfo__notice-stage" role="region" aria-label="공고문 내용" tabIndex={0}>
                  {noticeWidth > 0 && <PdfPages url={noticeUrl} width={pageWidth} />}
                </div>
              </div>
            </section>
          )}
        </div>
      </div>

      {enlarged && noticeUrl && (
        <FilePreview
          url={noticeUrl}
          name={`${posting.title} 공고문`}
          kind="pdf"
          onClose={() => setEnlarged(false)}
        />
      )}
    </main>
  )
}
