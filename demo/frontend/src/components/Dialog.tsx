/**
 * 신청자 화면의 대화상자. 화면 맨 위(body 바로 아래)에 그린다.
 * 열리면 제목으로 포커스를 옮기고, Tab은 대화상자 안에서만 돌며, Esc로 닫고, 닫힌 뒤에는 연 자리로 포커스를 돌려준다.
 * 열려 있는 동안 뒤 화면은 `inert`로 조작할 수 없고 스크롤되지 않는다.
 *
 * 담당자 화면이 함께 쓰는 components/Modal.tsx와는 따로 둔다(담당자 화면 모양이 바뀌지 않게).
 * 모양은 styles/components.css의 `.dialog*`에 있다.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import Icon from './Icon.tsx'
import { guardDialogTab } from '../lib/dialog-tab.ts'

const openDialogs: HTMLElement[] = []
const FOCUSABLE = 'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'

export default function Dialog({ title, description, onClose, returnFocus, children, footer, size = 'md', closeOnOverlay = true, className = '' }: {
  title: string
  description?: string
  onClose: () => void
  /** 연 자리가 사라졌을 때 포커스를 돌려줄 곳. */
  returnFocus?: () => HTMLElement | null
  children?: ReactNode
  footer?: ReactNode
  /** 폭: sm 400px · md 560px · lg 760px. */
  size?: 'sm' | 'md' | 'lg'
  /** 바깥 어두운 영역을 눌러 닫을지. 확인 대화상자는 false로 둔다. */
  closeOnOverlay?: boolean
  className?: string
}) {
  const id = useId()
  const [host] = useState(() => document.createElement('div'))
  const dialog = useRef<HTMLDivElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const focusFallback = useRef(returnFocus)
  const close = useRef(onClose)
  useEffect(() => { close.current = onClose; focusFallback.current = returnFocus }, [onClose, returnFocus])

  useEffect(() => {
    const origin = document.activeElement instanceof HTMLElement ? document.activeElement : null
    document.body.append(host)
    const background = Array.from(document.body.children)
      .filter((node): node is HTMLElement => node instanceof HTMLElement && node !== host)
      .map((node) => ({ node, inert: node.inert }))
    for (const { node } of background) node.inert = true
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    openDialogs.push(host)
    heading.current?.focus()
    const dialogControls = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
      .filter((node) => node.getClientRects().length > 0 && !node.closest('[inert]'))
    const onKey = (event: KeyboardEvent) => {
      if (openDialogs.at(-1) !== host) return
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        close.current()
        return
      }
      if (event.key !== 'Tab') return
      const controls = dialogControls()
      const first = controls[0]
      const last = controls.at(-1)
      if (!first) { event.preventDefault(); heading.current?.focus(); return }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
        event.preventDefault(); last?.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.current?.contains(document.activeElement))) {
        event.preventDefault(); first.focus()
      }
    }
    const onFocus = (event: FocusEvent) => {
      if (openDialogs.at(-1) === host && !dialog.current?.contains(event.target as Node)) heading.current?.focus()
    }
    document.addEventListener('keydown', onKey, true)
    document.addEventListener('focusin', onFocus)
    const releaseTab = guardDialogTab(() => (openDialogs.at(-1) === host ? dialog.current : null), dialogControls)
    return () => {
      releaseTab()
      document.removeEventListener('keydown', onKey, true)
      document.removeEventListener('focusin', onFocus)
      openDialogs.splice(openDialogs.indexOf(host), 1)
      for (const { node, inert } of background) node.inert = inert
      document.body.style.overflow = previousOverflow
      host.remove()
      const target = origin?.isConnected && origin !== document.body && origin.getClientRects().length > 0 ? origin : focusFallback.current?.()
      if (target?.isConnected && !target.closest('[inert]')) target.focus()
    }
  }, [host])

  return createPortal(
    <div className="dialog-overlay" onClick={closeOnOverlay ? onClose : undefined}>
      <div
        ref={dialog}
        className={`dialog dialog--${size} ${className}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        aria-describedby={description ? `${id}-description` : undefined}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog__head">
          <h2 id={`${id}-title`} ref={heading} className="dialog__title" tabIndex={-1}>{title}</h2>
          <button type="button" className="dialog__close" onClick={onClose} aria-label="닫기"><Icon name="close" /></button>
        </div>
        <div className="dialog__body">
          {description && <p id={`${id}-description`} className="dialog__description">{description}</p>}
          {children}
        </div>
        {footer && <div className="dialog__foot">{footer}</div>}
      </div>
    </div>,
    host,
  )
}
