# 리뉴얼 1단계: 사업 저장소와 사업 목록 화면

Parent: `11-14-program-service-renewal` (read its `prd.md` for the fixed constraints).

## Goal

Give the service one program store and the first screens on both sides that read it, so that "officer publishes → applicant sees it" works end to end.

## Requirements

### R1 — Program store (backend)

- A persistent store of programs posted by officers ("사업"): title, application period, status (작성 중 / 게시 / 마감), notice PDF, form-bundle PDF, guidance text, form template (empty for now).
- The existing job package appears in the store as one already-published program linked to its rule set, without changing how its applications, rules or criteria work.
- Officer API: list (with application count and needs-check count), create a draft with both PDFs, read, edit basic fields, publish, close, delete a draft, view the stored PDFs.
- Public API: list published programs, read one, view its notice PDF. Drafts are never visible publicly.
- Files are served inline only.

### R2 — Applicant screens

- `/` is "사업 찾기": published programs as cards (name, period, 접수 중 / 접수 예정 / 마감).
- `/programs/:id` is "사업 안내": name, period, guidance text, notice PDF viewer when there is one, and "신청하기".
- "신청하기" for the job package enters the existing flow at `/apply/identity`. For programs whose application flow is not built yet (step 4), the button is disabled with a short explanation.
- The applicant flow under `/apply/...` behaves as before. Its home button goes to `/`.
- Opening `/` no longer creates a draft application.

### R3 — Officer screens

- `/officer` is the program list: cards with name, period, status, application count, needs-check count, and "새 사업 올리기".
- `/officer/programs/new` creates a draft from title, period, notice PDF and form-bundle PDF, with validation messages next to the fields.
- `/officer/programs/:id` is that program's workspace. For the job package it shows the existing application list and review detail unchanged in content. For other programs it shows the program summary, its PDFs, publish/close/delete actions and an empty application state.
- Existing officer links (`/officer/<role>`, `/officer/<role>/review/<id>`, `?mode=officer`, `?mock=1`) keep opening the same list or detail.

### R4 — Nothing else changes

`ReviewDetail.tsx` and `DocumentViewer.tsx` stay byte-identical. `engine_v2`, `engine`, rule modules and existing API responses are unchanged. No new dependency.

## Acceptance Criteria

- [x] Backend tests for the store pass (create, validation failures, publish/close/delete rules, public visibility, counts, inline files), and the existing backend suite still passes (1,227 + 62 = 1,289).
- [x] All 18 scenario modules exit 0 (P4 included).
- [x] `npm run lint` 0 warnings, `npm run build` exit 0 with no chunk-size notice, `node src/forms/phone.test.ts` exit 0.
- [x] Browser: create a draft → publish → it appears at `/`; close → shown as 마감; job package "신청하기" reaches `/apply/identity`; `/officer?mock=1` and an old review link still work; `/` creates no draft application.
- [x] `git diff main -- demo/frontend/src/pages/officer/ReviewDetail.tsx demo/frontend/src/pages/officer/DocumentViewer.tsx engine_v2 engine` is empty.
