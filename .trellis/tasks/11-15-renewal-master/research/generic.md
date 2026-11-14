# Generic posting, form and application integration research

## Compatibility findings

- `demo/backend/tests/test_postings_api.py` asserts exact `PUBLIC_KEYS`, `DETAIL_KEYS` and `OFFICER_KEYS`, including created and list items. Keep those serializers unchanged. Expose new form/file/slot metadata through `GET /api/officer/postings/{id}/workspace`; public application configuration can use an application-bound endpoint.
- Existing legacy create calls supply exactly `title`, `apply_start`, `apply_end`, `notice_pdf` and `forms_pdf`; they require `ProgramPosting.template_json == {}` after creation. Existing tests expect these legacy drafts to publish without reviewed layouts and remain `can_apply=False`. A new managed workflow must be explicitly opted into, e.g. `workflow_version=1`, and the new officer UI always opts in. Keep old registry-only rows visible but non-applicable.
- Tests require existing basic PATCH title/date/guidance responses remain identical. Built-in row's title is immutable but legacy API supports period and guidance edits; new UI can show built-in read-only without breaking that API.
- Stage 6's universal unconfirmed publication restriction conflicts with legacy tests. Root agreed to isolate managed v1 publication restrictions; report the compatibility boundary rather than weakening existing tests.
- Existing file validation only checks PDF magic and size; adding actual PyMuPDF parse/encryption/page validation preserves existing synthetic valid PDFs. Enforce form page bound 20; notice limit can be separately bounded. `MAX_PDF_BYTES=20 MiB` matches old API.
- `ProgramPosting.template_json` exists and can store versioned workflow metadata, selected slots, form manifests and confirmation revisions without changing existing SQLite columns. Add separate tables when application snapshots/filled values require ownership and isolation.

## Recommended managed API contract

Keep legacy CRUD entry points and shapes. Add:

- creation form field `workflow_version=1`; original `forms_pdf` remains supported and allow repeated additional form PDFs;
- `/workspace`: metadata `{workflow_version, required_documents, forms:[{id,title,url,page_sizes,layout,confirmed,revision}], publication_blockers}`;
- `/forms/{form_id}/draft`: derive fresh layout from file; invalidate confirmation;
- `/forms/{form_id}/layout`: validate and save all field geometry/type/required/autofill metadata; invalidate confirmation on any change;
- `/forms/{form_id}/confirm`: reject empty layout or any `needs_review` field; confirm exact revision;
- `/guidance/draft`: deterministic title/period/docs draft by default;
- `/unpublish`: move published to draft. Strict publish validates basic data, stored PDFs, valid period and all forms confirmed.

Layout mutation/confirmation/publish should be transactional and reject edits to published form structure or first withdraw to draft. Fields must be finite numeric values inside actual page bounds, unique opaque IDs, allowed type/source enums and bounded labels. PDF object IDs/AcroForm field names are internal and not public IDs. `needs_review` defaults true for automatic proposals, including high-confidence AcroForm proposals.

## Coordinate and render contracts

`demo/backend/forms/coords.py::FormCoords` contains `form_no`, `title`, `template:Path`, `fields:dict`, `source`, optional `public_form/internal_form/masks/requirements`. Coordinates use top-left PDF points; `page` is zero-based and boxes `[x0,y0,x1,y1]`. `available` requires at least one field and existing template.

Renderer types are only `text`, `check`, `image`. Keep physical `type` compatible and add semantic `kind` (`text`, `number`, `date`, `check`, `radio`, `signature`), with signature mapped to `image`, number/date mapped to `text`, radio mapped to `check`. Add `confidence`, `needs_review`, `required`, `autofill`, `label`, `group_id` and stable opaque IDs without changing existing fixtures. Text needs `x`, baseline `y`, `size`, `align`, `font_family`; checks/images use `box` and page. Existing renderer's text branch expects type text; raw semantic types are not sufficient.

`demo/backend/forms/render.py::render(FormCoords,FilledForm)` can render arbitrary uploaded template paths with no fixture writes. `FilledForm` holds `texts`, selected `checks` and decoded signature `images`. Existing application forms are selected by `forms/values.py::available_forms` and hardcoded `BUILDERS`; generic dispatch must bypass those at API layer. `api/forms.py` owns form listing/layout/template/page/filled-PDF routes, combined PDF generation, submission snapshot and applicant archive-cookie check.

