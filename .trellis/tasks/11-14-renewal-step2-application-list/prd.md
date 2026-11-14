# 리뉴얼 2단계: 담당자 신청 목록 개편

Parent: `11-14-program-service-renewal` (read its `prd.md` for the fixed constraints).

## Goal

An officer opening a program's application list sees first what needs their attention, with less text and fewer controls.

## Requirements

### R1 — Three queues as tabs

- 확인 필요 (default): not yet decided and the automatic result is anything other than 적합 (확인필요, 부적합, or not reviewed).
- 적합: not yet decided and the automatic result is 적합.
- 처리 완료: the officer has decided (any decision, including 보류).
- Each tab shows its count. Counts follow the current search and period, and the role's scope.

### R2 — Table

- Columns: 신청번호, 성명, 접수일시, 처리상태. Nothing else (no per-document columns, score, missing-document count, region, or one-line reason).
- 처리상태 shows the officer's decision for decided rows and the automatic result for undecided rows, as text with colour.
- A row opens the existing review detail, unchanged.
- Order: oldest submission first.

### R3 — Filters

Search (신청번호 or 성명) and submission period only. A reset control appears when either is set.

### R4 — Bulk actions

The bulk decision buttons appear only while at least one row is selected, with the number selected.

### R5 — Why it needs checking

A row can be expanded in place to show why the case needs checking: the documents that are not 적합 and their findings. The expansion is loaded on demand. Step 3 will add an LLM-written explanation in the same place; step 2 shows the rule-based findings only and must not call any LLM.

### R6 — Unchanged

- Role tabs (읍·면·동 / 시군 / 도) and their scope selectors stay.
- `ReviewDetail.tsx` and `DocumentViewer.tsx` stay byte-identical. Decisions, criteria editing, mock mode, and URL restoration of the list and the detail keep working.
- Existing API parameters and response fields keep working; additions only.

## Acceptance Criteria

- [ ] Backend tests cover the queue filter, the search, queue counts under search/period/scope, and the reasons endpoint; the backend suite and all 18 scenario modules pass.
- [ ] `npm run lint` 0 warnings, `npm run build` exit 0 without a chunk-size notice, `node src/forms/phone.test.ts` exit 0.
- [ ] Browser (mock and real data): default tab is 확인 필요 with only undecided non-적합 rows; switching tabs changes rows and keeps counts consistent with the program card; search and period narrow all three counts; selecting rows shows the bulk bar and a bulk decision moves rows to 처리 완료; expanding a row shows its reasons; opening a row and going Back restores tab, search, period and page.
- [ ] `git diff main -- demo/frontend/src/pages/officer/ReviewDetail.tsx demo/frontend/src/pages/officer/DocumentViewer.tsx engine_v2 engine demo/backend/rules` is empty.
