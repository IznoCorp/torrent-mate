# Phase 9 — CLI Test Coverage (NEW)

**Effort** : **1.5-2 jours** (révisé 2026-05-23 après audit des harnesses existants —
11 commandes library déjà shippées + 1 in-progress par l'agent d'implémentation
parallèle ; scope restant = 17 critiques + 6 non-critiques + harmonisation 11 existants)
**Theme** : combler le déficit de tests par-commande sur la surface CLI restante
(`personalscraper <command>`), avec **sections thématiques cohérentes** alignées sur le
pattern d'harnesse E2E déjà adopté dans `tests/commands/_e2e_helpers.py`.
**Insertion** : entre Phase 8 (Polish) et la Phase 10 (Archive-docs, ex-Phase 9).
Phase 8.7 (Pin commands tests SH-25 / CL-S) est **absorbée** dans 9.1.

## Contexte 2026-05-23 — audit harnesses existants

L'agent d'implémentation a déjà produit (commits b9cb39c..7564153 + 1 untracked) :

| Cmd                      | Tests | Sections                                                  | Status       |
| ------------------------ | ----- | --------------------------------------------------------- | ------------ |
| `library-doctor`         | 5     | Smoke + Realistic + Closure-BD-D + Idempotence            | committed    |
| `library-verify`         | 9     | Smoke + Realistic + Closure-BD-D + Idempotence            | committed    |
| `library-repair`         | 6     | Smoke + Realistic + Closure-BD-D + Idempotence + Dry-run  | committed    |
| `library-reconcile`      | 7     | Smoke + Realistic + Closure-BD-D                          | committed    |
| `library-index`          | 7     | Smoke + Realistic + Closure-BD-D-#2-merkle                | committed    |
| `library-scan`           | 6     | Smoke + Realistic + Idempotence + Dry-run + Hidden        | committed    |
| `library-gc`             | 7     | Smoke + Realistic + Threshold + Idempotence + Dry-run     | committed    |
| `library-status`         | 6     | Smoke + Realistic                                         | committed    |
| `library-init-canonical` | 5     | Smoke + Realistic + CHECK-safe filter                     | committed    |
| `library-ghost-audit`    | 5     | Smoke + Realistic + NTFS dirent                           | committed    |
| `library-relink`         | 6     | Smoke + Empty + Dry-run + Apply + Exclusivity + Unmatched | 🚧 untracked |

**Infrastructure shipped** : `tests/commands/_e2e_helpers.py` (273 LOC, 12 helpers) +
`tests/commands/conftest.py` (36 LOC autouse mock `load_config`).

→ Phase 9 doit **s'aligner sur ce pattern existant**, pas le reformer.

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phase 8 mergée (surface CLI stabilisée : `qbit-restart` 8.3, `clean`/`cleanup` 8.5,
  `trailers audit` 8.6, `_upsert_media_item` dedup 8.12)
- 11 harnesses library E2E shippés (b9cb39c..7564153) + 1 in-progress committé
- `make check` vert sur HEAD avant 9.1

## Coverage matrix

| Item                                                                        | Sub-phase | Source              |
| --------------------------------------------------------------------------- | --------- | ------------------- |
| Infrastructure extension (pipeline mocks + events + JSON schema)            | 9.1       | NEW (absorbe SH-25) |
| Pipeline commands coverage (7 cmds — 0 shipped)                             | 9.2       | NEW                 |
| Library mutators restants (3 cmds — rescrape, backfill-ids, clean)          | 9.3       | NEW                 |
| Library diagnostic restants (4 cmds — validate, analyze, recommend, report) | 9.4       | NEW                 |
| Trailers + Config mutators (4 cmds — 0 shipped)                             | 9.5       | NEW                 |
| Non-critiques restants (6 cmds — 2 déjà shippés)                            | 9.6       | NEW                 |
| Harmonisation 11 existants + matrix + gate (ACC-50..54)                     | 9.7       | NEW                 |

## Scope & classification

### Critiques restants (17 cmds — sur 28 totales, 11 déjà shippés)

