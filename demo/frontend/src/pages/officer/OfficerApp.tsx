/**
 * 담당자 화면의 입구. 주소 하나에 화면 하나만 올린다.
 *
 *   /officer                    사업 목록
 *   /officer/programs/new       새 사업 올리기
 *   /officer/programs/:id...    사업 작업 공간 (기본 사업은 접수 목록·심사 화면)
 *
 * 리뉴얼 전의 주소(`/officer/<역할>`, `/officer/<역할>/review/<번호>`,
 * `/officer/criteria/<사업>`, 목록 필터가 붙은 `/officer?...`)는 기본 사업의 작업
 * 공간으로 옮겨 같은 목록·상세를 연다. 기본 사업의 번호는 서버에 물어야 알 수
 * 있어서, 옮기는 일은 작업 공간이 사업을 찾은 직후에 한다.
 */
import { useCallback, useEffect, useState } from 'react'

import type { OfficerPosting } from '../../api.ts'
import { currentParams, routeUrl } from '../../navigation-url.ts'
import NewProgram from './OneShotNewProgram.tsx'
import ProgramList from './ProgramList.tsx'
import ProgramWorkspace from './ProgramWorkspace.tsx'
import OfficerSession from './OfficerSession.tsx'

type Route =
  | { screen: 'list' }
  | { screen: 'new' }
  | { screen: 'workspace'; target: number | 'builtin'; posting?: OfficerPosting }

/** 예전 접수 목록이 주소에 쓰던 값. 하나라도 있으면 목록·상세로 가던 링크다. */
const OLD_LIST_PARAMS = [
  'role', 'region', 'town', 'status', 'ai', 'submitted_from', 'submitted_to', 'page', 'page_size', 'slot',
]

function readRoute(): Route {
  const path = window.location.pathname
  if (/^\/officer\/programs\/new\/?$/.test(path)) return { screen: 'new' }
  const workspace = /^\/officer\/programs\/([1-9]\d*)(?:\/.*)?$/.exec(path)
  if (workspace) return { screen: 'workspace', target: Number(workspace[1]) }
  if (/^\/officer\/programs(?:\/.*)?$/.test(path)) return { screen: 'list' }
  const params = currentParams()
  const oldPath = /^\/officer\/[^/]/.test(path)
  const oldQuery = [...params.keys()].some((key) => OLD_LIST_PARAMS.includes(key) || key.startsWith('o_'))
  return oldPath || oldQuery ? { screen: 'workspace', target: 'builtin' } : { screen: 'list' }
}

/** 예전 주소를 기본 사업의 작업 공간 주소로 고쳐 쓴다. 뒤에 붙은 경로와 값은 그대로 둔다. */
function moveOldLink(postingId: number): void {
  const path = window.location.pathname
  if (path.startsWith('/officer/programs/')) return
  const rest = /^\/officer\/[^/]/.test(path) ? path.slice('/officer'.length).replace(/\/$/, '') : ''
  const keep: Record<string, string | null> = {}
  for (const [key, value] of currentParams()) {
    if (key !== 'mode') keep[key] = value
  }
  routeUrl(`/officer/programs/${postingId}${rest}`, keep, true)
}

function OfficerScreens() {
  const [route, setRoute] = useState<Route>(readRoute)

  // `?mode=officer`로 들어왔거나 알 수 없는 주소면 사업 목록의 주소로 맞춘다.
  useEffect(() => {
    if (route.screen === 'list') routeUrl('/officer', {}, true)
  }, [route])

  const go = useCallback((next: Route, path: string, replace = false) => {
    routeUrl(path, {}, replace)
    setRoute(next)
    window.scrollTo({ top: 0 })
  }, [])

  const toList = useCallback(() => go({ screen: 'list' }, '/officer'), [go])
  /** 지운 사업이나 없는 기본 사업의 주소는 방문 기록에 남기지 않는다. */
  const replaceWithList = useCallback(() => go({ screen: 'list' }, '/officer', true), [go])

  if (route.screen === 'new') {
    return (
      <NewProgram
        onCancel={toList}
        onCreated={(posting) => { go(
          { screen: 'workspace', target: posting.id, posting }, `/officer/programs/${posting.id}`, true,
        ); routeUrl(`/officer/programs/${posting.id}`, { tab: 'settings' }, true) }}
      />
    )
  }

  if (route.screen === 'workspace') {
    return (
      <ProgramWorkspace
        key={route.target}
        target={route.target}
        initialPosting={route.posting}
        onBuiltinFound={moveOldLink}
        onBack={toList}
        onGone={replaceWithList}
      />
    )
  }

  return (
    <ProgramList
      onNew={() => go({ screen: 'new' }, '/officer/programs/new')}
      onOpen={(posting) => go(
        { screen: 'workspace', target: posting.id, posting }, `/officer/programs/${posting.id}`,
      )}
    />
  )
}

export default function OfficerApp() {
  return <OfficerSession><OfficerScreens /></OfficerSession>
}
