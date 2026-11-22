/**
 * 진입점. 주소로 신청자 쪽과 담당자 쪽 중 하나를 고른다.
 *
 *   /officer...        담당자 쪽 (사업 목록 · 새 사업 · 사업 작업 공간)
 *   /apply...          신청자 쪽 (신청)
 *   그 밖(/ 포함)      ?mode=officer면 담당자, 아니면 신청자 (사업 찾기 · 사업 안내)
 *
 * 각 쪽의 입구(ApplicantApp, OfficerApp)가 자기 주소를 맡아 화면 하나를 올리고,
 * 주소도 자기 경로로 고쳐 쓴다. 그래서 한 번에 한 쪽만 마운트한다.
 */
import { lazy, Suspense, useEffect, useState } from 'react'

import { handleApplicantHistory } from './lib/applicant-navigation.ts'
import logo from './assets/brand/jbyouthhub-logo.png'
import { currentMode, goToHome, routeUrl, type Mode } from './navigation-url.ts'
import './app-shell.css'

/** 쪽별로 나눠 싣는다. 한쪽의 전역 CSS(.btn 등)가 다른 쪽 화면에 섞이지 않는다. */
const ApplicantApp = lazy(() => import('./pages/applicant/ApplicantApp.tsx'))
const OfficerApp = lazy(() => import('./pages/officer/OfficerApp.tsx'))

const TITLES: Record<Mode, string> = {
  applicant: '전북 청년정책 신청',
  officer: '전북 청년정책 담당자',
}

export default function App() {
  /** 문서를 불러올 때 한 번 정한다. 다른 화면으로는 새로 불러와야만 넘어간다. */
  const [mode] = useState<Mode>(currentMode)
  /** 값이 바뀌면 현재 화면이 새로 마운트돼 주소에서 상태를 다시 읽는다. */
  const [screenKey, setScreenKey] = useState(0)
  /** 담당자 머리글 오른쪽 자리. 로그인 상태·로그아웃 버튼을 여기에 그린다. */
  const [toolsHost, setToolsHost] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    const onHistoryChange = (event: PopStateEvent) => {
      if (handleApplicantHistory(event)) return
      // 한 번 실린 화면별 CSS는 내려가지 않는다. 다른 화면의 주소로 이동하면 문서를 새로 불러온다.
      if (currentMode() !== mode) {
        window.location.reload()
        return
      }
      setScreenKey((key) => key + 1)
    }
    window.addEventListener('popstate', onHistoryChange)
    return () => window.removeEventListener('popstate', onHistoryChange)
  }, [mode])

  useEffect(() => {
    document.title = TITLES[mode]
  }, [mode])

  const goHome = () => {
    if (mode === 'officer') routeUrl('/officer')
    else goToHome()
    setScreenKey((key) => key + 1)
    window.scrollTo({ top: 0 })
  }

  if (mode === 'officer') {
    return (
      <div className="app-shell app-shell--officer">
        <header className="shell">
          <div className="shell__inner">
            <button className="shell__home" type="button" onClick={goHome} aria-label="사업 목록으로 이동">
              <img className="shell__logo" src={logo} alt="전북청년허브센터" />
            </button>
            <span className="shell__role">담당자</span>
            <div className="shell__tools" ref={setToolsHost} />
          </div>
        </header>
        <Suspense fallback={null}>
          <OfficerApp key={screenKey} headerHost={toolsHost} />
        </Suspense>
      </div>
    )
  }

  return (
    <Suspense fallback={null}>
      <ApplicantApp key={screenKey} />
    </Suspense>
  )
}
