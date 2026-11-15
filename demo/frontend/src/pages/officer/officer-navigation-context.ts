import { createContext } from 'react'

export type ModernNavigationRegistration = () => () => void

/** Mounted modern drawers own logout; the final cleanup restores the legacy bar. */
export function createModernNavigationRegistration(onCountChanged: (count: number) => void): ModernNavigationRegistration {
  let count = 0
  return () => {
    count += 1
    onCountChanged(count)
    let active = true
    return () => {
      if (!active) return
      active = false
      count -= 1
      onCountChanged(count)
    }
  }
}

export const OfficerNavigationContext = createContext<ModernNavigationRegistration | null>(null)