**Pipeline (7 / 7 manquants)** : `ingest`, `sort`, `process`, `verify` (pipeline-step,
distinct de `library-verify`), `dispatch`, `enforce`, `run`

**Library mutators restants (3 / 11)** : `library-rescrape`, `library-backfill-ids`,
`library-clean`
(déjà shippés : `library-repair`, `library-relink` [in-progress], `library-gc`,
`library-scan`, `library-index`, `library-init-canonical`, `library-reconcile`,
`library-verify`)

**Library diagnostic restants (4 / 6)** : `library-validate`, `library-analyze`,
`library-recommend`, `library-report`
(déjà shippés : `library-doctor`, `library-ghost-audit`)

**Trailers (2 / 2 manquants)** : `trailers download`, `trailers cleanup`

**Config (2 / 2 manquants)** : `init-config`, `config migrate-category`

→ **17 commandes critiques restantes** + 11 déjà shippées = 28 totales.

### Non-critiques restants (6 cmds — sur 8 totales, 2 déjà shippés)

**Manquants** : `library-search`, `library-show`, `torrents-list`, `trailers list`,
`trailers verify` (alias `audit` post-8.6), `info`
**Déjà shippés** : `library-status`, `library-ghost-audit` (en partie via diagnostic)

→ **6 commandes non-critiques restantes**.

## Sections thématiques (au lieu de matrice 23-points)

**Décision 2026-05-23** : abandonner la matrice 23-points théorique au profit de sections
thématiques cohérentes avec le pattern existant. Un script `cli-coverage-report.py`
parsera les en-têtes `# ── N. <Thème> ──` directement depuis les fichiers de test.

### Critiques — 8 sections obligatoires

1. **Smoke** : `--help` exit 0, signature basique
2. **Realistic scenarios** : happy path avec BDD seedée + FS dans tmp_path
3. **Errors** : config absente/corrompue, args manquants, BDD vide ou corrompue,
   path inexistant, combinaisons exclusives → erreur claire (pas de traceback brut)
4. **Idempotence** : 2 runs successifs = même état BDD (helper `bdd_diff_ignoring`)
5. **Dry-run** : `--dry-run` n'écrit rien (snapshot FS avant/après identique)
   → **N/A** justifié pour cmds sans flag dry-run (diagnostic read-only)
6. **Output** : `--format json` schéma stable (clés requises validées) +
   `--format text` lisible + exit code non-zero sur erreur
7. **Events** : EventBus émet selon matrix v2.1 (assertion via `assert_events_emitted`
   qui lit la matrix comme source de vérité)
8. **Closure-of-loop** : pattern BD-D — état post-mutation reflète bien le diff attendu
   (drain repair_queue, soft-delete media_file, etc.)
   → **N/A** justifié pour cmds sans cycle BDD ↔ FS

### Non-critiques — 4 sections obligatoires

1. **Smoke** : `--help` + signature
2. **Realistic** : happy path read-only
3. **Errors** : args invalides + config absente
4. **Output** : `--format json` parseable

## Sub-phases

### 9.1 Infrastructure extension (absorbe SH-25 / CL-S)

**Sites** :

- **NE PAS RÉÉCRIRE** `tests/commands/_e2e_helpers.py` (273 LOC déjà shippé) — étendre :
  - `mock_qbit_client(monkeypatch)` : faux client qBittorrent
  - `mock_transmission_client(monkeypatch)` : faux client Transmission
  - `mock_tmdb_client(monkeypatch)`, `mock_tvdb_client(monkeypatch)`,
    `mock_omdb_client(monkeypatch)`, `mock_trakt_client(monkeypatch)` :
    faux clients réseau retournant payloads canoniques
  - `mock_yt_dlp(monkeypatch)` : pour `trailers download`
  - `seed_pipeline_lock(staging_dir)` : crée `pipeline.lock` pour tester point lock concurrent
  - `seed_staging_layout(tmp_path, config)` : crée `001-MOVIES/`, `002-TVSHOWS/` etc.
    selon `staging_dirs` config
