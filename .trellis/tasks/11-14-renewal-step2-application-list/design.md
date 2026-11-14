# Design — step 2

## Backend (`demo/backend/api/officer.py`, additive)

### `GET /api/officer/applications` — two new optional parameters

| Parameter | Meaning |
| --- | --- |
| `queue` | `needs_check` \| `pass` \| `done`. `needs_check`: no officer decision and AI status is not `PASS` (including not reviewed). `pass`: no decision and AI status `PASS`. `done`: any decision. Unknown value → 400 like the other filters. May be combined with the existing `status` / `ai_status` (all filters apply). |
| `q` | Trimmed text, at most 50 characters (longer → 400). Case-insensitive substring match on the application number or the applicant name. Empty after trimming means no search. |

These definitions must be the same predicate the program store uses for `needs_check_count` (see `api/postings.py`); share one helper rather than writing it twice.

### Response additions

- `queues`: `{"needs_check": n, "pass": n, "done": n}` counted over the rows that pass scope, `program`, `q` and the period — that is, every filter except `queue`, `status` and `ai_status`. The three numbers add up to the number of such rows.
- `filters.applied` gains `queue` and `q`.

Everything else in the response stays as it is. If an existing test or scenario asserts the exact key set and fails because of these additions, stop and report instead of editing that test.

### `GET /api/officer/applications/{application_id}/reasons` (new)

Why this case needs checking, from data the review already stored. No LLM.

```json
{
  "application_id": 12,
  "ai_status": "NEEDS_REVIEW",
  "ai_status_label": "확인필요",
  "source": "rules",
  "documents": [
    {
      "slot_key": "resident",
      "label": "주민등록표 초본",
      "status": "NEEDS_REVIEW",
      "status_label": "확인필요",
      "findings": [{"code": "…", "message": "…", "severity": "NEEDS_REVIEW"}]
    }
  ],
  "missing": [{"slot_key": "…", "label": "…"}]
}
```

- `documents`: uploaded documents whose stage-1 status is not `PASS`, in checklist order, with their findings (`code`, `message`, `severity` only; values masked the same way the review detail masks them).
- `missing`: required checklist slots with no upload.
- Reuse the helpers the review detail endpoint uses for labels, masking and the checklist. Role scoping follows the detail endpoint (same `role` query parameter and the same 403/404 behaviour).
- 404 for an unknown application or a draft.

## Frontend

### API client and mock

- `OfficerListQuery` gains `queue` and `q`; `OfficerList` gains `queues`. New `fetchApplicationReasons(id, role)`.
- `pages/officer/mock-data.ts`: `mockOfficerList` honours `queue` and `q` and returns `queues` with the same rules; a mock reasons function returns reasons for mock ids built from the mock documents. Mock and real mode must behave the same from the screen's point of view.

### List screen (`pages/officer/ApplicationList.tsx`, `OfficerConsole.tsx`, `officer.css`)

Layout from top to bottom:

1. Role tabs and scope selectors — as they are.
2. Queue tabs: 확인 필요 · 적합 · 처리 완료, each with its count; 확인 필요 is selected by default and its count is emphasised when above 0. Implemented as a tablist with arrow-key movement.
3. One toolbar row: search input (placeholder "신청번호 또는 성명"), submission period (two date inputs), and "조건 지우기" when any is set. Search applies on Enter or after a short pause in typing; it resets the page to 1.
4. Selection bar — rendered only while rows are selected: "N건 선택", the role's bulk decision buttons, "선택 해제". It replaces the toolbar row's position without shifting the table (reserve the height or overlay it).
5. Table: checkbox, 신청번호, 성명, 접수일시, 처리상태, and a narrow last column with the expand button (aria-expanded, label "확인 필요 사유 보기"). The expand button is shown for undecided rows that are not 적합.
6. Expanded row: a full-width row under the application with the reasons — documents with their status and findings as a short list, missing documents, and a link-style button "심사 화면 열기". Loading, empty ("저장된 사유가 없습니다. 심사 화면에서 서류를 확인해 주세요.") and error-with-retry states. Only one row is expanded at a time. A comment marks where step 3 will place the LLM explanation; nothing is rendered for it now.
7. Pagination — as it is.

Removed from the screen: program, AI-result, status and sort selectors; the per-document columns; score, missing-count and region columns; the first-come progress block if it only repeats numbers (keep it if it carries the supplement notice the officer needs — decide by reading what it shows and say which in the report).

### URL state

- New list parameters `queue` (omitted when `needs_check`) and `q`, added to `NAVIGATION_PARAMS`. Period and page keep their existing parameters. Opening a detail and returning restores queue, search, period, page and scroll as the list does today.
- Old parameters `status`, `ai`, `sort` in saved links are ignored except: `status=approve|hold|reject` opens 처리 완료, `status=pending` with `ai=PASS` opens 적합, any other `status=pending` opens 확인 필요.

### Look

- Dense officer look, existing tokens and classes in `officer.css`; new rules prefixed `.alist__` (new file `pages/officer/application-list.css`) or added next to the existing list rules — do not restyle the review detail.
- Status as text plus colour. No emoji, no English.
- Empty states per tab: 확인 필요 "확인이 필요한 신청이 없습니다.", 적합 "적합으로 판정된 미처리 신청이 없습니다.", 처리 완료 "처리한 신청이 없습니다."; with a search or period set: "조건에 맞는 신청이 없습니다." and the reset control.

## Out of scope

LLM calls, changes to the review detail, changes to decisions or criteria logic, program settings.
