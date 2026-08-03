# Phase 2 — Web routes/models (D3/D4), frontend (D5), config.example (D6), docs (D7)

## Gate (inputs from phase 1)

Phase 1 committed and green: backend + tests carry zero lacale except the
exempted `tests/acquire/test_removed_tracker_history.py`; the residual py grep
returns exactly `web/routes/acquisition_ranking.py` + `web/models/acquisition.py`;
`make lint` / `make test` green; `personalscraper` imports.

## Sub-phase 2.1 — web sample rewrite + dead exclusion — `refactor(rm-lacale): …`

`personalscraper/web/routes/acquisition_ranking.py` (verified 2026-08-03):

- D4 — of the 12 preview samples, exactly TWO use `provider="lacale"`:
  s5 (L96-106: VOSTFR/720p/HDTV/x264, 1.5 GB, 15 seeders/0 leechers) and
  s6 (L108-118: MULTI/2160p/BluRay/x265, 16 GB, 3 seeders — "low seed").
  Rewrite onto live trackers keeping the SAME quality/seed shapes so the preview
  stays representative: s5 → `c411`, s6 → `tr4ker` (titles' `— lacale` suffix
  updated to match). Keep tracker mix plausible vs the existing s1-s4/s7-s12
  (currently c411×4, tr4ker×4 among the live ones).
- D3 — delete the dead exclusion `known = sorted(k for k in _TRACKER_CLASSES if k != "lacale")`
  (L248) → `known = sorted(_TRACKER_CLASSES)`; rewrite the comment L244-245
  (no lacale mention). Behavior identical once the factory no longer knows lacale.
- `personalscraper/web/models/acquisition.py` docstrings: L586 provider example
  list (drop `lacale`), L620-624 `known_trackers` description (drop the
  "excluding lacale" clause).
- **`make openapi` in the SAME commit** (docstrings feed OpenAPI): commit the
  regenerated `frontend/openapi.json` + `frontend/src/api/schema.d.ts` (this also
  clears the lacale hits inside `schema.d.ts`). CI fails on drift otherwise.
- Update `tests/unit/web/routes/test_acquisition_ranking_preview.py` (2 hits —
  pins the sample set / known_trackers roster; flip to the new samples and the
  full-roster expectation).
  Gate: `pytest tests/unit/web -q` green; `git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts` clean after a second `make openapi`.

## Sub-phase 2.2 — frontend — `refactor(rm-lacale): …`

- `frontend/src/components/config/SecretsTab.tsx` L47: remove the
  `LACALE_PASSKEY: "Passkey LaCale"` label entry (D5). No SecretsTab test
  references lacale (verified) — but re-grep after edit.
- Frontend test fixtures using `source_tracker: "lacale"` → `"c411"` (render-a-string
  behavior unchanged; the D2 historic-render pin lives in the exempted backend
  regression test): `frontend/src/pages/AcquisitionPage.test.tsx` (L140, 814, 829
  — includes a `getByText("lacale")` assertion to flip),
  `frontend/src/components/acquisition/ObligationsPanel.test.tsx` (L79, 247-250 —
  same), `frontend/src/hooks/useAcquisition.test.tsx` (L111),
  `frontend/src/api/acquisition.test.ts` (L86).
- Gates (all, before commit — repo rule): `cd frontend && npm run typecheck && npm run lint && npm run lint:ds && npm run test -- --run && npm run build`.
  Check: `rg -i "lacale" -g '*.ts' -g '*.tsx' frontend/src/` → zero.

## Sub-phase 2.3 — config.example + .env.example — `refactor(rm-lacale): …`

- `config.example/tracker.json5`: delete the `lacale: { … }` provider block
  (L13-…), the PROVIDER_CREDS comment mention (L2), the PROVIDER_OPTIONAL_SECRETS
  comment mention (L7), drop `"lacale"` from `priority` (L44) and from the
  commented per-media-type priority examples (L46-47).
- `.env.example` L133-140: delete the LaCale block (`LACALE_API_KEY`,
  `LACALE_PASSKEY`, `LACALE_ANNOUNCE_URL`, `LACALE_SOURCE` + comments)
  — found by grep, absent from the DESIGN §3 map (INDEX deviation 6).
- LIVE `~/.torrentmate/config/tracker.json5` untouched (post-merge operator step, D6).
  Check: `rg -i "lacale" -g '*.json5' config.example/` → zero;
  `rg -i "lacale" -g '.env.example' .` → zero. CI-safe: CI never loads real config.

## Sub-phase 2.4 — docs purge — `refactor(rm-lacale): …`

- DELETE `docs/reference/lacale-api.md` (`git rm` — tracked file, no -f needed).
- `docs/reference/architecture.md` L89 (tracker dir comment "— lacale, c411, tr4ker")
  - L95 (`lacale.py` tree entry) — purge.
- `docs/reference/c411-api.md` — 8 mentions (L177, 251, 272, 316-320, 338, 355):
  the "_parse_title reused from LaCale / import from lacale.py" story is STALE
  (parsing moved to shared `_quality.py` — its docstring says so). Rewrite those
  passages to reference `personalscraper/api/tracker/_quality.py`; keep the rps
  rationale without naming LaCale.
- `docs/reference/config-overlay-layout.md` L123: drop `LACALE_PASSKEY` from the
  `.env.example` example (keep `C411_PASSKEY`) — absent from DESIGN §3 map.
- Root `CLAUDE.md` reference-index L253: tracker row → "C411 / Tr4ker trackers …".
- Traps: `git add -f` for modified docs/ paths if newly added (global gitignore
  `docs/` rule); tracked-file edits stage normally. `git add -f CLAUDE.md` needed.
  Check: `rg -i "lacale" -g '*.md' docs/reference/ CLAUDE.md` → zero.

## Phase gate (all green before phase 3)

1. `make lint` && `make test` — green, 0 ERROR.
2. `make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts` — no drift.
3. `cd frontend && npm run typecheck && npm run lint && npm run lint:ds && npm run test -- --run` — green.
4. Combined residual grep (corrected all-glob form — see INDEX deviation 1):
   `rg -i "lacale" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.json5' -g '*.md' -g '!tests/acquire/test_removed_tracker_history.py' personalscraper/ tests/ frontend/src/ config.example/ docs/reference/ CLAUDE.md .env.example`
   → zero hits (exit 1).