- **Nouveaux helpers** :
  - `assert_no_python_traceback(result)` : exit non-zero MAIS message user-friendly
  - `assert_json_schema(result, required_keys=[...], optional_keys=[...])` :
    parse JSON + valide schéma minimal
  - `assert_events_emitted(captured_bus, [EventClass, ...])` : lit
    `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md` comme
    source de vérité pour la liste attendue (anti-drift)
  - `fs_snapshot(path) -> dict` : hash récursif pour assertion `--dry-run`
  - `bdd_diff_ignoring(conn, before_snapshot, ignore_cols=["updated_at", "last_seen"])` :
    exclut colonnes time-sensitive du diff (anti faux-positif idempotence)
  - `capture_event_bus(monkeypatch) -> list[Event]` : intercepte les publish() pour
    assertions §22 (Events section)
- **Pin test SH-25** : `tests/commands/test_pin_existence.py` (nouveau) — test paramétré
  sur la liste complète des commandes Typer exposées :
  - Extraction via `personalscraper --help` parsé ou introspection `app.registered_commands`
  - Assert `--help` exit 0 + signature de base présente
  - Garantit zéro disparition silencieuse au refactor

**Audit pré-écriture** : examiner les 12 helpers shippés, identifier overlaps,
réutiliser maximum. Produire `audit/13-cli-test-fixtures.md` (court mémo).

**Module size** : `_e2e_helpers.py` à 273 LOC actuels. Ajouter ~200 LOC d'extensions
le porte à ~470 LOC, **< warning 800**. OK.

**Commit** : `test(tech-debt): extend _e2e_helpers with pipeline mocks, events, JSON schema + pin existence test (9.1, absorbe SH-25)`

---

### 9.2 Pipeline commands coverage (7 cmds — 0 shipped)

**Sites** : `tests/commands/test_<cmd>_e2e.py` pour chacune des 7 cmds pipeline.

**Commandes** : `ingest`, `sort`, `process`, `verify` (pipeline), `dispatch`, `enforce`, `run`

**Approche** :

- Adopter strictement le pattern observé dans `test_library_*_e2e.py`
- Sections `# ── 1. Smoke ──` à `# ── 8. Closure-of-loop ──` (8 sections critiques)
- Mock qBittorrent/Transmission via helpers 9.1
- FS dans `tmp_path` avec layout staging seedé via `seed_staging_layout`
- BDD réelle via `make_synthetic_db`
- Test SIGINT mid-run pour `run` : interruption propre, lock libéré, pas d'orphelin
- Test `pipeline.lock` présent → comportement défini (point Errors)
- Test idempotence : re-run `sort` / `process` = no-op via `bdd_diff_ignoring`
- Assertions events via `assert_events_emitted` (matrix v2.1)

**Estimated tests/cmd** : 8-10 (1-2 par section), soit ~60 tests pour les 7 cmds pipeline.

**Module size** : si fichier > 800 LOC (warn) → splitter par section
(`test_<cmd>_e2e.py` smoke/realistic/idempotence + `test_<cmd>_errors_e2e.py` +
`test_<cmd>_events_e2e.py`).

**Commit** : `test(tech-debt): pipeline commands E2E coverage — 7 cmds (9.2)`

---

### 9.3 Library mutators restants (3 cmds)

**Sites** : `tests/commands/test_library_<cmd>_e2e.py` pour les 3 cmds.

**Commandes** : `library-rescrape`, `library-backfill-ids`, `library-clean`

**Approche** :

- Pattern identique aux 11 harnesses existants
- Mock TMDB/TVDB pour `library-rescrape`, `library-backfill-ids` (mocks 9.1)
- Test FK enforcement post-ACC-02 (PRAGMA `foreign_keys=ON`)
- Section Closure-of-loop OBLIGATOIRE pour `library-rescrape` (cycle scrape →
  external_ids_json → canonical_provider)
- Sections Errors + Output + Events OBLIGATOIRES (gap détecté sur les 11 existants
  → traité en 9.7 harmonisation)

