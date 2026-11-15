/**
 * 사업 목록 — 담당자가 처음 보는 화면.
 *
 * 카드 하나가 사업 하나다. 작성 중인 사업이 맨 앞에 오고, 카드를 누르면 그 사업의
 * 작업 공간으로 들어간다. 기본 사업의 작업 공간은 접수 목록이다.
 */
import { useEffect, useState } from 'react'

import { fetchOfficerPostings, isOfficerMockCounted, type OfficerPosting } from '../../api.ts'
import { Skeleton, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import { isPlainClick, routeHref } from '../../navigation-url.ts'
import { formatPeriod } from '../../posting-format.ts'
import './officer.css'
import './program-list.css'

interface Props {
  onNew: () => void
  onOpen: (posting: OfficerPosting) => void
}

const count = (value: number) => `${value.toLocaleString('ko-KR')}건`

export default function ProgramList({ onNew, onOpen }: Props) {
  const [items, setItems] = useState<OfficerPosting[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const showSkeleton = useDelayedFlag(items === null && !failed)

  useEffect(() => {
    let active = true
    fetchOfficerPostings()
      .then((list) => {
        if (!active) return
        // 서버가 이미 작성 중을 앞에 준다. 순서가 어긋나도 화면은 같은 규칙을 지킨다.
        setItems([...list.filter((item) => item.phase === 'draft'), ...list.filter((item) => item.phase !== 'draft')])
      })
      .catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [attempt])

  return (
    <main className="plist">
      <header className="plist__head">
        <h1 className="plist__title">사업 목록</h1>
        {items && <span className="plist__count">전체 {items.length.toLocaleString('ko-KR')}개</span>}
        <button type="button" className="btn btn--primary plist__new" onClick={onNew}>새 사업 올리기</button>
      </header>

      {items && isOfficerMockCounted() && (
        <p className="officer__mock">
          <strong>목업 데이터</strong> 기본 사업의 신청·확인 필요 건수는 예시로 채운 접수 목록을 센 값입니다.
        </p>
      )}

      <div className="plist__body">
        {failed ? (
          <div className="plist__notice" role="alert">
            <strong>사업 목록을 불러오지 못했습니다.</strong>
            <button
              type="button"
              className="btn"
              onClick={() => { setFailed(false); setAttempt((value) => value + 1) }}
            >
              다시 시도
            </button>
          </div>
        ) : items === null ? (
          showSkeleton && (
            <Skeleton className="plist__grid" label="사업 목록을 불러오는 중">
              {[0, 1, 2].map((index) => (
                <div className="plist__card plist__card--loading" key={index} aria-hidden="true">
                  <SkeletonLine width="64px" />
                  <SkeletonLine width={index === 1 ? '50%' : '68%'} />
                  <SkeletonLine width="180px" />
                  <SkeletonLine width="70%" />
                </div>
              ))}
            </Skeleton>
          )
        ) : items.length === 0 ? (
          <div className="plist__notice">
            <strong>등록된 사업이 없습니다.</strong>
            <span>새 사업 올리기로 첫 사업을 만들어 주세요.</span>
          </div>
        ) : (
          <ul className="plist__grid">
            {items.map((item) => (
              <li key={item.id}>
                <a
                  className="plist__card"
                  href={routeHref(`/officer/programs/${item.id}`)}
                  onClick={(event) => {
                    if (!isPlainClick(event)) return
                    event.preventDefault()
                    onOpen(item)
                  }}
                >
                  <span className="plist__top">
                    <span className={`plist__chip plist__chip--${item.phase}`}>{item.phase_label}</span>
                    {item.builtin && <span>기본 사업 · 읽기 전용</span>}
                    {item.builtin && <span className="plist__tag">기본 사업</span>}
                  </span>
                  <strong className="plist__name">{item.title}</strong>
                  <span className="plist__period">{formatPeriod(item.apply_start, item.apply_end)}</span>
                  <span className="plist__stats">
                    <span className="plist__stat">
                      신청 <strong>{count(item.application_count)}</strong>
                    </span>
                    <span className={item.needs_check_count > 0 ? 'plist__stat plist__stat--alert' : 'plist__stat'}>
                      확인 필요 <strong>{count(item.needs_check_count)}</strong>
                    </span>
                    <span className="plist__go" aria-hidden="true">{item.builtin ? '신청 목록' : '사업 열기'}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  )
}
