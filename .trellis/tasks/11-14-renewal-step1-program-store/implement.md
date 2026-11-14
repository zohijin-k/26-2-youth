# Implementation plan — step 1

Branch `feat/renewal-step1-program-store` from `main`. Two halves run in parallel against `design.md`.

## Backend half (only `demo/backend/**`)

1. [x] `ProgramPosting` model and the idempotent built-in row in `init_db()`.
2. [x] `api/postings.py` with the public and officer routers; register both in `main.py`.
3. [x] Tests in `demo/backend/tests/test_postings_api.py` following the existing pytest conventions (find how other tests get their client and temporary database).
4. [x] Run: new tests, the whole backend pytest suite, and scenario P4.

## Frontend half (only `demo/frontend/src/**`)

1. [x] `api.ts`: posting types and functions.
2. [x] `ApplicantApp.tsx`, `ProgramFinder.tsx`, `ProgramInfo.tsx`; `goToHome()` to `/`.
3. [x] `OfficerApp.tsx`, `ProgramList.tsx`, `NewProgram.tsx`, `ProgramWorkspace.tsx`; `OfficerConsole` base path and old-link rewrite.
4. [x] `App.tsx` lazy entries.
5. [x] Run: `npm run lint`, `npm run build`, `node src/forms/phone.test.ts` in `demo/frontend`.

## After both halves (main session)

1. [x] Check agent, then full verification: backend suite, 18 scenarios, frontend commands, browser walk-through with screenshots.
2. [x] Documents (`README.md`, `demo/README.md`, `docs/DEVELOPMENT.md`) and `.trellis/spec/frontend/state-management.md` for the new routes.
3. [ ] Commits, pull request, merge, archive.

## Environment on this Mac

- Python with the project requirements and pytest: `/Users/zohijin/Desktop/2026-2-capstone/.venv/bin/python` (use by absolute path; do not modify that environment). Run from the repository root, for example `<python> -m pytest demo/backend/tests -q`.
- Scenario modules: `<python> -m demo.backend.tests.run_p4_scenarios` from the repository root.
- `demo/frontend/node_modules` is installed. OCR models and synthetic fonts are present (gitignored).
- Never stage or touch the untracked directory `26-2-youth-officer/` at the repository root, and never stop processes on ports 8000, 5173, 5174, 8001 or 5175.
- No git commit, branch switch, stash or push by sub-agents.
