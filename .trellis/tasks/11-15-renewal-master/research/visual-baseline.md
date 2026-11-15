# Synthetic officer baseline

Starting frontend commit: `7472697`; archived only demo/frontend from this repository into `/tmp/renewal-visual/baseline`. Existing node_modules linked. Temporary vite proxy points to backend 8010. Ports 8010 and 5183 were free before startup. Runtime database `/tmp/renewal-visual/demo.db` and storage `/tmp/renewal-visual/storage` are isolated by `visual_backend.py`; repository runtime data was neither opened nor reset. OCR disabled. No real LLM requests.

Screenshots: `shots/baseline-programs.png`, `shots/baseline-list.png`, `shots/baseline-review.png`, viewport 1440×1000, full-page capture, Korean locale, Asia/Seoul timezone, reduced motion. All show deterministic built-in synthetic mock data. No browser page errors. Review screenshot visually checked: original mock document and right-hand review panels rendered. Exact resolved URLs in visual-baseline.json.

## Reuse

Run backend from repository root: `.venv/bin/python -m uvicorn visual_backend:app --app-dir .trellis/tasks/11-15-renewal-master --host 127.0.0.1 --port 8010`. Run a temporary frontend copy with vite proxy 8010 on port 5183. Do not use production runtime DB/storage.

Playwright: `PLAYWRIGHT_BROWSERS_PATH=/tmp/renewal-browser VISUAL_PHASE=final node .trellis/tasks/11-15-renewal-master/visual-officer.mjs`. Installed package defaults to the user-authorized temporary npm installation; PLAYWRIGHT_PACKAGE can override its index.mjs path. Screen names are English. Compare after final captures: `.venv/bin/python .trellis/tasks/11-15-renewal-master/compare-officer.py`.

Local bind and Chromium launch required sandbox escalation. Those actions were authorized by the user. Stop only the processes started for this phase after capture. New feature screenshots should use a separate 940px context; preserve this 1440px context for baseline comparison.
