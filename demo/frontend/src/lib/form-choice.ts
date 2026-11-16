/** Applicant choice fields of officer-published forms: one choice per radio group, and the
 * circle drawn around a chosen printed word (`choice_mark: 'circle'`). */
import type { PdfBox } from './form-box.ts'

export interface ChoiceField { field_type?: string; group?: string; choice_mark?: string }
export type ChoiceFields = Iterable<readonly [string, ChoiceField]>

/** Values after toggling one choice; picking a radio clears every other field of its group. */
export function toggledChoices(values: Readonly<Record<string, unknown>>, fields: ChoiceFields, key: string, checked: boolean): Record<string, unknown> {
  const all = [...fields]
  const next: Record<string, unknown> = { ...values, [key]: checked }
  const field = all.find(([id]) => id === key)?.[1]
  if (checked && field?.field_type === 'radio' && field.group) {
    for (const [id, item] of all) if (id !== key && item.group === field.group) next[id] = false
  }
  return next
}

/** A required radio is satisfied once any field of its group is chosen. */
export function choiceSatisfied(values: Readonly<Record<string, unknown>>, fields: ChoiceFields, key: string): boolean {
  const all = [...fields]
  const field = all.find(([id]) => id === key)?.[1]
  if (field?.field_type === 'radio' && field.group) return all.some(([id, item]) => item.group === field.group && values[id] === true)
  return values[key] === true
}

/** Oval around a chosen word: the word box padded on every side (same as forms/render.py). */
export function circleMarkBox(box: PdfBox): PdfBox {
  const height = box[3] - box[1]
  const padX = Math.max(2, height * 0.35)
  const padY = Math.max(1.5, height * 0.3)
  return [box[0] - padX, box[1] - padY, box[2] + padX, box[3] + padY]
}
