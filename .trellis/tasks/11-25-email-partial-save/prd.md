# Keep unfinished emails out of incremental form saves

## Goal

Typing an email address in the applicant forms must not produce failed saves. Incremental (per-edit) saves send only an email the backend can accept, while full flushes keep sending the typed value so the backend still validates it.

## Background

- On 2026-11-25 a tester filling the double-savings forms on the temporary demo caused 26 HTTP 400 responses in ten minutes. The same save pattern exists here.
- `demo/frontend/src/forms/PdfFormsWorkspace.tsx` `setText` calls `onForm1` on every keystroke.
  - `demo/frontend/src/pages/applicant/ApplyFlow.tsx` `onForm1` immediately PATCHes the whole `form1`.
  - `demo/frontend/src/pages/applicant/GenericProgramFlow.tsx` `save` does the same for officer-authored programs, whose "이메일" fields map to `email`.
- `demo/backend/api/applications.py` `_normalize_form_values` rejects any nonempty malformed email with 400, so every keystroke before the address is complete fails and the save state shows a failure.
- The sheet already shows the inline hint "이메일 형식으로 입력해 주세요." while the address is malformed.
- 26-2-savings-applicant has its own task with the same slug for the same fix.

## Requirements

- R1: An incremental `form1` save in `ApplyFlow` and `GenericProgramFlow` never carries a nonempty email that fails the shared email format. While the typed address is unfinished, it carries the last email that could be saved (empty or a previously valid address), so other fields keep saving and a stored address is not wiped.
- R2: Full flushes (`ApplyFlow.persistForms`, `GenericProgramFlow.persist`) keep sending the typed form, so a malformed email is still rejected by the backend and reported as before.
- R3: The restored draft's email seeds the "last savable" value, so editing a saved address does not clear it on the server mid-edit.
- R4: Keep the on-sheet hint, required-field rules, error copy, other fields' save behavior and the backend API unchanged.

## Acceptance Criteria

- [x] AC1 (R1): Simulating keystrokes of a valid address yields no incremental payload whose email the shared validator rejects, and the final payload carries the full address.
- [x] AC2 (R1, R3): Shortening a saved valid address into an invalid one keeps sending the last valid value; clearing the field sends an empty email.
- [x] AC3 (R2): Full flushes still PATCH the typed form value.
- [x] AC4 (R4): `npm run lint`, `npm run build` and `node --test src/forms/phone.test.ts src/pages/officer/bulk-actions.test.ts src/lib/*.test.ts tests/*.test.ts` pass.

## Verification (2026-11-25)

- The backend email rule is the same as in 26-2-savings-officer, where an API replay on a temporary database returned 400 for 22 of 26 typed prefixes before the fix and 0 with the savable-email rule; a full save with an unfinished address still returned 400.
- `tests/email-save.test.ts` covers AC1 and AC2. AC3 holds because `ApplyFlow.persistForms` and `GenericProgramFlow.persist` are unchanged and still send the typed form.
- `npm run lint` reported no findings; `npm run build` passed; the Node test command passed 142 of 142.
- Not run: a real-browser check (no browser on this VM) and backend suites (backend unchanged).

## Verification on the new main (2026-11-26)

- main advanced to `29e2687` (PR #44, #45). A 3-way merge of this change has no conflicts.
- PR #45 changed no save, `form1` or email lines in `ApplyFlow` or `GenericProgramFlow`.
- On the merged result, `npm run lint`, `npm run build` and the Node test command (142 of 142) passed.

## Out of Scope

- Backend validation or API changes, and debouncing or batching incremental saves.

## Notes

- Lightweight task: PRD-only. The user asked on 2026-11-25 to implement this fix in both savings applicant and youth, with Trellis tasks under developer `hcw889`.
