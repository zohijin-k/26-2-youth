/**
 * 확인 대화상자. 브라우저 기본 confirm 대신 쓴다.
 * 제목은 질문("~하시겠습니까?"), 버튼은 동사(취소 왼쪽 / 실행 오른쪽).
 * 열리면 제목이 포커스를 받고, Esc·닫기 버튼·취소 버튼은 모두 `onCancel`이다. 바깥 영역을 눌러도 닫히지 않는다.
 */
import type { ReactNode } from 'react'

import Dialog from './Dialog.tsx'

export default function ConfirmDialog({
  title, description, confirmLabel, cancelLabel = '취소', tone = 'primary', onConfirm, onCancel, returnFocus, children, size = 'sm',
}: {
  title: string
  description?: string
  /** 무엇을 하는지 동사로 적는다. 예: `본인인증 하기`, `제출하기`. */
  confirmLabel: string
  cancelLabel?: string
  /** `danger`는 되돌릴 수 없는 동작에만 쓴다. */
  tone?: 'primary' | 'danger'
  onConfirm: () => void
  onCancel: () => void
  returnFocus?: () => HTMLElement | null
  /** 설명 아래에 보여 줄 요약(입력값 목록 등). */
  children?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}) {
  return (
    <Dialog
      title={title}
      description={description}
      onClose={onCancel}
      returnFocus={returnFocus}
      size={size}
      closeOnOverlay={false}
      footer={(
        <>
          <button type="button" className="btn" onClick={onCancel}>{cancelLabel}</button>
          <button type="button" className={tone === 'danger' ? 'btn btn--danger' : 'btn btn--primary'} onClick={onConfirm}>{confirmLabel}</button>
        </>
      )}
    >
      {children}
    </Dialog>
  )
}
