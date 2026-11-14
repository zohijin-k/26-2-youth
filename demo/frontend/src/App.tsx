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
  const [headerHost, setHeaderHost] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    const onHistoryChange = () => {
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
        <nav className="shell" aria-label="담당자 화면">
          <span className="shell__title">
            <button className="shell__mark" type="button" onClick={goHome} aria-label="사업 목록으로 이동">
              전북
            </button>
            <span>
              <strong>전북 청년정책</strong>
              <small>담당자 사업 관리·신청서류 검토</small>
            </span>
          </span>
        </nav>
        <Suspense fallback={null}>
          <OfficerApp key={screenKey} />
        </Suspense>
      </div>
    )
  }

  return (
    <div className="app-shell app-shell--applicant">
      <nav className="shell" aria-label="신청 서비스">
        <div className="shell__inner">
          <span className="shell__title">
            <button className="shell__mark" type="button" onClick={goHome} aria-label="사업 찾기로 이동">전북</button>
            <span><strong>전북 청년정책 신청</strong></span>
          </span>
          <div ref={setHeaderHost} className="shell__application" />
        </div>
      </nav>
      <Suspense fallback={null}>
        <ApplicantApp key={screenKey} headerHost={headerHost} />
      </Suspense>
    </div>
  )
}
