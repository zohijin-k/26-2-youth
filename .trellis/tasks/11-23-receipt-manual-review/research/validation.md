# Validation — 2026-11-23 KST

Base: youth main 19a56fa7137133bfbdee2d8ea920b62b0ad62fbf (neutral OCR PR #37 merged). Isolated branch feat/youth-receipt-manual-review. macOS arm64, Python 3.14.6, Node 26.13.1. External OCR/LLM providers disabled; synthetic temporary DB/files only. No production migration/deployment. PRODUCTION_NOT_READY.

- Full `python -B -m pytest -q -p no:cacheprovider demo/backend/tests engine_v2/tests`: **3,598 passed, 3 skipped**, 144.65s. Backend 2,325; engine 1,273. Three existing skips require synthetic fonts; own models are present and hash-verified. Prior full run also 3,598/3.
- New `demo/backend/tests/test_receipt_manual_review.py`: **36 passed** (final independent check, 1.97s). Actual receipt slots, PDF/PNG/JPG, callbacks forbidden, malformed/empty/encrypted/wrong-slot errors, original byte and full-table invariance, owner/officer authorization, mixed PDF requiring independent slots/reading, dangling original/absence refusal, actual submit/review/CAS/memo/immutability, other FAIL precedence, historical preservation and unchanged non-receipt supplement deadlines.
- Policy set: **30 passed**: existing non-receipt 29 unchanged plus the explicitly superseded receipt-quality case now requiring manual review. The other two original image-size cases also now test no receipt quality measurement. No engine source is changed.
- Local `.github/ci/backend.py`: **453 passed** with network and SQLite-root restrictions (includes 36 receipt regressions; absent module fails closed). Final committed-source run is recorded in external evidence. Existing Review CAS, mixed-writer and integrity-closure tests remain unchanged.
- `node node_modules/typescript/bin/tsc -b`, `npm run build`, `npm run lint`: exit 0; all Node test files via `.github/ci/frontend.mjs`: **138 passed**.
- Real browser lifecycle: public API create/form/self-check/consent/selection/upload/submit, then real officer UI inline PDF + PNG, manual-review panel without OCR confidence, existing hold/memo and reload, submitted mutation 409: **Chromium 159.0.8154.6, Firefox 159.0, WebKit 27.2 all PASS**. Creation uses legacy public API fixtures, not a fully typed modern applicant UI journey; non-receipt files use authored fixture OCR. The original bytes, server pipeline and officer UI are real. Own-OCR regression is separately covered by the full suite. Servers shut down after checks.
- Browser harness correction: wait for the exact original-file request, document loading, changed nonblank canvas and manual panel before taking screenshots. An earlier Firefox navigation AbortError was observed once; the final corrected harness passed all three engines without page errors. No unrelated viewer code was changed.
- Legacy date-parity fixture expected the whole application to PASS despite selected receipts: only its aggregate expectation is changed to NEEDS_REVIEW; all interview document/date assertions remain unchanged.

Original main was 3,562 passed/3 skipped. The 36 added tests account for the new 3,598. The existing receipt-quality tests change only the policy explicitly authorized by the user. `engine/`, `engine_v2/`, DB models, Review revision/guard implementation, officer decision routes and DocumentViewer are untouched.

## Source/review limits

Valid file contents are intentionally not classified as receipts; officers must detect semantically incorrect evidence. Historical stored OCR/results/decisions are not rewritten or migrated. There is no receipt-specific approval endpoint; existing application-level memo/decision/CAS records the review. Routine receipt-only manual review does not start a deficiency/supplement deadline.

The earlier README PRs youth #36 and officer #42 are held separately because inherited standalone P4/P6 calls lack CAS preconditions and P16/P18 assertions disagree with current date behavior. Those scenario defects are not fixed or hidden by this receipt change. Existing current-main pytest, critical CI and requested policy guards pass. Remaining engine decisions P1–P19 and README decisions (8) remain undecided; P20 records only the explicit receipt decision.

External evidence directory: `/private/tmp/phase7d-finish-20261123/evidence` (JUnit, exact commands, source/ref manifests and browser screenshots).
