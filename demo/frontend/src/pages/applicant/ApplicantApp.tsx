/**
 * 신청자 화면의 입구. 주소 하나에 화면 하나만 올린다.
 *
 *   /               사업 찾기
 *   /programs/:id   사업 안내
 *   /apply...       신청 (기존 ApplyFlow)
 *
 * ApplyFlow는 마운트되자마자 신청 건을 만들거나 복원한다. 그래서 사업을 찾아보는
 * 동안에는 올리지 않는다 — "신청하기"를 눌러 /apply로 들어올 때만 올린다.
 */
import { useEffect, useState } from 'react'

import { routeUrl } from '../../navigation-url.ts'
import logo from '../../assets/brand/jbyouthhub-logo.png'
import ApplyFlow from './ApplyFlow.tsx'
import ProgramFinder from './ProgramFinder.tsx'
import ProgramInfo from './ProgramInfo.tsx'
import '../../styles/tokens.css'
import '../../styles/base.css'
import '../../styles/components.css'
import './applicant-shell.css'


type Route = { screen: 'finder' } | { screen: 'info'; id: number } | { screen: 'flow' }

function readRoute(): Route {
  const path = window.location.pathname
  if (path.startsWith('/apply')) return { screen: 'flow' }
  const info = /^\/programs\/([1-9]\d*)\/?$/.exec(path)
  if (info) return { screen: 'info', id: Number(info[1]) }
  return { screen: 'finder' }
}

export default function ApplicantApp() {
  const [headerHost, setHeaderHost] = useState<HTMLDivElement | null>(null)
  const [route, setRoute] = useState<Route>(readRoute)

  // 알 수 없는 주소는 사업 찾기로 보고 주소도 맞춘다.
  useEffect(() => {
    if (route.screen === 'finder') routeUrl('/', {}, true)
  }, [route])

  const go = (next: Route, path: string) => {
    routeUrl(path)
    setRoute(next)
    window.scrollTo({ top: 0 })
  }

  const content = route.screen === 'flow' ? <ApplyFlow headerHost={headerHost} /> : route.screen === 'info' ? (
      <ProgramInfo
        key={route.id}
        postingId={route.id}
        onBack={() => go({ screen: 'finder' }, '/')}
        onApply={(path) => {
          // 신청 화면은 같은 쪽이라 문서를 다시 부르지 않는다. 그 밖의 주소는 통째로 이동한다.
          if (path.startsWith('/apply')) go({ screen: 'flow' }, path)
          else window.location.assign(path)
        }}
      />
  ) : <ProgramFinder onOpen={(id) => go({ screen: 'info', id }, `/programs/${id}`)} />

  return (
    <div className="app-shell app-shell--applicant">
      <a className="skip-link" href="#main">본문으로 건너뛰기</a>
      <header className="shell">
        <div className="shell__inner">
          <button type="button" className="shell__home" onClick={() => go({ screen: 'finder' }, '/')} aria-label="사업 찾기로 이동">
            <img className="shell__logo" src={logo} alt="전북지역거점 청년지원센터 전북청년허브센터" />
          </button>
          <div className="shell__tools" ref={setHeaderHost} />
        </div>
      </header>
      <main id="main" className="shell-main" tabIndex={-1}>{content}</main>
      <footer className="site-footer"><div className="site-footer__inner"><p className="site-footer__service">
        {route.screen === 'flow' && <strong>「전북청년 취업지원패키지」 신청</strong>}
        <span>전북청년허브센터</span>
      </p></div></footer>
    </div>
  )
}