`api/forms.py::snapshot_written_pdf` writes atomically under ignored `storage/forms_exports/<application_no>.pdf`. Reuse this archive path and applicant cookie authorization. Generic submitted archives must use application-frozen layout/PDF revision, not mutable posting metadata. New uploads must not overwrite PDF bytes referenced by existing submitted applications. Public originals can be served through application-owned template routes, inline/no-store.

`form_layout` projects built-in internal keys to `f0000...`; frontend `fetchFormLayout` remaps them with `FORM_FIELD_KEYS[form_no]`. Generic form names have no binding entry and thus naturally retain opaque IDs. Do not expose detector anchor/source metadata, engine/fallback messages or filesystem paths publicly; whitelist geometry, public labels, required/kind/identity source and safe form identifiers.

## PdfFormsWorkspace reuse

The component already loads forms/layouts per application, overlays controls on rasterized PDF pages and offers preview, save and reset. Extend with an explicit generic mode/config rather than a parallel renderer. Current built-in assumptions to guard:

1. `selfCheckItems=JOB_PACKAGE_SELF_CHECK_ITEMS` and always rendered section.
2. `requiredKeys(formNo)` defaults generic unknown forms to job self-check keys; use layout field `required` metadata for generic.
3. Subsidy fetch and selection control behavior; skip entirely for generic.
4. Checkbox value resolution uses dotted keys/group names and final option segment. Generic checks must read/write their own opaque ID booleans, radio fields use explicit `group_id`.
5. `signatureValue/setSignature` map all non-job-consent forms to `job.signature`. Generic signature target must read/write selected opaque field, supporting multiple signatures per form.
6. Hardcoded continue button label “지원 항목 선택하기”; generic label is “서류 업로드로”.
7. Identity locking currently only recognizes keys `name` and `birth`; generic autofill fields carry sources and must be locked consistently server/client where required.
8. `readText` date/system key handling is built-in. Use generic field semantic `kind` for number/date controls and ordinary values for opaque IDs.
9. Reset logic must clear only that form's fields and restore allowed identity defaults.
10. Built-in form APIs cache raster output via coordinate loader; generic page previews need direct `render_page_png(render(custom_spec,filled),...)` or a separate safe cache key that includes immutable template revision and complete input values.

## Document slots and assessment

`rules/required_docs.py::DocRequirement` is reusable. Catalog can be derived from existing built-in checklist permutations, deduplicated by stable slot and retaining `doc_type`, accepted alternatives, required fields, signature/date metadata. Do not treat nonupload `application_form`/`bank_account` placeholders as generic upload slots: bank_account deliberately uses a placeholder RESIDENT_ABSTRACT doc type and would misclassify a bankbook if promoted to upload. Expose only real existing upload slots, with public labels/issuer/notes.

`api/common.py::checklist_for` currently delegates built-in criteria and selections. Add generic snapshot branch returning chosen requirements; never silently use job-package required docs. Preserve exact requirement rules for selected known slots, without adding generic eligibility rules.

`api/documents.py` upload delegates `upload_assessment.assess_upload`, which calls unchanged `check_document`, retains uncertain recognition as NEEDS_REVIEW and known failures. Reuse that boundary and `document_dict` applicant allowlist. Its `_checklist_response` resolves built-in program/criteria and must branch for generic; context update likewise must preserve snapshot metadata. Explicit-slot upload currently has no bounded raw read and validates suffix; new generic path should enforce existing frontend limit and actual PDF/image validation without changing OCR rules. `_upload_merged` can reuse requirement assignment but generic tests should prefer explicit slots.

`upload_assessment` receipt handling calls selected subsidy amounts; generic receipt slots should not require subsidy selections and must retain NEEDS_REVIEW if OCR cannot read evidence. Filename must not establish type/verdict; tests use synthesized body content and renamed files.

## Application/runtime integration

