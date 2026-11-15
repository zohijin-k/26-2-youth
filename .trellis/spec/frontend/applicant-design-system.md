# Applicant Design System

## Ownership and isolation

`pages/applicant/ApplicantApp.tsx` is the only entry importing `styles/tokens.css`, `styles/base.css`, `styles/components.css`, and `pages/applicant/applicant-shell.css`. It owns the logo header, header portal host, skip link, main landmark, and footer. `ApplyFlow` owns application state and renders its header controls into that host. The officer side remains a separate lazy entry and a separate document when switching sides.

The applicant styles intentionally include global element rules and portal styles. Never import them from `App.tsx`, `api.ts`, or officer code. Applicant dialogs, file previews, file links, and document badges have `Applicant*` adapters; preserve the shared officer components' markup and styles. Moving a shared CSS file between generated chunks is possible: compare the officer dependency CSS, not just a single chunk's filename or size.

## Tokens and original documents

UI color, font-size, and radius declarations read `styles/tokens.css`. Normal controls use 40/48/56px sizes, text is at least 13px, and responsive width queries use 600/900px. The logo (assets/brand/jbyouthhub-logo.png, 252×80, trimmed to the mark with a small white margin) sits directly on the white header and is shared with the officer header. Wider than 1360px, the applicant app sits in a centered `--frame-max` (1280px) box on a `--frame-outer` page background. Its sampled navy is `#173975`; the red, yellow and green are decoration only. Font files and the OFL license ship locally.

Original PDF coordinates, masks, page scaling, fonts and field sizing remain the original renderer's responsibility. `--pdf-*` tokens preserve its ink and translucent overlays. The 2px PDF field radius and coordinate-scaled text sizes are document exceptions, not UI control precedents. Initially missing fields use a brand outline; attempted continuation exposes errors. Use the single focus outline in `base.css`.

## Input and dialogs

Keep every `aria-describedby` target mounted for the lifetime of its input, including after a date becomes valid. Initial data-load errors need an explicit retry action. Keep primary actions enabled for missing input. Validate on blur after interaction and on attempted submission; show actionable errors and move focus. The gate itself stays unchanged. Use `ConfirmDialog` for identity finalization, final submission and clearing stored content; it handles focus containment/return, Escape, background inertness, and prevents dismissal by outside clicks. `ApplicantModal` provides document viewers without altering officer `Modal`.

Signature image selection must decode and re-encode a valid PNG before passing it to the existing form payload; reject unreadable images locally. Ignore stale image-reader completions and restore the signature when canvas dimensions change.

Use citizen-safe error copy only at applicant presentation boundaries. Do not change error semantics globally in the shared API: restore logic still distinguishes a missing application from a network failure. Preserve approved legal and finding text verbatim.

## Upload feedback

`upload-queue.ts` is a pure reducer enforcing at most one active upload. Each slot has one pending or failed item. Other slots remain editable; queued items can be cancelled and failed requests retried with the same `File`. Preflight checks stop only unsupported formats, empty files and password-protected PDFs. Other PDF probe failures proceed to the server.

`uploadDocument` accepts an optional progress observer and abort signal while retaining the same endpoint and multipart fields. XHR upload progress is transport progress only. `QueueItem.progressKnown` stays false until a computable byte event arrives; `transferPercentage` returns null until then, so even an initial 0% is shown only when measured. After bytes are sent, use indeterminate processing, elapsed time and a session-observed estimate. No default duration is invented before a measurement exists. Render the upload response immediately and reconcile the checklist in the background. Guard reconciliation and callbacks against stale generations.

Receipt next-step text comes only from the submit response and is retained per application in tab storage for refresh. Current receipt facts and status still come from the server. Do not store identity or form values in URLs.

## Quality checks

Run frontend lint, build, the existing phone/officer tests, applicant helper tests under `src/lib`, and the Node tests under `tests/`. The design task's `research/verify_design.py` checks color/font/radius tokens, breakpoints and contrast pairs. Run the existing backend scenarios, especially the source-path gate in P4, after adding source files.

Browser capture, 320/390px overflow, keyboard walkthrough, dialog focus behavior, original PDF alignment, slow server feedback, print output and officer pixel comparisons require an actual browser. Source audits, contrast calculations, or unchanged CSS histories do not substitute for those checks. Record unavailable checks explicitly.

## Upload transport contract

### 1. Scope / Trigger

The frontend upload function gained an optional progress observer; backend signatures and schemas did not change.

### 2. Signatures

```ts
uploadDocument(
  id: number, slotKey: string, file: File, declaredIssueDate: string,
  progress?: {
    onProgress: (sent: number, total: number) => void
    onSent: () => void
    signal: AbortSignal
  },
): Promise<UploadedDocument>
```

### 3. Contracts

`POST /api/applications/{id}/documents`, browser-generated multipart content type, fields `file`, `slot_key`, and optional `declared_issue_date`. Without observers use the original fetch transport. With observers use XHR and resolve the same `UploadedDocument`. No new environment key or endpoint is introduced.

### 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Known transfer length | Report actual loaded/total bytes |
| Unknown transfer length | Do not invent a percentage |
| Transfer finished, response pending | `onSent`; promise remains pending |
| Non-2xx | Reject server detail or the existing status error |
| Network failure | Reject `TypeError`; applicant maps to connection guidance |
| Abort, including pre-aborted signal | Reject `AbortError`; stale generations do not update UI |

### 5. Good / Base / Bad Cases

Good: two files selected in different slots are queued, one request active, second cancellable. Base: first file has no elapsed-time estimate because there are no observations. Bad: treat 100% transferred as server confirmation or start concurrent OCR requests.

### 6. Tests Required

`tests/upload-transport.test.ts` asserts endpoint/method/multipart keys, real progress, a delayed response staying pending, response identity, server errors, and aborts. Queue tests assert no concurrent active requests, ordering, cancellation, same-file retry and immutability. Estimate tests assert null without measurements and scaling from actual observations.

### 7. Wrong vs Correct

Wrong: increment a timer-driven percentage until the server responds. Correct: use transport bytes while sending, then an indeterminate progressbar with elapsed time until the response arrives.


## Entry bundle boundary

Keep officer screens lazy and officer mock data behind dynamic imports in the shared API. Import the built-in program code from program-scope.ts; officer-scope reexports it for older callers. Do not statically import mock-data from the officer container, because that defeats the dedicated dynamic mock chunk. Validate the Vite manifest's applicant static graph and scan generated applicant chunks for mock-only identifiers after changing shared API imports. The development proxy can use VITE_API_TARGET to isolate manual test servers.
