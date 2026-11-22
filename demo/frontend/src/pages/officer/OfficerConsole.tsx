import { confirmOfficerLeave } from './review-navigation.ts'
/**
 * 담당자 콘솔 — 접수 목록 ↔ 건별 분할 심사 (P4).
 *
 * 상단의 **역할 전환 토글**이 이 화면의 축이다 (R4.5). 시행지침의 선발 절차가
 * 읍·면·동 → 시군 → 도·청년허브센터로 올라가는데, 같은 화면에서 보이는 범위와
 * 가능한 액션만 달라지는 것을 보여주면 충분하다. 데모는 로그인을 하지 않는다 —
 * 인증이 아니라 절차 구조를 시연하는 것이 목적이다.
 *
 * 주소는 사업 작업 공간(`/officer/programs/<id>`)을 바닥으로 삼는다. 역할·심사 건·
 * 심사 기준 경로가 그 뒤에 붙는다 (`<바닥>/city/review/9`).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import {
  OFFICER_QUEUES,
  OFFICER_SORTS,
  fetchOfficerList,
  fetchReviewDetail,
  postDecision,
  fetchOfficerRoles,
  isOfficerMockActive,
  isOfficerMockId as isMockId,
  postBulkDecision,
  type DecisionKey,
  type OfficerList,
  type OfficerListQuery,
  type OfficerQueue,
  type OfficerRole,
  type OfficerSort,
} from '../../api.ts'
import ApplicationList, { ApplicationListSkeleton } from './ApplicationList.tsx'
import RejectApplication from './RejectApplication.tsx'
import ReviewDetail from './ReviewDetail.tsx'
import useDelayedFlag from '../../hooks/useDelayedFlag.ts'
import { currentParams, routeUrl } from '../../navigation-url.ts'
import { YOUTH_PROGRAM } from '../../officer-scope.ts'
import './officer.css'

/** 처음 여는 구분은 확인 필요, 정렬은 중요도순이다 — 담당자가 지금 봐야 할 건부터 보인다. */
const DEFAULT_QUERY: OfficerListQuery = {
  role: 'province', program: YOUTH_PROGRAM, sort: 'importance', queue: 'needs_check', page: 1, page_size: 20,
}
/** 주소에 그대로 싣는 목록 조건. 구분은 기본값이면 싣지 않으므로 따로 다룬다. */
const QUERY_KEYS = ['region', 'town', 'submitted_from', 'submitted_to', 'q'] as const
const SEARCH_MAX = 50

/**
 * 주소에서 읽은 구분.
 *
 * 예전 링크에는 구분 대신 처리상태(`status`)와 AI판정(`ai`)이 붙어 있다. 그 조합에
 * 가장 가까운 구분을 연다: 판단한 건은 처리 완료, 미처리이면서 적합은 적합, 그 밖의
 * 미처리는 확인 필요. 그 값들은 첫 주소 쓰기에서 지워진다.
 */
function savedQueue(params: URLSearchParams): OfficerQueue {
  const queue = params.get('queue') as OfficerQueue
  if (OFFICER_QUEUES.includes(queue)) return queue
  const status = params.get('status') ?? params.get('o_status')
  if (status === 'approve' || status === 'hold' || status === 'reject') return 'done'
  const ai = params.get('ai') ?? params.get('o_ai_status')
  return status === 'pending' && ai === 'PASS' ? 'pass' : 'needs_check'
}

