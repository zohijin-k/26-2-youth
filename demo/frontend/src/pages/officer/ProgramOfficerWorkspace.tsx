import { useId, useRef, useState, type KeyboardEvent } from 'react'
import { fetchOfficerPosting, type OfficerPosting } from '../../api.ts'
import { routeUrl } from '../../navigation-url.ts'
import GenericApplicationList from './GenericApplicationList.tsx'
import GenericReviewDetail from './GenericReviewDetail.tsx'
import OfficerConsole from './OfficerConsole.tsx'
import ProgramPreviewEditor from './ProgramPreviewEditor.tsx'
import { OfficerDrawer } from './OfficerModern.tsx'
import { officerLabel } from './officer-modern-model.ts'
import './program-officer-workspace.css'
import './program-modern-workspace.css'

type Tab = 'applications' | 'settings' | 'info'
const TABS = [['applications', '신청 목록'], ['settings', '사업 설정'], ['info', '사업 정보']] as const
export default function ProgramOfficerWorkspace({ posting, onBack }: { posting: OfficerPosting; onBack: () => void }) {
  const base = `/officer/programs/${posting.id}`
  const [info, setInfo] = useState(posting)
  const [tab, setTab] = useState<Tab>(() => { const value = new URLSearchParams(window.location.search).get('tab'); return value === 'settings' || value === 'info' ? value : 'applications' })
  const [application, setApplication] = useState<number | null>(() => { const match = /\/applications\/([1-9]\d*)\/?$/.exec(window.location.pathname); return match ? Number(match[1]) : null })
  const id = useId()
  const tabs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({})
  const [infoError, setInfoError] = useState('')
  const refreshInfo = () => { setInfoError(''); void fetchOfficerPosting(posting.id).then(setInfo).catch(() => setInfoError('사업 정보를 새로 불러오지 못했습니다.')) }
  const select = (next: Tab) => { setTab(next); setApplication(null); routeUrl(base, { tab: next }); window.scrollTo({ top: 0 }); if (next === 'info') refreshInfo() }
  const tabKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const at = TABS.findIndex(([key]) => key === tab)
    const next = event.key === 'ArrowRight' ? (at + 1) % TABS.length : event.key === 'ArrowLeft' ? (at + TABS.length - 1) % TABS.length : event.key === 'Home' ? 0 : event.key === 'End' ? TABS.length - 1 : -1
    if (next < 0) return
    event.preventDefault(); const key = TABS[next][0]; select(key); tabs.current[key]?.focus()
  }
  const chipTabs = <div className="om-chips om-workspace__tabs" role="tablist" aria-label="사업 작업 공간">{TABS.map(([key, label]) => <button ref={(element) => { tabs.current[key] = element }} type="button" role="tab" id={`${id}-${key}`} aria-selected={tab === key} aria-controls={`${id}-panel`} tabIndex={tab === key ? 0 : -1} className="om-chip" key={key} onClick={() => select(key)} onKeyDown={tabKey}>{label}</button>)}</div>
  const infoCard = <section className="om-card om-workspace__info"><h2>사업 정보</h2>{infoError && <p className="om-notice" role="alert">{infoError} <button type="button" className="om-text" onClick={refreshInfo}>다시 시도</button></p>}<dl><dt>신청 기간</dt><dd>{info.apply_start} ~ {info.apply_end}</dd><dt>상태</dt><dd>{posting.builtin ? info.phase_label : officerLabel(info.status)}</dd><dt>신청 수</dt><dd>{info.application_count}건</dd><dt>확인 필요</dt><dd>{info.needs_check_count}건</dd></dl></section>
  // The built-in workspace keeps the original list/review screens below a shared modern header.
  if (posting.builtin) return <div className="program-officer-workspace">
    <div className="om om-workspace program-officer-workspace__top">
      <OfficerDrawer postingId={posting.id} current={tab} onList={onBack} onTab={select} /><header className="om-head om-head--grid"><h1>{info.title}</h1><span className="om-chip om-chip--success">{info.phase_label}</span>{chipTabs}</header>
    </div>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${tab}`}>
      {tab === 'applications' && <OfficerConsole basePath={base} />}
      {tab === 'settings' && <div className="om om-workspace"><section className="om-card om-workspace__info"><h2>기본 사업 설정 · 읽기 전용</h2><dl><dt>사업명</dt><dd>{posting.title}</dd><dt>신청 기간</dt><dd>{posting.apply_start} ~ {posting.apply_end}</dd><dt>안내</dt><dd>{posting.guidance_text || '기존 사업의 확정된 기준으로 운영합니다.'}</dd></dl></section></div>}
      {tab === 'info' && <div className="om om-workspace">{infoCard}</div>}
    </div>
  </div>
  if (application) return <GenericReviewDetail postingId={posting.id} applicationId={application} onBack={() => select('applications')} />
  if (tab === 'settings') return <ProgramPreviewEditor postingId={posting.id} onBack={onBack} onPostingChanged={setInfo} focusHeadingOnLoad />
  return <main className="om om-page om-workspace">
    <OfficerDrawer postingId={posting.id} current={tab} onList={onBack} onTab={select} /><header className="om-head om-head--grid"><h1>{info.title}</h1><span className="om-chip">{officerLabel(info.status)}</span>{chipTabs}</header>
    <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${tab}`}>
      {tab === 'applications' ? <GenericApplicationList postingId={posting.id} onOpen={(applicationId) => { setApplication(applicationId); routeUrl(`${base}/applications/${applicationId}`, {}); window.scrollTo({ top: 0 }) }} /> : infoCard}
    </div>
  </main>
}
