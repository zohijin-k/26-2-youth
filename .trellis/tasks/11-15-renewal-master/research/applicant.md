# Applicant stages

## Stage 1

Historical search: `git log --all -S bankbookFileName` and `-S accountHolder` found 1c686a3 `FormJobApplication.tsx`. It had an account block (bank name, holder, account number, bankbook attachment). Its `FormSheet.FileAttach` only retained the selected filename. Restored the missing holder/attachment alongside the existing qualification block, adding real file persistence through the document upload endpoint and existing inline preview.

The bankbook slot already existed as `bank_account` (upload=false, fulfilled by account-form attachment), so its existing text now matches the UI. New bankbook uploads are limited to 20MB, inspect content and reject invalid/encrypted files, and remain NEEDS_REVIEW for officer original-account confirmation. They do not call the OCR engine or change rules. Existing scenario-only filename values remain compatible.

New acceptance: 9 backend cases (including parametrization): missing holder/attachment and restoration, stale-save filename preservation, identity-name mismatch blocks final and submit, five invalid uploads, encrypted PDF, full API identity → form → fixtures upload → submission/archive and unchanged JP numbering/first-come. All test storage and DB are temporary.

Targeted backend verification: 75 passed (new attachment cases plus existing officer queue and age suites). Frontend typecheck/lint passes.

Changed files: api/applications.py, api/documents.py, api/review.py, test_account_attachment.py, frontend AccountInputs.tsx, PdfFormsWorkspace.tsx, form1-model.ts, ApplyFlow.tsx. No existing tests changed.
