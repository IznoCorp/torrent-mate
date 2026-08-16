# Documentation audit — language mixing & staleness (2026-08-16)

> Scope: every tracked `*.md` (1068 files). Method: mechanical language
> classification (FR/EN stopword ratio, code blocks stripped) over the full
> corpus, plus three deep-read passes (root docs, `docs/reference/`, live
> engineering artifacts) verifying claims against the code at `0.97.6`
> (branch `fix/vo-title`, HEAD `c72fec09`).

## 0. Corpus shape

| Area | Files | Language profile |
|---|---|---|
| `docs/archive/` | 923 | frozen history: 598 EN, 214 FR, 33 mixed |
| `docs/reference/` | 35 | all EN except `product-intent.md` (FR by design) |
| `docs/features/` | 40 | mixed bag — 2 dirs monolingual FR |
| `docs/superpowers/` | 33 | mostly EN; 2026-04/05 sets monolingual FR |
| `docs/analysis/` | 15 | EN except 1 FR + 2 mixed |
| `docs/pipeline-runs/` | 10 | all FR-under-EN-headings |
| root + misc | 12 | 4 user docs FR, 3 mixed, rest EN |

The stated policy already exists (`CLAUDE.md` §Language + §Design Reference:
durable artifacts in English; French only for quoted UI copy) — it is simply
not enforced, and parts of `CLAUDE.md` itself violate it.

## 1. Language findings (live files only)

### 1a. Genuinely MIXED files (the forbidden case)

