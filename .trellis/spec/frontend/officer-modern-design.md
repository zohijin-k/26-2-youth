# Modern officer surfaces

## Isolation and tokens

Apply `.om` only to a new or migrated officer surface. Import
`officer-modern-tokens.css` and `officer-modern.css`, never applicant global
styles or applicant-only adapters. Every copied token name and value must match
`styles/tokens.css`, including separate base and responsive declarations.
Typography rules are scoped separately: body 16px, supporting text 15px, minimum
14px, line height 1.55, headings 22px/19px. Use the applicant spacing, color,
radius and 40px/48px control tokens. Text/background pairs need 4.5:1 contrast.

The shared officer shell (App.tsx, app-shell.css) is a white header with the
hub logo, brand stripe and a "담당자" label; the session bar portals into its
right-hand slot. Wider than 1540px, the whole officer app sits in a centered
1440px box on a #e8ecf1 page. The built-in job-package workspace uses the modern
`.om` head (title, status chip, chip tabs); its OfficerConsole,
ApplicationList, ReviewDetail and DocumentViewer stay outside `.om` and get
their visual polish only from scoped rules in program-officer-workspace.css.
Never restyle officer.css or application-list.css directly, and never put
overflow/radius rules on review `.panel` elements (that clips the findings).

Program workspace heads (built-in and managed) use `.om-head--grid`: title |
status chip, then chip tabs on their own row. Switching job-package roles must not move the
list: ApplicationList always renders the check column (an empty cell when the
role cannot bulk-act), role notes stay on one fixed-height line, and the queue
tab row has a fixed height whether or not region selects are shown.
Do not change original PDF geometry or inherit modern UI typography into the
viewer. Generic detail gives its header and findings panel separate `.om` roots.
Upload, login and program-list entry screens also use scoped modern styles.
OfficerShell registers its mounted presence through OfficerNavigationContext.
Authenticated screens use sidebar logout and suppress the redundant session bar; the
shell cleanup restores the original bar. This context controls presentation only,
never authentication or roles. Keep mock bypass behavior and legacy bar JSX intact.

## Actions and keyboard interaction

Keep one dark primary action in a viewport. Other actions use outlined buttons,
text actions or pill chips. Preview progress chips replace a persistent review
sidebar. Render a completed pending count as a static status chip, while keeping
the active pending-items menu and every individual confirmation visible. The template confirmation action saves and confirms together; its
outline treatment avoids competing with sticky publication.

Use OfficerShell (sidebar) for business navigation and OfficerMenu for secondary row or
item actions. Preserve mock query parameters via routeHref. Menus and drawers
support Escape, arrow/Home/End movement, contained Tab navigation, outside
click dismissal and opener focus restoration. Disabled and CSS-hidden controls
must not enter the focus cycle. When menu actions open a dialog, flush the menu
close and restore its opener before mounting the dialog.

Use OfficerConfirm/OfficerDialog around the existing officer Modal. Do not
change the shared Modal to obtain modern styling. Confirmation dialogs contain
and restore focus, close with Escape, and prevent overlay pointerdown from
moving focus or dismissing the dialog. Destructive actions need confirmation.
When settings navigation replaces the chip tablist, focus the loaded preview
heading instead of leaving focus on a removed tab.

### Modern navigation lifecycle

```ts
type ModernNavigationRegistration = () => () => void
declare function createModernNavigationRegistration(onCountChanged: (count: number) => void): ModernNavigationRegistration
```

OfficerSession creates one stable registration function; each mounted
OfficerShell registers in an effect and returns its cleanup. A count of zero
renders the original legacy bar. A positive count leaves logout in the sidebar.
Cleanup is idempotent so StrictMode or overlapping drawer lifetimes cannot leave
negative counts or restore the bar too early. The unit assertion sequence is
`[1, 2, 1, 0]` for two mounts, repeated first cleanup and final cleanup. Browser
checks must retain exact legacy pixels in both authenticated and mock sessions.
Do not inspect ancestor DOM classes or change authentication state to decide
whether to show the bar.

## Publication and evidence contracts

Editing an analysis item resets its individual needs_review flag. Never provide
bulk confirmation. Publication may start with unsaved analysis edits after all
individual confirmations and form confirmations are complete. Dirty template
layouts still block it. The transaction is:

1. Save the reviewed analysis.
2. Fetch fresh server workspace data.
3. Require a present array of server publish_blockers containing no blockers.
4. Publish only then. Otherwise show the server reasons below the sticky bar.

