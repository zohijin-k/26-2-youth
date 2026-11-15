/** 백엔드 호출. vite dev 서버가 /api 를 :8000 으로 프록시한다. */

import { FORM_FIELD_KEYS } from './forms/form-field-bindings.ts'
import { youthOfficerRole } from './officer-scope.ts'
import { YOUTH_PROGRAM } from './program-scope.ts'
import { officerSessionResponse } from './officer-session.ts'

type OfficerMocks = typeof import('./pages/officer/mock-data.ts')
let loadedOfficerMocks: OfficerMocks | null = null
const loadOfficerMocks = async (): Promise<OfficerMocks> =>
  loadedOfficerMocks ??= await import('./pages/officer/mock-data.ts')

/** Loaded only by officer requests; synchronous membership supports the officer banner. */
export const isOfficerMockId = (applicationId: number): boolean =>
  loadedOfficerMocks?.isMockId(applicationId) ?? false

/**
 * 사업 설정. 화면 분기는 전부 이 값으로 한다.
 *
 * 컴포넌트 안에서 `code === 'job_package'` 같은 비교를 하지 않는 것이 규칙이다.
 * 선발 방식·보완 정책·연령 기준·지원 항목은 서버가
 * 이 구조체 하나로 알려준다.
 */
export interface Program {
  code: string
  name: string
  announcement_date: string
  document_cutoff: string
  age_basis_date: string
  birth_range: [string, string]
  selection: 'scored' | 'first_come' | 'manual'
  is_first_come: boolean
  supplement_days: number | null
  allows_supplement: boolean
  has_income_requirement: boolean
  has_work_requirement: boolean
  has_subsidy_items: boolean
  apply_period: [string, string]
  /** 2차 모집이 있는 사업의 2차 신청 기간. 없으면 null. */
  apply_period_2: [string, string] | null
  quota_by_region: Record<string, number> | null
  quota_total: number | null
  /** 서버가 제공하는 자가진단 문항 번호. */
  self_check_items: number[]
  /** 지원 항목표. 항목이 없는 사업은 null. */
  subsidy_catalog: SubsidyCatalogItem[] | null
  site_url: string
  call_center: string
  notes: string[]
}

/** 취업지원패키지 지원 항목 1종 (사업계획서 「지원내용」 표). */
export interface SubsidyCatalogItem {
  item_type: string
  label: string
  description: string
  unit_cap: number
  max_count: number
  count_scope: 'application' | 'year' | 'lifetime'
  used_count?: number
  remaining_count?: number
  /** true면 실비(영수증 금액과 한도 중 작은 값), false면 정액. */
  actual_cost: boolean
  needs_receipt: boolean
  max_amount: number
  note: string
  amount_label: string
  count_label: string
  extra_docs: string[]
  performance_target: number | null
}

export interface SubsidySelection {
  item_type: string
  count: number
  receipts: (number | null)[]
  linked_interview_indices: (number | null)[]
}

/** 지급 계산 한 줄. `calculation`이 "왜 이 금액인가"의 답이다. */
export interface SubsidyLine {
  item_type: string
  label: string
  index: number
  unit_cap: number
  actual_cost: boolean
  receipt_amount: number | null
  granted_amount: number
  calculation: string
  linked_interview_index: number | null
  pending: boolean
}

export interface SubsidyEstimate {
  lines: SubsidyLine[]
  total_granted: number
  warnings: string[]
  pending: boolean
}

export interface SubsidyState {
  program_code: string
  program_name: string
  catalog: SubsidyCatalogItem[]
  selections: SubsidySelection[]
  estimate: SubsidyEstimate
  notice: string
}

/** 선착순 접수 순번 (R6). 점수제 사업에서는 null. */
export interface FirstComeInfo {
  enabled: boolean
  position: number
  quota: number | null
  remaining: number | null
  submitted: boolean
  notice: string
}

/** 서류 보완 기한 (E12). 보완이 없는 사업에서는 null. */
export interface SupplementInfo {
  days: number | null
  deadline: string
  days_left: number
  hours_left: number
  expired: boolean
  targets: { label: string; reason: string }[]
  notice: string
}

export interface ApplicationRow {
  id: number
  application_no: string
  program_code: string
  status: string
  form1_json: Record<string, unknown>
  self_check_json: Record<string, string>
  form5_json: Record<string, unknown>
  identity_json: Partial<Identity> | null
  eligibility_blockers?: Blocker[]
}

export interface SelfCheckResult {
  eligible: boolean
  completed: boolean
  failed_item: number | null
  reason: string
  alternative: string
  /** 서버가 확인한 자가진단 문항 수. */
  total_items: number
}

export interface ConsentPayload {
  consent_type: 'privacy' | 'unique_id' | 'third_party' | 'admin_info'
  agreed: boolean
  signature_data_url?: string
  signature_kind?: 'electronic' | 'handwritten'
}

/** 업로드 즉시 판정 결과 한 줄. 사유만 주면 신청자는 또 전화한다 — 해결 방법과 발급처가 함께 온다. */
export interface Finding {
  code: string
  message: string
  how_to_fix: string
  link: string
  severity: 'FAIL' | 'NEEDS_REVIEW'
}

