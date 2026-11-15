import type { OfficerPosting } from './api.ts'

export type FieldKind = 'text' | 'number' | 'date' | 'check' | 'radio' | 'signature'
export type AutofillSource = 'name' | 'birth' | 'mobile' | 'phone' | 'address' | 'email'

export interface DocumentSlotOption { key: string; label: string }

export interface ManagedFormField {
  type: 'text' | 'check' | 'image'
  field_type?: FieldKind
  page: number
  box: [number, number, number, number]
  label?: string
  required?: boolean
  autofill_source?: AutofillSource | null
  group?: string
  confidence?: number
  needs_review?: boolean
  [key: string]: unknown
}

export interface ManagedFormLayout {
  form_no?: string
  title?: string
  fields?: Record<string, ManagedFormField>
  page_sizes?: { width: number; height: number }[]
  [key: string]: unknown
}

export interface ManagedProgramForm {
  id: number
  file_name: string
  file_url: string
  layout: ManagedFormLayout
  confirmed: boolean
  updated_at: string
}

export interface ManagedProgramData {
  posting: OfficerPosting
  managed: boolean
  required_docs: string[]
  slot_options: DocumentSlotOption[]
  forms: ManagedProgramForm[]
  publish_blockers?: string[]
}

export interface ManagedProgramFields {
  title: string
  apply_start: string
  apply_end: string
  guidance_text: string
  required_docs: string[]
}

async function workspaceRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { credentials: 'same-origin', ...options })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
      ? body.detail : '사업 정보를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    throw new Error(message)
  }
  return body as T
}

export const fetchDocumentSlotOptions = () =>
  workspaceRequest<{ items: DocumentSlotOption[] }>('/api/officer/postings/slots/catalog').then((body) => body.items)

export const fetchProgramWorkspace = (id: number) =>
  workspaceRequest<ManagedProgramData>(`/api/officer/postings/${id}/workspace`)

export const saveProgramWorkspace = (id: number, fields: ManagedProgramFields) =>
  workspaceRequest<ManagedProgramData>(`/api/officer/postings/${id}/workspace`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fields),
  })

export function replaceProgramFiles(id: number, notice: File | null, forms: File[]) {
  const body = new FormData()
  if (notice) body.append('notice_pdf', notice)
  for (const form of forms) body.append('forms_pdfs', form)
  return workspaceRequest<ManagedProgramData>(`/api/officer/postings/${id}/workspace/files`, { method: 'POST', body })
}


export const draftProgramForm = (postingId: number, formId: number) =>
  workspaceRequest<ManagedProgramData>(`/api/officer/postings/${postingId}/workspace/forms/${formId}/draft`, { method: 'POST' })

export const saveProgramForm = (postingId: number, formId: number, layout: ManagedFormLayout) =>
  workspaceRequest<ManagedProgramData>(`/api/officer/postings/${postingId}/workspace/forms/${formId}/layout`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ layout }),
  })

export const confirmProgramForm = (postingId: number, formId: number) =>
  workspaceRequest<ManagedProgramData>(`/api/officer/postings/${postingId}/workspace/forms/${formId}/confirm`, { method: 'POST' })

export const unpublishProgram = (id: number) =>
  workspaceRequest<ManagedProgramData>(`/api/officer/postings/${id}/unpublish`, { method: 'POST' })

export const draftProgramGuidance = (id: number) => workspaceRequest<{ text: string; source: string; basis: string }>(`/api/officer/postings/${id}/workspace/guidance-draft`, { method: 'POST' })
