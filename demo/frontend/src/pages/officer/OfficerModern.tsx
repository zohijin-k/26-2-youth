import { useContext, useEffect, useId, useRef, useState, type ReactNode, type RefObject } from 'react'
import { flushSync } from 'react-dom'
import Modal from '../../components/Modal.tsx'
import { OfficerNavigationContext } from './officer-navigation-context.ts'
import { menuKeyResult, officerDestination, restorePanelFocus } from './officer-modern-model.ts'
import './officer-modern-tokens.css'
import './officer-modern.css'

export interface OfficerAction {
  label: string
  onSelect: () => void
  disabled?: boolean
  danger?: boolean
}
const FOCUSABLE = 'button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]'
function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((item) =>
    !item.hidden && !item.closest('[hidden]') && item.getClientRects().length > 0)
}
function useFocusPanel(open: boolean, root: RefObject<HTMLDivElement | null>, onClose?: () => void, arrows = true) {
  const close = useRef(onClose)
  useEffect(() => { close.current = onClose }, [onClose])
  useEffect(() => {
    const panel = root.current
    if (!open || !panel) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const initial = focusables(panel)[0] || panel
    initial.focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && close.current) {
        event.preventDefault(); event.stopPropagation(); close.current(); return
      }
      const items = focusables(panel)
      const index = items.indexOf(document.activeElement as HTMLElement)
      const result = menuKeyResult(event.key, index, items.length, event.shiftKey)
      if (result.kind === 'focus' && (arrows || event.key === 'Tab')) {
        event.preventDefault(); items[result.index]?.focus()
      }
    }
    const contain = (event: FocusEvent) => {
      if (event.target instanceof Node && !panel.contains(event.target)) (focusables(panel)[0] || panel).focus()
    }
    panel.addEventListener('keydown', keydown)
    document.addEventListener('focusin', contain)
    return () => {
      panel.removeEventListener('keydown', keydown)
      document.removeEventListener('focusin', contain)
      restorePanelFocus(previous)
    }
  }, [open, root, arrows])
}

/** Secondary actions stay reachable by keyboard without competing with the page action. */
export function OfficerMenu({ actions, label = '더보기', disabled = false, children }: {
  actions: OfficerAction[]; label?: string; disabled?: boolean; children?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  useFocusPanel(open, panel, () => setOpen(false))
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !panel.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])
  return <div className="om-menu">
    <button ref={trigger} type="button" className="om-icon" aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={id}
      disabled={disabled} onClick={() => setOpen((value) => !value)} onKeyDown={(event) => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true) }
      }}>{children || '⋮'}</button>
    {open && <div ref={panel} id={id} className="om-menu__panel" role="menu" aria-label={label} tabIndex={-1}>
      {actions.map((action) => <button key={action.label} type="button" role="menuitem" disabled={action.disabled}
        className={action.danger ? 'om-menu__danger' : undefined} onClick={() => {
          // Complete focus restoration before an action mounts a dialog.
          flushSync(() => setOpen(false)); action.onSelect()
        }}>{action.label}</button>)}
    </div>}
  </div>
}

export type OfficerLocation = 'list' | 'new' | 'applications' | 'settings' | 'info'
export function OfficerDrawer({ postingId, current, disabled = false, onList, onTab }: {
  postingId?: number; current?: OfficerLocation; disabled?: boolean; onList?: () => void
  onTab?: (tab: 'applications' | 'settings' | 'info') => void
}) {
  const registerNavigation = useContext(OfficerNavigationContext)
  useEffect(() => registerNavigation?.(), [registerNavigation])
  const [open, setOpen] = useState(false)
  const id = useId()
  const panel = useRef<HTMLDivElement>(null)
  useFocusPanel(open, panel, () => setOpen(false))
  const link = (label: string, location: OfficerLocation, path: string, tab?: 'applications' | 'settings' | 'info') => <a
    href={officerDestination(path, tab)} aria-current={current === location ? 'page' : undefined}
    onClick={(event) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      if (location === 'list' && onList) { event.preventDefault(); onList() }
      else if (tab && onTab) { event.preventDefault(); onTab(tab) }
      setOpen(false)
    }}>{label}</a>
  return <div className="om-drawer">
    <button type="button" className="om-icon" disabled={disabled} aria-label="메뉴 열기" aria-expanded={open} aria-controls={id}
      aria-haspopup="dialog" onClick={() => setOpen(true)}>≡</button>
    {open && <div className="om-drawer__shade" onPointerDown={(event) => { if (event.target === event.currentTarget) setOpen(false) }}>
      <div id={id} ref={panel} className="om-drawer__panel" role="dialog" aria-modal="true" aria-label="담당자 메뉴" tabIndex={-1}>
        <div className="om-drawer__head"><strong>사업 관리</strong><button type="button" className="om-icon" aria-label="메뉴 닫기" onClick={() => setOpen(false)}>✕</button></div>
        <nav aria-label="담당자 이동">
          {link('사업 목록', 'list', '/officer')}
          {postingId && <>{link('이 사업의 신청 목록', 'applications', `/officer/programs/${postingId}`, 'applications')}
            {link('사업 설정', 'settings', `/officer/programs/${postingId}`, 'settings')}
            {link('사업 정보', 'info', `/officer/programs/${postingId}`, 'info')}</>}
          {link('새 사업 올리기', 'new', '/officer/programs/new')}
          <button type="button" onClick={() => {
            void fetch('/api/officer/logout', { method: 'POST', credentials: 'same-origin' }).then((response) => {
              if (response.ok) window.location.assign('/officer/login')
            })
          }}>로그아웃</button>
        </nav>
      </div>
    </div>}
  </div>
}

/** Officer Modal adapter: trap/return focus and keep outside clicks from dismissing it. */
export function OfficerDialog({ title, onClose, children, footer, variant }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; variant?: 'default' | 'viewer' | 'printable-viewer'
}) {
  const root = useRef<HTMLDivElement>(null)
  useFocusPanel(true, root, undefined, false)
  return <div className="om om-dialog" ref={root} onPointerDownCapture={(event) => {
    // Outside pointer presses must not blur the dialog's focused control.
    if (event.target instanceof Element && event.target.classList.contains('modal-overlay')) { event.preventDefault(); event.stopPropagation() }
  }} onClickCapture={(event) => {
    if (event.target instanceof Element && event.target.classList.contains('modal-overlay')) event.stopPropagation()
  }}><Modal title={title} onClose={onClose} footer={footer} variant={variant}>{children}</Modal></div>
}

export function OfficerConfirm({ title, children, onConfirm, onClose, confirmLabel = '삭제', busy = false }: {
  title: string; children: ReactNode; onConfirm: () => void; onClose: () => void; confirmLabel?: string; busy?: boolean
}) {
  return <OfficerDialog title={title} onClose={onClose} footer={<>
    <button type="button" className="btn" disabled={busy} onClick={onClose}>취소</button>
    <button type="button" className="btn btn--danger" disabled={busy} onClick={onConfirm}>{confirmLabel}</button>
  </>}>{children}</OfficerDialog>
}
