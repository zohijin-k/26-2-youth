import { useEffect, useState } from 'react'
import { fetchOfficerPosting, fetchOfficerPostings, isNotFound, type OfficerPosting } from '../../api.ts'
import ProgramOfficerWorkspace from './ProgramOfficerWorkspace.tsx'
import './officer.css'
import './program-workspace.css'

interface Props {
  target: number | 'builtin'; initialPosting?: OfficerPosting; onBuiltinFound: (id: number) => void
  onBack: () => void; onGone: () => void
}
export default function ProgramWorkspace({ target, initialPosting, onBuiltinFound, onBack, onGone }: Props) {
  const [posting, setPosting] = useState<OfficerPosting | null>(initialPosting || null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let current = true
    const load = typeof target === 'number' ? fetchOfficerPosting(target) : fetchOfficerPostings().then((items) => items.find((item) => item.builtin) || null)
    load.then((found) => {
      if (!current) return
      if (!found) { onGone(); return }
      if (target === 'builtin') onBuiltinFound(found.id)
      setPosting(found); setError('')
    }).catch((problem: unknown) => {
      if (!current) return
      if (isNotFound(problem)) { onGone(); return }
      setError('사업 정보를 불러오지 못했습니다.')
    })
    return () => { current = false }
  }, [target, attempt, onBuiltinFound, onGone])
  if (!posting) return <main className="pwork pwork--page"><button className="btn" onClick={onBack}>사업 목록</button><p role={error ? 'alert' : 'status'}>{error || '사업 정보를 불러오고 있습니다.'}</p>{error && <button className="btn" onClick={() => setAttempt((value) => value + 1)}>다시 시도</button>}</main>
  return <ProgramOfficerWorkspace posting={posting} onBack={onBack} />
}
