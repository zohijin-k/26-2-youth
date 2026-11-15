import { useContext, useEffect, useRef } from 'react'
import { OfficerShellContext, type OfficerShellNav, type OfficerTab } from './officer-shell-context.ts'

/** 화면이 자기 위치와 이동 함수를 사이드바에 알린다. 그리는 것은 없다. */
export function useOfficerShellNav(nav: Omit<OfficerShellNav, 'handlers'> & {
  onList?: () => void; onTab?: (tab: OfficerTab) => void
}): void {
  const publish = useContext(OfficerShellContext)
  const handlers = useRef({ onList: nav.onList, onTab: nav.onTab })
  useEffect(() => { handlers.current = { onList: nav.onList, onTab: nav.onTab } })
  const { postingId, current, disabled } = nav
  useEffect(() => {
    if (!publish) return
    publish({ postingId, current, disabled, handlers })
    return () => publish(null)
  }, [publish, postingId, current, disabled])
}
