import { requireReviewRevision } from './lib/review-revision.ts'
import { HttpError } from './lib/http-error.ts'
import type { OfficerDocument, OfficerRole, DecisionKey } from './api.ts'
import { officerSessionResponse } from './officer-session.ts'

export interface GenericCriterion {
  id: string; type: string; label: string; values: Record<string, unknown>
  result: string; requires_check: boolean; source_document_ids: number[]; basis?: string; quote?: string; page?: number
}
export interface GenericReviewData {
  revision: number | null; application_id: number; posting_id: number; application_no: string; name: string; status: string; program_name: string
  submitted_at: string | null; ai: { final_status: string }; documents: OfficerDocument[]; criteria: GenericCriterion[]
  checks: { document_ids: string[]; checklist_ids: string[]; fingerprint: string; current: boolean }
  decision: { decision: string | null; memo: string | null }; role: OfficerRole; can_approve: boolean; approval_blockers: string[]
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(15000), ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers } })
  officerSessionResponse(path, response)
  if (!response.ok) throw await HttpError.fromResponse(response, `심사 정보를 처리하지 못했습니다 (${response.status})`)
  return response.json() as Promise<T>
}
const path = (posting: number, application: number) => `/api/officer/programs/${posting}/applications/${application}`
export const fetchGenericReview = (posting: number, application: number) => request<GenericReviewData>(path(posting, application))
export const saveGenericChecks = (posting: number, application: number, checks: { document_ids: string[]; checklist_ids: string[]; fingerprint: string }) =>
  request<GenericReviewData>(`${path(posting, application)}/checks`, { method: 'PUT', body: JSON.stringify(checks) })
export const decideGeneric = (posting: number, application: number, decision: DecisionKey, memo: string, expectedRevision: number, notice?: string) => {
  requireReviewRevision(expectedRevision)
  return request<GenericReviewData>(`${path(posting, application)}/decision`, { method: 'POST', body: JSON.stringify({ role: 'province', decision, memo, expected_revision: expectedRevision, ...(notice === undefined ? {} : { notice }) }) })

}
