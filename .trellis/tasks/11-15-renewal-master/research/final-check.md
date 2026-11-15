# Final Trellis check

Scope: baseline `7472697` through stages 1–8 plus the pending stage-9 bundle, shared constants and documentation candidate. Review covered backend/frontend contracts and project specs; no shared source changes were made by this check agent. Root owns final full-suite gates and visual verification.

## Concrete findings

1. **Whitespace-only required generic text could establish completion and PASS.** `required_missing` treated only the empty string as missing, while the value boundary accepted ordinary text containing only whitespace. Prepared `/tmp/renewal-final-whitespace.patch` adds trimmed emptiness and a new API regression for spaces, tab/newline and NBSP. The regression checks final blockers, submit rejection and conservative review status. It passed in an isolated temporary package; root has applied the source fix.
2. **Owners could delete ordinary generic evidence after submission while the cached review stayed PASS.** Prepared `/tmp/renewal-final-immutability.patch` adds a generic-only draft guard to DELETE and a new regression proving submitted PASS evidence remains present, cannot be replaced/deleted, and continues to have zero missing evidence in the officer pass queue. Targeted whitespace plus evidence-integrity verification: **2 passed**, 3.38 seconds, synthetic/fake OCR only. This patch must be applied before the final stage gate.

No further concrete blocker was found in the reviewed confirmation, allowlist, ownership, frozen form PDF or LLM transport boundaries. Closing these two findings adds two backend cases: expected backend total 1,409 and new backend count 92; frontend remains 48 total / 16 new. Root must update documentation and confirm actual totals with the final suite output.

## Preservation checks

- Every path in `protected-files.json` matches its recorded SHA-256, including ReviewDetail, DocumentViewer, officer.css and shared viewer dependencies.
- Every existing engine/backend/frontend test file checked against baseline is byte-identical. Only new tests were added; expectations were not weakened.
- No changes under engine code, backend rule definitions or original form coordinate fixtures were found.
- Pre-existing older task metadata modification and the root logo remain outside this work's intended commit set.

## Contract checks

- Managed posting publication verifies nonempty layouts and exact confirmed layout hashes; saved edits erase confirmation, and generated proposals retain review flags. Geometry validation uses actual PDF bounds and rejects invalid kinds/sources/numeric coordinates.
- Generic applications freeze PDF bytes, layouts, chosen requirements and guidance in application-owned storage. Subsequent posting edits cannot rewrite the frozen template or submitted combined form archive.
- Generic applicant routes and uploaded files require the corresponding owner cookie; alternate integer spellings are covered. Officer routes remain a distinct existing demo surface. Incompatible generic review detail returns 409 and is deliberately not linked from the generic list.
- Generic value persistence accepts only frozen opaque keys, validates dates/numbers/checks/signature PNGs, locks verified name/birth and redacts identifier suffixes. Public layouts omit internal detector anchors/confidence/template paths. Public generic identity omits signature storage paths.
- New job-package browser sessions require actual stored bankbook evidence, not a client filename. Context updates retain the server marker, stale autosaves cannot restore deleted evidence, UUID subfolders preserve earlier same-name originals, and submitted bankbook modifications are refused.
- Generic review sends any FAIL/NEEDS_REVIEW/unknown upload outcome to confirmation handling; required fields cannot establish PASS when missing. Existing bulk final-selection refusal is reused.
- Applicant-shared API now dynamically imports officer mock code only from officer requests. Shared program constants replace duplicated frontend scope literals; backend built-in posting scope reuses JOB_PACKAGE. Protected detail code is unchanged.

## Optional LLM review

Default provider remains none even when credentials are present; JBAI requires explicit provider plus enable flag and complete HTTPS settings. Both drafting entry points build positive projections. Review explanation codes are rebuilt from a static vocabulary of field names and rule text, never stored finding messages or OCR/applicant values. The transport re-projects again, suppresses unknown codes, blocks credential-forwarding redirects and returns a static fallback without logging exception contents. Generated wording never changes rule statuses.

The provider reads process environment, not the configuration file itself. Existing python-dotenv dependency and uvicorn's `--env-file` support were verified from local code/help only. Root added the explicit optional `.env` startup command to README, demo README and DEVELOPMENT. No actual configuration file was read and no real provider request was made. Real JBAI text endpoint compatibility remains an explicitly documented verification limit.

## Documentation and verification boundary

New paths, four-step authoring, managed-vs-legacy compatibility, conservative list assignment, generic ownership and the missing generic detail link match actual source. Backend counts need the two final regression additions reflected as above; Node count stays unchanged. Existing legacy API fixtures retain their compatibility path and do not activate generic online application. Automatic extraction remains a draft requiring human confirmation, not an accuracy guarantee.

This check used source/hash review and isolated light synthetic regression tests only. It did not rerun heavy OCR suites or use the separate visual agent's server ports. Final engine/backend/scenario/frontend gate results and screenshot/pixel evidence belong to root's run report.

Additional isolated light privacy verification completed: `test_llm_drafts.py`, `test_draft_messages_api.py` and `test_generic_access.py` — **22 passed in 0.95s**. Providers were fake/default-none; no external network or heavy OCR was used.

## Final generic evidence augmentation (supersedes the minimal DELETE patch)

Prepared `/tmp/renewal-final-document-safety.patch` against the current stage-9 source, already containing the whitespace fix. It includes the generic submitted-DELETE refusal plus unique UUID directories for direct/merged sources, atomic generic row replacement with a fresh draft check, and per-event-loop/application mutation serialization in the existing owner middleware. The lock registry has weak loop keys and weak lock values; ownership is checked first, unrelated applications and GETs remain independent, and idle lock entries disappear.

An interrupted generic merged upload marks only newly saved paths NEEDS_REVIEW, retaining full source references and preserving FAIL outcomes. Prior committed paths are excluded. No existing rule evaluator or legacy upload path changes. Four new tests cover submitted mutation refusal, direct/merged same-name bytes, partial-merge interruption/prior valid rows, and focused ASGI write ordering/ownership/cleanup. Generic21 + ownership3 + safety4 + whitespace1: **29 passed in 3.02s**. Expected final backend total becomes **1,412 / new95**, frontend remains48/new16. Root owns the actual full-gate totals.

The locking boundary is the existing local demo's single uvicorn worker. It intentionally does not coordinate multiple processes, external scripts or external DB/file edits. Source bytes stay immutable across in-flight replacements because new requests write to distinct paths; serialized submit handlers re-read the committed application state. This is a bounded demo safety fix, not a new production coordination platform.

Legacy preservation subset on the same isolated augmentation candidate: existing account, account-integrity, postings and officer-queue suites — **104 passed in 4.20s**. Combined targeted evidence is 29 generic/ownership/safety/whitespace plus104 legacy cases, all passed; no heavy OCR or network was used.


Root integration closure: whitespace and all document safety patches are applied in 03c40e1. The final current-source browser rerun passed 17 assertions, including submitted DELETE/reupload refusal and stable archive bytes. Full gates 9 and 10 both pass: engine1267/backend1412/Node48/scenarios18. No reviewed blocker remains beyond the deliberately unlinked generic detail and documented compatibility/provider boundaries.
