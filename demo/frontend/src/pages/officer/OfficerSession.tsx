import { confirmOfficerLeave } from './review-navigation.ts'
import { useEffect, useState, type ReactNode, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { officerReturnPath } from '../../officer-session.ts'
import { createModernNavigationRegistration, OfficerNavigationContext } from './officer-navigation-context.ts'
import './officer-fonts.css'
import './officer-session.css'
import './officer-modern-tokens.css'
import './officer-modern.css'
import './officer-entry-modern.css'

export default function OfficerSession({ children, headerHost = null }: { children: ReactNode; headerHost?: HTMLElement | null }) {
  const mock = new URLSearchParams(window.location.search).get('mock') === '1'
  const loginPage = window.location.pathname === '/officer/login'
  const [reauthenticate, setReauthenticate] = useState(false)
  const [sessionCheck, setSessionCheck] = useState(0)
  const [ready, setReady] = useState(mock)
  const [modernDrawerCount, setModernDrawerCount] = useState(0)
  const [registerModernDrawer] = useState(() => createModernNavigationRegistration(setModernDrawerCount))
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (mock) return
    let active = true
    let expiryTimer: ReturnType<typeof setTimeout> | undefined
    const expired = () => {
      if (!loginPage) { setReauthenticate(true); setError('로그인 시간이 끝났습니다. 입력은 이 탭에 유지됩니다. 다시 로그인해 주세요.') }
    }
    window.addEventListener('officer-session-expired', expired)
    {
      void fetch('/api/officer/session', { credentials: 'same-origin' }).then(async (response) => {
        if (!active) return
        if (response.status === 503 && loginPage) {
          const body = await response.json() as { detail?: string }
          if (active) setError(body.detail || '담당자 설정이 필요합니다.')
        } else if (!loginPage) {
          if (response.ok) {
            const body = await response.json() as { expires_at: number }
            if (!active) return
            const remaining = body.expires_at * 1000 - Date.now()
            if (!Number.isFinite(remaining) || remaining <= 0) { expired(); return }
            setReady(true); setReauthenticate(false)
            expiryTimer = setTimeout(expired, remaining)
          }
          else if (response.status === 401) expired()
          else setError(response.status === 503 ? '일시적으로 담당자 세션을 확인할 수 없습니다 (503).' : '담당자 세션을 확인하지 못했습니다.')
        }
      }).catch(() => { if (active) setError('서버에 연결하지 못했습니다. 다시 시도해 주세요.') })
    }
    return () => { active = false; clearTimeout(expiryTimer); window.removeEventListener('officer-session-expired', expired) }
  }, [mock, loginPage, sessionCheck])

  if (mock) return children
  const login = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/officer/login', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
      const body = await response.json().catch(() => null) as { detail?: string } | null
      setPassword('')
      if (!response.ok) { setError(body?.detail || '로그인하지 못했습니다.'); return }
      if (loginPage) window.location.replace(officerReturnPath(new URLSearchParams(window.location.search).get('returnTo')))
      else { setReady(true); setReauthenticate(false); setError(''); setSessionCheck((value) => value + 1) }
    } catch { setError('서버에 연결하지 못했습니다. 다시 시도해 주세요.') }
    finally { setBusy(false) }
  }
  const loginForm = <main className="om officer-login om-entry-login"><form onSubmit={(event) => void login(event)}>
    <span className="officer-login__eyebrow">전북 청년정책 · 담당자</span>
    <h1>담당자 로그인</h1>
    <label htmlFor="officer-password">담당자 비밀번호</label>
    <input id="officer-password" type="password" autoComplete="current-password" required autoFocus value={password}
      disabled={busy} onChange={(event) => setPassword(event.target.value)} />
    {error && <p role="alert">{error}</p>}
    <button className="btn btn--primary" disabled={busy} type="submit">{busy ? '확인 중' : '로그인'}</button>
  </form></main>
  if (loginPage) return loginForm
  if (!ready && !reauthenticate) return <main className="om officer-login om-entry-login"><p role={error ? 'alert' : 'status'}>{error || '담당자 세션을 확인하고 있습니다.'}</p><button type="button" className="btn" onClick={() => { setError(''); setSessionCheck((value) => value + 1) }}>다시 시도</button></main>
  // 로그인 상태 줄은 머리글 오른쪽 자리가 있으면 그곳에 그린다. 서랍이 있는 화면은 서랍의 로그아웃을 쓴다.
  const sessionBar = <div className="officer-session-bar"><span>담당자 로그인됨</span><button type="button" className="btn" onClick={() => {
    if (!confirmOfficerLeave()) return
    void fetch('/api/officer/logout', { method: 'POST', credentials: 'same-origin' }).then(() => window.location.replace('/officer/login'))
  }}>로그아웃</button></div>
  return <OfficerNavigationContext.Provider value={registerModernDrawer}>{!reauthenticate && modernDrawerCount === 0 && (headerHost ? createPortal(sessionBar, headerHost) : sessionBar)}<div hidden={reauthenticate} inert={reauthenticate}>{ready && children}</div>{reauthenticate && loginForm}</OfficerNavigationContext.Provider>
}
