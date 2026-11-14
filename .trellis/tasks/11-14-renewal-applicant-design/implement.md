# Implementation plan

Continue the existing in-progress applicant design task. Its approved PRD and design remain the scope. Preserve the files already supplied in the working tree; do not include unrelated work in commits.

1. Inspect the reference through the local clone and sample the supplied logo. Record the existing style inventory. Browser capture was attempted with CUA: browser access host unavailable; native Chrome control also lacks permission. Record this limitation rather than fabricate capture evidence.
2. Connect the existing tokens, fonts and accessible components only from the lazy applicant entry. Move applicant shell ownership there; preserve the officer branch and shared index styles.
3. Replace applicant screen styles with tokens. Apply headings, navigation focus, form validation and confirmation, receipt and responsive tables. Preserve original PDF coordinates/rendering.
4. Add a sequential upload queue with immediate local previews, actual transport progress, preflight checks, inline retry and session-observed estimates. Keep request endpoints and payloads unchanged.
5. Run lint, TypeScript/build, existing frontend pure tests, tests for imported/adapted helpers, backend regression suite and existing scenarios. Review the full diff against the prompt; record unverified browser states and any deliberate exceptions.
6. Update frontend spec with reusable applicant isolation rules. Present a concrete commit plan for approval; do not commit or push without that approval.

## Continuation review

On 2026-11-15, complete the approved commit groups, including the owner-approved preparation files. Do not start later renewal phases. Fix the remaining applicant presentation gaps in `DocumentUpload`, `upload-queue`, `SubsidyItems`, and `SignaturePad`; these changes retain endpoints, payloads, submission gates and original document geometry. Verify measured-progress logic with the queue tests, rerun frontend lint/build/tests, P4 source gates, contrast audit and the officer CSS comparison. Browser acceptance stays open while CUA and native Chrome permission are unavailable.
