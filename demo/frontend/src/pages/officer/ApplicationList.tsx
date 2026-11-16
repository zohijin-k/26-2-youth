/**
 * 신청 목록 — 담당자가 지금 봐야 할 건부터 보인다.
 *
 * 위에서 아래로: 구분 탭(확인 필요 · 적합 · 처리 완료) → 검색·기간 한 줄 → 표 → 쪽 번호.
 * 행을 고르면 검색 줄 자리에 일괄 처리 버튼이 뜬다. 자리를 미리 잡아 두었으므로
 * 표는 움직이지 않는다. 확인 필요 건은 행을 펼쳐 사유를 먼저 읽을 수 있다.
 */
import { Fragment, useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import {
  OFFICER_QUEUES,
  fetchApplicationReasons,
  fetchReasonExplanation,
  type ApplicationReasons,
  type DecisionKey,
  type OfficerList,
  type OfficerListQuery,
  type OfficerRow,
} from '../../api.ts'
import { Skeleton, SkeletonLine } from '../../components/Skeleton.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import { formatDayTime } from '../../posting-format.ts'
import { bulkActionsFor, queueOf } from './bulk-actions.ts'
import SortToggle from './SortToggle.tsx'
import RejectionTable from './RejectionTable.tsx'
import { LIST_TABS, nextTab, shownTabOf, tabCount, tabOf, tabQuery, type ListTab } from './list-tabs.ts'
import './application-list.css'

const QUEUE_COPY: Record<ListTab, { label: string; empty: string }> = {
  needs_check: { label: '확인 필요', empty: '확인이 필요한 신청이 없습니다.' },
  pass: { label: '적합', empty: '적합으로 판정된 미처리 신청이 없습니다.' },
  done: { label: '처리 완료', empty: '처리한 신청이 없습니다.' },
  rejected: { label: '반려', empty: '반려한 신청이 없습니다.' },
}

const HEADERS = ['신청번호', '성명', '접수일시', '처리상태']
const SEARCH_MAX = 50
/** 글자를 치다 멈춘 뒤 검색을 보내기까지의 시간. */
const SEARCH_PAUSE_MS = 300

type ReasonState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; data: ApplicationReasons }

/** 담당자 판단이 없고 자동 판정이 적합이 아닌 건. 이 건에만 사유 펼침이 있다. */
const needsCheck = (row: OfficerRow) => queueOf(row) === 'needs_check'

/** 처리상태 표기. 판단한 건은 담당자 판단을, 아닌 건은 자동 판정을 보여준다. */
function StatusChip({ row }: { row: OfficerRow }) {
  const tone = row.decision ?? (row.ai_status ?? 'none').toLowerCase()
  const label = row.decision ? row.decision_label : row.ai_status_label
  return <span className={`alist__chip alist__chip--${tone}`}>{label}</span>
}

interface Props {
  list: OfficerList
  generic?: boolean
  query: OfficerListQuery
  onQuery: (patch: Partial<OfficerListQuery>) => void
  /** 심사 화면 열기. `slotKey`가 있으면 그 서류를 연 채로 시작한다. */
  onOpen: (applicationId: number, slotKey?: string) => void
  selected: number[]
  onSelect: (ids: number[]) => void
  /** 고른 건을 한 번에 처리한다. 처리가 끝나면 돌아온다. */
  onBulk: (decision: DecisionKey) => Promise<void>
  busy: boolean
  /** 일괄 처리 결과 한 줄. 없으면 빈 문자열. */
  notice: string
}

