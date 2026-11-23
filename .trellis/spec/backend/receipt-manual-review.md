# Youth receipt manual review

Canonical PAYMENT_RECEIPT requirements must short-circuit before the shared assessment reader and check_document. Never call OCR/Document AI, extraction, identity inference, confidence or quality measurement for these slots. File-envelope validation may inspect magic bytes and open PDF/images; it must not read text, classify contents or evaluate administrative rules. Invalid/empty/encrypted attachments are request errors, not document FAIL. Persist NEEDS_REVIEW with RECEIPT_MANUAL_REVIEW and no OCR measurements.

Do not select this policy from a filename or arbitrary _receipt suffix. Preserve mandatory slot presence, original-byte storage, owner cookies, authorized inline file access and draft-only mutations. A dangling or unsafe receipt original must block submission. Automatic merged/auto uploads remain disabled; a receipt upload cannot satisfy another required slot. Non-receipt slots retain normal reading even for the same combined PDF.

Exclude receipt rows and requirements together from automatic application review, preserving row-to-file reference alignment. Append manual reasons and inline originals and merge NEEDS_REVIEW into stage1/final while retaining another document's FAIL. Never fabricate receipt confidence/PASS or add a receipt-specific approval endpoint. Use existing role-authorized application memo/decision and Review CAS, preserving 428/422/409 and full DB/file invariance on rejection. Historical records are not rewritten; no DB migration.

This explicit 2026-11-23 decision supersedes only receipt-quality cases in the earlier quality contract. Preserve all other quality/recognition and Phase 7 policy behavior. Run test_receipt_manual_review.py, non-receipt quality tests, auth/immutability and Review integrity/CAS suites, full backend/engine regression, types/build/lint and real browser original viewing. Use synthetic files and isolated databases. PRODUCTION_NOT_READY.

Routine manual receipt review alone is not a detected deficiency and must not start a supplementation deadline; retain the existing deadline rules for other automatic findings.
