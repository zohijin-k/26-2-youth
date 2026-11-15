# Execution

0. Create requested branch; record user dirty files; check ten protected hashes; run A/B/C/D gate; capture six modern surfaces and two legacy surfaces.
1. Add scoped tokens, menus/drawer and Korean label helpers with tests. Full gate, safety check, specified commit.
2. Simplify preview and template toolbar; atomic save/refetch/publish; individual evidence confirmation; tests. Full gate, safety check, specified commit.
3. Simplify upload/login/list; preserve upload restrictions. Full gate, safety check, specified commit.
4. Simplify generic workspace/list and review panel while retaining DocumentViewer and selection rules. Full gate, safety check, specified commit.
5. Complete screenshots at 1440×900, 1280/1024 overflow, unchanged legacy pixels, synthetic browser journey and two read-only security probes. Update documentation and report. Full gate, safety check, specified commit.

Every failed stage: export failed-stageN.patch, restore only stage-owned code, record failure and continue. Never amend, push, open PR or merge. Never modify backend/engine/test suites there. Existing frontend behavior assertions stay unchanged; list any copy-only assertion changes in report.