function savedOfficerPage(basePath: string): {
  query: OfficerListQuery
  open: { id: number; slot: string | null; reject?: boolean } | null
  showCriteria: boolean
} | null {
  const params = currentParams()
  // 제거된 신청 화면·사업 경로만 목록으로 보낸다. 취업패키지 상세 ID는 그대로 복원한다.
  if (window.location.pathname.startsWith('/apply')
    || /(?:double_savings|doubling_savings|double-savings)/.test(window.location.pathname)
    || (!window.location.pathname.startsWith('/officer') && params.get('mode') === 'applicant')) return null
  // 바닥 경로 뒤에 붙은 부분만 읽는다. 다른 사업의 주소면 아무것도 복원하지 않는다.
  const rest = window.location.pathname.startsWith(basePath) ? window.location.pathname.slice(basePath.length) : null
  const detailRoute = rest === null ? null : /^(?:\/([^/]+))?(?:\/review\/([1-9]\d*)(\/reject)?)?\/?$/.exec(rest)
  const criteriaRoute = rest === null ? null : /^\/criteria\/([^/]+)\/?$/.exec(rest)
  const legacy = [...QUERY_KEYS.map((key) => `o_${key}`), 'o_status', 'o_ai_status', 'o_role', 'o_page', 'o_page_size', 'o_open', 'o_slot', 'o_criteria', 'o_criteria_program'].some((key) => params.has(key))
  if (!detailRoute && !criteriaRoute && !legacy) return null
  const query: OfficerListQuery = {
    ...DEFAULT_QUERY,
    role: detailRoute?.[1] || params.get('role') || params.get('o_role') || DEFAULT_QUERY.role,
  }
  for (const key of QUERY_KEYS) {
    const value = params.get(key) ?? params.get(`o_${key}`)
    if (value) query[key] = value
  }
  query.q = query.q?.trim().slice(0, SEARCH_MAX) || undefined
  query.queue = savedQueue(params)
  // 반려 탭은 처리 완료 + 반려 필터다(list-tabs.ts).
  if (query.queue === 'done' && (params.get('status') ?? params.get('o_status')) === 'reject') query.status = 'reject'
  const sort = params.get('sort') as OfficerSort
  if (OFFICER_SORTS.some((item) => item.key === sort)) query.sort = sort
  const page = Number(params.get('page') ?? params.get('o_page'))
  const pageSize = Number(params.get('page_size') ?? params.get('o_page_size'))
  if (Number.isSafeInteger(page) && page > 0) query.page = page
  if (Number.isSafeInteger(pageSize) && pageSize > 0) query.page_size = pageSize
  const openId = Number(detailRoute?.[2] ?? params.get('o_open'))
  return {
    query,
    open: Number.isSafeInteger(openId) && openId > 0 ? { id: openId, slot: params.get('slot') ?? params.get('o_slot'), reject: !!detailRoute?.[3] } : null,
    showCriteria: criteriaRoute?.[1] === YOUTH_PROGRAM || (params.get('o_criteria') === '1' && params.get('o_criteria_program') !== 'double_savings'),
  }
}