**Estimated tests/cmd** : 7-9, soit ~25 tests pour les 3 cmds.

**Commit** : `test(tech-debt): library mutators E2E coverage — rescrape + backfill-ids + clean (9.3)`

---

### 9.4 Library diagnostic restants (4 cmds)

**Sites** : `tests/commands/test_library_<cmd>_e2e.py` pour les 4 cmds.

**Commandes** : `library-validate`, `library-analyze`, `library-recommend`, `library-report`

**Approche** :

- Pattern identique
- **Golden files JSON** : pour chaque cmd qui produit un rapport,
  `tests/commands/golden/<cmd>_<scenario>.json` — détecte les drifts de format
- BDD seedée avec ghosts, orphans, FK breakages, missing files → assertions sur
  diagnostic produit (chaque issue type doit être détecté)
- Section Output OBLIGATOIRE avec validation schéma JSON

**Anti-mocking rule** : ne PAS mocker le module testé (interdit
`@patch("personalscraper.commands.library.analyze.run_analyze")` dans `test_library_analyze_e2e.py`).

**Estimated tests/cmd** : 6-8, soit ~28 tests pour les 4 cmds.

**Commit** : `test(tech-debt): library diagnostic E2E coverage + golden files — validate, analyze, recommend, report (9.4)`

---

### 9.5 Trailers + Config mutators (4 cmds)

**Sites** :

