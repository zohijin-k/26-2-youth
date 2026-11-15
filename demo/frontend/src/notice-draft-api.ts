import type { ManagedProgramData } from './program-workspace-api.ts'
import { officerSessionResponse } from './officer-session.ts'

export interface DraftEvidence {
  id: string; page: number | null; quote: string; source?: string; confidence: number; needs_review: boolean
  basis_evidence?: DraftEvidence; table_evidence?: DraftEvidence[]; sources?: DraftEvidence[]
}
export interface DraftValue<T> extends DraftEvidence { value: T }
export interface DraftDocument extends DraftEvidence { slot_key: string | null; label: string; original_label?: string; required: boolean; type: string }
export interface DraftCriterion extends DraftEvidence { type: string; label: string; values: Record<string, unknown>; engine_rule?: string | null }
export interface NoticeDraft {
  version: number; status: string; title: DraftValue<string>; period: DraftValue<{ apply_start: string; apply_end: string }>
  guidance: DraftValue<string>; required_docs: DraftDocument[]; criteria: DraftCriterion[]
  source_pages: { page: number; text: string }[]; warnings: string[]
  suggestions?: { target_id: string; type: string; text?: string; values?: Record<string, unknown>; page: number | null; quote: string; source: string; confidence: number; needs_review: boolean }[]
}
export interface AnalyzedProgramData extends ManagedProgramData { analysis?: NoticeDraft | null }
async function request<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: 'same-origin', ...init })
  officerSessionResponse(url, response)
  const body = await response.json() as T & { detail?: string }
  if (!response.ok) throw new Error(body.detail || '공고문을 분석하지 못했습니다.')
  return body
}
export function analyzeProgram(notice: File, forms: File[], supplemental: string) {
  const body = new FormData(); body.append('notice_pdf', notice); body.append('supplemental', supplemental)
  forms.forEach((file) => body.append('forms_pdfs', file))
  return request<AnalyzedProgramData>('/api/officer/programs/analyze', { method: 'POST', body })
}
export const saveProgramAnalysis = (id: number, analysis: NoticeDraft) => request<AnalyzedProgramData>(`/api/officer/postings/${id}/analysis`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ analysis }),
})
export function pendingDraftItems(draft: NoticeDraft): DraftEvidence[] {
  return [draft.title, draft.period, draft.guidance, ...draft.required_docs, ...draft.criteria].filter((item) => item.needs_review)
}