export type DocStatus = 'PASS' | 'FAIL' | 'NEEDS_REVIEW'

export interface UploadedDocument {
  document_id: number
  slot_key: string
  file_name: string
  file_format: string
  /** 원본을 브라우저 안에서 여는 주소 (인라인 스트리밍) */
  file_url: string
  expected_doc_type: string | null
  detected_doc_type: string | null
  declared_issue_date: string | null
  status: DocStatus | null
  findings: Finding[]
  extracted: Record<string, string>
  ocr_confidence: number | null
  elapsed_ms: number | null
  page_index: number | null
  uploaded_at: string
}

/** 체크리스트 한 줄. `upload`가 false면 온라인 작성으로 대체된 항목이다. */
export interface DocRequirementRow {
  slot_key: string
  doc_type: string
  /** 이 자리에 인정되는 서류들. 응시확인서 **또는** 성적표처럼 택1인 칸이 있다. */
  doc_type_choices: string[]
  /** 서류에 반드시 찍혀 있어야 하는 항목 (예: 응시확인서의 "응시일"). */
  required_fields: string[]
  label: string
  required: boolean
  upload: boolean
  fulfilled_by: string
  requires_signature: boolean
  check_declared_date: boolean
  date_basis: 'issue_date' | 'payment_date' | 'interview_date' | 'exam_date' | 'none'
  date_basis_label: string
  min_issue_date: string | null
  max_issue_date: string | null
  issue_rule_label: string
  issuer: string
  issuer_url: string
  notes: string[]
  warnings: string[]
  alternatives: string[]
  accept: string[]
  documents: UploadedDocument[]
}

export interface DocContext {
  work_category?: string | null
  admin_fixed_term?: boolean
  workplace_count?: number
  handwritten_admin_consent?: boolean
  paper_forms?: Record<string, boolean>
}

/** 업로드 화면이 사업 코드로 분기하지 않도록 서버가 내려주는 안내. */
export interface ChecklistProgram {
  code: string
  name: string
  selection: 'scored' | 'first_come' | 'manual'
  allows_supplement: boolean
  supplement_days: number | null
  document_cutoff: string
  announcement_date: string
  application_period: string[]
  application_period_2: string[] | null
  asks_work_category: boolean
  has_subsidy_items: boolean
  paper_forms: Record<string, boolean>
}

export interface Checklist {
  context: DocContext
  program: ChecklistProgram
  work_categories: string[]
  accepted_formats: string[]
  items: DocRequirementRow[]
  upload_total: number
  upload_done: number
  unassigned: UploadedDocument[]
  /** 판정 컷라인 등 TF 미확정 가정값 안내. `(데모 추정치)` 라벨이 붙어 온다. */
  assumption_notes: string[]
}

export interface MergedUploadResult {
  mode: 'merged'
  source_file: string
  page_count: number
  assigned: UploadedDocument[]
  unassigned: UploadedDocument[]
}

/** 제출을 막는 항목 하나. `goto`는 "어디로 가면 고칠 수 있는가"다. */
export interface Blocker {
  kind: 'form' | 'consent' | 'document' | 'context' | 'subsidy' | 'eligibility' | 'identity'
  target: string
  label: string
  message: string
  goto: 'form1' | 'consent' | 'upload' | 'subsidy' | 'identity' | 'forms'
}

export interface FinalCheck {
  application_no: string
  program_code: string
  program_name: string
  allows_supplement: boolean
  supplement_days: number | null
  selection: 'scored' | 'first_come' | 'manual'
  first_come: FirstComeInfo | null
  subsidy: SubsidyEstimate | null
  status: string
  can_submit: boolean
  already_submitted: boolean
  blockers: Blocker[]
  warnings: string[]
  form_summary: { label: string; value: string }[]
  documents: UploadedDocument[]
}

export interface SubmitResult {
  application_no: string
  submitted_at: string | null
  status: string
  message: string
  next_steps: string[]
  first_come: FirstComeInfo | null
  supplement: SupplementInfo | null
  subsidy: SubsidyEstimate | null
  notice: string
}

/**
 * 마이페이지 응답.
 *
 * ⚠️ 점수 필드가 없는 것이 사양이다 (공고문: "평가결과는 공개하지 않음").
 * 이 인터페이스에 점수·구간·순위를 추가하면 안 된다.
 */
