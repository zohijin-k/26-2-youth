# Officer UI polish design

Only new officer surfaces receive an `.om` scope. Copy applicant token declarations into that scope; shared legacy header and job_package screens remain untouched. Use native officer Modal for destructive confirmations and a shared focus-managed menu/drawer primitive. Keep DocumentViewer outside the modern typography scope where possible.

Publication is a save → refetch → server-blocker check → publish transaction. Local pending confirmations and unconfirmed/dirty template layouts still prevent starting it. Do not weaken any server decisions, review fingerprints, approval conditions or individual confirmation requirements.

Evidence is collapsed after confirmation, with one-line quotes for pending items. Secondary actions live in menus. Use compact summary cards with explicit editing expansion. Keep existing dynamic mock import and separate applicant entry.

All fixture servers use isolated temporary storage and synthetic documents. Preserve baseline screenshots, source hashes and test results. Failed stages are exported as patches and reverted only for files owned by that stage; preserve pre-existing user modifications.
