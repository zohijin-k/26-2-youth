# 범용 사업 서비스 리뉴얼

## Approval

Owner decisions on 2026-11-14: renew the whole frontend around user flows; build a real program store in the backend (not browser storage); fill forms on top of the original PDF; show the LLM reason by expanding a row in the application list; Claude implements and verifies directly.

## Goal

Turn the youth job-package demo into a generic program service. An officer posts a program and its forms become the applicant's screens. One program store links both sides: publish → applicants can see it; submit → it appears in the officer's list.

## User flows

Officer: program list → post a new program (title, application period, notice PDF, form-bundle PDF) → draft form template is detected → officer confirms and corrects the template (position, kind, required, autofill from identity) → guidance message (LLM draft from the notice, officer edits) → preview and publish.

Applicant: find a program → program information → identity check → fill the forms as the template defines, sign → upload documents (existing OCR reading) → submit (filled form PDF is produced).

## Fixed constraints

- The review detail screen (`pages/officer/ReviewDetail.tsx`, `DocumentViewer.tsx`) is not modified.
- The 읍·면·동 / 시군 / 도 role tabs stay.
- Application list: tabs 확인 필요 (default) / 적합 / 처리 완료; columns 신청번호·성명·접수일시·처리상태 only; filters are search and period; bulk buttons only when rows are selected; no one-line reason column.
- LLM is used only for the guidance draft and for explaining why a case needs checking. Real document values and real names are never sent to it; only codes, field names and rules.
- Form PDFs are plain PDFs converted from HWP (no field metadata); a template is published only after officer confirmation.
- Scenario P4 reads frontend paths and forbids the words `download` and `attachment` in source under `demo/` outside its allowlist. Keep `forms/PdfFormsWorkspace.tsx`, `forms/pdf-forms-workspace.css`, `pages/applicant/DocumentUpload.tsx` where they are, and do not use those two words in new source.
- Youth and savings repositories stay separate.

## Steps (child tasks, one pull request each)

1. Program store and program list screens — `11-14-renewal-step1-program-store`
2. Officer application list redesign (tabs, four columns, row expansion for the reason) — `11-14-renewal-step2-application-list`
   - Applicant design system (owner's design prompt and the 전북청년허브센터 logo, added 2026-11-14) — `11-14-renewal-applicant-design`. Runs after step 2; steps 3 and 4 build new applicant screens on it.
3. New-program flow: template detection, template editor, guidance message, preview and publish
4. Applicant flow driven by the program and its template; "my applications"
5. Documents, specs and test baselines

## Acceptance (parent)

- Every step's pull request is merged with its own verification record.
- Engine, backend and scenario baselines do not regress; new backend behaviour has tests.
- Both flows can be walked end to end in a browser against the real backend.