export interface ApplicationStatus {
  application_no: string
  program_code: string
  program_name: string
  status: string
  submitted_at: string | null
  progress: { label: string; state: 'done' | 'current' | 'todo' }[]
  result_notice: string
  first_come: FirstComeInfo | null
  supplement: SupplementInfo | null
  subsidy: SubsidyEstimate | null
  documents: UploadedDocument[]
  consents: {
    consent_type: string
    label: string
    agreed: boolean
    agreed_at: string
    signature_kind: string | null
  }[]
  call_center: string
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  officerSessionResponse(path, res)
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path} 실패 (${res.status})`)
  return res.json() as Promise<T>
}

/** 파일 업로드는 multipart라 Content-Type을 브라우저가 붙이게 둔다. */
async function form<T>(path: string, body: FormData): Promise<T> {
  const res = await fetch(path, { method: 'POST', body })
  officerSessionResponse(path, res)
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(detail?.detail ?? `업로드 실패 (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const fetchPrograms = () => json<Program[]>('/api/programs')

export const createApplication = (programCode: string) =>
  json<ApplicationRow>('/api/applications', {
    method: 'POST',
    body: JSON.stringify({ program_code: programCode, applicant_flow_version: 1 }),
  })

export const fetchApplication = (id: number) =>
  json<ApplicationRow>(`/api/applications/${id}`)

export const fetchApplicationConsents = (id: number) =>
  json<{ consent_type: string; agreed: boolean }[]>(`/api/applications/${id}/consents`)

export const patchApplication = (
  id: number,
  body: { form1?: unknown; self_check?: unknown; form5?: unknown },
) =>
  json<ApplicationRow>(`/api/applications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })

export interface FormFieldLayout {
  type: 'text' | 'check' | 'image'
  required?: boolean
  field_type?: 'text' | 'number' | 'date' | 'check' | 'radio' | 'signature'
  readonly?: boolean
  group?: string
  control?: 'radio_text'
  page: number
  box: [number, number, number, number]
  label_box?: [number, number, number, number]
  click_box?: [number, number, number, number]
  choice_box?: [number, number, number, number]
  choice_group_box?: [number, number, number, number]
  cell_box?: [number, number, number, number]
  x?: number
  y?: number
  size?: number
  align?: 'left' | 'center'
  format?: 'yyyy' | 'yy' | 'none'
  auto_date?: boolean
  date_part?: 'year' | 'month' | 'day'
  date_reference?: { size: number; baseline: number; render_baseline: number; render_size_scale: number; character: string; font_family: 'serif' | 'sans'; glyph_box: [number, number, number, number] }
  group_box?: [number, number, number, number]
  font_family?: 'serif' | 'sans'
  anchor?: string
  label?: string
}

export interface FormLayout {
  form_no: string
  title: string
  public_form: string | null
  page_sizes: { width: number; height: number }[]
  fields: Record<string, FormFieldLayout>
  requirements?: ({ kind: 'all_or_none'; fields: string[] } | { kind: 'when_choice'; field: string; equals: string; required: string[] })[]
  masks?: { page: number; box: [number, number, number, number] }[]
  auto_date: string
}

export interface ApplicantFormSummary {
  form_no: string
  public_form: string | null
  title: string
  label: string
  file_url: string
  file_name: string
  hwp_available: boolean
}

export const fetchOriginalHwpOptions = (id: number) =>
  json<{ url: string | null; label: string | null }>(`/api/applications/${id}/forms/files/original-hwp/options`)
export const fetchInterviewFormFileOptions = (id: number) =>
  json<{ blank: string; hwp: string | null }>(`/api/applications/${id}/forms/files/job_interview_confirmation/options`)

export const fetchFormLayout = async (id: number, formNo: string): Promise<FormLayout> => {
  const layout = await json<FormLayout>(`/api/applications/${id}/forms/layouts/${encodeURIComponent(formNo)}`)
  const bindings = FORM_FIELD_KEYS[formNo] || []
  const fields = Object.fromEntries(Object.entries(layout.fields).map(([opaqueId, field], index) => [bindings[index] || opaqueId, field]))
  const keyById = Object.fromEntries(bindings.map((key, index) => [`f${String(index).padStart(4, '0')}`, key]))
  const requirements = (layout.requirements || []).map((rule) => rule.kind === 'all_or_none'
    ? { ...rule, fields: rule.fields.map((key) => keyById[key] || key) }
    : { ...rule, field: (keyById[rule.field] || rule.field).split('.')[0], required: rule.required.map((key) => keyById[key] || key) })
  return { ...layout, fields, requirements }
}

export const fetchApplicantForms = (id: number) =>
  json<ApplicantFormSummary[]>(`/api/applications/${id}/forms`)

/** 본인인증 결과. 서류 본인 대조의 기준이 된다 (연락처는 가려서 돌아온다). */
export interface Identity {
  name: string
  birth: string
  phone: string
  method: string
  verified_at: string
}

export interface IdentityPayload {
  name: string
  /** YYYY-MM-DD */
  birth: string
  phone: string
  pledge: boolean
  signature_data_url: string
  /** electronic(화면에 직접 서명) | uploaded(서명 파일 올리기) */
  signature_kind: 'electronic' | 'uploaded'
}

/** 본인인증 (데모). 실패 사유는 서버 문구 그대로 보여준다. */
export async function verifyIdentity(id: number, body: IdentityPayload): Promise<Identity> {
  const res = await fetch(`/api/applications/${id}/identity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = (await res.json().catch(() => null)) as
    | { identity?: Identity; detail?: string }
    | null
  if (!res.ok || !data?.identity) {
    throw new Error(data?.detail ?? `본인인증 실패 (${res.status})`)
  }
  return data.identity
}

export const postSelfCheck = (id: number, answers: Record<string, string>) =>
  json<SelfCheckResult>(`/api/applications/${id}/self-check`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
  })

export const postConsents = (id: number, consents: ConsentPayload[]) =>
  json<{ saved: unknown[] }>(`/api/applications/${id}/consents`, {
    method: 'POST',
    body: JSON.stringify({ consents }),
  })

