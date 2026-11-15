# Real API synthetic browser journey

Prepared scripts only; servers must wait for root stage9 readiness. `visual-e2e.mjs` uses the actual local API and UI at PC 940×1000, synthetic PDFs and a 1600×1800 unknown PNG, real owner cookies and the existing shared PDF workspace/uploader. It creates/reviews/confirms/publishes through officer UI, verifies no draft is allocated by three identity visits, then completes applicant identity→form/signature→upload→final→receipt→my page and checks officer needs-check reasons plus rule-based automatic explanation. All paths/screenshots are English.

Setup: `.venv/bin/python .trellis/tasks/11-15-renewal-master/visual-fixtures.py` (already tested; table produces exactly 3 draft fields). Backend wrapper disables local/external OCR and LLM credentials/settings, with default none provider. It supports `RENEWAL_VISUAL_ROOT` so the final run can use a fresh isolated /tmp directory while the baseline database remains intact. Its `/__visual__/counts` returns value-free synthetic row counts.

After checking ports are free: run `.venv/bin/python -m uvicorn visual_backend:app --app-dir .trellis/tasks/11-15-renewal-master --host 127.0.0.1 --port 8010` with `RENEWAL_VISUAL_ROOT=/tmp/renewal-visual/final-run`, and run root frontend using `VITE_API_TARGET=http://127.0.0.1:8010` on 5183 after stage9 adds that setting. Execute `PLAYWRIGHT_BROWSERS_PATH=/tmp/renewal-browser node .trellis/tasks/11-15-renewal-master/visual-e2e.mjs`. Write/read files under the chosen /tmp root only; never use the production runtime DB or storage.

Output: shots/officer-step1..4, applicant-program-info/identity/forms/upload/final/receipt/mypage, officer-needs-check; visual-e2e-result.json records IDs, counts, assertions and browser errors. On failure the script records e2e-failure.png and leaves evidence; it does not delete data. Stop only servers launched for this run.

For final pixel checks, run `VISUAL_PHASE=final visual-officer.mjs` with the final code and builtin-only baseline database (or before creating the synthetic generic program) to isolate UI changes from added registry data. Compare-officer.py reports dimensions/changed pixels; the builtin registry's new read-only badge is an intentional change, while list/review should match. Baseline registry data stays in /tmp/renewal-visual/demo.db.

## Final executed result

Final source was tested with the real API and UI on 8010/5183. Synthetic runtime root: `/tmp/renewal-visual/e2e-complete-20261115`. Counts: applications0→1, postings1→2 (builtin1 plus published generic2), application `JP-2026-000001`. All15 assertions passed;12 E2E screenshots plus3 final officer regression captures saved. Page errors0, test errors0. The explicit refresh check canceled3 in-flight read requests (ERR_ABORTED); later owner API/images succeeded. No real OCR/LLM calls or production runtime reads/writes.

At940px, inspected template editor boxes/properties, published-form preview, actual applicant PDF modal with autofill/text/signature, upload result and officer reasons/tab screenshot. Content is aligned and readable without horizontal clipping. Unknown synthetic PNG remains NEEDS_REVIEW and enters needs-check1/pass0; rule basis plus rules-provider automatic explanation is shown. Owner cookie403 isolation, inline original200, generated written PDF200 and bulk approval409 pass. Existing generic review detail is left unlinked as required.

Final officer baseline comparison at1440px used the preserved builtin-only database before generic fixtures were added: application list0 changed pixels, review0 changed pixels; registry621 changed pixels (0.043125%) from the intentional read-only badge. Exact stats: visual-pixel-comparison.json. Both owned servers were stopped after verification and ports8010/5183 checked free. No product source fix was needed; only automation selectors were adjusted for an already-generated draft, native select labels and duplicate header/receipt navigation.

## Final safety-source rerun

Reran the actual whole UI journey after final whitespace, immutable-submit, unique upload paths, request locking and interrupted-merge guards. Fresh isolated root `/tmp/renewal-visual/e2e-final-safety-20261115`; applications0→1 and postings1→2. All17 assertions pass,12 screenshots refreshed, zero page/test errors. Added real API DELETE and reupload after submission: both409, with exact written-archive PDF bytes unchanged after each attempt. Existing final officer pixel comparisons remain valid because frontend UI did not change. No product fixes or live provider calls were needed.
