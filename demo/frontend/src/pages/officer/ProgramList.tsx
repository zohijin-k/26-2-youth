import { useEffect, useState } from 'react'
import { fetchOfficerPostings, isOfficerMockCounted, type OfficerPosting } from '../../api.ts'
import { isPlainClick, routeHref, routeUrl } from '../../navigation-url.ts'
import { formatPeriod } from '../../posting-format.ts'
import { OfficerDrawer, OfficerMenu } from './OfficerModern.tsx'
import { officerLabel } from './officer-modern-model.ts'
import './officer.css'
import './program-list.css'
import './officer-entry-modern.css'

interface Props { onNew: () => void; onOpen: (posting: OfficerPosting) => void }
const count = (value: number) => `${value.toLocaleString('ko-KR')}건`
// A published program also closes when the server's application period has ended.
const displayStatus = (item: OfficerPosting) => item.phase === 'closed' ? 'closed' : item.status
export default function ProgramList({ onNew, onOpen }: Props) {
  const [items, setItems] = useState<OfficerPosting[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    fetchOfficerPostings().then((list) => {
      if (!active) return
      setItems([...list.filter((item) => item.phase === 'draft'), ...list.filter((item) => item.phase !== 'draft')])
    }).catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [attempt])
  const retry = () => { setFailed(false); setItems(null); setAttempt((value) => value + 1) }
  const openTab = (item: OfficerPosting, tab: 'settings' | 'info') => { onOpen(item); routeUrl(`/officer/programs/${item.id}`, { tab }) }
  return <main className="om om-page om-entry-list plist">
    <header className="om-head plist__head"><OfficerDrawer current="list" /><h1 className="plist__title">사업 목록</h1>
      {items && <span className="om-subtle">전체 {items.length.toLocaleString('ko-KR')}개</span>}
      <button type="button" className="btn btn--primary plist__new" onClick={onNew}>새 사업 올리기</button>
    </header>
    {items && isOfficerMockCounted() && <p className="om-subtle">합성 목업 데이터입니다.</p>}
    <div className="plist__body">
      {failed || items === null || items.length === 0 ? <div className="om-notice om-row" role={failed ? 'alert' : items === null ? 'status' : undefined}>
        <span>{failed ? '사업 목록을 불러오지 못했습니다.' : items === null ? '사업 목록을 불러오고 있습니다.' : '등록된 사업이 없습니다.'}</span>
        <button type="button" className="btn" onClick={retry}>다시 시도</button>
      </div> : <ul className="plist__grid">{items.map((item) => <li key={item.id} className="om-program-card">
        <div className="om-row om-program-top"><span className={`om-chip${displayStatus(item) === 'draft' ? ' om-chip--warning' : displayStatus(item) === 'published' ? ' om-chip--success' : ''}`}>{officerLabel(displayStatus(item))}</span>
          {item.builtin && <span className="om-subtle">기본 사업 · 읽기 전용</span>}
          {!item.builtin && <OfficerMenu label={`${item.title} 더보기`} actions={[
            { label: '사업 설정', onSelect: () => openTab(item, 'settings') },
            { label: '사업 정보', onSelect: () => openTab(item, 'info') },
          ]} />}
        </div>
        <a className="plist__card" href={routeHref(`/officer/programs/${item.id}`)} onClick={(event) => {
          if (!isPlainClick(event)) return
          event.preventDefault(); onOpen(item)
        }}>
          <strong className="plist__name">{item.title}</strong>
          <span className="plist__period">{formatPeriod(item.apply_start, item.apply_end)}</span>
          <span className="plist__stats"><span>신청 <strong>{count(item.application_count)}</strong></span>
            <span className={item.needs_check_count > 0 ? 'om-program-pending' : undefined}>확인 필요 <strong>{count(item.needs_check_count)}</strong></span>
          </span>
        </a>
      </li>)}</ul>}
    </div>
  </main>
}