export const fetchChecklist = (id: number) =>
  json<Checklist>(`/api/applications/${id}/required-documents`)

/** 여러 서류를 한 파일로 올린 경우. 페이지별로 쪼개 슬롯에 자동 배정한다. */
export function uploadDocument(
  id: number,
  slotKey: string,
  file: File,
  declaredIssueDate: string,
  progress?: { onProgress: (sent: number, total: number) => void; onSent: () => void; signal: AbortSignal },
) {
  const body = new FormData()
  body.append('file', file)
  body.append('slot_key', slotKey)
  if (declaredIssueDate) body.append('declared_issue_date', declaredIssueDate)
  const path = `/api/applications/${id}/documents`
  if (!progress) return form<UploadedDocument>(path, body)
  // Same multipart request and response; XHR exposes real transport progress.
  return new Promise<UploadedDocument>((resolve, reject) => {
    const request = new XMLHttpRequest()
    const abort = () => request.abort()
    const clean = () => progress.signal.removeEventListener('abort', abort)
    request.open('POST', path)
    request.responseType = 'json'
    request.upload.onprogress = (event) => { if (event.lengthComputable) progress.onProgress(event.loaded, event.total) }
    request.upload.onload = progress.onSent
    request.onload = () => {
      clean()
      if (request.status >= 200 && request.status < 300) resolve(request.response as UploadedDocument)
      else reject(new Error(typeof request.response?.detail === 'string' ? request.response.detail : `업로드 실패 (${request.status})`))
    }
    request.onerror = () => { clean(); reject(new TypeError('Network request failed')) }
    request.onabort = () => { clean(); reject(new DOMException('Request aborted', 'AbortError')) }
    progress.signal.addEventListener('abort', abort, { once: true })
    if (progress.signal.aborted) { clean(); reject(new DOMException('Request aborted', 'AbortError')); return }
    request.send(body)
  })
}

/** 여러 서류를 한 파일로 올린 경우. 페이지별로 쪼개 슬롯에 자동 배정한다. */
export function uploadMerged(id: number, file: File) {
  const body = new FormData()
  body.append('file', file)
  body.append('slot_key', 'auto')
  return form<MergedUploadResult>(`/api/applications/${id}/documents`, body)
}

export const deleteDocument = (id: number, documentId: number) =>
  json<{ deleted: string }>(`/api/applications/${id}/documents/${documentId}`, {
    method: 'DELETE',
  })

/** 취업지원패키지 지원 항목 — 저장된 선택과 예상 지원금. */
export const fetchSubsidyItems = (id: number) =>
  json<SubsidyState>(`/api/applications/${id}/subsidy-items`)

/** 고른 항목을 통째로 저장하고, 다시 계산된 지급액을 받는다. */
export const saveSubsidyItems = (id: number, items: SubsidySelection[]) =>
  json<SubsidyState>(`/api/applications/${id}/subsidy-items`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  })

export const fetchFinalCheck = (id: number) =>
  json<FinalCheck>(`/api/applications/${id}/final-check`)

export const submitApplication = (id: number) =>
  json<SubmitResult>(`/api/applications/${id}/submit`, { method: 'POST' })

export const fetchStatus = (id: number) =>
  json<ApplicationStatus>(`/api/applications/${id}/status`)

/* ================================================================== 담당자 API (officer tip) */

export type IssueRule = { mode: 'after_date' | 'after_notice' | 'within_days' | 'none'; date?: string; days?: number }

export type CriteriaSubsidyDoc = {
  suffix: string; doc_type: string; label: string; accepted: string[]; required_fields: string[];
  notes: string[]; warnings: string[]; date_basis: 'issue_date' | 'payment_date' | 'interview_date' | 'exam_date' | 'none'
}

export type CriteriaSubsidyItem = {
  item_type: string; label: string; description: string; unit_cap: number; max_count: number;
  count_scope: 'application' | 'year' | 'lifetime'
  actual_cost: boolean; note: string; extra_docs: CriteriaSubsidyDoc[]
}

export interface CriteriaData {
  version: number
  announcement_date: string
  application_period: string[]
  application_period_2: string[] | null
  document_issue_rules: Record<string, IssueRule>
  document_issue_fallback: IssueRule
  document_date_bases: Record<string, 'issue_date' | 'payment_date' | 'interview_date' | 'exam_date' | 'none'>
  nhis_payment_months: string[]
  nhis_acquisition_loss_years: number
  supplement: { allowed: boolean; days: number | null }
  subsidy_catalog: CriteriaSubsidyItem[]
  paper_forms: Record<string, boolean>
}

export interface CriteriaVersion extends CriteriaData { changed_at?: string; changed_role?: string }

export interface CriteriaHistory { current: CriteriaVersion; history: CriteriaVersion[] }

export const fetchOfficerCriteria = (code: string, role = 'province') =>
  json<CriteriaHistory>(`/api/officer/programs/${code}/criteria?role=${encodeURIComponent(role)}`)

export const saveOfficerCriteria = (code: string, role: string, data: Omit<CriteriaData, 'version'>) =>
  json<CriteriaVersion>(`/api/officer/programs/${code}/criteria?role=${encodeURIComponent(role)}`, {
    method: 'PUT', body: JSON.stringify(data),
  })

