# Verification — step 1 (2026-11-14)

Environment: macOS, Python 3.14.6, Node 26.13.1. Synthetic fonts and own OCR models present. Browser checks ran against an isolated copy of the working tree with its own database and storage (backend on a scratch port, real new routes).

## Suites on the final working tree

| Check | Result |
| --- | --- |
| `python -m pytest demo/backend/tests` | 1289 passed (1227 before + 62 for the program store), 0 failed |
| 18 scenario modules | all exit 0; per-module counts unchanged (P2 53, P3 186, P4 189, P5 152, P6 261, P7 253, P8 89, P9 98, P11 38, P12 29, P13 26, P14 8 forms, P15 129, P16 96, P17 75, P18 180, P19 24, P20 7) |
| `python -m pytest engine_v2/tests` | exit 0 (run before the review fixes; `engine_v2` is untouched) |
| `npm run lint` | exit 0, 0 warnings |
| `npm run build` | exit 0, no chunk-size notice; largest JS chunk 452.58 kB |
| `node src/forms/phone.test.ts` | exit 0 |
| Frozen files (`ReviewDetail.tsx`, `DocumentViewer.tsx`, `engine_v2`, `engine`, `demo/backend/rules`) vs `main` | no difference |
| Forbidden words in added or changed source under `demo/` | none |

## Browser walk-through (headless Chromium, 0 console errors)

| Step | Result |
| --- | --- |
| `/` | program finder; only `GET /api/postings`; no application created |
| `/programs/1` | job package information; 신청하기 enabled |
| `/officer` | program list; built-in card |
| `/officer/programs/new`, empty submit | five field messages under their fields |
| Fill and save | draft workspace at `/officer/programs/2`; public list still shows only the job package |
| 게시하기 with confirmation | published; public list shows both, new program `can_apply` false |
| View stored PDF | opens in the viewer |
| `/` after publish, `/programs/2` | new program listed; notice rendered; 신청하기 disabled with "이 사업의 온라인 신청은 준비 중입니다." |
| 390x844 on finder and information | no horizontal overflow |
| 마감하기 with confirmation | public list shows 마감 |
| Job package 신청하기 | reaches `/apply/identity`; the only POST is the draft creation after the click |
| Home button in the flow | returns to `/` |
| `/officer?mock=1` | built-in card shows the mock counts; opening it shows the mock list (20 rows per page) |
| Old link `/officer/province/review/<id>?mock=1` | rewritten to `/officer/programs/1/province/review/<id>?mock=1`, same detail |
| `/?mode=officer` | program list at `/officer` |

Not covered in a browser: uploads near 20 MB, two tabs changing the same program, a real (non-mock) application list inside the built-in workspace, WSL2 or Node 22.

## Review (trellis-check, report-only) — no blocker or major; fixes applied

| Finding | Action |
| --- | --- |
| Out-of-range id returned 500 | 404 through one lookup helper; tests added |
| Deleted draft ids were reused (late delete could remove a new program's files) | `sqlite_autoincrement`; test added |
| Title accepted control characters; guidance text had no limit | whitespace collapsed, control characters refused, 20,000-character limit; tests added |
| Late responses acted on a replaced screen (new-program save, delete) | callbacks skipped after unmount |
| Publish or close could succeed while the screen showed a failure | the write response is used; on error the program is re-read |
| A slow first load could overwrite the state after an action | load results ignored once an action has started |
| Network failure showed browser English | Korean message |
| Card counts disagreed with the list under automatic mock fallback | counts follow the same rule as the list; banner shown |
| Confirmation dialog did not take focus | focus on 취소, returned to the trigger on close |
| Date inputs accepted five-digit years | `max` attributes and a format check with a field message |
| Stale routing text in `state-management.md` and one comment | rewritten |

Left for later steps: a screen to edit the built-in program's period (documented API call for now), request-size cap before the upload is spooled, URL normalisation for non-built-in workspaces, `can_apply` enforced by the application API, one alert region for multiple field errors.
