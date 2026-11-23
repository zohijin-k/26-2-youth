# Standalone scenario stabilization (2026-11-23)

PRODUCTION_NOT_READY. Synthetic temporary databases/files only; no production migration or deployment.

P4/P6/P16/P18 failed on both youth main `19a56fa7137133bfbdee2d8ea920b62b0ad62fbf` and README PR #36 HEAD `43a09665cde26f072653967aa214daa00ffc7276`. Their four source blobs were identical at those refs. These failures predate the README change and the receipt PR.

| Module | Existing failure | Corrected verification |
|---|---|---|
| P4 | Missing CAS token returned 428; strict source scan also matched an upload comment | Observe authorized GET revision; send single/bulk revision fields, assert missing428/type422/stale409 with full Review/Application invariance; remove only misleading prose/internal error wording, keep the scan unchanged |
| P6 | Missing CAS token, then missing decision label | Send exact observed revision and assert successful +1 |
| P16 | Event aliases were expected to establish absent issue-date labels | Assert NEEDS_REVIEW / REQUIRED_FIELD_UNREADABLE and retain explicit issue-label PASS controls |
| P18 | Low-confidence dates were expected to establish definite bounds violations | Assert LOW_OCR_CONFIDENCE review, no definite date violation; confident out-of-range dates still FAIL |

Receipt PR #38 was verified separately and merged as `03dc62f68b48a67bbd9c910a1609a44a39a3ccc1`. Its explicitly approved policy intentionally supersedes P5/P6/P12's old automatic receipt amount/date verdict expectations. Those scenarios now assert manual review, empty extraction and unused OCR callbacks. Every temporary-store helper used here points `api.common.STORAGE` at the same synthetic document store, so the required-original check is exercised rather than bypassed. S10 submits successfully with both manual receipt reasons and no deadline caused solely by manual review; an independent unreadable abstract still starts its existing supplementation period.

All 18 modules passed: **1930 checks plus P14's eight form sets**. P4 199, P6 271, P16 105, P18 182. No skipped modules or relaxed safety checks. Existing Phase7 policy19 rows and the three damaged payment NEEDS_REVIEW cases remain unchanged.

Run from the repository root:

```bash
python -m demo.backend.tests.run_p4_scenarios
python -m demo.backend.tests.run_p6_scenarios
python -m demo.backend.tests.run_p16_job_docs_scenarios
python -m demo.backend.tests.run_p18_applicant_precheck_scenarios
```

P16 tests retained low-level reader/rule interfaces with authored synthetic OCR. Canonical receipt upload bypass is tested independently by `test_receipt_manual_review.py`; low-level extraction is not an automatic upload decision.