/* ------------------------------------------------------------------ 담당자 화면
 *
 * 원본 파일은 `/api/files/{id}`가 `inline`으로만 흘린다. 이 파일 어디에도 파일을
 * 로컬에 저장하는 경로를 만들지 않는다 — 뷰어가 URL을 직접 읽는 것이 전부다 (R4.1).
 */

/** 원본에서 값을 읽어낸 위치. PDF 포인트, **좌상단 원점**이다. */
export interface BBox {
  page: number
  x0: number
  y0: number
  x1: number
  y1: number
}

export type DecisionKey = 'approve' | 'reject' | 'hold'

export interface OfficerAction {
  key: DecisionKey
  /** 버튼 표기. 같은 approve라도 역할마다 뜻이 다르다. */
  label: string
  result_label: string
  tone: 'primary' | 'danger' | 'neutral'
}

export interface OfficerRole {
  key: string
  name: string
  stage: string
  scope: string
  requires_region: boolean
  requires_town: boolean
  can_bulk: boolean
  notes: string[]
  actions: OfficerAction[]
}

export interface OfficerRow {
  application_id: number
  application_no: string
  name: string
  region: string
  town: string
  program_code: string
  program_name: string
  ai_status: DocStatus | null
  ai_status_label: string
  missing_count: number
  submitted_at: string | null
  status: string
  decision: DecisionKey | null
  decision_label: string
  officer_role: string | null
  /**
   * 신청한 지원 항목 요약 ("면접비 2회 · 자격증 응시료 1회").
   *
   * 선착순 사업은 점수가 없고, 담당자가 목록에서 먼저 보는 것이 "이 사람이 무엇을
   * 신청했는가"다. 점수제 사업에서는 비어 온다.
   */
  items_label?: string | null

}

/**
 * 신청 목록의 세 구분.
 *
 *   needs_check  담당자 판단이 없고 자동 판정이 적합이 아닌 건 (확인필요·부적합·미심사)
 *   pass         담당자 판단이 없고 자동 판정이 적합인 건
 *   done         담당자가 판단한 건 (보류 포함)
 */
export type OfficerQueue = 'needs_check' | 'pass' | 'done'

export const OFFICER_QUEUES: readonly OfficerQueue[] = ['needs_check', 'pass', 'done']

export interface OfficerListQuery {
  role: string
  region?: string
  town?: string
  program?: string
  status?: string
  ai_status?: string
  submitted_from?: string
  submitted_to?: string
  sort?: string
  page?: number
  page_size?: number
  queue?: OfficerQueue
  /** 신청번호 또는 성명에서 찾을 글자. 50자 이하. */
  q?: string
}

export interface OfficerList {
  role: OfficerRole
  scope: {
    region: string
    town: string
    region_locked: boolean
    town_locked: boolean
    regions: string[]
    towns: string[]
  }
  filters: {
    programs: { code: string; name: string }[]
    ai_statuses: { value: string; label: string }[]
    statuses: { value: string; label: string }[]
    sorts: { value: string; label: string }[]
    applied: Record<string, string | null>
  }
  /**
   * 목록 컬럼. 표의 헤더와 셀이 **둘 다** 이 배열을 따른다. 사업에 따라 컬럼이
   * 달라져도 같은 배열로 헤더와 셀을 렌더링한다.
   */
  columns: { key: string; label: string }[]
  /** 취업지원패키지 접수 진행률. */
  first_come: {
    program_code: string
    program_name: string
    quota: number
    applied: number
    selected: number
    remaining: number
    rate_percent: number
    supplement_days: number | null
    notice: string
  } | null
  /**
   * 구분별 건수. 관할·검색어·기간까지만 건 뒤에 센 값이라 어느 구분을 보고 있어도
   * 세 숫자가 같다.
   */
  queues: Record<OfficerQueue, number>
  total: number
  page: number
  page_size: number
  page_count: number
  rows: OfficerRow[]
}

/** 목록에서 행을 펼쳤을 때 보이는, 이 건을 확인해야 하는 사유. */
export interface ApplicationReasons {
  explanation?: { text: string; label: string; basis: string } | null
  application_id: number
  ai_status: DocStatus | null
  ai_status_label: string
  /** 사유의 출처. 지금은 규칙 판정 결과(`rules`)뿐이다. */
  source: string
  /** 올렸지만 적합이 아닌 서류. 체크리스트 순서다. */
  documents: {
    slot_key: string
    label: string
    status: DocStatus | null
    status_label: string
    findings: { code: string; message: string; severity: string }[]
  }[]
  /** 아직 올리지 않은 필수 서류. */
  missing: { slot_key: string; label: string }[]
}

