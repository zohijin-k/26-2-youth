# Verification — step 2 (2026-11-14, macOS)

## Automated

| Check | Result |
| --- | --- |
| Backend `pytest demo/backend/tests` | 1,306 passed (1,289 + 17 in `test_officer_queue_api.py`) |
| 18 scenario modules (`run_p*_scenarios.py`) | all exit 0 |
| `npm run lint` | 0 warnings |
| `npm run build` | exit 0, no chunk-size notice (shared chunk 453.50 kB) |
| `node src/forms/phone.test.ts` | exit 0 |
| `git diff main -- ReviewDetail.tsx DocumentViewer.tsx engine_v2 engine demo/backend/rules` | empty |

## Browser (isolated copy, backend 8011 + app 5181)

Real backend with 7 synthetic submitted applications (3 needs-check incl. one not reviewed, 2 pass, 1 approved, 1 held):

- Default tab 확인 필요 with 3 rows, counts 3 / 2 / 2; switching tabs changes rows and keeps counts.
- Program card counts (7, 3) match the tabs.
- Search "가상삼" → 1 / 0 / 0; unknown text → "조건에 맞는 신청이 없습니다." with 조건 지우기; reset restores.
- Period from 2026-11-04 narrows 확인 필요 to 1.
- Reasons expansion: non-PASS documents with findings, missing required slot, 심사 화면 열기; an unreviewed case shows the missing slot.
- Open a row from 적합 with a search, Back → same tab, search text and URL.
- Select one row → bar "1건 선택 · 최종 선정 · 보류 · 반려 · 선택 해제"; 최종 선정 moves it: 적합 1, 처리 완료 3, notice "1건을 처리 완료로 옮겼습니다."
- Old link `?status=pending&ai=PASS` opens 적합 and the URL becomes `?queue=pass`.
- 390px: no page-level horizontal scroll; the table scrolls inside its box (officer screens are PC-first, as documented).
- Mock mode: 117 / 192 / 121, reasons from mock documents, tab switching works.
- Console: only a 400 for the synthetic document file (the seed stored no file), not a screen error.

## Review notes

- Reasons role handling matches the review detail (role validated; no region 403 in either).
- The first-come progress block is removed from the list; the supplement deadline notice the officer needs stays in the review detail.
- Fixed during review: the mock reasons function threw synchronously, which would have left a row in the loading state; `fetchApplicationReasons` is now `async` so the error state shows.

## Follow-up before merge: no bulk approve from 확인 필요 (owner request, 2026-11-14)

Owner rule: in the 확인 필요 tab, bulk actions are 보류·반려 only (no pass without looking at the documents).

- Backend: `POST /api/officer/applications/decisions` with `approve` returns 409 and processes nothing when any selected case is in the needs-check queue (`queue_of`); hold/reject stay allowed; approve of pass or decided cases and single approve from the review screen are unchanged.
- Frontend: the selection bar uses `bulkActionsFor(queue, actions)` (`pages/officer/bulk-actions.ts`); mock mode refuses the same way.
- Baselines: main after the step-1 merge (`106be0b`) = 1,289 backend tests (measured again in a worktree); step 2 = 1,306 (+17); with this guard = 1,317 (+11). 18 scenario modules exit 0. Lint 0, build without chunk notice, `phone.test.ts` and new `bulk-actions.test.ts` exit 0.
- Browser (real and mock): selection bar shows 보류·반려 in 확인 필요, 최종 선정·보류·반려 in 적합 and 처리 완료; no console errors.
- Role tabs (읍·면·동 / 시군 / 도) and their rendering are unchanged from main; `demo/backend/rules` has no diff.
