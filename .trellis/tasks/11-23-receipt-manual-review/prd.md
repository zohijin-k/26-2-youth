# Youth receipt manual review

User-approved policy (2026-11-23): payment receipts are original evidence for authorized officers, never OCR/Document AI or automatic document PASS/FAIL inputs. Preserve required receipt slots, original bytes, ownership, officer authentication, draft-only mutation and Review CAS/audit. Do not change other document policies or create receipt-specific approval endpoints. No migration/deployment. PRODUCTION_NOT_READY.

Acceptance: identify actual slots; prove no reader/extractor/confidence/rule call for receipts; validate file envelopes; keep missing required slots blocking; render PDF/images inline; submit and record an existing authorized CAS decision with stale-write rejection; prove mixed files cannot fulfill other slots without their own OCR; preserve historical rows and unrelated engine results; document the policy matrix.
