# 신청 목록 정렬과 반려 페이지

Owner feedback 2026-11-16 (design reference: example.png at repo root, job-package list).

1. Application lists sort by 중요도순 (more 확인 필요 items first, default), 최신순, 등록순. Applies to the built-in and per-program lists.
2. 반려 opens a dedicated reject page (own URL): pick reasons from the application's 확인 필요 items, edit the applicant notice, optional internal memo, confirm. The notice shows on the applicant's 마이페이지; the memo does not.

Verification: backend full suite, frontend tsc/oxlint/unit/build, Playwright (e2e_backend.py + e2e.mjs, seeded temp DB, job-package flow) 8/8. Generic-program reject page and 마이페이지 rendering covered by backend tests and type checks only.
