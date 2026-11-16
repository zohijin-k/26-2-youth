# Generic program review

Generic review detail lives under the posting and application identifiers. Check
both the application program code and the immutable posting snapshot; a different
posting returns 404. Keep the built-in detail implementation and DocumentViewer
unchanged, and import the viewer in the separate generic screen.

Store human document and criterion confirmations in the additive
GenericReviewChecks table. Bind checks to the full evidence fingerprint, including
document bytes, written archive, input identity, frozen criteria and rule results.
A stale fingerprint cannot save checks or authorize approval. Missing original
files block approval even when check identifiers are present.

Every generic approval entry point, including the legacy individual and bulk
decision APIs, must call the shared guard. Bulk approval cannot process a review
that is not PASS, including a previously held item. Preflight all generic members
before mutating any bulk member. Require a reason for hold/reject, and keep final
decisions immutable. Officer roles remain workflow choices after authentication.

The written-PDF officer URL streams the stored archive with an inline response.
Do not import the applicant file-export API in the officer route or reuse its disposition.
Generic details contain document verdicts and criterion evidence, never the
built-in score sheet. Manual criteria and uncertain automatic results require
human checks; an AI suggestion cannot change a verdict.

The protected DocumentViewer has an existing one-page PDF first-render issue.
Generic details may expose a contained, officer-only raster of that exact page
and pass it to the unchanged viewer's image mode. Keep the original PDF URL and
bytes intact. Scope the preview to the posting, submitted application and owned
document (or its written archive); wrong scope returns 404 and missing session
returns 401. This display adapter does not change a document verdict.

## List sort and rejection notice

`/api/officer/applications` accepts `sort` = importance | latest | submitted | score.
Registration order (submitted_at, id) is the base and tie-breaker. `importance`
sorts by `check_count` = non-PASS uploaded documents + missing required upload
slots (decided rows count 0), computed by `_pending_reasons`, the same helper as
the reasons endpoint, over all filtered rows before paging.

Decision requests take an optional `notice` (≤2000). Only a reject stores it in
`Review.reject_notice`; any other decision clears it. Applicant status responses
expose `rejection: {notice, decided_at}` only when the application is decided
and the decision is reject. `officer_memo` never reaches the applicant.
