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
