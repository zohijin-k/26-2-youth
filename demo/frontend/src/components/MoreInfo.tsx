/**
 * 접어 둔 설명. 화면에는 한 줄 요약만 두고, 자세한 안내는 눌렀을 때만 펼친다.
 * 브라우저 기본 details/summary라 키보드·화면 낭독기에서 그대로 열고 닫힌다.
 *
 * - `inline`(기본): 문단 사이에 끼우는 "자세히 보기" 줄
 * - `card`: 카드 한 장 전체를 접는다. 요약 줄이 카드 제목이 된다.
 */
import type { ReactNode } from 'react'

import Icon from './Icon.tsx'

export default function MoreInfo({ summary = '자세히 보기', meta, variant = 'inline', open, className, children }: {
  summary?: ReactNode
  /** 요약 줄 오른쪽에 붙는 짧은 값(건수 등). */
  meta?: ReactNode
  variant?: 'inline' | 'card'
  open?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <details className={`more more--${variant}${className ? ` ${className}` : ''}`} open={open}>
      <summary className="more__summary">
        <span className="more__label">{summary}</span>
        {meta != null && meta !== false && <span className="more__meta">{meta}</span>}
        <Icon name="chevronDown" size={20} className="more__chevron" />
      </summary>
      <div className="more__body">{children}</div>
    </details>
  )
}