- `tests/commands/test_trailers_download_e2e.py`
- `tests/commands/test_trailers_cleanup_e2e.py`
- `tests/commands/test_init_config_e2e.py` (étend l'existant `test_init_config.py`
  s'il existe pour cmd-level, sinon nouveau fichier)
- `tests/commands/test_config_migrate_category_e2e.py`

**Approche** :

- Pattern identique aux 11 harnesses library
- Mock yt-dlp pour `trailers download` (subprocess + network) — helper 9.1
- Test `init-config` sur dir vide / dir existant non-vide / dir non-writable
- Test `config migrate-category` reverse-engineering des renames (BDD + FS sync)
- Test placement Plex-conformant trailers (movies flat vs TV `Trailers/` subfolder)
  → exploite invariants DEV #42, #43

**Estimated tests/cmd** : 6-8, soit ~28 tests pour les 4 cmds.

**Commit** : `test(tech-debt): trailers + config E2E coverage (9.5)`

---

### 9.6 Non-critiques restants (6 cmds)

**Sites** : `tests/commands/test_<cmd>_e2e.py` pour les 6 cmds.

**Commandes** : `library-search`, `library-show`, `torrents-list`, `trailers list`,
`trailers verify` (alias `audit`), `info`

**Approche** :

- Sections réduites : **4 obligatoires** (Smoke / Realistic / Errors / Output)
- Pas de Closure-of-loop, pas de Mutations (N/A par construction)
- Pas d'Events sauf si la cmd émet (`info` émet `cli.invoke.info` post-ACC-18 → tester)

**Estimated tests/cmd** : 4-5, soit ~28 tests pour les 6 cmds.

**Commit** : `test(tech-debt): non-critical commands E2E coverage (9.6)`

---

### 9.7 Harmonisation 11 existants + matrix + report script + gate finale

**9.7.a — Harmonisation des 11 harnesses existants**

Gap détecté en audit : 11 harnesses shipped n'ont pas tous les 8 sections requises.

Pour chaque harness existant, ajouter les sections manquantes :

- **Errors** : args invalides, config absente, BDD corrompue — souvent manquant
- **Output** : `--format json` schéma stable validé via `assert_json_schema` — souvent partiel
- **Events** : `assert_events_emitted` pour matrix v2.1 — **absent partout**

**Audit pré-harmonisation** : table `tests/commands/` × 8 sections cochées
(✅ / ❌ / N/A) → produit `docs/features/tech-debt/audit/14-cli-harness-sections.md`.

**Commit (par groupe de 3-4 harnesses)** :
`test(tech-debt): harmonize library-{doctor,verify,repair,reconcile} harnesses with Errors+Output+Events sections (9.7.a/1)`
`test(tech-debt): harmonize library-{index,scan,gc,status,init-canonical,ghost-audit} (9.7.a/2)`
`test(tech-debt): harmonize library-relink (post-commit + sections, 9.7.a/3)`

**9.7.b — Matrix doc + report script**

- `docs/features/tech-debt/cli-coverage-matrix.md` (nouveau) — tableau auto-généré :
  - Lignes : 28 critiques + 8 non-critiques = 36 commandes
  - Colonnes : 8 sections critiques (4 pour non-critiques, N/A justifiés)
  - Cellules : ✅ / ❌ / N/A
- `scripts/cli-coverage-report.py` (nouveau) :
  - Parse `tests/commands/test_*_e2e.py` pour extraire les en-têtes
    `# ── N\. (<Theme>) ──` via regex
  - Détecte `# ── N. Smoke`, `Realistic`, `Errors`, `Idempotence`, `Dry-run`,
    `Output`, `Events`, `Closure-of-loop`, `Mutations` (alias accepté)
  - Agrège par commande × section
  - Génère le tableau Markdown
  - Mode `--check` : exit 1 si ≥ 1 ❌ sur critiques (hors N/A justifiés en footnote
    `cli-coverage-matrix.md`), exit 0 sinon
  - Mode `--write` : régénère `cli-coverage-matrix.md` (idempotent)
- `Makefile` : ajouter cible `make cli-coverage-check`

**9.7.c — Mises à jour IMPL/INDEX/ACC + gate**

- `IMPLEMENTATION.md` Phase 9 marquée [x] avec SHA gate
- `plan/INDEX.md` : Phase 9 [ ] → [x]
- `ACCEPTANCE.md` ACC-50..54 verts (modifier statut 🟡 → ✅)

**Commit gate** : `chore(tech-debt): phase 9 gate — CLI test coverage (ACC-50..54 ✅)`

## ACCEPTANCE (nouveaux critères)

### ACC-50 — CLI coverage report check 🟡

```bash
python3 scripts/cli-coverage-report.py --check
# Expected: exit 0 (0 ❌ sur critiques, N/A explicites OK pour Closure-of-loop / Dry-run
# / Mutations sur cmds read-only — listés en footnote cli-coverage-matrix.md)
```

### ACC-51 — Section count threshold 🟡

```bash
# Compter les sections couvertes vs attendues
python3 scripts/cli-coverage-report.py --metrics 2>&1
# Expected: ≥ 28 cmds critiques × 6 sections moyennes (les 8 - 2 N/A typiques) = 168 sections OK
# + ≥ 8 cmds non-critiques × 4 sections = 32 sections OK
# Total: ≥ 200 sections actives sur l'ensemble des harnesses.
```

### ACC-52 — Coverage matrix doc committed and synced 🟡

```bash
python3 scripts/cli-coverage-report.py --write
git diff --exit-code docs/features/tech-debt/cli-coverage-matrix.md
# Expected: exit 0 (matrix doc à jour vs dernière exécution des tests)
```

### ACC-53 — Each critical command has Closure-of-loop OR explicit N/A 🟡

```bash
python3 scripts/cli-coverage-report.py --section "Closure-of-loop" --filter critical
# Expected: zero ❌ (chaque cmd critique a soit la section, soit un N/A justifié
# en footnote cli-coverage-matrix.md avec raison — ex: query-only diagnostic)
```

### ACC-54 — Each critical command has Events section verified against matrix v2.1 🟡

```bash
python3 scripts/cli-coverage-report.py --section "Events" --filter critical
# Expected: zero ❌. Section Events doit faire au moins 1 assertion
# assert_events_emitted contre la matrix v2.1 source de vérité.
```

## Risques & garde-fous

1. **Désync avec l'agent d'implémentation parallèle** : risque que l'agent continue à
   ajouter des harnesses pendant 9.x. Mitigation : `9.7.a` audit table source de
   vérité au moment du gate ; ré-audit à chaque sub-phase. Communication : annoter
   `IMPLEMENTATION.md` "Phase 9 active — harnesses E2E centralisés ici".

2. **Module size hard-block** (DEV #46 / Phase 8.11) : harnesses pipeline peuvent
   dépasser 800 LOC (matrice 8 sections × ~10 tests). Mitigation : splitter par
   section au-delà de 600 LOC (`test_<cmd>_e2e.py` + `test_<cmd>_errors_e2e.py` +
   `test_<cmd>_events_e2e.py`).

3. **Temps d'exécution `make test`** : ~150 nouveaux tests E2E (estimés 9.2-9.6) +
   ~70 existants = ~220 tests dans `tests/commands/`. Chaque test crée une BDD
   synthétique + FS tmp → 1-2 s/test = 4-7 min sur ces tests seuls. Mitigation :
   marker `@pytest.mark.e2e_command`, opt-in via `pytest -m e2e_command`, parallélisation
   via `pytest-xdist` si déjà installé.

4. **Drift matrix v2.1 ↔ tests Events** : matrix v2.1 évolue post-Phase 7.
   Mitigation : `assert_events_emitted` lit la matrix comme source de vérité (pas de
   liste hard-codée) — réutilise mécanisme `pipeline-event-monitor` agent.

5. **Faux positifs sur tests d'idempotence** : `updated_at` et `last_seen` changent
   sur re-run. Mitigation : helper `bdd_diff_ignoring(cols=[...])` documenté.

6. **Effort sous-estimé** : 1.5-2 j basé sur ~17 cmds critiques + 6 non-critiques + harmonisation.
   Si harmonisation 9.7.a déborde (11 harnesses × 3 sections manquantes en moyenne =
   33 ajouts), peut prendre 1 j à elle seule. Mitigation : prioriser Events
   (gap le plus critique), accepter Errors+Output en best-effort si dérive.

## Garde-fous mandatoires (anti-pattern checks)

- Chaque sub-phase commence par `make test` (baseline) et finit par `make test`
  (no regression sur autres tests)
- Chaque test mutateur DOIT vérifier BDD post-état (pattern observé dans les 11 harnesses)
- Aucun mock du module testé lui-même (interdit
  `@patch("personalscraper.commands.X.Y")` dans le test de la cmd `X-Y`)
- Pattern strict : `# ── N. <Theme> ──` en en-tête de section, regex parseable
- Régression tests obligatoires en 9.3 : DEV #9, #14, BD-D, DEV #53
  (déjà couverts par les 11 harnesses existants pour BD-D)

## Dépendances

**Amont** :

- Phase 8 mergée (surface CLI stabilisée)
- Phase 8.11 module-size hard-block : Phase 9 doit respecter le seuil 1000 LOC
- 11 harnesses library shippés (b9cb39c..7564153) — Phase 9 capitalise dessus
- `library-relink` harness untracked → soit l'agent commit avant 9.1, soit 9.7.a l'absorbe

**Aval** :

- Phase 10 (archive-docs) : pas de dépendance code
- PR gate ACC-final-\* : ACC-50..54 ajoutés au gate final

## Sub-phase checklist (gate)

- [ ] 9.1 infrastructure extension (pipeline mocks + events + JSON schema + pin test) commit + PASS
- [ ] 9.2 pipeline E2E (7 cmds) commit + PASS
- [ ] 9.3 library mutators restants (3 cmds) commit + PASS
- [ ] 9.4 library diagnostic restants (4 cmds) + golden files commit + PASS
- [ ] 9.5 trailers + config (4 cmds) commit + PASS
- [ ] 9.6 non-critiques restants (6 cmds) commit + PASS
- [ ] 9.7.a harmonisation 11 existants (Errors + Output + Events sections)
- [ ] 9.7.b matrix doc + report script + Makefile cible
- [ ] 9.7.c IMPL/INDEX/ACC mis à jour + gate commit
- [ ] `make check` vert
- [ ] `python3 scripts/cli-coverage-report.py --check` exit 0
- [ ] Effort réel logged dans IMPLEMENTATION.md (vs estimate 1.5-2 j)
