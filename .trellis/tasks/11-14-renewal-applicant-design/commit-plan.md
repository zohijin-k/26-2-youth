# Approved commit plan

The owner approved both commit groups and inclusion of the existing preparation files on 2026-11-15, then confirmed the continuation scope is the current applicant design task only. Browser acceptance remains pending. Save the implementation and verification record without archiving the task. Do not push.

## 1. `feat(frontend): apply applicant design system and updated hub logo`

- `demo/frontend/src/App.tsx`
- `demo/frontend/src/api.ts`
- `demo/frontend/src/app-shell.css`
- `demo/frontend/src/assets/brand/jbyouthhub-logo.png`
- `demo/frontend/src/components/ApplicantFileLink.tsx`
- `demo/frontend/src/components/ApplicantFilePreview.tsx`
- `demo/frontend/src/components/ApplicantModal.tsx`
- `demo/frontend/src/components/ApplicantStatusBadge.tsx`
- `demo/frontend/src/components/Dialog.tsx`
- `demo/frontend/src/components/SignaturePad.tsx`
- `demo/frontend/src/forms/FormSheet.tsx`
- `demo/frontend/src/forms/PdfFormsWorkspace.tsx`
- `demo/frontend/src/forms/pdf-forms-workspace.css`
- `demo/frontend/src/lib/file-precheck.ts`
- `demo/frontend/src/lib/receipt-steps.ts`
- `demo/frontend/src/lib/upload-estimate.ts`
- `demo/frontend/src/pages/applicant/ApplicantApp.tsx`
- `demo/frontend/src/pages/applicant/ApplyFlow.tsx`
- `demo/frontend/src/pages/applicant/DocumentUpload.tsx`
- `demo/frontend/src/pages/applicant/FinalCheck.tsx`
- `demo/frontend/src/pages/applicant/IdentityCheck.tsx`
- `demo/frontend/src/pages/applicant/MyPage.tsx`
- `demo/frontend/src/pages/applicant/ProgramFinder.tsx`
- `demo/frontend/src/pages/applicant/ProgramInfo.tsx`
- `demo/frontend/src/pages/applicant/SubsidyItems.tsx`
- `demo/frontend/src/pages/applicant/applicant-shell.css`
- `demo/frontend/src/pages/applicant/apply-flow.css`
- `demo/frontend/src/pages/applicant/document-upload.css`
- `demo/frontend/src/pages/applicant/final-check.css`
- `demo/frontend/src/pages/applicant/identity-check.css`
- `demo/frontend/src/pages/applicant/my-page.css`
- `demo/frontend/src/pages/applicant/program-finder.css`
- `demo/frontend/src/pages/applicant/program-info.css`
- `demo/frontend/src/pages/applicant/subsidy-items.css`
- `demo/frontend/src/pages/applicant/upload-queue.ts`
- `demo/frontend/src/styles/base.css`
- `demo/frontend/src/styles/components.css`
- `demo/frontend/src/styles/tokens.css`
- `demo/frontend/tests/file-precheck.test.ts`
- `demo/frontend/tests/receipt-steps.test.ts`
- `demo/frontend/tests/upload-estimate.test.ts`
- `demo/frontend/tests/upload-queue.test.ts`
- `demo/frontend/tests/upload-transport.test.ts`

## 2. `docs: record applicant design contracts and verification limits`

- `.trellis/spec/frontend/applicant-design-system.md`
- `.trellis/spec/frontend/index.md`
- `.trellis/spec/frontend/pdf-form-workspace.md`
- `.trellis/spec/frontend/state-management.md`
- `.trellis/tasks/11-14-renewal-applicant-design/commit-plan.md`
- `.trellis/tasks/11-14-renewal-applicant-design/design.md`
- `.trellis/tasks/11-14-renewal-applicant-design/implement.md`
- `.trellis/tasks/11-14-renewal-applicant-design/prd.md`
- `.trellis/tasks/11-14-renewal-applicant-design/research/baseline-style-inventory.json`
- `.trellis/tasks/11-14-renewal-applicant-design/research/design-audit.json`
- `.trellis/tasks/11-14-renewal-applicant-design/research/officer-css-comparison.json`
- `.trellis/tasks/11-14-renewal-applicant-design/research/verify_design.py`
- `.trellis/tasks/11-14-renewal-applicant-design/verification.md`

## Existing preparation files — approved for commit 1

These were already dirty or untracked before the design session. The owner explicitly approved including them; add every path below to commit 1.

- `THIRD_PARTY_NOTICES.md`
- `demo/frontend/src/assets/fonts/PretendardGOV/LICENSE.txt`
- `demo/frontend/src/assets/fonts/PretendardGOV/PretendardGOV-Bold.subset.woff2`
- `demo/frontend/src/assets/fonts/PretendardGOV/PretendardGOV-Medium.subset.woff2`
- `demo/frontend/src/assets/fonts/PretendardGOV/PretendardGOV-Regular.subset.woff2`
- `demo/frontend/src/components/ConfirmDialog.tsx`
- `demo/frontend/src/components/Icon.tsx`
- `demo/frontend/src/components/Notice.tsx`
- `demo/frontend/src/components/ProgressBar.tsx`
- `demo/frontend/src/components/Spinner.tsx`
- `demo/frontend/src/hooks/useBeforeUnload.ts`
- `demo/frontend/src/hooks/useDocumentTitle.ts`
- `demo/frontend/src/lib/error-copy.ts`
- `demo/frontend/src/lib/error-copy.test.ts`
- `demo/frontend/src/lib/format.ts`
- `demo/frontend/src/lib/format.test.ts`
- `demo/frontend/src/lib/identity-validation.ts`
- `demo/frontend/src/lib/identity-validation.test.ts`

## Excluded by default

- `logo.png` — owner-provided root original; the copied runtime asset is in commit 1.
- `.trellis/tasks/11-14-renewal-applicant-design/task.json` — pre-existing task status change.

Approval is recorded above; no additional confirmation is required for these groups. Do not archive or use `/trellis:finish-work` until the remaining browser acceptance is complete.

## Execution record

- Commit 1 completed: `258e88c1dbdc54bff635c90e1ede6d33a7aafe50` (61 files, including all approved preparation files).
- Commit 2 saves this approval/execution record, design contracts and verification results.
- No push, archive or completed-status transition: browser acceptance is still pending.