export interface OfficerDocument {
  document_id: number
  slot_key: string
  label: string
  expected_doc_type: string | null
  detected_doc_type: string | null
  status: DocStatus | null
  findings: Finding[]
  /** 인라인 스트리밍 주소. 뷰어가 이 URL을 그대로 읽는다. */
  file_url: string
  file_name: string
  file_format: string
  page_index: number | null
  extracted: Record<string, string>
  bboxes: Record<string, BBox>
  ocr_confidence: number | null
  ocr_tier: string | null
  /** 실제로 글자를 읽은 엔진 (jbai·applevision·pdftext 등). 담당자 화면 전용 */
  ocr_engine: string | null
  /** 앞 엔진이 실패해 다른 엔진으로 대체한 사유 (예: 전북AI 응답 시간 초과) */
  ocr_fallback_reason: string | null
  /** 판독을 유지한 경우 담당자가 참고할 품질 메모 */
  ocr_quality_note: string | null
  declared_issue_date: string | null
  uploaded_at: string
}

/** 작성 서식 한 장 (P7 / R9). 업로드 서류와 같은 뷰어에서 인라인으로 연다. */
export interface FormExport {
  form_no: string
  public_form: string | null
  title: string
  label: string
  /** 인라인 스트리밍 주소. 저장 링크가 아니다. */
  file_url: string
  file_name: string
}

export interface ReviewDetailData {
  application_id: number
  application_no: string
  criteria_version?: number | null
  name: string
  /** 본인인증 여부. 목업 데이터에는 없다. */
  identity?: {
    verified: boolean
    method: string | null
    verified_at: string | null
    pledge_signed: boolean
    pledge_kind?: string | null
  }
  program_code: string
  program_name: string
  region: string
  town: string
  status: string
  submitted_at: string | null
  ai: {
    final_status: DocStatus | null
    final_status_label: string
    stage1_status: string | null
    stage2_status: string | null
    recommended_action: string
    reasons: { stage: string; code: string; message: string; doc_type: string | null }[]
  }
  /** 취업지원패키지 항목별 지급 내역. */
  subsidy: SubsidyEstimate | null
  /** 7일 보완 기한. 보완이 없는 사업이거나 보완 대상이 아니면 null. */
  supplement: SupplementInfo | null
  documents: OfficerDocument[]
  /** 신청자가 작성한 서식을 원본 서식 모양 그대로 내보낸 PDF. 없으면 빈 배열. */
  forms: FormExport[]
  eligibility: { key: string; label: string; ok: boolean; basis: string }[]
  exclusions: { label: string; answer: string; ok: boolean; source: string }[]
  decision: {
    decision: DecisionKey | null
    label: string
    memo: string | null
    officer_role: string | null
    decided_at: string | null
  }
  role: OfficerRole
}

function query(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  return search.toString()
}

// ---------------------------------------------------------------- 담당자 목업

/**
 * 담당자 화면 목업 전환 (`pages/officer/mock-data.ts`).
 *
 * 켜지는 조건은 둘이다.
 *
 *   - `?mock=1` — 강제로 켠다. 백엔드가 떠 있어도 목업을 본다.
 *   - 자동 — 신청 목록 API가 실패했거나 **접수 건이 0건**일 때. (사업 목록은 항상 백엔드에서
 *     읽으므로, 백엔드가 꺼져 있으면 신청 목록까지 들어갈 수 없다.) 빈 표를 띄우고
 *     "데이터가 없습니다"로 시연이 끊기는 것보다, 예시로 채운 화면을 보여주고
 *     목업임을 상단에 밝히는 편이 낫다.
 *
 * `?mock=0`을 붙이면 어떤 경우에도 목업을 쓰지 않는다 — 실제 접수 건이 0건인 것을
 * 확인해야 할 때 쓴다.
 */
function mockMode() {
  const value = new URLSearchParams(window.location.search).get('mock')
  return { forced: value === '1' || value === 'on', blocked: value === '0' || value === 'off' }
}

let mockActive = false

export const isOfficerMockActive = () => {
  const mode = mockMode()
  return !mode.blocked && (mode.forced || mockActive)
}

const youthList = (list: OfficerList): OfficerList => ({
  ...list,
  role: youthOfficerRole(list.role),
  columns: list.columns.filter((column) => column.key !== 'total_score'),
  filters: {
    ...list.filters,
    programs: list.filters.programs.filter((program) => program.code === YOUTH_PROGRAM),
    sorts: [{ value: 'submitted', label: '접수순 (선착순)' }],
  },
  rows: list.rows.filter((row) => row.program_code === YOUTH_PROGRAM),
})

export const fetchOfficerRoles = async (): Promise<OfficerRole[]> => {
  if (isOfficerMockActive()) return (await loadOfficerMocks()).MOCK_ROLES.map(youthOfficerRole)
  try {
    return (await json<OfficerRole[]>('/api/officer/roles')).map(youthOfficerRole)
  } catch (error) {
    if (mockMode().blocked) throw error
    mockActive = true
    return (await loadOfficerMocks()).MOCK_ROLES.map(youthOfficerRole)
  }
}

