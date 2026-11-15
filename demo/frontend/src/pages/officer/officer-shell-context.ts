import { createContext, type RefObject } from 'react'

export type OfficerTab = 'applications' | 'settings' | 'info'
export type OfficerShellLocation = 'list' | 'new' | OfficerTab

/** 지금 화면이 사이드바에 알리는 값. 이동 함수는 매번 바뀌므로 ref로 넘긴다. */
export interface OfficerShellNav {
  postingId?: number
  current?: OfficerShellLocation
  /** 참이면 사이드바 이동을 막는다(저장 안 한 수정, 처리 중 등). */
  disabled: boolean
  handlers: RefObject<{ onList?: () => void; onTab?: (tab: OfficerTab) => void }>
}

export const OfficerShellContext = createContext<((nav: OfficerShellNav | null) => void) | null>(null)
