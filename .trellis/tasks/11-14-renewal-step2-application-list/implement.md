# Implementation plan — step 2

Branch `feat/renewal-step2-application-list` from `main`. One implementer, backend first.

1. [ ] Backend: shared queue predicate; `queue` and `q` on the list; `queues` in the response; the reasons endpoint; tests in `demo/backend/tests/test_officer_queue_api.py`.
2. [ ] Run the new tests, the whole backend suite and scenarios P3, P4, P6 (they exercise the officer list).
3. [ ] Frontend: API client and mock data; list screen; URL state.
4. [ ] Run `npm run lint`, `npm run build`, `node src/forms/phone.test.ts` in `demo/frontend`.
5. [ ] Main session: check, full verification (backend suite, 18 scenarios, browser walk-through with screenshots), documents, commits, pull request. Merging waits for the owner.

## Environment on this Mac

- Python with the project requirements and pytest: `/Users/zohijin/Desktop/2026-2-capstone/.venv/bin/python` (absolute path; do not modify that environment). Run from the repository root.
- `demo/frontend/node_modules` is installed. OCR models and synthetic fonts are present (gitignored).
- Never stage or touch the untracked directory `26-2-youth-officer/` at the repository root, and never stop processes on ports 8000, 5173, 5174, 8001 or 5175.
- The disk is nearly full (about 11 GB free). Do not create extra clones or copy `node_modules`; remove any scratch files you create.
- No git commit, branch switch, stash or push by sub-agents.
