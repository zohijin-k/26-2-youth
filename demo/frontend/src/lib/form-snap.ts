/** Officer "칸 추가" click: use a server snap suggestion, else a default-size box. */
import { boundedBox, type PageSize, type PdfBox } from './form-box.ts'

export type SnapKind = 'text' | 'number' | 'date' | 'check' | 'radio' | 'signature'
export interface SnapSuggestion { box: PdfBox | null; field_type?: string; label?: string }
export interface SnappedField { box: PdfBox; field_type: SnapKind; type: 'text' | 'check' | 'image'; label: string }

export const DEFAULT_FIELD_SIZE = { width: 120, height: 20 }
const KINDS: readonly SnapKind[] = ['text', 'number', 'date', 'check', 'radio', 'signature']

export function snappedField(snap: SnapSuggestion | null, at: { x: number; y: number }, page: PageSize): SnappedField {
  if (!snap || !snap.box) {
    const x = Math.min(at.x, page.width - DEFAULT_FIELD_SIZE.width)
    const y = Math.min(at.y, page.height - DEFAULT_FIELD_SIZE.height)
    return { box: boundedBox([x, y, x + DEFAULT_FIELD_SIZE.width, y + DEFAULT_FIELD_SIZE.height], page), field_type: 'text', type: 'text', label: '새 입력칸' }
  }
  const field_type = KINDS.find((kind) => kind === snap.field_type) || 'text'
  const type = field_type === 'signature' ? 'image' : field_type === 'check' || field_type === 'radio' ? 'check' : 'text'
  return { box: boundedBox(snap.box, page), field_type, type, label: (snap.label || '').trim().slice(0, 200) || '새 입력칸' }
}