Do not publish after a failed save, failed refresh, malformed blocker response or
navigation away before the next request. Server publication eligibility remains
authoritative. Do not infer eligibility from stale blocker data.

Pending evidence shows one truncated quote while its full evidence stays closed.
Confirmed evidence starts collapsed. Expanded evidence deduplicates quotes and
has one notice-page action. Hide numeric confidence; below 0.6 use a weak-evidence
chip, and manual entries use a no-evidence/manual-input chip. Document/criterion
cards show a summary until the user chooses Edit. Internal enum values need
Korean presentation labels; reader details stay collapsed.

## Generic list and review

Use chip tabs for workspace navigation and queue filters; row secondary actions
belong in menus. Reset selected application IDs when role, scope, date, queue or
committed search changes. A reset only on input events misses selections made
during the search debounce. Disable stale-row bulk actions while fetching.
Retain bulkActionsFor and server role/approval gates. Hold/reject need a reason.

Document and criterion cards share a status/reason shape. Original document tabs
are the navigation controls; right-hand card names are static headings to avoid
duplicating those buttons. Keep individual
original/checklist confirmations visible, bind saves to the server fingerprint,
and enable final selection only through can_approve. Put processing controls
below the scrollable findings in a sticky panel; verify all controls fit at a
900px viewport height. Never change the original viewer to obtain this layout.

## Verification

Run the full engine, backend, 18-module scenario and frontend gate before each
commit. Frontend checks include TypeScript, zero-warning lint/build and unit
tests. Keep backend/engine/test files unchanged. Synthetic pytest fixtures can
consume gigabytes: give each gate suite its own temporary base directory and
clean it after collecting logs. Do not delete unrelated temporary data.

At 1440x900 capture six target surfaces and the two legacy surfaces before/after.
Require zero legacy pixel differences without alignment patches. Check horizontal
overflow at 1280px and 1024px, and record pre-existing protected legacy overflow.
Exercise actual menu/dialog focus, settings navigation, search selection reset,
save-before-publication and per-item approval in a browser. Keep officer mock
data dynamically imported and verify the generated static entry graphs exclude
its separate chunk. Existing behavior assertions must not be weakened.

## Sidebar shell and new-application badges

OfficerApp wraps every authenticated screen in OfficerShell: a 248px sticky
left sidebar (program list, new program, one entry per posting with the current
posting's 신청 목록/사업 설정/사업 정보, logout) and the main column. The pill
"메뉴" button lives in the white header's right slot (portal into headerHost)
and collapses/expands the sidebar; at 1279px and below the sidebar is an
overlay closed by Escape or the shade, returning focus to the button. Keep the
1280px pinned threshold: the legacy job-package review overflows a narrower
main column.

Screens still render `<OfficerDrawer …/>`, but it draws nothing. It publishes
postingId, current location, `disabled` and the onList/onTab handlers through
`useOfficerShellNav`. When `disabled` is true every sidebar link is blocked,
so unsaved-edit guards keep working. Sidebar tab navigation without a screen
handler remounts the workspace (route nonce) so the URL tab is re-read.

Badges need no backend change. OfficerShell polls `fetchOfficerPostings` every
30s while visible and on each screen change. `officer-badges.ts` compares
application_count with per-browser seen counts (localStorage). First sight sets
the baseline to the current count, and viewing a posting's application list
marks it seen. Totals show on the menu button, the 사업 목록 link and the
document title; labels cap at 99+.

## Officer font and optical centering

OfficerSession imports `officer-fonts.css`, which declares the same Pretendard
GOV files as `styles/base.css`. Without it, every `.om` font stack silently
falls back to the system font (Apple SD Gothic Neo on macOS), and Korean text
rides 1-2px high inside buttons. Use the font only on `.om`, the officer header,
the sidebar and the job-package list/head. ReviewDetail and DocumentViewer keep
their original stack.

Even with Pretendard, Hangul ink sits about 0.05em above line-box center.
Pill chips and `.om .btn` shift their vertical padding by 1px (top +1, bottom
-1). Bottom-border tabs need a matching transparent top border. `text-box-trim`
does not affect inline-flex buttons, so do not rely on it. Verify centering by
measuring ink rows in 2x screenshots; keep every control within ±0.5px.

Truncated sidebar program names use a custom fixed-position tooltip (portal to
body). It appears on hover and keyboard focus, only when the name is actually
clipped. Do not rely on `title`: it is delayed and is not shown in every
environment.
