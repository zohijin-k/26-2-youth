import { confirmOfficerLeave } from './review-navigation.ts'
/**
 * 담당자 화면 틀: 왼쪽 사이드바 + 본문.
 *
 * 각 화면은 예전처럼 <OfficerDrawer …/>를 그리지만, 이제 그 컴포넌트는 아무것도 그리지 않고
 * 현재 위치 · 잠금 여부 · 이동 함수를 이 틀에 알려 준다. 그래서 저장 안 한 수정이 있을 때
 * 이동을 막는 등 화면마다의 규칙이 사이드바에도 그대로 적용된다.
 *
 * 메뉴 버튼은 흰 머리글 오른쪽 자리(headerHost)에 그린다. 넓은 화면에서는 사이드바를 접고
 * 펼치고, 좁은 화면에서는 사이드바를 본문 위에 겹쳐 연다.
 *
 * 새 신청 알림: 사업 목록 API의 신청 수를 주기적으로 다시 받아, 이 브라우저에서 마지막으로
 * 본 수보다 늘어난 만큼을 숫자 뱃지로 보여 준다. 그 사업의 신청 목록을 열면 본 것으로 친다.
 */
import { useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { fetchOfficerPostings, type OfficerPosting } from '../../api.ts'
import { isPlainClick } from '../../navigation-url.ts'
import { OfficerNavigationContext } from './officer-navigation-context.ts'
import { OfficerShellContext, type OfficerShellNav, type OfficerTab } from './officer-shell-context.ts'
import { badgeLabel, newApplicationCounts, readSeenCounts, writeSeenCounts, type SeenCounts } from './officer-badges.ts'
import { officerDestination } from './officer-modern-model.ts'
import './officer-shell.css'

const POLL_MS = 30_000
const SIDEBAR_KEY = 'officer-sidebar-open'
const NARROW = '(max-width: 1279px)'

function readSidebarPreference(): boolean {
  try {
    if (window.matchMedia(NARROW).matches) return false
    return window.localStorage.getItem(SIDEBAR_KEY) !== '0'
  } catch { return true }
}

interface Props {
  headerHost: HTMLElement | null
  onList: () => void
  onNew: () => void
  onProgram: (posting: OfficerPosting, tab?: OfficerTab) => void
  children: ReactNode
}

export default function OfficerShell({ headerHost, onList, onNew, onProgram, children }: Props) {
  const [nav, setNav] = useState<OfficerShellNav | null>(null)
  const [open, setOpen] = useState(readSidebarPreference)
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches)
  const [postings, setPostings] = useState<OfficerPosting[]>([])
  const [seen, setSeen] = useState<SeenCounts>(readSeenCounts)
  const [tip, setTip] = useState<{ text: string; top: number; left: number } | null>(null)
  const sideId = useId()
  const side = useRef<HTMLElement>(null)
  const toggle = useRef<HTMLButtonElement>(null)

  // 사이드바가 로그아웃을 맡으므로 예전 로그인 상태 줄은 숨긴다.
  const registerNavigation = useContext(OfficerNavigationContext)
  useEffect(() => registerNavigation?.(), [registerNavigation])

  useEffect(() => {
    const media = window.matchMedia(NARROW)
    const change = () => { setNarrow(media.matches); setOpen(media.matches ? false : readSidebarPreference()) }
    media.addEventListener('change', change)
    return () => media.removeEventListener('change', change)
  }, [])

  // 처음 보는 사업은 지금 수를 기준으로 삼는다(첫 방문에 뱃지가 쏟아지지 않게).
  // 보고 있는 사업의 신청 목록이 열려 있으면 늘어난 건도 본 것으로 친다.
  const navRef = useRef<OfficerShellNav | null>(null)
  const postingsRef = useRef<OfficerPosting[]>([])
  const reconcileSeen = useCallback(() => {
    const viewing = navRef.current
    const list = postingsRef.current
    if (!list.length) return
    setSeen((previous) => {
      let next: SeenCounts | null = null
      for (const item of list) {
        const here = viewing?.postingId === item.id && viewing.current === 'applications'
        if (previous[item.id] === undefined || (here && previous[item.id] !== item.application_count)) {
          next ??= { ...previous }
          next[item.id] = item.application_count
        }
      }
      if (!next) return previous
      writeSeenCounts(next)
      return next
    })
  }, [])

  // 신청 수를 주기적으로 다시 받는다. 탭이 보이지 않는 동안은 쉬고, 다시 보이면 바로 받는다.
  const refresh = useCallback(() => {
    void fetchOfficerPostings().then((list) => {
      postingsRef.current = list
      setPostings(list)
      reconcileSeen()
    }).catch(() => {})
  }, [reconcileSeen])
  useEffect(() => {
    refresh()
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') refresh() }, POLL_MS)
    const visible = () => { if (document.visibilityState === 'visible') refresh() }
    document.addEventListener('visibilitychange', visible)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', visible) }
  }, [refresh])

  // 화면이 위치를 알릴 때마다 받는다. 화면을 옮기면 목록을 새로 받는다(새 사업을 올렸거나 지웠을 수 있다).
  const publishNav = useCallback((next: OfficerShellNav | null) => {
    const before = navRef.current
    navRef.current = next
    setNav(next)
    if (next && (next.postingId !== before?.postingId || next.current !== before?.current)) {
      reconcileSeen()
      refresh()
    }
  }, [reconcileSeen, refresh])

  const badges = newApplicationCounts(postings, seen)
  const total = Object.values(badges).reduce((sum, value) => sum + value, 0)

  useEffect(() => {
    const base = '전북 청년정책 담당자'
    document.title = total > 0 ? `(${total}) ${base}` : base
  }, [total])

  const setSidebar = (next: boolean) => {
    setOpen(next)
    if (!narrow) { try { window.localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0') } catch { /* 저장 못 해도 동작은 같다 */ } }
  }

  // 좁은 화면의 겹친 사이드바: Esc로 닫고 메뉴 버튼으로 포커스를 돌려준다.
  useEffect(() => {
    if (!narrow || !open) return
    side.current?.querySelector<HTMLElement>('a,button')?.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault(); setOpen(false); toggle.current?.focus()
    }
    document.addEventListener('keydown', keydown)
    return () => document.removeEventListener('keydown', keydown)
  }, [narrow, open])

  const locked = nav?.disabled ?? false
  const after = () => { if (narrow) setOpen(false) }
  const goList = () => { const handler = nav?.handlers.current.onList; if (handler) handler(); else onList(); after() }
  const goProgram = (item: OfficerPosting, tab: OfficerTab = 'applications') => {
    const onTab = nav?.handlers.current.onTab
    if (nav?.postingId === item.id && onTab) onTab(tab)
    else onProgram(item, tab)
    after()
  }
  // 잘린 사업명은 마우스를 올리거나 키보드로 닿으면 바로 전체 이름을 띄운다.
  // 브라우저 기본 title 말풍선은 늦게 뜨고 환경에 따라 안 뜨므로 쓰지 않는다.
  const showTip = (anchor: HTMLElement, text: string) => {
    const name = anchor.querySelector<HTMLElement>('.osb__program-name')
    if (!name || name.scrollWidth <= name.clientWidth) { setTip(null); return }
    const rect = anchor.getBoundingClientRect()
    setTip({ text, top: rect.top + rect.height / 2, left: rect.right + 8 })
  }
  const hideTip = () => setTip(null)
  const link = (label: ReactNode, href: string, active: boolean, run: () => void, className = 'osb__link', tipText?: string) => <a
    className={className} href={href} aria-current={active ? 'page' : undefined} aria-disabled={locked || undefined}
    onMouseEnter={tipText ? (event) => showTip(event.currentTarget, tipText) : undefined}
    onFocus={tipText ? (event) => showTip(event.currentTarget, tipText) : undefined}
    onMouseLeave={tipText ? hideTip : undefined}
    onBlur={tipText ? hideTip : undefined}
    onClick={(event) => {
      if (!isPlainClick(event)) return
      event.preventDefault()
      hideTip()
      if (!locked) run()
    }}>{label}</a>

  const menuButton = <button ref={toggle} type="button" className="osb-toggle" aria-label={total > 0 ? `메뉴 · 새 신청 ${total}건` : '메뉴'}
    aria-expanded={open} aria-controls={sideId} onClick={() => setSidebar(!open)}>
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><path d="M4 6.5h16M4 12h16M4 17.5h16" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none" /></svg>
    <span className="osb-toggle__label">메뉴</span>
    {total > 0 && <span className="osb-badge osb-badge--toggle" aria-hidden="true">{badgeLabel(total)}</span>}
  </button>

  return <OfficerShellContext.Provider value={publishNav}>
    {headerHost && createPortal(menuButton, headerHost)}
    <div className={`osb${open ? ' osb--open' : ' osb--closed'}${narrow ? ' osb--narrow' : ''}`}>
      {narrow && open && <div className="osb__shade" onPointerDown={() => setOpen(false)} />}
      <aside ref={side} id={sideId} className="om osb__side" aria-label="담당자 메뉴" hidden={!open} onScroll={hideTip}>
        <nav className="osb__nav" aria-label="담당자 이동">
          {link(<><span>사업 목록</span>{total > 0 && <span className="osb-badge" aria-label={`새 신청 ${total}건`}>{badgeLabel(total)}</span>}</>, officerDestination('/officer'), nav?.current === 'list', goList)}
          {link(<span>새 사업 올리기</span>, officerDestination('/officer/programs/new'), nav?.current === 'new', () => { onNew(); after() })}
        </nav>
        {postings.length > 0 && <nav className="osb__nav osb__programs" aria-label="사업 바로가기">
          <p className="osb__section">사업</p>
          {postings.map((item) => {
            const here = nav?.postingId === item.id
            const count = badges[item.id] ?? 0
            return <div key={item.id} className={here ? 'osb__program is-current' : 'osb__program'}>
              {link(<><span className="osb__program-name">{item.title}</span>{count > 0 && <span className="osb-badge" aria-label={`새 신청 ${count}건`}>{badgeLabel(count)}</span>}</>,
                officerDestination(`/officer/programs/${item.id}`), false, () => goProgram(item), 'osb__link', item.title)}
              {here && <div className="osb__sub">
                {link('신청 목록', officerDestination(`/officer/programs/${item.id}`, 'applications'), nav?.current === 'applications', () => goProgram(item, 'applications'), 'osb__sublink')}
                {link('사업 설정', officerDestination(`/officer/programs/${item.id}`, 'settings'), nav?.current === 'settings', () => goProgram(item, 'settings'), 'osb__sublink')}
                {link('사업 정보', officerDestination(`/officer/programs/${item.id}`, 'info'), nav?.current === 'info', () => goProgram(item, 'info'), 'osb__sublink')}
              </div>}
            </div>
          })}
        </nav>}
        <div className="osb__foot">
          {locked && <p className="osb__lock" role="status">저장하지 않은 수정이 있어 이동할 수 없습니다.</p>}
          <button type="button" className="osb__logout" onClick={() => {
            if (!confirmOfficerLeave()) return
            void fetch('/api/officer/logout', { method: 'POST', credentials: 'same-origin' }).then((response) => {
              if (response.ok) window.location.assign('/officer/login')
            })
          }}>로그아웃</button>
        </div>
      </aside>
      <div className="osb__main">{children}</div>
    </div>
    {tip && open && createPortal(<div role="tooltip" className="osb-tip" style={{ top: tip.top, left: tip.left, maxWidth: `min(360px, calc(100vw - ${Math.round(tip.left) + 12}px))` }}>{tip.text}</div>, document.body)}
  </OfficerShellContext.Provider>
}
