# Modern officer surfaces

## Isolation and tokens

Apply `.om` only to a new or migrated officer surface. Import
`officer-modern-tokens.css` and `officer-modern.css`, never applicant global
styles or applicant-only adapters. Every copied token name and value must match
`styles/tokens.css`, including separate base and responsive declarations.
Typography rules are scoped separately: body 16px, supporting text 15px, minimum
14px, line height 1.55, headings 22px/19px. Use the applicant spacing, color,
radius and 40px/48px control tokens. Text/background pairs need 4.5:1 contrast.

Keep the shared navy shell, authenticated session bar, built-in job-package
workspace, ApplicationList, ReviewDetail and DocumentViewer outside `.om`.
Do not change original PDF geometry or inherit modern UI typography into the
viewer. Generic detail gives its header and findings panel separate `.om` roots.
Upload, login and program-list entry screens also use scoped modern styles.
OfficerDrawer registers its mounted presence through OfficerNavigationContext.
Modern screens use drawer logout and suppress the redundant session bar; the last
drawer cleanup restores the original bar. This context controls presentation only,
never authentication or roles. Keep mock bypass behavior and legacy bar JSX intact.

## Actions and keyboard interaction

Keep one dark primary action in a viewport. Other actions use outlined buttons,
text actions or pill chips. Preview progress chips replace a persistent review
sidebar. Render a completed pending count as a static status chip, while keeping
the active pending-items menu and every individual confirmation visible. The template confirmation action saves and confirms together; its
outline treatment avoids competing with sticky publication.

Use OfficerDrawer for business navigation and OfficerMenu for secondary row or
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
OfficerDrawer registers in an effect and returns its cleanup. A count of zero
renders the original legacy bar. A positive count leaves logout in the drawer.
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
