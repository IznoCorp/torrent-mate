# Phase 5 — Integration Gates + ACC + Docs

## Gate

- [ ] Phases 1–4 complete — all code shipped, all unit tests pass
- [ ] Frontend: `make lint` + `npx tsc --noEmit` + `npx vitest run` all green
- [ ] Backend: `make lint` + `make test` green
- [ ] `make check` green (module-size, typed-api guardrails)
- [ ] `python -c "import personalscraper"` smoke test

---

### Sub-phase 5.1 — Integration tests

**Modifies:** (adds integration tests to existing test suites)
**Test files:**

- `tests/integration/test_scrape_arbiter_e2e.py` — end-to-end: enqueue → list → resolve →
  NFO written → decision resolved → pipeline_run row success
- `tests/unit/web/decisions/test_runner_lifecycle.py` — runner lifecycle: success, failure,
  SIGTERM, pipeline.lock held during child

**DESIGN ref:** §9 — runner lifecycle (S3-style, real child): success → NFO written +
decision resolved; failure → pending + row error; `pipeline.lock` held during child

Integration E2E: set up a staging folder with a mock movie file, insert a
`scrape_decision` row with `status='pending'`, call `scrape-resolve` on it, assert NFO
exists, decision row is `resolved`, `pipeline_run` row has `status='success'`. Runner
lifecycle: mock provider failure → exit code 1 → decision stays `pending` +
`pipeline_run.status='error'` + `output_tail` contains error. Pipeline lock probe: while
child is running, assert `is_lock_held()` returns True; after child exits, lock is
released.

**Commit:** `test(scrape-arbiter): add integration and runner-lifecycle tests`

---

### Sub-phase 5.2 — ACC criteria (SH-16 executable)

**Creates:** `docs/features/scrape-arbiter/ACCEPTANCE.md`
**Test:** run each ACC-NN command after deploy-to-staging, verify expected output

**DESIGN ref:** §9 — every ACC-NN is an executable shell command with documented expected
output

Write ACCEPTANCE.md with executable criteria:

- `ACC-01`: Enqueue observed on a real `--dry-run`-first pipeline run.
  `personalscraper run --dry-run 2>&1 | grep "queued_for_decision" | wc -l` → expected:
  `≥ 0` (structural check; on a staging with mid-band items, count ≥ 1).

- `ACC-02`: Live resolve exercised on staging-safe data.
  `personalscraper scrape-resolve "/path/to/staging/item" --provider tmdb --id 12345`
  → expected: exit 0, NFO written, `sqlite3 library.db "SELECT status FROM scrape_decision
WHERE staging_path='...'"` → `resolved`.

- `ACC-03`: Badge count via authenticated curl.
  `curl -s -b cookies.txt https://tm-staging.iznogoudatall.xyz/api/decisions?status=pending
| jq '.pending_count'` → expected: integer ≥ 0.

- `ACC-04`: Resolve via web API returns 202.
  `curl -s -X POST -b cookies.txt -H "X-Requested-With: XMLHttpRequest"
https://tm-staging.iznogoudatall.xyz/api/decisions/1/resolve -d
'{"provider":"tmdb","provider_id":12345}' | jq '.run_uid'` → expected: 32-char hex
  string.

- `ACC-05`: Search returns fresh candidates.
  `curl -s -X POST -b cookies.txt -H "X-Requested-With: XMLHttpRequest"
https://tm-staging.iznogoudatall.xyz/api/decisions/1/search -d
'{"title":"Inception","year":2010}' | jq '.candidates | length'` → expected: ≥ 1.

- `ACC-06`: Dismiss marks row + staging 403 blocks dismiss.
  `curl -s -X POST -b cookies.txt https://tm-staging.iznogoudatall.xyz/api/decisions/1/dismiss`
  → expected (staging): 403. On prod equivalent: 200.

**Commit:** `docs(scrape-arbiter): add ACCEPTANCE.md with executable criteria`

---

### Sub-phase 5.3 — Docs update

**Modifies:**

- `docs/reference/web-ui.md` (add §S5 — scrape-arbiter feature)
- `docs/reference/scraping.md` (document behavior change: mid-band enqueue vs auto-accept)
- `docs/reference/indexer-json-shapes.md` (already done in phase 1.2 — verify)

**DESIGN ref:** §8 — behavior change documented in `web-ui.md` §S5 + `scraping.md`

web-ui.md §S5: document the `/decisions` page, the decision queue workflow, the badge,
threshold behavior, error states (409, 410, 502), and the runner lifecycle. Reference the
existing `scrape-resolve` command. Follow existing doc conventions (section numbering,
cross-references to related docs).

scraping.md: document the batch behavior change: mid-band (0.5–0.8) no longer
auto-accepts; instead enqueues to `scrape_decision` with trigger `mid_band`. Note
`<0.5` item behavior is additive (decision row + existing skip semantics). Note the three
triggers and their operator intent.

**Commit:** `docs(scrape-arbiter): document S5 feature in web-ui.md and scraping.md`

---

### Sub-phase 5.4 — Final gate

No file changes — verification only:

1. `make check` — lint + test + module-size + typed-api guardrails all green.
2. Residual import grep: for any module renamed/deleted across phases, grep
   `personalscraper/` + `tests/` for old import paths. Zero matches.
3. `python -c "import personalscraper"` — smoke test.
4. CI green on the PR (frontend lint+typecheck+vitest + backend lint+test + OpenAPI drift
   guard).
5. Re-exercise all ACC-NN criteria on staging.
6. Per-design invariants check: single auth perimeter, epoch timestamps, NFC
   normalization, `_CLI_SELF_LOCKING` includes `scrape-resolve`, `require_not_staging` on
   write routes, XRW on mutations.

**Commit:** (no commit — this is the gate before `/implement:feature-pr` auto-invoke)
