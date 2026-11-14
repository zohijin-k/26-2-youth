# Design — step 1

This file is the contract between the backend and frontend halves. Both are implemented in parallel; do not change a name or shape here without updating this file.

## Naming

The code already uses "program" for the rule sets in `rules/programs.py` and the routes `/api/programs`. The new stored entity is a **posting** (`ProgramPosting`): one program as posted by an officer. The UI always says "사업".

## Data model — `ProgramPosting` (table `programposting`, in `demo/backend/models.py`)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int, primary key | used in URLs |
| `title` | str | 1–100 characters after trimming |
| `apply_start`, `apply_end` | date | `apply_start <= apply_end` |
| `status` | str | `draft` \| `published` \| `closed` |
| `rule_code` | str, nullable, unique | set only for built-in programs (`job_package`); links to `rules/programs.py` and `Application.program_code` |
| `notice_file_name`, `forms_file_name` | str, nullable | original names, for display |
| `notice_path`, `forms_path` | str, nullable | relative to the storage root: `postings/<id>/notice.pdf`, `postings/<id>/forms.pdf` |
| `guidance_text` | str, default `""` | filled in step 3 |
| `template_json` | JSON, default `{}` | filled in step 3 |
| `created_at`, `updated_at` | datetime | |
| `published_at` | datetime, nullable | |

Built-in row: `init_db()` inserts one row with `rule_code="job_package"`, `status="published"` and the title from `get_program("job_package")`, if no row with that `rule_code` exists. `apply_start` is the rule's `apply_period` start. `apply_end` is the rule's `apply_period` end when that is on or after the seed day; otherwise it is December 31 of the seed day's year, so the existing applicant flow stays usable in the demo after the real period has passed. The seed day comes from the same "today" source as the phase derivation (`api/postings._today`). The posting's period is listing and gating data owned by the officer (editable through PATCH); the rule set's own dates (announcement date, criteria) are untouched. The seed is idempotent and never overwrites an existing row. The savings program is not seeded.

## Derived fields in every response

- `phase`: `draft` when status is draft; `closed` when status is closed or today is after `apply_end`; `upcoming` when published and today is before `apply_start`; otherwise `open`.
- `phase_label`: 작성 중 / 접수 예정 / 접수 중 / 마감.
- `builtin`: `rule_code is not None`.
- `can_apply`: `phase == "open" and builtin` (until step 4).
- `apply_path`: `"/apply/identity"` when `can_apply`, else `null`.
- `has_notice`, `has_forms`: whether the file exists.

## API

All errors use `HTTPException(status, "한국어 문장")` like the rest of the backend. No authentication, like the existing officer API.

### Public — router prefix `/api/postings`

| Method and path | Result |
| --- | --- |
| `GET /api/postings` | `{"items": [PublicPosting]}`; status `published` or `closed` only; order: open, upcoming, closed, then newest `apply_start` first |
| `GET /api/postings/{id}` | `PublicPostingDetail`; 404 for unknown or draft |
| `GET /api/postings/{id}/files/notice.pdf` | the notice PDF inline; 404 when absent or draft |

`PublicPosting`: `id, title, apply_start, apply_end, phase, phase_label, builtin, can_apply, apply_path, has_notice`.
`PublicPostingDetail`: the same plus `guidance_text` and `notice_url` (`/api/postings/{id}/files/notice.pdf` or `null`).

### Officer — router prefix `/api/officer/postings`

| Method and path | Result |
| --- | --- |
| `GET /api/officer/postings` | `{"items": [OfficerPosting]}`, drafts included; order: drafts first, then as the public list |
| `POST /api/officer/postings` | multipart: `title`, `apply_start`, `apply_end` (ISO dates), `notice_pdf`, `forms_pdf`; creates a draft; 201 with `OfficerPosting` |
| `GET /api/officer/postings/{id}` | `OfficerPosting` |
| `PATCH /api/officer/postings/{id}` | JSON, any of `title`, `apply_start`, `apply_end`, `guidance_text`; built-in rows accept `apply_start`, `apply_end` and `guidance_text` with the same validation as other rows, and reject `title` with 409 |
| `POST /api/officer/postings/{id}/publish` | draft or closed → published; sets `published_at` on first publish; 409 if either PDF is missing on a non-built-in row |
| `POST /api/officer/postings/{id}/close` | published → closed; 409 from other states |
| `DELETE /api/officer/postings/{id}` | drafts only, never built-in (409); removes its files; 204 |
| `GET /api/officer/postings/{id}/files/{kind}.pdf` | `kind` is `notice` or `forms`; inline |

