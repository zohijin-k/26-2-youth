# Program authoring and review

New program creation accepts the notice, one or more form PDFs and optional
public supplemental text. Analysis opens the five-section applicant-shaped editor
directly: ① title/period, ② guidance, ③ forms, ④ upload documents split into
필수 업로드 서류 (required) and 추가 업로드 서류 (not required) by the required flag,
⑤ 신청 자격 기준 (criteria). Do not show the 지정/기타 서류 distinction as a chip;
an unslotted document shows only 담당자 확인. Each confirmation button reads
작성완료. Officer-entered items (source manual, no quote) show no chip and no
근거 toggle. Guidance renders one paragraph per typed line break, both in the
officer preview and for applicants.

A program can be deleted at any status (editor menu or list card menu) while no
application row, including applicant drafts, references `posting_{id}`; the
server refuses otherwise and asks to close it instead. A published or closed
program shows an outlined 수정하기 button that unpublishes after confirmation. Reuse the shared guidance paragraphs and existing template editor; do
not import applicant global CSS into the officer entry.

Every editable candidate retains its source evidence. Editing reopens human
confirmation. Show pending candidates and form fields through the sticky progress/pending chips;
source links render the requested notice page with PdfPages. Do not use a native
PDF frame with file-saving controls. Pending field navigation must preserve
unsaved form changes; require saving before switching through external targets.

The server owns publication eligibility. Pending confirmations and unconfirmed or locally dirty form layouts prevent starting publication.
Unsaved analysis edits are allowed after individual confirmation: save, fetch fresh workspace
state, and publish only when the fresh server blockers array is present and empty.
Do not publish after a failed save/refresh or navigation away before publication.
Unconfirmed partial drafts can be saved. Existing managed drafts enter this editor
with manual evidence, without fabricated citations.

Program workspaces have application, settings and information tabs. Generic rows
open the separate generic detail and the unchanged DocumentViewer. Bind check
saves to the server fingerprint. Final selection remains disabled until server
approval checks pass. Bulk hold/reject actions need a supplied reason.

## Application list sorting and rejection

Both application lists (built-in ApplicationList and GenericApplicationList) show
the shared SortToggle: 중요도순 (`importance`, default), 최신순 (`latest`), 등록순
(`submitted`). The built-in console keeps a non-default sort in the `sort` query
parameter. Rows carry `check_count`; undecided rows with a count show "확인 N건".

The 반려 action never decides in place. It opens RejectApplication at
`.../review/<id>/reject` (built-in) or `.../applications/<id>/reject` (generic).
Picked 확인 필요 reasons become `- ` lines in an editable applicant notice
(`reject-notice.ts`); confirmation goes through OfficerConfirm and sends
`notice` plus `memo` (internal memo, or the notice when empty). Bulk reject is
unchanged and stores no notice.

Both lists' queue tabs are `확인 필요 · 적합 · 처리 완료 · 반려` (`list-tabs.ts`). 반려
is `queue=done` + `status=reject`, counted by the list response's `rejected`, and
renders RejectionTable (application number, name, `decided_at`, `reject_notice`).
Pick the table shape from the server-applied filters (`shownTabOf`), never the tab
just clicked, or the previous tab's rows flash as rejections. The built-in console
keeps `status=reject` in the URL.