| File | Where the mixing is |
|---|---|
| `CHANGELOG.md` | EN header/banner, then **8 consecutive FR releases** (`0.60.0`→`0.65.2`, L26–172), then EN from `0.59.1` down |
| `CLAUDE.md` | FR sections L37–64 (Product Intent + Design Reference), FR table rows L288–289, stray FR clause L154 |
| `IMPLEMENTATION.md` | FR block L211–272 (metrics table + « Les trois questions ») inside EN doc |
| `docs/superpowers/specs/2026-05-03-module-size-decomposition-design.md` | full FR paragraphs L148, 160, 174, 178 in EN narration |
| `docs/analysis/2026-08-05-provenance-spine-hole-handoff.md` | EN L1–37, then FR L38–203 (clean split) |
| `docs/analysis/2026-07-16-e7-screen-rule-sweep.md` | FR table headers/rule vocabulary under EN prose |
| `docs/reference/web-ui.md` | one FR **prose** sentence L1257–1258 (« Staging » n'est pas une étape…) — the other FR hits are legitimate quoted UI strings |
| `docs/pipeline-runs/*.md` (10) | EN scaffolding (`## Status:`, step names) wrapping FR findings prose, body-wide |

### 1b. Monolingual-French engineering artifacts (wrong language, no mixing)

Live/recent: `ROADMAP.md` (549 L), `docs/features/file-absorbee/*` (6 files),
`docs/features/recherche-juste/*` (11 files), `docs/features/provenance/EPIC-ROADMAP.md`,
`docs/superpowers/roadmap/llm-assistant/brainstorming.md`,
`docs/superpowers/specs+plans/2026-04-22-implement-skills-refactor*` (7 files),
`docs/superpowers/plans/2026-05-03-config-*` (2 files),
`.github/PULL_REQUEST_TEMPLATE.md` (31 L, 100 % FR).

### 1c. French that is (probably) intentional — needs operator confirmation

User/operator-facing docs: `README.md`, `MANUAL.md`, `INSTALLATION.md`,
`CONFIGURATION.md`, `docs/reference/product-intent.md` (constitution, FR by
operator decision). All near-pure FR, coherent. Quoted French UI strings inside
English docs are per-convention correct everywhere they were checked
(`BUGS.md`, `web-ui.md`, vo-title DESIGN, maquette README, plan files).

`docs/features/vo-title/DESIGN.md` (current feature) is clean English.

## 2. Staleness findings

### 2a. Root docs

- **`CHANGELOG.md` — worst file in the repo.** FROZEN banner says "stopped
  after 0.19.0 … code moved on to 0.49.x … resumes at 1.0.0", yet 8 releases
  (0.55.0–0.65.2) sit right below it; newest entry 0.65.2 (2026-07-31) vs code
  0.97.6 — ~32 minor versions unlogged. Header still says "personalscraper".
- **`ROADMAP.md`** — status stamped 2026-07-04; S2/S3/S4 web waves still `[P2]`
  though shipped & archived; zero mention of the shell-mobile/maquette mission;
  "UX mobile" listed *hors scope v1* (L346) — actively contradicts reality.
- **`IMPLEMENTATION.md`** — header still `shell-mobile` / `feat/shell-mobile`
  while the branch is `fix/vo-title` with `docs/features/vo-title/DESIGN.md`
  existing. The designated anti-drift file is itself drifted. Also:
  `pm2 restart torrentmate-design` (app absent from `ecosystem.config.js`),
  stale `http.server 8899` recipe pre-dating `serve.py`, and a dangling ref to
  `docs/analysis/2026-08-12-app-component-duplication-audit.md` (L344).
- **`CLAUDE.md`** — stale facts: CLI entry point is now `torrentmate`
  (`personalscraper` = alias); module-size "advisory in 0.9.0 / block in
  0.10.0" long since shipped as a hard block; "6000+ tests" vs ~9281;
  Reference-Index row still says "scheduling (launchd)" (decommissioned →
  PM2); "11 implement:* skills" (now 12); "max-3 fix cycles" (now
  track-scaled 5/2/1); kanban S2/S3/S4 tickets listed as claimable though
  shipped.
- **User docs (README/MANUAL/INSTALLATION/CONFIGURATION)** — content is
  ~6 weeks / ~30 minor versions behind: the `search` command absent everywhere
  (MANUAL documents every sibling but not it); `personalscraper-search` PM2
  cron missing from MANUAL + INSTALLATION tables; config-home relocation
  (`~/.torrentmate/config`) absent from CONFIGURATION (which still says
  "never commit config/ — gitignored", contradicted by `conf/config_git.py`)
  and INSTALLATION; the whole `frontend/maquette/` track invisible in
  README/MANUAL. CONFIGURATION otherwise field-accurate; MANUAL's `library-*`
  inventory and 9-step pipeline table verified accurate.
- **`BUGS.md`** — healthy, actively maintained (2026-08-15), EN with
  per-convention FR quotes. Caveat: despite the generic title it only ledgers
  web-UI/maquette bugs.

### 2b. `docs/reference/` verdicts

- **STALE**: `promises.md` (module-size table wrong: real WARN set is 7 files,
  two at 999/1000, none scraper); `event-bus.md` (39 vs **48** events, 10
  undocumented, AppContext has 6 fields not 3); `scraping.md` (broken sample
  import `personalscraper.api.errors` — real: `api._contracts`);
  `runbook-post-merge.md` (`library init-canonical` sub-group form doesn't
  exist → `library-init-canonical`; `launchd-plists/` doesn't exist, PM2
  cutover done); `external-ids-flow.md` (resolved caveat still present;
  `config/trakt.json5` doesn't exist); `feature-lifecycle.md`
  (`acceptance-check.sh` never existed; "target 0.17.0" 80 minors past).
- **MINOR DRIFT**: `architecture.md` (`notifier.py` ghost, event counts,
  `transports/` → `api/transport/`, `preferences.json5` not an overlay, dead
  `acquire-store` link), `commands.md` (grab `--followed-id` missing; no
  sections for `cross-seed`, `acquisition-requeue/-rescrape`,
  `library-refresh-path`), `web-ui.md` (PM2 table misses
  `personalscraper-search`; S1-era routes/ tree; 4 dead `docs/features/…`
  links), `maintenance.md` (REGISTRY is a list of 26, not dict of 25),
  `logging.md` (`notifier.py`, `storage.json5` → `disks.json5`),
  `indexer.md` (tables from migrations 011–016 missing: `pipeline_run`,
  `scrape_decision`, `destructive_op`), `config-overlay-layout.md` (trees omit
  `acquire.json5`; dead config-home link), `grab-core.md`, `testing.md`
  ("fail-fast" comment wrong), `storage.md` (`_fs_probe` moved to
  `core/sqlite/`), `telegram-api.md` + `healthchecks-api.md` (migration-plan
  sections overtaken; `notifier.py` ghosts).
- **CURRENT**: `pipeline-internals.md`, `naming.md`, `insights.md`,
  `trailers.md`, `libraries.md`, `tmdb-api.md`, `qbittorrent-api.md` (light
  pass on the other provider docs).
- Incidental code finding: `commands/health_check.py:178-179` registers the
  command twice (`@app.command` stacked on `@command_with_telemetry`).

### 2c. Archive backlog (root cause of much of the noise)

The archive step folded into `/implement:create-branch` has been skipped
repeatedly:

- **8 of 10 `docs/features/` dirs are merged features never archived**:
  `decisions-spine` (#361), `file-absorbee` (#413), `parcours` (#359),
  `provenance` (#357), `recherche-juste` (#410), `run-linkage` (#363),
  `spine-actions` (#365), `webui-ux` (#249). Still live: `tech-debt-2`
  (never built, on ROADMAP) and `vo-title` (current).
- **7 superseded plans** `docs/superpowers/plans/2026-08-12-shell-mobile-phase-*`
  (~5.6k lines) encode the order the mission explicitly abandoned on
  2026-08-13; referenced by nothing live.
- **Completed superpowers sets**: 2026-04-22 skills-refactor (7 files, FR),
  2026-05-03 config campaign (2 FR + 1 mixed spec), 2026-07-16 design-overhaul,
  2026-08-06 acq-mobile, 2026-08-08 maquette-parity (ledger still referenced —
  keep with its execution plan or re-point).
- **All 10 `docs/pipeline-runs/`** (Apr–Jun 2026): zero live inbound
  references (all 21 refs are inside `docs/archive/`).
- **11 of 15 `docs/analysis/`** have no live inbound reference. Keep:
  `2026-08-08-maquette-parity-ledger.md`,
  `2026-08-10-acquisition-refonte-analysis-and-transfer.md`,
  `03-god-modules-debt-audit.md` (cited by tech-debt-2).
- **Dead cross-references**: 7 `docs/features/<codename>/…` links in
  `docs/reference/` point at archived codenames (`acquire-store`,
  `config-home`, `grab-core`, `maint-dash`, `config-editor`, `scrape-arbiter`,
  `tm-shell`); `personalscraper/notifier.py` is cited by 4 docs though
  deleted; 3 `docs/analysis/…` files are cited but never existed
  (one from the live `IMPLEMENTATION.md:344`).

## 3. Proposed remediation plan

**Guardrail**: run on a dedicated branch (`chore/docs-language`), not on
`fix/vo-title`. Archives (`docs/archive/`, 923 files) stay untouched — frozen
history is exempt from the language rule (translating it rewrites the record).

- **Phase A — operator arbitration (blocking, see §4).**
- **Phase B — archival sweep (no translation).** Move the 8 merged feature
  dirs, the 7 superseded shell-mobile plans, completed superpowers sets, all
  pipeline-runs, and the 11 dead analysis files into `docs/archive/…`.
  Once archived they inherit the archive exemption — the monolingual-FR sets
  (`file-absorbee`, `recherche-juste`, skills-refactor, pipeline-runs…) need
  **no translation**, which shrinks the translation surface by ~40 files.
- **Phase C — fix references.** Re-point the 7 dead `docs/features/` links to
  `docs/archive/features/`, purge the `notifier.py` ghosts, fix/remove the 3
  dangling analysis refs, re-head `IMPLEMENTATION.md` to the actual current
  feature.
- **Phase D — de-mix the live mixed files (translate FR → EN in place).**
  `CLAUDE.md` (2 sections + strays), `IMPLEMENTATION.md` (L211–272),
  `CHANGELOG.md` (banner rewrite + unify entries), `web-ui.md` L1257,
  module-size spec L148–178, plus whichever of §1b stays live after Phase B
  (at minimum `llm-assistant/brainstorming.md`, `provenance/EPIC-ROADMAP.md`
  if kept, `ROADMAP.md` per arbitration).
- **Phase E — content refresh.** The 6 STALE reference docs, then the
  MINOR-DRIFT batch; user-doc refresh (in French): `search` command +
  `personalscraper-search` cron, config-home relocation, maquette track;
  `CLAUDE.md` stale facts; ROADMAP resync with reality.

## 4. Open arbitration points (operator decisions)

1. **Confirm the user-doc exception set**: README / MANUAL / INSTALLATION /
   CONFIGURATION / product-intent stay French? (Recommended: yes.)
2. **`.github/PULL_REQUEST_TEMPLATE.md`** — engineering artifact currently
   100 % FR. Translate to EN, or treat as operator-facing FR?
3. **`ROADMAP.md`** — engineering planning doc, monolingual FR. Translate to
   EN during the resync, or declare it operator-facing FR?
4. **`CHANGELOG.md` target language** — it is user-facing by genre but its
   recent entries are engineering narratives. One language must win
   (recommended: English, matching the pre-0.60 history), and decide whether
   to backfill 0.66→0.97 or re-freeze honestly with a truthful banner.
5. **CLAUDE.md constitution sections** (Product Intent / Design Reference,
   FR L37–64): translate to EN like the rest of CLAUDE.md, or keep FR because
   they quote the FR constitution? (Recommended: translate the framing,
   keep quoted §-titles in FR.)
6. **Archive exemption** confirmed? (Recommended: yes — never translate
   `docs/archive/`.)

## 5. Addendum — re-verification against `main` @ 9842e44d (2026-08-16)

The audit passes above ran against `fix/vo-title` @ `c72fec09` (0.97.6).
Before remediation started, `main` moved to 0.97.11 (#436–#441). Deltas:

- **vo-title merged** (#436). `docs/features/vo-title/` becomes the 9th
  merged-but-unarchived feature dir; `shell-mobile` is the current feature
  again, so the `IMPLEMENTATION.md` header is **no longer stale** — that
  fix is dropped. Note instead: the header still claims "`main` … is touched
  once, at the end" while SP1–SP4b merged onto `main` PR by PR — left for
  the operator to reconcile (mission statement, not a doc defect).
- `BUGS.md` moved again (#439, B-019/020/023 closed) — still healthy.
- All other findings re-apply unless contradicted during remediation; every
  fix is re-verified against the code at 0.97.11 before being applied.

## 6. Operator arbitration (2026-08-16) — RESOLVED

- `CLAUDE.md`: **entirely English**; French allowed only to quote app
  sections/screens named in French and media titles.
- All other recommendations approved as stated: user docs (README, MANUAL,
  INSTALLATION, CONFIGURATION, product-intent) stay French; `docs/archive/`
  is exempt and never translated; CHANGELOG unifies to English with a
  truthful banner (no 0.66→0.97 backfill); ROADMAP and the PR template are
  engineering artifacts → English. Work happens on a dedicated workspace
  (`chore/docs-language`).