export default function ApplicationList({
  list,
  generic = false,
  query,
  onQuery,
  onOpen,
  selected,
  onSelect,
  onBulk,
  busy,
  notice,
}: Props) {
  const uid = useId()
  const queue = query.queue ?? 'needs_check'
  /** 보이는 탭. 반려 탭은 처리 완료 중 반려만 거른 것이다. */
  const tab = tabOf(query)
  /** 지금 표에 있는 행이 속한 구분. 탭을 막 옮긴 직후에는 `queue`보다 한 박자 늦다. */
  const shownQueue = OFFICER_QUEUES.find((key) => key === list.filters.applied.queue) ?? queue
  const canBulk = list.role.can_bulk
  const columnCount = HEADERS.length + 2

  // ---- 검색어. 입력 칸의 글자는 여기서 쥐고, 멈췄을 때만 목록 조건으로 올린다.
  const appliedSearch = query.q ?? ''
  const [text, setText] = useState(appliedSearch)
  const [seenSearch, setSeenSearch] = useState(appliedSearch)
  if (appliedSearch !== seenSearch) {
    setSeenSearch(appliedSearch)
    // 밖에서 바뀐 경우(역할 전환·조건 지우기)에만 칸을 맞춘다. 치는 중인 공백은 건드리지 않는다.
    if (appliedSearch !== text.trim()) setText(appliedSearch)
  }
  const searchTimer = useRef<number | undefined>(undefined)
  const searchInput = useRef<HTMLInputElement>(null)
  useEffect(() => () => window.clearTimeout(searchTimer.current), [])

  // ---- 펼친 행. 한 번에 하나만 펼친다.
  const [expanded, setExpanded] = useState<number | null>(null)
  const [reasons, setReasons] = useState<Record<number, ReasonState>>({})
  const openId = list.rows.some((row) => row.application_id === expanded) ? expanded : null
  const openState = openId === null ? undefined : reasons[openId]
  // 응답이 빨리 오면 내용이 든 채로 한 번에 펼친다. 늦을 때만 자리 표시를 먼저 보인다.
  const showLoading = useDelayedFlag(openState?.status === 'loading')

  const tabs = useRef<Partial<Record<ListTab, HTMLButtonElement | null>>>({})
  const selectAll = useRef<HTMLInputElement>(null)

  const filtered = Boolean(appliedSearch || text.trim() || query.submitted_from || query.submitted_to)
  const pageIds = list.rows.map((row) => row.application_id)
  const allChecked = pageIds.length > 0 && pageIds.every((id) => selected.includes(id))
  const someChecked = pageIds.some((id) => selected.includes(id))
  const selecting = canBulk && selected.length > 0

  useEffect(() => {
    if (selectAll.current) selectAll.current.indeterminate = someChecked && !allChecked
  }, [someChecked, allChecked])

  /** 목록 조건을 바꾼다. 펼친 행은 접는다. */
  const change = (patch: Partial<OfficerListQuery>) => {
    setExpanded(null)
    onQuery(patch)
  }

  const submitSearch = (value: string) => {
    window.clearTimeout(searchTimer.current)
    const next = value.trim()
    if (next !== appliedSearch) change({ q: next || undefined, page: 1 })
  }

  const typeSearch = (value: string) => {
    setText(value)
    window.clearTimeout(searchTimer.current)
    searchTimer.current = window.setTimeout(() => submitSearch(value), SEARCH_PAUSE_MS)
  }

  const resetFilters = () => {
    window.clearTimeout(searchTimer.current)
    setText('')
    change({ q: undefined, submitted_from: undefined, submitted_to: undefined, page: 1 })
    searchInput.current?.focus()
  }

  const pickQueue = (next: ListTab, focus = false) => {
    if (next !== tab) change({ ...tabQuery(next), page: 1 })
    if (focus) tabs.current[next]?.focus()
  }

  const onTabKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const to = nextTab(tab, event.key)
    if (!to) return
    event.preventDefault()
    pickQueue(to, true)
  }

  const loadReasons = (id: number) => {
    setReasons((prev) => ({ ...prev, [id]: { status: 'loading' } }))
    fetchApplicationReasons(id, list.role.key)
      .then(async (data) => {
        const explanation = await fetchReasonExplanation(id, list.role.key).catch(() => null)
        setReasons((prev) => ({ ...prev, [id]: { status: 'ready', data: { ...data, explanation } } }))
      })
      .catch(() => setReasons((prev) => ({ ...prev, [id]: { status: 'error' } })))
  }

  const toggleReasons = (id: number) => {
    if (openId === id) {
      setExpanded(null)
      return
    }
    setExpanded(id)
    if (reasons[id]?.status !== 'ready') loadReasons(id)
  }

  /** 표 안에서 Esc를 누르면 펼친 행을 접고, 펼침 버튼으로 초점을 돌려놓는다. */
  const onTableKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape' || openId === null) return
    event.preventDefault()
    setExpanded(null)
    document.getElementById(`${uid}-more-${openId}`)?.focus()
  }

  const toggleRow = (id: number) => {
    onSelect(selected.includes(id) ? selected.filter((other) => other !== id) : [...selected, id])
  }

  const clearSelection = () => {
    onSelect([])
    selectAll.current?.focus()
  }

  /** 처리가 끝나면 일괄 처리 버튼이 사라진다. 초점은 건수가 바뀐 탭으로 옮긴다. */
  const runBulk = (decision: DecisionKey) => {
    void onBulk(decision).then(() => tabs.current[tab]?.focus())
  }

  const onSearchSubmit = (event: FormEvent) => {
    event.preventDefault()
    submitSearch(text)
  }

  return (
    <div className="alist">
      <div className="alist__head">
        <div className="alist__tabs" role="tablist" aria-label="신청 구분">
          {LIST_TABS.map((key) => {
            const on = key === tab
            const count = tabCount(list, key)
            const loud = key === 'needs_check' && count > 0
            return (
              <button
                key={key}
                ref={(element) => { tabs.current[key] = element }}
                type="button"
                role="tab"
                id={`${uid}-tab-${key}`}
                aria-selected={on}
                aria-controls={`${uid}-panel`}
                tabIndex={on ? 0 : -1}
                className={on ? 'alist__tab alist__tab--on' : 'alist__tab'}
                onClick={() => pickQueue(key)}
                onKeyDown={onTabKey}
              >
                {QUEUE_COPY[key].label}
                <span className={loud ? 'alist__count alist__count--loud' : 'alist__count'}>
                  {count.toLocaleString('ko-KR')}
                  <span className="alist__sr">건</span>
                </span>
              </button>
            )
          })}
        </div>

        {/* 관할 선택. 역할이 관할을 요구할 때만 있다. 건수와 표가 모두 이 범위를 따른다. */}
        {(list.scope.region_locked || list.scope.town_locked) && (
          <div className="alist__scope">
            {list.scope.region_locked && (
              <label>
                시군
                <select
                  value={list.scope.region}
                  onChange={(event) => change({ region: event.target.value, town: '', page: 1 })}
                >
                  {list.scope.regions.map((region) => (
                    <option key={region} value={region}>{region}</option>
                  ))}
                </select>
              </label>
            )}
            {list.scope.town_locked && (
              <label>
                읍·면·동
                <select
                  value={list.scope.town}
                  onChange={(event) => change({ town: event.target.value, page: 1 })}
                >
                  {list.scope.towns.length === 0 && <option value="">(접수 없음)</option>}
                  {list.scope.towns.map((town) => (
                    <option key={town} value={town}>{town}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
      </div>

      <div className={selecting ? 'alist__bar alist__bar--selecting' : 'alist__bar'}>
        <form className="alist__filters" role="search" onSubmit={onSearchSubmit}>
          <input
            ref={searchInput}
            type="search"
            className="alist__search"
            placeholder="신청번호 또는 성명"
            aria-label="신청번호 또는 성명 검색"
            maxLength={SEARCH_MAX}
            autoComplete="off"
            value={text}
            onChange={(event) => typeSearch(event.target.value)}
          />
          <span className="alist__period" role="group" aria-label="접수일">
            <span aria-hidden="true">접수일</span>
            <input
              type="date"
              aria-label="접수일 시작"
              max={query.submitted_to || undefined}
              value={query.submitted_from ?? ''}
              onChange={(event) => change({ submitted_from: event.target.value || undefined, page: 1 })}
            />
            <span aria-hidden="true">~</span>
            <input
              type="date"
              aria-label="접수일 종료"
              min={query.submitted_from || undefined}
              value={query.submitted_to ?? ''}
              onChange={(event) => change({ submitted_to: event.target.value || undefined, page: 1 })}
            />
          </span>
          {filtered && (
            <button type="button" className="alist__link" onClick={resetFilters}>조건 지우기</button>
          )}
        </form>

        {selecting && (
          <div className="alist__selection" role="group" aria-label="선택한 신청 일괄 처리">
            <strong className="alist__selection-count">{selected.length.toLocaleString('ko-KR')}건 선택</strong>
            {/* 확인 필요 탭에서는 승인을 일괄로 할 수 없다 — 보류·반려만 보인다. */}
            {bulkActionsFor(shownQueue, list.role.actions).map((action) => (
              <button
                key={action.key}
                type="button"
                className={`btn btn--${action.tone}`}
                disabled={busy}
                onClick={() => runBulk(action.key)}
              >
                {action.result_label}
              </button>
            ))}
            <button type="button" className="alist__link" disabled={busy} onClick={clearSelection}>
              선택 해제
            </button>
          </div>
        )}

        <span className="alist__notice" role="status">{notice}</span>
        <SortToggle value={query.sort} disabled={busy} onChange={(sort) => change({ sort, page: 1 })} />
      </div>

      <div
        className="alist__panel"
        role="tabpanel"
        id={`${uid}-panel`}
        aria-labelledby={`${uid}-tab-${tab}`}
        onKeyDown={onTableKey}
      >
        {shownTabOf(list) === 'rejected' ? <RejectionTable rows={list.rows} tableClassName="alist__table" onOpen={(id) => onOpen(id)} /> : <table className="alist__table">
          <colgroup>
            {/* 일괄 처리가 없는 역할도 열을 비워 둔다. 역할을 바꿔도 열 위치가 그대로다. */}
            <col className="alist__col-check" />
            <col className="alist__col-no" />
            <col />
            <col className="alist__col-time" />
            <col className="alist__col-status" />
            <col className="alist__col-more" />
          </colgroup>
          <thead>
            <tr>
              {canBulk ? (
                <th scope="col" className="alist__check">
                  <label>
                    <input
                      ref={selectAll}
                      type="checkbox"
                      aria-label="전체 선택"
                      checked={allChecked}
                      disabled={pageIds.length === 0}
                      onChange={() => onSelect(allChecked ? [] : pageIds)}
                    />
                  </label>
                </th>
              ) : <td className="alist__check" aria-hidden="true" />}
              {HEADERS.map((label) => <th key={label} scope="col">{label}</th>)}
              <th scope="col"><span className="alist__sr">확인 필요 사유</span></th>
            </tr>
          </thead>
          <tbody>
            {list.rows.map((row) => {
              const id = row.application_id
              const open = openId === id
              const checked = selected.includes(id)
              const state = open ? openState : undefined
              const showReasons = state !== undefined && (state.status !== 'loading' || showLoading)
              const rowClass = [
                'alist__row',
                checked ? 'alist__row--checked' : '',
                open ? 'alist__row--open' : '',
              ].filter(Boolean).join(' ')
              return (
                <Fragment key={id}>
                  <tr className={rowClass} onClick={() => generic ? toggleReasons(id) : onOpen(id)}>
                    {canBulk ? (
                      <td className="alist__check" onClick={(event) => event.stopPropagation()}>
                        <label>
                          <input
                            type="checkbox"
                            aria-label={`${row.application_no} 선택`}
                            checked={checked}
                            onChange={() => toggleRow(id)}
                          />
                        </label>
                      </td>
                    ) : <td className="alist__check" aria-hidden="true" />}
                    <td>
                      <button
                        type="button"
                        className="alist__open"
                        aria-label={`${row.application_no} ${row.name} ${generic ? '사유 보기' : '심사 화면 열기'}`}
                        onClick={(event) => {
                          event.stopPropagation()
                          if (generic) toggleReasons(id); else onOpen(id)
                        }}
                      >
                        {row.application_no}
                      </button>
                    </td>
                    <td className="alist__name">{row.name}</td>
                    <td className="alist__time">{formatDayTime(row.submitted_at)}</td>
                    <td><StatusChip row={row} />{!row.decision && !!row.check_count && <span className="alist__checks">확인 {row.check_count}건</span>}</td>
                    <td className="alist__more" onClick={(event) => event.stopPropagation()}>
                      {(generic || needsCheck(row)) && (
                        <button
                          type="button"
                          id={`${uid}-more-${id}`}
                          className="alist__toggle"
                          aria-expanded={open}
                          aria-controls={`${uid}-reasons-${id}`}
                          aria-label={`${row.application_no} 확인 필요 사유 보기`}
                          onClick={() => toggleReasons(id)}
                        >
                          사유
                          <span className="alist__chevron" aria-hidden="true" />
                        </button>
                      )}
                    </td>
                  </tr>
                  {showReasons && (
                    <tr className="alist__reason-row">
                      <td colSpan={columnCount}>
                        <Reasons
                          id={`${uid}-reasons-${id}`}
                          row={row}
                          state={state}
                          onRetry={() => loadReasons(id)}
                          onOpen={onOpen}
                          generic={generic}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
            {list.rows.length === 0 && (
              <tr className="alist__empty-row">
                <td colSpan={columnCount}>
                  <p>{filtered ? '조건에 맞는 신청이 없습니다.' : QUEUE_COPY[shownQueue].empty}</p>
                  {filtered && (
                    <button type="button" className="alist__link" onClick={resetFilters}>조건 지우기</button>
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>}
      </div>

      {list.page_count > 1 && (
        <nav className="pager" aria-label="쪽 이동">
          {Array.from({ length: list.page_count }, (_, index) => index + 1).map((page) => (
            <button
              key={page}
              type="button"
              className={page === list.page ? 'pager__on' : undefined}
              aria-current={page === list.page ? 'page' : undefined}
              onClick={() => change({ page })}
            >
              {page}
            </button>
          ))}
        </nav>
      )}
    </div>
  )
}

/**
 * 펼친 행 — 이 건을 왜 확인해야 하는가.
 *
 * 적합이 아닌 서류마다 한 줄씩, 서류 이름과 판정, 그 아래 확인 사항을 문장으로
 * 적는다. 올리지 않은 필수 서류도 같은 목록에 넣는다. 규칙 판정이 저장해 둔
 * 값만 보여준다.
 */
function Reasons({ id, row, state, onRetry, onOpen, generic = false }: {
  generic?: boolean
  id: string
  row: OfficerRow
  state: ReasonState
  onRetry: () => void
  onOpen: (applicationId: number, slotKey?: string) => void
}) {
  const data = state.status === 'ready' ? state.data : null
  const empty = data !== null && data.documents.length === 0 && data.missing.length === 0
  return (
    <div className="alist__reasons" id={id} role="region" aria-label={`${row.application_no} 확인 필요 사유`}>
      {state.status === 'loading' && (
        <Skeleton className="alist__reasons-loading" label="사유를 불러오는 중">
          <SkeletonLine width="220px" />
          <SkeletonLine width="460px" />
          <SkeletonLine width="380px" />
        </Skeleton>
      )}

      {state.status === 'error' && (
        <p className="alist__reasons-note" role="alert">
          사유를 불러오지 못했습니다.
          <button type="button" className="btn" onClick={onRetry}>다시 시도</button>
        </p>
      )}

      {generic && <p className="alist__reasons-note">자격 규칙 미설정 — 담당자가 공고문 기준으로 확인</p>}
      {empty && !generic && (
        <p className="alist__reasons-note">저장된 사유가 없습니다. 심사 화면에서 서류를 확인해 주세요.</p>
      )}

      {data !== null && !empty && (
        <ul className="alist__reason-list">
          {data.documents.map((doc, index) => (
            <li key={`${doc.slot_key}:${index}`}>
              <span className={`alist__chip alist__chip--${(doc.status ?? 'none').toLowerCase()}`}>
                {doc.status_label}
              </span>
              <div>
                <strong>{doc.label}</strong>
                {doc.findings.length > 0 ? (
                  <ul className="alist__findings">
                    {[...new Set(doc.findings.map((finding) => finding.message))].map((message) => (
                      <li key={message}>{message}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="alist__findings-none">기록된 확인 사항이 없습니다.</p>
                )}
              </div>
            </li>
          ))}
          {data.missing.map((slot) => (
            <li key={slot.slot_key}>
              <span className="alist__chip alist__chip--none">미제출</span>
              <div>
                <strong>{slot.label}</strong>
                <p className="alist__findings-none">필수 서류를 올리지 않았습니다.</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {data?.explanation && <section className="alist__reasons-note"><strong>{data.explanation.label}</strong><p>{data.explanation.text}</p><small>{data.explanation.basis}</small></section>}
      {generic && <p className="alist__reasons-note">이 사업의 건별 심사 화면 연결은 준비 중입니다.</p>}

      {!generic && state.status !== 'loading' && (
        <button
          type="button"
          className="alist__link"
          // 확인할 서류가 있으면 그 서류를 연 채로 심사 화면을 시작한다.
          onClick={() => onOpen(row.application_id, data?.documents[0]?.slot_key)}
        >
          심사 화면 열기
        </button>
      )}
    </div>
  )
}

/** 목록이 도착하기 전의 자리 표시. 실제 화면과 같은 틀과 높이를 쓴다. */
export function ApplicationListSkeleton() {
  return (
    <Skeleton className="alist" label="신청 목록을 불러오는 중">
      <div className="alist__head">
        <div className="alist__tabs" aria-hidden="true">
          {LIST_TABS.map((key) => (
            <span key={key} className="alist__tab">{QUEUE_COPY[key].label}</span>
          ))}
        </div>
      </div>
      <div className="alist__bar" aria-hidden="true">
        <SkeletonLine width="260px" className="alist__bar-skeleton" />
        <SkeletonLine width="300px" className="alist__bar-skeleton" />
      </div>
      <table className="alist__table" aria-hidden="true">
        <colgroup>
          <col className="alist__col-check" />
          <col className="alist__col-no" />
          <col />
          <col className="alist__col-time" />
          <col className="alist__col-status" />
          <col className="alist__col-more" />
        </colgroup>
        <thead>
          <tr>
            <th />
            {HEADERS.map((label) => <th key={label}>{label}</th>)}
            <th />
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 8 }, (_, index) => (
            <tr key={index} className="alist__row">
              <td />
              <td><SkeletonLine width="150px" /></td>
              <td><SkeletonLine width="64px" /></td>
              <td><SkeletonLine width="130px" /></td>
              <td><SkeletonLine width="72px" /></td>
              <td />
            </tr>
          ))}
        </tbody>
      </table>
    </Skeleton>
  )
}
