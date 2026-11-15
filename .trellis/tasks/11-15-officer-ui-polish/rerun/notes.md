# Stage3 rerun notes

- Same branch feat/officer-ui-polish, starting ffbaab7. Initial df -h / reported27GiB; persisted second probe25GiB, above15GB. No other repository or generated artifacts were accessed.
- Existing failed-stage3.patch passed git apply --check and applied cleanly.
- Before source edits, captured6modern surfaces,2mock legacy surfaces and2authenticated legacy surfaces with fixed synthetic baseline program IDs.
- Modern drawer context suppresses duplicate modern logout bar only; original authenticated legacy bar JSX is byte-identical, no Provider DOM or modern style ancestor. Mock bypass unchanged.
- Native Choose File buttons counted separately to avoid understating the previous upload UI. No navigation tag changes were used to game button counts. Mandatory confirmation/publication/selection controls remain visible.
- Full synthetic journey passed18 assertions, with save→fresh workspace→publish requests observed; no browser page errors.
- Entry checks6groups, menu/dialog checks5groups, workspace checks4groups passed. Metadata-free valid PDF accepted; server PDF validation unchanged.
- New Playwright readiness checks were adapted to hidden file input markup and explicit UI readiness rather than Vite networkidle; business assertions unchanged. Existing frontend unit expectations unchanged.
- Four legacy whole-screen1440×900 comparisons, including authenticated session bar, have0different pixels without alignment corrections.
- Code gate passed engine1267/backend1645/C18/frontend67/tsc/lint/build; no frontend warnings. New navigation lifecycle test1, existing tests unchanged.
- run_rerun_gate.py allocates unique temporary suite directories and cleans only those. It persists disk snapshots and stops on ENOSPC; no ENOSPC occurred.

- Document gate also passed1267/1645/C18/frontend67, tsc/lint/build0warnings; no ENOSPC. Entry navigation links passed3groups. Final10hashes match.
