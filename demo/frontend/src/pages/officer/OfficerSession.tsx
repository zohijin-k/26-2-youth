import { useEffect, useState, type ReactNode, type FormEvent } from 'react'
import { officerLoginUrl, officerReturnPath } from '../../officer-session.ts'
import './officer-session.css'

export default function OfficerSession({ children }: { children: ReactNode }) {
  const mock = new URLSearchParams(window.location.search).get('mock') === '1'
  const loginPage = window.location.pathname === '/officer/login'
  const [ready, setReady] = useState(mock)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (mock) return
    let active = true
    let expiryTimer: ReturnType<typeof setTimeout> | undefined
    const expired = () => {
      if (!loginPage) window.location.replace(officerLoginUrl(window.location.pathname + window.location.search))
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
            setReady(true)
            expiryTimer = setTimeout(expired, remaining)
          }
          else expired()
        }
      }).catch(() => { if (active) setError('서버에 연결하지 못했습니다. 새로고침해 주세요.') })
    }
    return () => { active = false; clearTimeout(expiryTimer); window.removeEventListener('officer-session-expired', expired) }
  }, [mock, loginPage])

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
      window.location.replace(officerReturnPath(new URLSearchParams(window.location.search).get('returnTo')))
    } catch { setError('서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.') }
    finally { setBusy(false) }
  }
  if (loginPage) return <main className="officer-login"><form onSubmit={(event) => void login(event)}>
    <span className="officer-login__eyebrow">전북 청년정책 · 담당자</span>
    <h1>담당자 로그인</h1><p>사업 관리와 신청서류 검토를 시작합니다.</p>
    <label htmlFor="officer-password">담당자 비밀번호</label>
    <input id="officer-password" type="password" autoComplete="current-password" required autoFocus value={password}
      disabled={busy} onChange={(event) => setPassword(event.target.value)} />
    {error && <p role="alert">{error}</p>}
    <button className="btn btn--primary" disabled={busy} type="submit">{busy ? '확인 중' : '로그인'}</button>
    <small>역할과 지역은 로그인한 뒤 선택합니다.</small>
  </form></main>
  if (!ready) return <main className="officer-login" role={error ? 'alert' : 'status'}>{error || '담당자 세션을 확인하고 있습니다.'}</main>
  return <><div className="officer-session-bar"><span>담당자 로그인됨</span><button type="button" className="btn" onClick={() => {
    void fetch('/api/officer/logout', { method: 'POST', credentials: 'same-origin' }).then(() => window.location.replace('/officer/login'))
  }}>로그아웃</button></div>{children}</>
}