export const fetchOfficerList = async (params: OfficerListQuery): Promise<OfficerList> => {
  // Published programs keep their own server list and never receive synthetic fallback rows.
  if (params.program?.startsWith('posting_')) {
    return json<OfficerList>(`/api/officer/applications?${query({ ...params })}`)
  }
  const scoped = { ...params, program: YOUTH_PROGRAM, sort: 'submitted' }
  const mockList = async () => youthList((await loadOfficerMocks()).mockOfficerList(scoped))
  if (isOfficerMockActive()) return mockList()
  try {
    const body = await json<OfficerList>(`/api/officer/applications?${query(scoped)}`)
    const unfiltered = !params.region && !params.town && !params.q
      && !params.submitted_from && !params.submitted_to
    const received = body.queues.needs_check + body.queues.pass + body.queues.done
    if (received === 0 && unfiltered && !mockMode().blocked) {
      mockActive = true
      return mockList()
    }
    return youthList(body)
  } catch (error) {
    if (mockMode().blocked) throw error
    mockActive = true
    return mockList()
  }
}

export const fetchReviewDetail = async (applicationId: number, role: string): Promise<ReviewDetailData> => {
  const mocks = mockMode().blocked ? null : await loadOfficerMocks()
  const detail = mocks?.isMockId(applicationId)
    ? mocks.mockReviewDetail(applicationId, role)
    : await json<ReviewDetailData>(`/api/officer/applications/${applicationId}?${query({ role })}`)
  if (detail.program_code !== YOUTH_PROGRAM) {
    throw new Error('이 화면에서는 청년 취업지원패키지 신청만 확인할 수 있습니다.')
  }
  return { ...detail, role: youthOfficerRole(detail.role) }
}

/** 행을 펼쳤을 때 읽는 확인 필요 사유. 저장된 규칙 판정 결과만 온다. */
export const fetchApplicationReasons = async (applicationId: number, role: string): Promise<ApplicationReasons> => {
  const mocks = mockMode().blocked ? null : await loadOfficerMocks()
  return mocks?.isMockId(applicationId)
    ? mocks.mockApplicationReasons(applicationId)
    : json<ApplicationReasons>(`/api/officer/applications/${applicationId}/reasons?${query({ role })}`)
}

export const postDecision = async (
  applicationId: number,
  body: { role: string; decision: DecisionKey; memo: string },
) => {
  const mocks = mockMode().blocked ? null : await loadOfficerMocks()
  if (mocks?.isMockId(applicationId)) {
    mocks.mockDecide([applicationId], body.role, body.decision, body.memo)
    const detail = mocks.mockReviewDetail(applicationId, body.role)
    return { decision: body.decision, label: detail.decision.label, decided_at: detail.decision.decided_at }
  }
  return json<{ decision: string; label: string; decided_at: string | null }>(
    `/api/officer/applications/${applicationId}/decision`,
    { method: 'POST', body: JSON.stringify(body) },
  )
}

export const postBulkDecision = async (body: {
  role: string
  decision: DecisionKey
  memo: string
  application_ids: number[]
}) => {
  const mocks = mockMode().blocked ? null : await loadOfficerMocks()
  if (mocks && body.application_ids.every(mocks.isMockId)) {
    const refusal = mocks.mockBulkRefusal(body.application_ids, body.role, body.decision)
    if (refusal) throw new Error(refusal)
    return { processed: mocks.mockDecide(body.application_ids, body.role, body.decision, body.memo) }
  }
  return json<{ processed: number }>('/api/officer/applications/decisions', {
    method: 'POST', body: JSON.stringify(body),
  })
}

/* ================================================================== 사업 저장소 (postings)
 *
 * 담당자가 올린 사업 한 건이 posting이다. 화면에서는 늘 "사업"이라고 부른다.
 * 공고문·서식 PDF는 인라인으로만 열린다 — 뷰어가 주소를 직접 읽는다.
 */

/** 서버가 오늘 날짜와 상태로 정해 주는 단계. 화면은 이 값으로만 갈린다. */
export type PostingPhase = 'draft' | 'upcoming' | 'open' | 'closed'

export type PostingStatus = 'draft' | 'published' | 'closed'

export interface PublicPosting {
  id: number
  title: string
  /** YYYY-MM-DD */
  apply_start: string
  /** YYYY-MM-DD */
  apply_end: string
  phase: PostingPhase
  /** 작성 중 / 접수 예정 / 접수 중 / 마감 */
  phase_label: string
  /** 규칙이 연결된 기본 사업인지. */
  builtin: boolean
  can_apply: boolean
  apply_path: string | null
  has_notice: boolean
}

export interface PublicPostingDetail extends PublicPosting {
  guidance_text: string
  /** 공고문을 인라인으로 여는 주소. 파일이 없으면 null. 담당자 응답에서는 담당자용 주소다. */
  notice_url: string | null
}

export interface OfficerPosting extends PublicPostingDetail {
  status: PostingStatus
  has_forms: boolean
  /** 서식 PDF를 인라인으로 여는 주소. 파일이 없으면 null. */
  forms_url: string | null
  notice_file_name: string | null
  forms_file_name: string | null
  application_count: number
  /** 담당자 판단이 없고 AI 판정이 적합이 아닌 건. 보류한 건은 판단한 것으로 센다. */
  needs_check_count: number
  /** 사업명을 고치거나 지울 수 있는지. 기본 사업은 false다. */
  editable: boolean
  created_at: string | null
  updated_at: string | null
  published_at: string | null
}

export interface NewPostingFields {
  title: string
  /** YYYY-MM-DD */
  apply_start: string
  /** YYYY-MM-DD */
  apply_end: string
  notice_pdf: File
  forms_pdf: File
  forms_pdfs?: File[]
  required_docs?: string[]
  guidance_text?: string
  workflow_version?: number
}

