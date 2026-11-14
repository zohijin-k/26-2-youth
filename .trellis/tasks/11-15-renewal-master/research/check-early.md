# Early cross-stage review

Reviewed implemented applicant stages 1–2 and prepared stages 4–6 without mutating shared source during regression gates.

## High-severity findings and prepared fixes

### Account-copy existence can be bypassed after deletion or by a filename

Original-code synthetic API reproduction in a temporary DB/storage confirmed both:

- setting `form1.bankbookFileName` through PATCH without a Document row satisfies that final-check field;
- uploading then DELETE-ing a bank_account Document leaves the old filename, so the final-check requirement stays satisfied even when bytes are gone.

Prepared `/tmp/renewal-bankbook-hardening.patch` adds explicit `CreateRequest.applicant_flow_version` (legacy default 0), sends version 1 from browser createApplication, persists the version marker in doc_context_json and preserves it through context updates. New managed job-package requests and all real bankbook uploads require a matching Document row plus existing bytes. PATCH ignores a spoofed filename without a row; DELETE clears the saved filename. Legacy direct synthetic API fixtures retain version 0 compatibility as requested by root.

### Same-name writes can mutate original bytes before the final draft check

Original bankbook upload writes bytes to the old applicant-name/slot/original-filename path before checking draft status in the DB transaction. A concurrent submit can make the request fail yet leave overwritten original bytes. Prepared fix writes to a fresh UUID subfolder while preserving the display basename; failed uncommitted candidates are removed. Deletion of submitted bankbook copies is refused. Earlier stored bytes remain unchanged when replacing a same-name file.

### AcroForm drafts initially failed layout-save validation

Prepared draft.py supplied `group=None` for nonradio widgets while validate_layout accepted only strings. Root was notified and normalized this to an empty group; current prepared validation now accepts a synthetic text-widget draft. No outstanding issue in the latest prepared files.

## Validation of prepared account fix

A temporary package copy contains source overlays only and uses synthetic PDFs, an isolated SQLite DB/storage, and the permitted public form templates/synthetic sample fixtures. New integrity suite: 5 passed. Combined new integrity plus stage-1 account suite: 14 passed. No existing tests changed. `git apply --check /tmp/renewal-bankbook-hardening.patch` passed against current shared source before stage 7 integration.

The patch includes new test file `demo/backend/tests/test_account_copy_integrity.py`; root can apply the patch once during stage 7. Application/Document/review hunks need merging with generic-runtime preparation, preserving both generic branches and marker retention.

## Other boundaries checked

- Identity entry now restores only and allocates through ensureApplication at verification submit; remembered/inflight state preserves the application ID for retry and refresh. No new allocation on repeated identity opens was found.
- Managed form geometry is checked on the server against real PDF page bounds; saved edits clear confirmation hash, and publication checks the matching confirmed layout hash. Uncertain generated fields remain review-required.
- Legacy postings remain registry-only/non-applicable; managed workflow publication restrictions are separate to preserve unchanged old tests.
- Template editor holds unsaved edits across tabs; publish is blocked while dirty or busy. No protected review/detail styles are modified by the prepared editor.
- Existing full-stage failures must remain uncommitted; prepared source remains isolated until root's stage gates pass.

## Combined stage 7 handoff

Prepared `/tmp/renewal-stage7-combined.patch` against captured shared stage 6 source. It merges generic runtime21 tests with account integrity5 tests, keeping generic create/freeze/read/patch/identity/doc-context/review branches and all bankbook marker/existence checks. Sole overlapping create hunk was manually reconciled. Targeted synthetic-only combined verification: **125 passed** (new generic21 + new integrity5 + existing account9 + existing postings/officer90). Full log in `/tmp/renewal-stage7-combined-tests.log`; patch apply-check passed. Apply only the combined patch, not its two component patches again.
