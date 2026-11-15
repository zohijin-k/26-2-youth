import { useState } from 'react'
import { fetchOfficerPosting, type OfficerPosting } from '../../api.ts'
import { routeUrl } from '../../navigation-url.ts'
import GenericApplicationList from './GenericApplicationList.tsx'
import GenericReviewDetail from './GenericReviewDetail.tsx'
import OfficerConsole from './OfficerConsole.tsx'
import ProgramPreviewEditor from './ProgramPreviewEditor.tsx'
import './program-officer-workspace.css'

type Tab = 'applications' | 'settings' | 'info'
export default function ProgramOfficerWorkspace({ posting, onBack }: { posting: OfficerPosting; onBack: () => void }) {
  const base = `/officer/programs/${posting.id}`
  const [info, setInfo] = useState(posting)
  const [tab, setTab] = useState<Tab>(() => { const value = new URLSearchParams(window.location.search).get('tab'); return value === 'settings' || value === 'info' ? value : 'applications' })
  const [application, setApplication] = useState<number | null>(() => { const match = /\/applications\/([1-9]\d*)\/?$/.exec(window.location.pathname); return match ? Number(match[1]) : null })
  const select = (next: Tab) => { setTab(next); setApplication(null); routeUrl(base, { tab: next }); window.scrollTo({ top: 0 }); if (next === 'info') void fetchOfficerPosting(posting.id).then(setInfo).catch(() => undefined) }
  if (!posting.builtin && application) return <GenericReviewDetail postingId={posting.id} applicationId={application} onBack={() => select('applications')} />
  return <div className="program-officer-workspace">
    <header className="program-officer-workspace__head"><button type="button" className="btn" onClick={onBack}>사업 목록</button><h1>{info.title}</h1><span>{info.phase_label}</span></header>
    <nav className="program-officer-workspace__tabs" aria-label="사업 작업 공간">{([['applications', '신청 목록'], ['settings', '사업 설정'], ['info', '사업 정보']] as const).map(([key, label]) => <button type="button" className="btn" aria-current={tab === key ? 'page' : undefined} key={key} onClick={() => select(key)}>{label}</button>)}</nav>
    {tab === 'applications' && (posting.builtin ? <OfficerConsole basePath={base} /> : <GenericApplicationList postingId={posting.id} onOpen={(id) => { setApplication(id); routeUrl(`${base}/applications/${id}`, {}); window.scrollTo({ top: 0 }) }} />)}
    {tab === 'settings' && (posting.builtin ? <section className="program-officer-workspace__info"><h2>기본 사업 설정 · 읽기 전용</h2><p>{posting.title}</p><p>{posting.apply_start} ~ {posting.apply_end}</p><p>{posting.guidance_text || '기존 사업의 확정된 기준으로 운영합니다.'}</p></section> : <ProgramPreviewEditor postingId={posting.id} onBack={onBack} onPostingChanged={setInfo} />)}
    {tab === 'info' && <section className="program-officer-workspace__info"><h2>사업 정보</h2><dl><dt>신청 기간</dt><dd>{info.apply_start} ~ {info.apply_end}</dd><dt>상태</dt><dd>{info.phase_label}</dd><dt>신청 수</dt><dd>{info.application_count}건</dd><dt>확인 필요</dt><dd>{info.needs_check_count}건</dd></dl></section>}
  </div>
}