`OfficerPosting`: every `PublicPostingDetail` field plus `status, has_forms, forms_url, notice_file_name, forms_file_name, application_count, needs_check_count, editable (not builtin), created_at, updated_at, published_at`.

Counts: for a built-in row, over applications with `program_code == rule_code` and status not draft. `application_count` is all of them. `needs_check_count` is those with no officer decision and an AI status other than PASS (NEEDS_REVIEW, FAIL or not reviewed). Reuse the entry logic in `api/officer.py`; do not re-implement status derivation. Non-built-in rows return 0 for both until step 4.

Validation (422 with the field named in the message): title empty or longer than 100; unparsable date; start after end; a file missing; a file that does not start with `%PDF-`; a file larger than 20 MB.

Files: stored under the existing storage root (`api/common.STORAGE`) in `postings/<id>/`. Served with `Content-Disposition: inline` using the same approach as `api/files.py`. The words `download` and `attachment` must not appear in any new or changed source file under `demo/` (scenario P4 scans for them).

## Frontend

### Routes

| Path | Screen | Chunk |
| --- | --- | --- |
| `/` | `pages/applicant/ProgramFinder.tsx` | applicant |
| `/programs/:id` | `pages/applicant/ProgramInfo.tsx` | applicant |
| `/apply/...` | `pages/applicant/ApplyFlow.tsx` (existing) | applicant |
| `/officer` | `pages/officer/ProgramList.tsx` | officer |
| `/officer/programs/new` | `pages/officer/NewProgram.tsx` | officer |
| `/officer/programs/:id...` | `pages/officer/ProgramWorkspace.tsx` → existing `OfficerConsole` for the built-in program | officer |

- `currentMode()` keeps its rule. `App.tsx` lazy-loads two entry components instead of the two screens: `pages/applicant/ApplicantApp.tsx` and `pages/officer/OfficerApp.tsx`. Each owns the paths of its side and renders exactly one screen. `ApplyFlow` is mounted only on `/apply...`, so `/` and `/programs/:id` create no draft.
- `goToHome()` goes to `/`.
- `OfficerConsole` takes its base path from the workspace (`/officer/programs/<id>`); its role and review segments follow that base. Old links `/officer/<role>` and `/officer/<role>/review/<id>` are rewritten to the built-in program's workspace and open the same view.
- `?mock=1` keeps working for the application list. When mock mode is forced, the built-in program's card counts come from the mock list so the numbers match what the list shows.
- In-side navigation uses `routeUrl` + state, as the existing screens do. Moving between the applicant and officer sides stays a full page load.

### API client (`src/api.ts`)

Add types `PublicPosting`, `PublicPostingDetail`, `OfficerPosting` and functions `fetchPostings`, `fetchPosting`, `fetchOfficerPostings`, `fetchOfficerPosting`, `createPosting(FormData fields)`, `updatePosting`, `publishPosting`, `closePosting`, `deletePosting`. Use the existing `json<T>` helper and error handling.

### Look and behaviour

- Applicant screens use the applicant shell and its tokens (`--workspace-*`); officer screens use the officer look in `officer.css`. Reuse existing classes (`.btn`, skeletons, `Modal`, `PdfPages` for the notice viewer). New CSS goes in a file per screen, every selector prefixed with that screen's block name. No new unscoped global class names.
- Every list has loading (existing skeleton pattern), empty and error states with a retry. Buttons that write are disabled while the request runs. Destructive actions (delete draft, close) ask for confirmation through `Modal`.
- Cards are links or buttons reachable by keyboard; status is text plus colour, never colour alone. Dates are shown as `2026.11.01 ~ 2026.11.30`.
- Korean UI text, plain and short, consistent with the existing screens.

## Out of scope for step 1

Template detection and editing, guidance drafting, application list redesign, applying to non-built-in programs, changes to `ReviewDetail.tsx` / `DocumentViewer.tsx`.

## Clarifications made during implementation

- In `OfficerPosting`, `notice_url` and `forms_url` point at the officer file routes (`/api/officer/postings/{id}/files/notice.pdf`, `.../forms.pdf`), because the public route returns 404 for drafts. In `PublicPostingDetail`, `notice_url` is the public route. Clients use the URL from the response.
- Validation messages name the field by its Korean label: `title` 사업명, `apply_start` 접수 시작일, `apply_end` 접수 종료일, `notice_pdf` 공고문 PDF, `forms_pdf` 서식 PDF. `detail` is always one sentence.
- "Today" for both the built-in seed and phase derivation comes from `models.posting_today()`; tests replace that one function.
- A held (보류) application counts as decided, so it is not part of `needs_check_count`.