export type PostingPatch = Partial<Pick<OfficerPosting, 'title' | 'apply_start' | 'apply_end' | 'guidance_text'>>

/** `json<T>`가 던진 오류가 404였는지. 없는 사업과 일시 오류를 화면에서 가른다. */
export const isNotFound = (error: unknown) => error instanceof Error && /실패 \(404\)/.test(error.message)

/**
 * 사업을 고치는 호출. 실패하면 서버가 준 한국어 문장을 그대로 던진다 — 어느 칸이
 * 왜 틀렸는지가 그 문장에 들어 있다. 204 응답에는 본문이 없다.
 */
async function writePosting<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
    officerSessionResponse(path, res)
  } catch {
    throw new Error('서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.')
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
    throw new Error(typeof body?.detail === 'string' ? body.detail : `요청을 처리하지 못했습니다 (${res.status})`)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

/** 기본 사업의 건수를 목업 목록에서 셌는지. 사업 목록의 목업 안내에 쓴다. */
let mockCountsUsed = false
export const isOfficerMockCounted = () => mockCountsUsed

/**
 * 신청 목록이 목업으로 채워지는 경우에는 기본 사업의 건수도 목업 목록에서 센다.
 * 카드의 숫자와 그 카드를 눌러 들어간 목록의 숫자가 같아야 한다. 신청 목록은
 * `?mock=1`이거나, `?mock=0`이 아니면서 실제 접수 건이 0건일 때 목업으로 바뀐다.
 */
async function withMockCounts(posting: OfficerPosting): Promise<OfficerPosting> {
  if (!posting.builtin) return posting
  const mode = mockMode()
  const mocked = !mode.blocked && (mode.forced || posting.application_count === 0)
  mockCountsUsed = mocked
  if (!mocked) return posting
  const list = (await loadOfficerMocks()).mockOfficerList({ role: 'province', program: YOUTH_PROGRAM, sort: 'submitted', page: 1, page_size: 1 })
  return { ...posting, application_count: list.total, needs_check_count: list.queues.needs_check }
}

/** 신청자 화면: 게시됐거나 마감된 사업. 접수 중 → 접수 예정 → 마감 순으로 온다. */
export const fetchPostings = async (): Promise<PublicPosting[]> =>
  (await json<{ items: PublicPosting[] }>('/api/postings')).items

export const fetchPosting = (id: number) => json<PublicPostingDetail>(`/api/postings/${id}`)

/** 담당자 화면: 작성 중인 사업까지. 작성 중이 맨 앞에 온다. */
export const fetchOfficerPostings = async (): Promise<OfficerPosting[]> => {
  if (mockMode().forced) return [await withMockCounts((await loadOfficerMocks()).mockPosting())]
  return Promise.all((await json<{ items: OfficerPosting[] }>('/api/officer/postings')).items.map(withMockCounts))
}

export const fetchOfficerPosting = async (id: number): Promise<OfficerPosting> => {
  if (mockMode().forced) return withMockCounts((await loadOfficerMocks()).mockPosting())
  return withMockCounts(await json<OfficerPosting>(`/api/officer/postings/${id}`))
}

/** 작성 중 상태로 만든다. multipart라 Content-Type은 브라우저가 붙인다. */
export function createPosting(fields: NewPostingFields) {
  const body = new FormData()
  body.append('title', fields.title)
  body.append('apply_start', fields.apply_start)
  body.append('apply_end', fields.apply_end)
  body.append('notice_pdf', fields.notice_pdf)
  body.append('forms_pdf', fields.forms_pdf)
  for (const form of fields.forms_pdfs || []) body.append('forms_pdfs', form)
  if (fields.workflow_version !== undefined) body.append('workflow_version', String(fields.workflow_version))
  if (fields.required_docs !== undefined) body.append('required_docs', JSON.stringify(fields.required_docs))
  if (fields.guidance_text !== undefined) body.append('guidance_text', fields.guidance_text)
  return writePosting<OfficerPosting>('/api/officer/postings', { method: 'POST', body })
}

export const updatePosting = (id: number, patch: PostingPatch) =>
  writePosting<OfficerPosting>(`/api/officer/postings/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })

export const publishPosting = (id: number) =>
  writePosting<OfficerPosting>(`/api/officer/postings/${id}/publish`, { method: 'POST' })

export const closePosting = (id: number) =>
  writePosting<OfficerPosting>(`/api/officer/postings/${id}/close`, { method: 'POST' })

/** 작성 중인 사업만 지울 수 있다. 올린 PDF도 함께 지워진다. */
export const deletePosting = (id: number) =>
  writePosting<void>(`/api/officer/postings/${id}`, { method: 'DELETE' })

export const fetchReasonExplanation = (id: number, role: string) => mockMode().forced
  ? Promise.resolve({ text: '제출 원본과 규칙 결과를 확인해 주세요.', label: '담당자 확인 안내', basis: '근거는 규칙 결과입니다.' })
  : json<{ text: string; label: string; basis: string }>(`/api/officer/applications/${id}/reason-explanation?${query({ role })}`)