export default function OfficerConsole({ basePath }: { basePath: string }) {
  const [initialPage] = useState(() => savedOfficerPage(basePath))
  const initialUrlWrite = useRef(true)
  const [roles, setRoles] = useState<OfficerRole[]>([])
  const [query, setQuery] = useState<OfficerListQuery>(initialPage?.query ?? DEFAULT_QUERY)
  const [list, setList] = useState<OfficerList | null>(null)
  /**
   * 열려 있는 심사 건. `slot`은 목록의 서류 칸을 눌러 들어왔을 때 띄울 서류다 —
   * 행을 눌러 들어오면 null이고 상세가 첫 서류를 연다.
   */
  const [open, setOpen] = useState<{ id: number; slot: string | null; reject?: boolean } | null>(initialPage?.open ?? null)
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  /** 일괄 처리 결과 한 줄. 행이 다른 구분으로 옮겨 가 사라진 이유를 알린다. */
  const [notice, setNotice] = useState('')
  /** 가장 최근에 보낸 목록 요청. 늦게 온 예전 응답이 새 목록을 덮지 않게 한다. */
  const latestRequest = useRef(0)
  /** 목업으로 넘어갔는지는 목록을 한 번 읽어 봐야 안다 — 응답이 온 뒤에 다시 잰다. */
  const [mock, setMock] = useState(isOfficerMockActive())
  const [showCriteria, setShowCriteria] = useState(initialPage?.showCriteria ?? false)
  const showListSkeleton = useDelayedFlag(!list && !error && !showCriteria && open === null)

  useEffect(() => {
    fetchOfficerRoles()
      .then(setRoles)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  const reload = useCallback(() => {
    latestRequest.current += 1
    const request = latestRequest.current
    return fetchOfficerList(query)
      .then((body) => {
        if (request !== latestRequest.current) return
        // 처리한 건이 다른 구분으로 옮겨 가면 보고 있던 쪽이 없어질 수 있다. 마지막 쪽을 다시 읽는다.
        if (body.page > body.page_count) {
          setQuery((prev) => ({ ...prev, page: body.page_count }))
          return
        }
        setList(body)
        setMock(isOfficerMockActive())
        setError('')
      })
      .catch((e: unknown) => {
        if (request === latestRequest.current) setError(e instanceof Error ? e.message : String(e))
      })
  }, [query])

  useEffect(() => { void reload() }, [reload])

  useEffect(() => {
    const path = showCriteria
      ? `${basePath}/criteria/${YOUTH_PROGRAM}`
      : open ? `${basePath}/${encodeURIComponent(query.role)}/review/${open.id}${open.reject ? '/reject' : ''}`
        : query.role === DEFAULT_QUERY.role ? basePath : `${basePath}/${encodeURIComponent(query.role)}`
    const params: Record<string, string | null> = {
      queue: !query.queue || query.queue === DEFAULT_QUERY.queue ? null : query.queue,
      page: query.page === DEFAULT_QUERY.page ? null : String(query.page ?? 1),
      page_size: query.page_size === DEFAULT_QUERY.page_size ? null : String(query.page_size ?? 20),
      sort: !query.sort || query.sort === DEFAULT_QUERY.sort ? null : String(query.sort),
      status: query.status === 'reject' ? 'reject' : null,
      slot: open?.slot ?? null,
    }
    for (const key of QUERY_KEYS) params[key] = query[key] ?? null
    routeUrl(path, params, initialUrlWrite.current)
    initialUrlWrite.current = false
  }, [query, open, showCriteria, basePath])

  const patch = (next: Partial<OfficerListQuery>) => {
    setQuery((prev) => ({ ...prev, ...next, program: YOUTH_PROGRAM }))
    setSelected([])
    setNotice('')
  }

  /** 역할을 바꾸면 관할 선택은 백엔드가 다시 정해준다 — 여기서는 비워 보낸다. */
  const switchRole = (role: string) => {
    if (!confirmOfficerLeave()) return
    setOpen(null)
    setShowCriteria(false)
    setQuery({ ...DEFAULT_QUERY, role })
    setSelected([])
    setNotice('')
  }

  /** 고른 건을 한 번에 처리한다. 끝나면(성공이든 실패든) 돌아오는 약속을 낸다. */
  const bulk = (decision: DecisionKey): Promise<void> => {
    if (!list || selected.length === 0) return Promise.resolve()
    setBusy(true)
    setNotice('')
    return postBulkDecision({
      role: list.role.key,
      decision,
      memo: `${list.role.name} 일괄 처리`,
      application_ids: selected,
      expected_revisions: Object.fromEntries(list.rows.filter((row) => selected.includes(row.application_id)).map((row) => [row.application_id, row.revision])),
    })
      .then(({ processed }) => {
        setSelected([])
        setNotice(query.queue === 'done'
          ? `${processed}건의 처리상태를 바꿨습니다.`
          : `${processed}건을 처리 완료로 옮겼습니다.`)
        return reload()
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false))
  }

  const activeRole = list?.role ?? roles.find((r) => r.key === query.role) ?? null
  const openId = open?.id
  const loadSummary = useCallback(() => openId ? fetchReviewDetail(openId, query.role) : Promise.reject(new Error('신청 건이 없습니다.')), [openId, query.role])

  return (
    <div className="officer">
      <header className="officer__head">
        <h2 className="officer__title">청년 취업지원패키지 신청 목록</h2>
        {/* 목업을 보고 있다는 사실을 숨기지 않는다. 이 배너가 없으면 시연을 보는
            사람이 실제 접수 건으로 오해한다. */}
        {mock && (open === null || isMockId(open.id)) && (
          <p className="officer__mock">
            <strong>목업 데이터</strong> 실제 접수 건이 없어 예시로 채운 화면입니다. 판단
            버튼은 눌리지만 브라우저 메모리에만 남고 새로고침하면 되돌아갑니다.
            <code>?mock=0</code>을 붙이면 실제 데이터만 봅니다.
          </p>
        )}
        <div className="officer__roles" role="group" aria-label="역할 전환">
          {roles.map((r) => (
            <button
              key={r.key}
              type="button"
              className={r.key === query.role ? 'officer__role officer__role--on' : 'officer__role'}
              onClick={() => switchRole(r.key)}
            >
              {r.name}
            </button>
          ))}
        </div>
        {activeRole && (
          <p className="officer__scope">
            <strong>{activeRole.stage}</strong> · 보이는 범위: {activeRole.scope}
          </p>
        )}
        {query.role === 'province' && <button type="button" className="officer__criteria-tab" onClick={() => { if (confirmOfficerLeave()) setShowCriteria((v) => !v) }}>
          {showCriteria ? '접수 목록' : '심사 기준'}
        </button>}
        {activeRole && (
          <ul className="officer__notes">
            {activeRole.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </header>

      {error && <p className="officer__error">{error}</p>}

      {showCriteria && query.role === 'province' ? (
        <section className="panel"><h2 className="panel__title">심사 기준 · 읽기 전용</h2><div className="panel__body"><p>취업지원패키지는 기존에 확정된 기준으로 운영합니다. 사업 설정 탭에서 기간과 안내를 확인할 수 있습니다.</p></div></section>
      ) : open?.reject ? (
        <RejectApplication
          key={`reject:${open.id}`}
          applicationId={open.id}
          role={query.role}
          load={loadSummary}
          onCancel={() => { if (confirmOfficerLeave()) setOpen({ id: open.id, slot: open.slot }) }}
          onSubmit={async (notice, memo, expectedRevision) => {
            await postDecision(open.id, { role: query.role, decision: 'reject', memo, notice, expected_revision: expectedRevision })
          }}
          verify={loadSummary}
          onSaved={() => {
            setOpen(null)
            setNotice('반려했습니다. 처리 완료 구분에서 확인할 수 있습니다.')
            void reload()
          }}
        />
      ) : open !== null ? (
        <ReviewDetail
          // 같은 건의 다른 서류로 다시 들어올 때 초기 탭 선택이 확실히 다시 돌게
          // 하는 값싼 보험이다.
          key={`${open.id}:${open.slot ?? ''}`}
          applicationId={open.id}
          role={query.role}
          initialSlotKey={open.slot}
          onBack={() => { if (confirmOfficerLeave()) setOpen(null) }}
          onReject={() => { if (confirmOfficerLeave()) setOpen({ id: open.id, slot: open.slot, reject: true }) }}
          onDecided={reload}
        />
      ) : list ? (
        <ApplicationList
          list={list}
          query={query}
          onQuery={patch}
          onOpen={(id, slot) => setOpen({ id, slot: slot ?? null })}
          selected={selected}
          onSelect={(ids) => {
            setSelected(ids)
            setNotice('')
          }}
          onBulk={bulk}
          busy={busy}
          notice={notice}
        />
      ) : showListSkeleton ? (
        <ApplicationListSkeleton />
      ) : null}
    </div>
  )
}
