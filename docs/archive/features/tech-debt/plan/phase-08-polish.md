# Phase 8 — Polish + Plan A reset + module-size hard-block + ACCEPTANCE.md

**Effort** : 3-4 jours (revised — adds DEV #25, #27, #41, #46, #49, #53 cleanup)
**Theme** : completer les should-have restants + Plan A reset+rescrape (DEV #27) + promote
module-size to hard-block (DEV #46) + bonus cleanups + produire ACCEPTANCE.md exécutable.

## Coverage matrix

| Item                                        | Sub-phase     | Source pattern    |
| ------------------------------------------- | ------------- | ----------------- |
| SH-3 / BD-S                                 | 8.1           | (cron)            |
| SH-6 / BD-U + BD-V                          | 8.2           | P16               |
| SH-14 / CL-B / DEV #20                      | 8.3           | P20               |
| SH-17 / CF-G / P11                          | 8.4           | P11               |
| SH-21 / AR-C                                | 8.5           | P26               |
| SH-22 / AR-D                                | 8.6           | P19               |
| SH-25 / CL-S (FOLDED → Phase 9.1)           | ~~8.7~~ → 9.1 | (tests)           |
| SH-26 / BD-H                                | 8.8           | P12               |
| CF-J / 15 criteria                          | 8.9           | P23, P32          |
| **DEV #27 Plan A reset+rescrape**           | 8.10 NEW      | P23, P24          |
| **DEV #46 0.10.0 module-size hard-block**   | 8.11 NEW      | P31 PROMISE_STALL |
| **DEV #53 \_upsert_media_item dedup logic** | 8.12 NEW      | (bonus)           |
| **DEV #25 event-bus module budgets**        | 8.13 NEW      | (audit)           |
| **DEV #41 test-coverage branch re-measure** | 8.14 NEW      | P32               |
| **DEV #49 test_cli @patch trim**            | 8.15 NEW      | P32               |

DESIGN sections impacted : §13 promise lifecycle, §14 success criteria, §11 architecture,
§9 BDD lifecycle invariants (post Plan A reset).

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phase 1-7 commited + gates verts
- Branch prête pour PR / merge

## Sub-phases

### 8.1 Cron backfill-ids (SH-3 / BD-S)

**Site** : `launchd-plists/` (à créer pendant 8.1 — n'existait pas) — ajouter
`com.personalscraper.backfill-ids.plist`.

**Contenu** : invocation hebdomadaire `personalscraper library-backfill-ids`
(Sunday 03:00). Log dans `~/.cache/personalscraper/backfill-ids.log`.

> **Plan drift corrigé 8.1 (2026-05-23)** : la version originale du plan disait
> `personalscraper library-index --mode backfill-ids --budget-seconds 1800`.
> Ces flags n'existent pas sur le CLI réel : `library-index` n'a pas de mode
> `backfill-ids` (modes valides : `full`, `quick`, `incremental`, `enrich`) et
> aucune commande n'expose `--budget-seconds`. La commande dédiée
> `library-backfill-ids` est la bonne invocation et n'a pas besoin de budget
> (elle est naturellement bornée par le nombre de rows restantes + rate-limits
> API). Le log dir `~/.cache/personalscraper/` doit être créé manuellement
> avant `launchctl bootstrap` (cf. README dans `launchd-plists/`).

**Commit** : `feat(tech-debt): launchd plist for weekly backfill-ids (SH-3)`

### 8.2 Audit `pending_op` + `item_issue` (SH-6 / BD-U + BD-V)

**Action** : grep callers.

- Si `pending_op` 0 callers → DROP via migration 007 (ou laisser, low priority).
- Si `item_issue` 0 callers ou seulement les sites mentionnés en item 7 (`release_linker.py:322`,
  `library/analyzer.py:112`+282) qui DOCUMENT le pattern mais n'insèrent rien → marquer comme
  "design intent, not yet wired" + créer issue 0.17+ pour câbler.

**Commit** : `chore(tech-debt): audit pending_op + item_issue tables (SH-6)`

### 8.3 `qbit-restart` command (SH-14 / CL-B / DEV #20)

**Décision Phase 8.3 (2026-05-23) : Option B retenue.**

**Rationale** :

- Sur l'install opérateur (macOS 14.5), qBittorrent est livré en GUI app
  (`/Applications/qBittorrent.app`) — pas de plist launchd déterministe à
  `~/Library/LaunchAgents/com.qbittorrent.plist` (vérifié `ls` 2026-05-23).
- Wrapper portable `launchctl unload/load` infaisable : le mécanisme de
  lancement (GUI manuel, `brew services`, `open -a`, ou launchd) varie par
  install et serait fragile à maintenir.
- L'action de recovery réelle (kill process + relaunch GUI app) reste manuelle
  côté opérateur. La matrice §INGEST recovery est mise à jour pour le refléter.

**Action personalscraper (ce commit)** :

- `tests/skill/test_matrix_cli_refs.py` : reformulation du xfail strict
  `qbit-restart` (devient documentation de la décision Option B) ; assouplit
  `test_matrix_parses_known_refs` qui exigeait `"qbit-restart" in commands`
  — la matrice patchée (v2.1.1) ne le mentionnera plus.
- `HANDOVER.md` : DEV #20 passe à `RÉSOLU Phase 8.3`.

**Action cross-repo (follow-up opérateur)** :

- Sur `.claude/personal-scraper`, patcher
  `skills/pipeline-monitor/references/design-conformity-matrix.md` ligne 94
  (DEVIATIONS table INGEST) : remplacer `personalscraper qbit-restart
recommandé` par `restart manuel qBit (GUI / launchctl selon install)`.
- Bump matrix version footer à v2.1.1.
- Une fois ce patch landé, le xfail strict `qbit-restart` devient un no-op
  (la commande n'apparaît plus dans `_load_params`) ; le `_KNOWN_BAD` row
  peut être supprimé en cleanup ultérieur sans urgence.

**Pas de nouvelle ACC** : DEV #20 reste couvert par ACC-14 (Test "matrix
references valid CLI", déjà ✅ SHIPPED `ff0a8d4` + `3b0d582`). L'invariant
"toute commande référencée matrix existe sur le CLI" reste enforced ; la
décision 8.3 retire la dette en supprimant la mention plutôt qu'en ajoutant
la commande.

**Commit** (option B retenue) : `docs(tech-debt): qbit-restart Option B — matrix removal decided (SH-14, DEV #20)`

### 8.4 Audit dead infrastructure (SH-17 / CF-G / P11)

**Script** : `scripts/audit-dead-infrastructure.py` (nouveau)

**Scope** :

- Tables avec 0 rows depuis init (`deleted_item` post-Phase 1 fix : devrait avoir des rows ;
  `item_issue` ; `pending_op`)
- Colonnes never populated (sortie : col + table + count NULL)
- Functions définies, jamais appelées : grep + AST analysis
- Protocols définis, jamais utilisés

Sortie : rapport markdown `docs/features/tech-debt/audit/12-dead-infrastructure.md` listant
chaque candidat à drop ou à câbler.

**Commit** : `chore(tech-debt): audit dead infrastructure script + report (SH-17)`

### 8.5 Expose `clean` + `cleanup` CLI sub-commands (SH-21 / AR-C)

**Site** : `personalscraper/commands/pipeline.py` — ajouter deux nouvelles commandes.

**Implementation** : wrappers Typer qui invoquent les sous-fns de `process/run.py`. Coût
faible. Permet debugging + composition.

**Commit** : `feat(tech-debt): expose clean + cleanup CLI sub-commands (AR-C)`

### 8.6 Trailers verify rename alias (SH-22 / AR-D)

**Site** : `personalscraper/trailers/cli.py`

**Implementation** : ajouter `@app.command("audit")` + alias deprecation `@app.command("verify")`
qui print warning + redirige vers `audit`. Retirer dans 0.17+.

**Commit** : `feat(tech-debt): trailers audit alias for trailers verify (AR-D)`

### 8.7 Pin commands tests (SH-25 / CL-S) — **FOLDED into Phase 9.1** (2026-05-23)

**Status** : déplacé dans la nouvelle **Phase 9 CLI Test Coverage** (sub-phase 9.1).
Le pin test (`tests/commands/test_pin_existence.py`) sera livré comme partie intégrante
de l'infrastructure de test CLI. Voir `phase-09-cli-coverage.md` §9.1.

Cette section est conservée pour traçabilité de la décision mais ne sera pas exécutée
en Phase 8. Le sub-phase checklist 8.7 ci-dessous est annulé.

### 8.8 Audit modules sans CLI (SH-26 / BD-H / CL-K extension)

**Script** : `scripts/audit-cli-coverage.py` (étendu de la version Phase 2.5)

Pour chaque module métier critique (`library/`, `indexer/`, `scraper/`, `trailers/`,
`ingest/`, `sorter/`, `dispatch/`, `verify/`, `enforce/`), vérifier qu'au moins UNE commande
CLI l'invoke en E2E.

**Commit** : `test(tech-debt): audit modules CLI coverage (SH-26)`

### 8.9 Produce ACCEPTANCE.md

**Site** : `docs/features/tech-debt/ACCEPTANCE.md` (nouveau)

**Format** : reprend les 15 criteria de DESIGN.md §6, expand chacun en :

```markdown
### ACCEPTANCE-N : <description>

**Criterion** : <human readable>
**Validation command** : `<exact shell command>`
**Expected output** : <expected result>
**Source items** : MUST-X, SH-Y, CF-Z (provider-ids), etc.

✅ / ❌ / 🟡 — status post-Phase 8
```

À cocher au moment de la phase gate de chaque phase.

**Commit** : `docs(tech-debt): ACCEPTANCE.md executable criteria (CF-J)`

### 8.10 Plan A reset + rescrape — VERIFY + retry (DEV #27 + #54 closure)

**Décision opérateur 2026-05-22 (option b)** : Plan A est lancé **en arrière-plan dès la fin
de Phase 1.9** (voir `phase-01-foundations.md` § "Post-commit action"). Il tourne pendant
Phases 2-7. Phase 8.10 devient donc principalement une **étape de vérification + retry si
nécessaire**.

**Preconditions** : Phase 1.9 init-canonical commit + Plan A background launch effectué.

**Sequence** :

1. Vérifier la complétion : `cat .data/plan-a-backfill.log | tail -50` — chercher
   `BackfillCompleted` event final ou exception non-traitée.
2. Si le PID est encore vivant : `kill -0 $(cat .data/plan-a-backfill.pid)` — attendre la fin.
3. Mesurer la couverture :
   - `SELECT COUNT(*) FROM media_item WHERE external_ids_json = '{}';` → doit tendre vers 0
   - `SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL;` → doit tendre vers 0
   - `personalscraper library-doctor` → reporte `canonical_provider populated > 90%`
4. **Si couverture < 90% (échec partiel — réseau, rate-limit, API quota)** :
   - Backup `library.db` → `library.db.bak.plan-a-retry-{date}`
   - Relancer en foreground avec budget plus généreux :
     `personalscraper library-index --mode backfill-ids --no-budget --retry-failed`
5. **Items restants empty (no NFO uniqueid)** : optionnel
   `library-rescrape --apply --filter "canonical_provider IS NULL"` (full TMDB scrape, slow).

**Resolves** : provider-ids ACCEPTANCE #3 (CLI present via Phase 2), #4 (data populated), #10
(8-show staging dispatch-ready validation). DEV #12 (provider-IDs empty sub-cause). DEV #27
(Plan A executed). DEV #54 (chicken-and-egg unblocked by init-canonical).

**Commit** : `chore(tech-debt): Plan A backfill verification + closure (DEV #27, #54)`
(commit du log final + bilan, action principale déjà tournée hors-commit en Phase 1.9 post).

### 8.11 Promote check-module-size to hard-block (DEV #46)

**Site** : `scripts/check-module-size.py` + `Makefile`.

**Bug** : DESIGN arch-cleanup promised hard-block in 0.10.0. We're at 0.15.1, 5 versions
overdue. Script still prints WARN but exits 0.

**Fix** :

1. Modify `scripts/check-module-size.py` :

   ```python
   # Change exit logic
   has_block = any(loc > BLOCK_LOC for loc in module_locs)
   has_warn = any(WARN_LOC <= loc <= BLOCK_LOC for loc in module_locs)
   if has_block:
       sys.exit(1)
   # WARN no longer blocks but is still printed for visibility
   ```

   Currently both `existing_validator.py` (917) and `tv_service.py` (986) are WARN (not BLOCK).
   Hard-block only triggers > 1000.

2. **Decision** : do we want WARN to ALSO block in 0.16.0 ?
   - Option A : keep WARN advisory, only BLOCK > 1000 → minimal disruption, but the 800 advisory
     is mostly ignored.
   - Option B : promote WARN to BLOCK in 0.16.0 → requires splitting `tv_service.py` (986)
     and `existing_validator.py` (917) RIGHT NOW. Heavy work, +1-2 d.

   **DESIGN tech-debt decision** : Option A for 0.16.0 (BLOCK > 1000 hard). Option B logged
   in roadmap 0.17+ with explicit "splits required" tag.

3. Add `docs/reference/promises.md` (new) listing the BLOCK threshold + which modules are
   close (within 100 LOC) — early warning system.

**Commit** : `feat(tech-debt): promote check-module-size to hard-block on >1000 LOC (DEV #46)`

### 8.12 Fix `_upsert_media_item` lookup-key consistency (DEV #53)

**Site** : `personalscraper/library/scanner.py` around `_upsert_media_item`.

**Bug** : `_upsert_media_item` looks up existing item by `(title, year)` but stored `title`
field contains `"(YYYY)"` literally on some rows (legacy) while new lookups use cleaned title.
Result : 1863 duplicate rows created on one scan_library() call.

**Fix** :

1. Normalize lookup key : strip `" (\d{4})$"` regex from both stored and lookup title before compare
2. Migration 007 : one-shot UPDATE to canonicalize title across all existing rows :
   ```sql
   UPDATE media_item
   SET title = REGEXP_REPLACE(title, ' \(\d{4}\)$', '', 1)
   WHERE title LIKE '% (____)';
   ```
3. Add UNIQUE constraint `UNIQUE(title, year, kind)` on `media_item` (post-migration) to
   prevent future duplicates at DB level.
4. Regression test : create item with `title="Foo"`, year=2020, then call \_upsert_media_item
   with same — assert no INSERT.

**Commit** : `fix(tech-debt): \_upsert_media_item canonical title lookup + UNIQUE constraint

- migration 007 (DEV #53)`

### 8.13 Sync event-bus catalog v1 13 → 17 (DEV #25)

**Sites** :

- `personalscraper/events/__init__.py:__all__` — append `BackfillStarted`,
  `BackfillItemCompleted`, `BackfillSkipped`, `BackfillCompleted`
- `docs/reference/event-bus.md` catalog table — bump from 13 to 17, add 4 rows
- DESIGN budget update : `core/event_bus.py` budget 400 → 420 (current 410), document
  rationale, OR split into `_emit.py` + `_subscribe.py` (more invasive)

**Decision tech-debt 0.16.0** : raise budget to 420 with rationale (provider-ids extension
is single-feature, not pattern). Split → 0.17+ if more events added.

**Commit** : `docs(tech-debt): event-bus catalog v1 13 → 17 + budgets raised (DEV #25)`

### 8.14 Test-coverage branch re-measure (DEV #41)

**Action** : run `make test-cov`, capture `coverage.xml`, update IMPLEMENTATION.md +
test-coverage archive note with current branch coverage figure. If drift > 5 % since
"91 %" claim, file a follow-up issue to recover the lost coverage (likely added by
provider-ids feature without proportional branch tests).

**Commit** : `docs(tech-debt): test-coverage branch re-measurement post-provider-ids (DEV #41)`

### 8.15 test_cli @patch trim (DEV #49)

**Site** : `tests/test_cli.py`.

**Action** : reduce `@patch` count from 52 → ≤25 (test-realism DESIGN §5 target). Strategies :

- Promote unit-level `@patch` to fixture-level for shared mocks
- Replace deep mocks with `MagicMock(spec=Class)` (test-realism goal)
- Extract integration tests to `tests/integration/` (where mocks are looser)

**Commit** : `refactor(tech-debt): trim test_cli @patch count 52 → ≤25 (DEV #49)`

## Phase 8 Gate (= PR gate) — GATE COMMIT `c8f20dd` (2026-05-24)

- [x] 8.1 cron entry present (SH-3) — `5426826`
- [x] 8.2 pending_op + item_issue audit done (SH-6, BD-U/V) — `ba47124` (both KEEP, full production wiring)
- [x] 8.3 qbit-restart decided — Option B (matrix removal), cross-repo patch on `.claude/personal-scraper` is operator follow-up (SH-14, DEV #20) — `017ea7b`
- [x] 8.4 dead infrastructure audit report committed (SH-17) — `92c4d11` (261 dead-function candidates surfaced)
- [x] 8.5 `personalscraper clean` + `cleanup` exposed (SH-21, AR-C) — `771e630` (33 new tests)
- [x] 8.6 `trailers audit` alias works (SH-22, AR-D) — `0c6886d` (46 tests)
- [~] 8.7 FOLDED into Phase 9.1 — pin test livré en Phase 9 CLI Test Coverage (SH-25) — see `a66c411` (40 pin tests)
- [x] 8.8 audit-cli-coverage exit 0 (SH-26) — `0376222` (5 new domains; 1 SH-26 finding `ingest`)
- [x] 8.9 ACCEPTANCE.md complete with all criteria ✅ (CF-J) — `addab31` (70 criteria reconciled)
- [x] 8.10 Plan A reset+rescrape — PARTIAL at gate `0da47b1` (audit + runbook), COMPLETED post-gate via **8.10.b** (`173d529`+`e68c484` — library-fix-nfo CLI), **8.10.c** (`82b32de`+`3a971f1`+`3cfffbb` — init-canonical chicken-and-egg fix), **8.10.d** (`c5b7332`+`807187e`+`52ad7ae` — OMDB quota tracker). Operator ran backfill 2026-05-24, library-doctor reports **91.3% external_ids populated** (DEV #27, #54 closed). Ratings rerun (next OMDB quota window) deferred — quota tracker now in place.
- [x] 8.11 check-module-size hard-blocks > 1000 (DEV #46) — `58c63d3`
- [x] 8.12 \_upsert_media_item dedup + migration 007 + test (DEV #53) — `bcb2065` (18 dedicated tests + 661 indexer regression)
- [x] 8.13 event-bus catalog v1 sync (DEV #25) — `fb96adb` (13→17 events re-exported; budget split deferred to 0.17+)
- [x] 8.14 branch coverage re-measured + IMPLEMENTATION updated (DEV #41) — `15a5a2e`+`b27de8b`+`0c3bc33` (87.09% branch / 91.88% combined, Δ -3.91pp vs 91% historical, within ±5pp band, no follow-up)
- [x] 8.15 test_cli @patch ≤ 25 (DEV #49) — `60d910d`+`df723b5`+`1cd653a` (52→20, target met)
- [x] `make check` vert (post pre-gate hygiene `5e4e183` for format + `3876636` cleared 3 pre-existing no-print ERRORs on `cli_helpers/output.py` via `typer.echo` migration + PRAGMA discipline fix on `library-fix-nfo`)
- [x] `personalscraper library-doctor` exit 0 sur DB prod post-toutes-phases — operator confirmed via Plan A retry audit 2026-05-24
- [ ] PR ready — at end of Phase 10

**Phase gate commit** : `chore(tech-debt): phase 8 gate — polish + Plan A reset + module-size hard-block + ACCEPTANCE complete`

**PR creation** : suite Phase 8 gate, lancer `/implement:feature-pr` (auto par
`/implement:phase` à la last phase) puis `/implement:pr-review`.
