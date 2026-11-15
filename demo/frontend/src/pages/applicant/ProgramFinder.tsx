/**
 * 사업 찾기 — 신청자가 처음 보는 화면.
 *
 * 게시된 사업을 접수 중 → 접수 예정 → 마감 순으로 보여 준다. 여기서는 신청 건을
 * 만들지 않는다. 카드를 눌러 안내를 읽고 "신청하기"를 눌러야 신청이 시작된다.
 */
import { useEffect, useState } from 'react'

import { fetchPostings, type PublicPosting } from '../../api.ts'
import { Skeleton, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import { isPlainClick, routeHref } from '../../navigation-url.ts'
import { formatDate } from '../../lib/format.ts'
import useDocumentTitle from '../../hooks/useDocumentTitle.ts'
import Icon from '../../components/Icon.tsx'
import './program-finder.css'

function Card({ posting, onOpen }: { posting: PublicPosting; onOpen: (id: number) => void }) {
  return (
    <li>
      <a
        className={`pfinder__card pfinder__card--${posting.phase}`}
        href={routeHref(`/programs/${posting.id}`)}
        onClick={(event) => {
          if (!isPlainClick(event)) return
          event.preventDefault()
          onOpen(posting.id)
        }}
      >
        <span className="pfinder__card-main">
          <span className={`pfinder__status pfinder__status--${posting.phase}`}><Icon name="calendar" size={16} />{posting.phase_label}</span>
          <strong className="pfinder__name">{posting.title}</strong>
          <span className="pfinder__period">
            <span className="pfinder__period-label">신청 기간</span>
            {formatDate(posting.apply_start.slice(0, 10))} ~ {formatDate(posting.apply_end.slice(0, 10))}
          </span>
        </span>
        <span className="pfinder__go" aria-hidden="true">안내 보기</span>
      </a>
    </li>
  )
}

export default function ProgramFinder({ onOpen }: { onOpen: (id: number) => void }) {
  const [items, setItems] = useState<PublicPosting[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const showSkeleton = useDelayedFlag(items === null && !failed)

  useDocumentTitle('사업 찾기 | 전북청년허브센터')
  useEffect(() => { document.querySelector<HTMLElement>('#main h1')?.focus() }, [])

  useEffect(() => {
    let active = true
    fetchPostings()
      .then((list) => { if (active) setItems(list) })
      .catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [attempt])

  const current = items?.filter((item) => item.phase !== 'closed') ?? []
  const closed = items?.filter((item) => item.phase === 'closed') ?? []

  return (
    <div className="pfinder">
      <header className="pfinder__head headband">
        <h1 tabIndex={-1} className="pfinder__title">사업 찾기</h1>
        <p className="pfinder__lead">지원 사업의 안내와 공고문을 확인하고 온라인으로 신청할 수 있습니다.</p>
      </header>

      <div className="pfinder__body">
        {failed ? (
          <div className="pfinder__notice" role="alert">
            <strong>사업 목록을 불러오지 못했습니다.</strong>
            <p>잠시 후 다시 시도해 주세요.</p>
            <button
              type="button"
              className="btn"
              onClick={() => { setFailed(false); setAttempt((value) => value + 1) }}
            >
              다시 시도하기
            </button>
          </div>
        ) : items === null ? (
          showSkeleton && (
            <Skeleton className="pfinder__list" label="사업 목록을 불러오는 중">
              {[0, 1, 2].map((index) => (
                <div className="pfinder__card pfinder__card--loading" key={index} aria-hidden="true">
                  <span className="pfinder__card-main">
                    <SkeletonLine width="56px" />
                    <SkeletonLine width={index === 1 ? '46%' : '62%'} className="pfinder__skeleton-name" />
                    <SkeletonLine width="210px" />
                  </span>
                </div>
              ))}
            </Skeleton>
          )
        ) : (
          <>
            {current.length > 0 ? (
              <section aria-labelledby="pfinder-current-title">
                <div className="pfinder__section-head">
                  <h2 className="pfinder__section-title" id="pfinder-current-title">진행 중인 사업</h2>
                  <span className="pfinder__count">{current.length}개</span>
                </div>
                <ul className="pfinder__list">
                  {current.map((item) => <Card key={item.id} posting={item} onOpen={onOpen} />)}
                </ul>
              </section>
            ) : (
              <div className="pfinder__notice">
                <strong>지금 신청할 수 있는 사업이 없습니다.</strong>
                <p>새 사업이 게시되면 이 화면에 표시됩니다.</p>
              </div>
            )}

            {closed.length > 0 && (
              <section className="pfinder__closed" aria-labelledby="pfinder-closed-title">
                <div className="pfinder__section-head">
                  <h2 className="pfinder__section-title" id="pfinder-closed-title">마감된 사업</h2>
                  <span className="pfinder__count">{closed.length}개</span>
                </div>
                <ul className="pfinder__list">
                  {closed.map((item) => <Card key={item.id} posting={item} onOpen={onOpen} />)}
                </ul>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}
