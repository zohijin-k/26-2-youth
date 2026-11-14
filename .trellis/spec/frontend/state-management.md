# State Management

> How state is managed in this project.

---

## Overview

<!--
Document your project's state management conventions here.

Questions to answer:
- What state management solution do you use?
- How is local vs global state decided?
- How do you handle server state?
- What are the patterns for derived state?
-->

(To be filled by the team)

---

## State Categories

The demo uses React component state for the active applicant and officer screens. Applicant paths contain only the stage, such as `/apply/identity`; keep the current application ID in tab-scoped `sessionStorage` under `applicant.activeApplicationId`. Restore applicant drafts only from this tab state, never from numeric path segments or an `application` query parameter. Missing, invalid, inaccessible, or unavailable saved state returns to the identity step (`/apply/identity`). Programs come from the program store (`/api/postings` for applicants, `/api/officer/postings` for officers); a program's id may appear in the path, an application's id may not. Refresh and stage history restore the active application in the same tab; copying a URL alone does not identify an application. Officer review paths live under the program workspace, for example `/officer/programs/1/province/review/9`; the older form `/officer/province/review/9` is rewritten to it. `currentMode()` in `navigation-url.ts` is the single place that chooses the side: `/officer...` is the officer side (program list at `/officer`), and any other path is the officer side only with `?mode=officer`, otherwise the applicant side (program finder at `/`, the application flow at `/apply...`). Apart from that entry rule, use query parameters only for optional filters and preserve unrelated options such as `mock` and `debug`. The officer application list keeps its tab in `queue` (omitted for the default `needs_check`) and its search in `q`; older links with `status`/`ai` open the nearest tab and those parameters are dropped on the first URL write. Fetch application data and consent values from the API when restoring an applicant draft; do not put forms or identity data in the URL. Hiding IDs does not replace server-side access checks.

The shared top bar may display active applicant controls through a React portal from `ApplyFlow`. `App` owns only the DOM host; `ApplyFlow` keeps ownership of the application number, stage, and My Page handler. Do not copy these values into a second shell store or synchronize them through window events. `App` mounts exactly one side, chosen once per document load by `currentMode()`, through its entry component: `pages/applicant/ApplicantApp.tsx` (`/` program finder, `/programs/<id>` program information, `/apply...` the application flow) or `pages/officer/OfficerApp.tsx` (`/officer` program list, `/officer/programs/new`, `/officer/programs/<id>...` the program workspace, which hosts `OfficerConsole` for the built-in program with its role and review segments under that base path; old `/officer/<role>...` links are rewritten there). Each entry reads its own paths and renders one screen. `ApplyFlow` is mounted only on `/apply...`, because it creates or restores a draft application on mount; the finder and information screens must not call application APIs. The two sides are separate `React.lazy` chunks so each side's global CSS (for example `.btn`) ships only with its own side; never import officer screens from applicant code or the reverse; moving between screens must be a full page load (the `popstate` handler reloads when the mode changes), because a loaded stylesheet is never removed. The header host exists only in the applicant shell. Returning home or remounting the applicant flow must remove the old portal content, rather than retaining a previous application's number or action.

---

## When to Use Global State

<!-- Criteria for promoting state to global -->

(To be filled by the team)

---

## Server State

<!-- How server data is cached and synchronized -->

(To be filled by the team)

---

## Common Mistakes

<!-- State management mistakes your team has made -->

(To be filled by the team)