Existing ProgramConfig lives in `rules/programs.py` (the attachment's `programs.py` reference is not api/programs). ProgramConfig encodes scored/first_come only; generic semantics should not accidentally inherit either. Rather than injecting uploaded programs into global `PROGRAMS`, use a new API runtime resolver that delegates built-ins unchanged and carries a `generic` flag. `criteria.default_criteria` directly indexes `PROGRAMS`, so merely adding `get_program` fallback is insufficient.

Recommended generic application snapshot table keyed by existing `Application.id`, storing posting ID, revision, public guidance, selected requirements and frozen forms metadata; filled values remain opaque-key allowlist. Application `program_code` can be `posting_<id>` with runtime resolver using snapshot/posting. Never set it to job_package or generic submissions become mixed with existing quota/order/account/self-check rules.

Call sites requiring generic guard:

- `api/applications.py`: create validation/version assignment, `read` and `verify_identity` age blockers, PATCH value allowlist and locked autofill.
- `api/common.py`: checklist and subsidy estimates.
- `api/documents.py`: checklist response, context validation and assessment boundaries.
- `api/review.py`: `_blockers`, `_run_review`, final check summary, first-come, supplement, submission and status. Generic submit uses existing document blockers (known FAIL still blocks) plus confirmed required fields and identity; generic review aggregate is PASS only when every selected requirement has PASS and required fields complete, otherwise NEEDS_REVIEW. No eligibility engine invocation for generic. Snapshot combined PDF at submit through existing archive function.
- `api/forms.py`: all legacy fixture/BUILDERS dispatch listed above.
- `api/officer.py`: Entry constructor `get_program`, list default sort and first-come rows, `_columns`, reasons and detail safeguards. Once one generic application exists `_load_entries` must not crash all list/count routes.
- `api/postings.py::_counts`: count generic using `posting_<id>`, not rule_code None.

Identity creation timing must preserve successful created application ID in session before verification response so failed network retries reuse it; generic and built-in active keys must be scoped by program to avoid restoring wrong posting.

## Officer list and protected detail

`officer.queue_of`: officer decision -> done; otherwise PASS -> pass; everything else -> needs_check. Reuse; generic Review.final_status drives it. `_doc_cells` uses checklist_for and can count selected generic slots. `_columns` inserts fixed savings document columns for every non-job program, so generic should use ordinary columns or dynamic selected slots. `_load_entries` reads all submitted Application rows and constructs Entry, so it needs generic-safe program resolution even when list filter is job_package.

`OfficerConsole` hardcodes YOUTH_PROGRAM in default query, every patch, criteria route and navigation. Add program prop for new generic use, hide criteria controls and built-in quota/first-come content. `api.ts` also clamps officer fetch/bulk through `youthOfficerRole`; generic requests must not get overwritten to job_package. Reuse ApplicationList tabs and reason expansion; suppress onOpen/onDocument detail handlers for generic outside protected detail and explain pending manual review connection. User expressly allows leaving generic detail unlinked if score sheet cannot be hidden externally.

`review_reasons` returns source rules, failed/uncertain docs and missing slots. Add generic warning “자격 규칙 미설정 — 담당자가 공고문 기준으로 확인” at expansion, including for PASS records. Optional LLM explanation must be below and distinguishable from authoritative stored rules. Bulk final approval currently rejects queue needs_check and must remain intact; inspect `_needs_check_application_numbers` rather than duplicating guards.

### Protected file inventory

Primary immutable detail files:

- `demo/frontend/src/pages/officer/ReviewDetail.tsx`
- `demo/frontend/src/pages/officer/DocumentViewer.tsx`
- `demo/frontend/src/pages/officer/officer.css` (contains .review__, viewer and shared officer styles; protect whole file, use new scoped CSS for posting editor)

Detail dependencies should remain unchanged unless unrelated bundle import refactoring is strictly required and verified:

- `demo/frontend/src/pages/officer/format.ts`
- `demo/frontend/src/components/StatusBadge.tsx`
- `demo/frontend/src/components/Skeleton.tsx` and `skeleton.css`
- `demo/frontend/src/hooks/useDelayedFlag.ts`

Review detail imports API methods/types only; changes inside shared API implementation must preserve built-in route/data behavior. There is no separate detail CSS import in either primary component. Existing officer list/new-program/workspace CSS files are outside detail and can be extended safely with scoped selectors.

## Stage 9 bundle observation

`App.tsx` already lazy-loads ApplicantApp and OfficerApp. The remaining leak is static `api.ts` import of `pages/officer/mock-data.ts`, shared by applicant entry. Dynamic-import the mock module only in officer mock branches; remove runtime isMockId dependency from applicant-shared exports or use a safe lightweight check. Ensure no static cycle pulls mock module back through shared components. Build and inspect transitive applicant entry chunks for `DS-2026-`, not only main index entry (index may contain solely lazy loader).
