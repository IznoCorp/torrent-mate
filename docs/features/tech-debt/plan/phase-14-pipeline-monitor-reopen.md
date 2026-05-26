# Phase 14 — Pipeline-Monitor Reopen (re-run 2026-05-25 23h49 findings)

**Run source** : `docs/pipeline-runs/2026-05-25-23h49-pipeline-run.md` (re-run après merge de Phase 12).
**Trigger** : opérateur a stoppé le pipeline au gate DISPATCH (zero-tolerance rule 11) sur 2 runs consécutifs. Le re-run prouve que :

- **DEV #4 critique persiste** malgré Phase 12.1 (provider-ids canonical_provider). 167 items inversés (vs 351 au run initial). La fix initiale a traité une partie des cas mais pas la régression à la source.
- **DEV #7 mineur persiste** malgré Phase 12.7 (media_file orphans, 102 inchangés).
- **5 nouveaux findings** non couverts par Phase 12 (disk residue, repair_queue schema, release_orphans, agents prompt fixes, matrix v2.2).
- **3 findings de Phase 12 confirmés résolus** (12.4 ENFORCE silent, 12.5 CLI lifecycle, 12.9 Mikado BDD restore) — pas re-couverts ici.
- **2 findings à re-vérifier** (12.2 .env.example, 12.8 season_count_drift) — non rapportés au re-run, possible résolution silencieuse.

**Effort** : 2-3 j séquentiel.
**Branch** : `fix/tech-debt` (continue).

**Phase 12 reste DONE (attestation historique intacte)** — Phase 14 est une réouverture chirurgicale des sub-phases défaillantes + ajout des nouvelles.

## Hiérarchie

- **P0 critique** (1) : 14.1 ACCEPTANCE_FAIL provider-ids #4 persistant (167 items, régression à la source non corrigée par Phase 12.1).
- **P1 majeur** (1) : 14.3 SCRAPE rescrape requalification (peut-être DESIGN_CONFORM via Unmatched Episode Policy — à investiguer avant fix).
- **P1 verify** (2) : 14.2 .env.example, 14.5 season_count_drift — re-tester pour confirmer résolution silencieuse.
- **P2 mineur** (7) : 14.4 media_file orphans persistants, 14.6 disk residue, 14.7 repair_queue schema, 14.8 release_orphans, 14.9 agents prompt fixes, 14.10 matrix v2.2 enrichment, 14.11 CI cleanup (display literal + matrix Python 3.12-only).

## Méthodologie

- Chaque sous-phase = 1 commit minimum + tests de régression obligatoires (`feedback_regression_test_per_bug` memory rule).
- `make check` vert avant chaque commit.
- Aucun bypass via CLI workaround (rule 12 pipeline-monitor skill).
- Backup BDD préalable obligatoire avant toute migration SQL (`cp .data/library.db .data/library.db.bak-phase13-$(date +%Y%m%d-%H%M%S)`).
- **Le re-run report `2026-05-25-23h49-pipeline-run.md` doit être commité dans la première sub-phase qui le référence** (convention repo pour les pipeline-runs).
- Re-run `/pipeline-monitor` post-Phase 14 pour confirmer DEVIATION LIST vide.

---

## 14.1 — Provider-IDs #4 PERSISTANT (P0 critique, reopen 12.1)

**Scope** : 167 items avec `canonical_provider` inversé au re-run 23h49 (vs 351 au run initial 09h57). Phase 12.1 (commit `7a010ee` + `1009285`) a livré une migration + regression test mais la régression persiste : nouveaux items insérés post-Phase 12 réintroduisent le bug. La fix initiale était curative (UPDATE one-shot) sans bloquer la source.

**Différence avec 12.1** :

- Couvrir la **nouvelle classe** observée au re-run : movies avec `canonical_provider='tvdb'` (inversé). 12.1 ne traitait que `kind='show' AND canonical_provider='tmdb'` + `kind='movie' AND canonical_provider IS NULL`.
- **Bloquer la régression à la source** : audit du code-path d'insertion / update qui réintroduit l'inversion.

**Tâches** :

1. Audit du delta : pourquoi 167 items présentent encore le bug malgré la migration de 12.1 ? Lister leur `created_at`/`updated_at` :
   - S'ils sont post-12.1 → bug d'insertion non corrigé (source).
   - S'ils sont pré-12.1 et n'ont pas matché les conditions de l'UPDATE → la condition WHERE de 12.1 était incomplète.
2. Identifier le code-path source. Candidats : `personalscraper/library/index_writer.py`, `personalscraper/scraper/orchestrator.py`, `personalscraper/scraper/movie_service.py`, `personalscraper/scraper/tv_service.py`. Greper toutes les assignations à `canonical_provider`.
3. Patcher le code-path : pour `kind='show'`, toujours écrire `'tvdb'` quand un `tvdb_id`/`external_ids_json.tvdb.series_id` est disponible. Pour `kind='movie'`, toujours `'tmdb'`. Refuser silencieusement les autres valeurs (logging warning + canonical_provider=NULL pour signaler).
4. Élargir la CLI `personalscraper library-fix-canonical-provider` (ou créer `library-fix-canonical-provider --aggressive`) pour couvrir la nouvelle classe (movies inversés vers tvdb).
5. Backup BDD + ré-exécuter la migration.
6. **Test de régression complémentaire** :
   - `test_canonical_provider_movie_inverted_tvdb_repaired` : seed avec movie `canonical_provider='tvdb'` + tmdb_id valide → repair → assert `canonical_provider='tmdb'`.
   - `test_canonical_provider_insertion_path_normalizes` : insère un media_item via le code-path normal (orchestrator path) avec des IDs mixtes → assert canonical_provider correct sans intervention manuelle. **Ce test doit fail sur le code AVANT la fix source.**

**ACCEPTANCE** :

```bash
sqlite3 /Users/izno/dev/PersonnalScaper/.data/library.db "
SELECT
  SUM(CASE WHEN kind='show' AND canonical_provider='tmdb'
            AND json_extract(external_ids_json, '\$.tvdb.series_id') IS NOT NULL THEN 1 ELSE 0 END) AS tv_inverted,
  SUM(CASE WHEN kind='movie' AND canonical_provider='tvdb'
            AND json_extract(external_ids_json, '\$.tmdb.id') IS NOT NULL THEN 1 ELSE 0 END) AS mv_inverted,
  SUM(CASE WHEN kind='movie' AND canonical_provider IS NULL
            AND json_extract(external_ids_json, '\$.tmdb.id') IS NOT NULL THEN 1 ELSE 0 END) AS mv_null
FROM media_item
WHERE external_ids_json IS NOT NULL AND external_ids_json != '{}';
"
# Expected: tv_inverted=0, mv_inverted=0, mv_null=0
# Note (plan correction, Phase 14.1) : the original ACCEPTANCE criterion
# (``kind='show' AND canonical_provider != 'tvdb' → 0``) was too strict —
# it flagged the legitimate "tmdb-only show" class (15 shows that have a
# valid tmdb_id but no tvdb_id, for which ``canonical_provider='tmdb'``
# is the correct deterministic value per ``_normalize_canonical_provider``
# and matches the ``test_invariant_tmdb_only_show_excluded`` Phase 12.1
# invariant test). The refined criterion above only counts genuine
# inversions, mirroring the WHERE clauses of the three repair SQL statements.

pytest tests/ -k "canonical_provider" -v
# Expected: all pass, including the new insertion-path normalization tests
```

**Commits** :

- `fix(library): block canonical_provider regression at insertion source (reopen 12.1)`
- `fix(provider-ids): aggressive canonical_provider repair (167 items, movies inversés)`
- `test(provider-ids): insertion-path normalization regression test`

**SHA** : `<pending>`

---

## 14.2 — .env.example verify (12.2 status check)

**Scope** : Phase 12.2 (commit `a2e3287` + `5986025`) a ajouté `OMDB_API_KEY`, `OMDB_DAILY_LIMIT`, `LIBRARY_ANALYZER_MAX_WORKERS` dans `.env.example` + script `check_env_keys.py`. Le re-run 23h49 ne rapporte pas ce finding → présomption de résolution.

**Tâches** :

1. Lancer le script de check :
   ```bash
   python3 scripts/check_env_keys.py
   ```
2. Si exit 0 + "0 missing keys" → marquer 14.2 DONE sans nouveau commit (référencer SHA de 12.2).
3. Si nouveaux keys manquants détectés → patch `.env.example` + commit.

**ACCEPTANCE** :

```bash
python3 scripts/check_env_keys.py
# Expected: exit 0, "0 missing keys"
```

**Commits** : `<aucun si vérification verte>` ou `docs(env): add <new key> to .env.example` selon issue.

**SHA** : `<pending>` ou référence 12.2.

---

## 14.3 — SCRAPE rescrape requalification (12.3 reopen)

**Scope** : Phase 12.3 (commits `4ae69c9` + `a33a516`) a livré "rescrape_drift episode_naming sweep + 3 parametric tests". Le re-run 23h49 montre que Top Chef Le Concours Parallèle (TVDB id 475278) est toujours en `status=blocked` au VERIFY avec `episode_unmatched_no_rename` pour S17E10 — MAIS le pipeline-monitor a classifié ça en **DESIGN_CONFORM** (Unmatched Episode Policy : TVDB n'a pas la S17 dans son catalogue, donc l'épisode reste en place sans rename).

**Question à trancher** :

- **Option A — DESIGN_CONFORM légitime** : la policy fonctionne comme prévu. Top Chef LCP S17 n'est juste pas encore sur TVDB. Le bug initial de 12.3 (rescrape sans rename quand artwork existe) a été fixé. Le `episode_unmatched_no_rename` actuel est un cas DIFFÉRENT (provider ne connaît pas la saison). → 14.3 marqué DONE, pas de nouveau commit.
- **Option B — La policy elle-même est trop conservatrice** : il faudrait peut-être permettre `allow_synthetic_rename_on_unmatched=True` par défaut, ou tenter un fallback TMDB quand TVDB est vide pour la saison. → 14.3 ouvert avec scope précis.

**Tâches** :

1. Investigation : lancer un test SCRAPE manuel sur Top Chef LCP. Confirmer que la branche rescrape_drift est exécutée (commit 12.3 effectif) ET que c'est bien `episode_unmatched_no_rename` qui kick in à cause de `show_season_empty season=17`.
2. Vérifier dans la matrix v2.1 §PROCESS:scrape que ce comportement est documenté DESIGN_CONFORM.
3. Si Option A confirmée → marquer DONE, ajouter une note dans la matrix si pas déjà présente.
4. Si Option B retenue → écrire fix + test. À discuter avec opérateur avant code.

**ACCEPTANCE** :

```bash
# Vérifier que la branche rescrape produit bien les events attendus
personalscraper process --dry-run 2>&1 | grep -E "show_rescrape_drift|nfo_would_write" | head -5
# Expected: rescrape_drift fired + nfo_would_write (commit 12.3 effective)

# Si Option A : pas d'ACC sur le rename, juste la documentation
grep -E "episode_unmatched_no_rename.*DESIGN_CONFORM|show_season_empty" /Users/izno/dev/PersonnalScaper/.claude/skills/pipeline-monitor/references/design-conformity-matrix.md
# Expected: >= 1 match (DESIGN_CONFORM documenté)
```

**Commits** : `<aucun>` si Option A, sinon `fix(scraper): <approach>` + `test(scraper): regression`.

**SHA** : `<pending>` ou DONE.

---

## 14.4 — media_file orphans PERSISTANT (P2 mineur, reopen 12.7)

**Scope** : Phase 12.7 (commits `008f4d1` + `6735275`) a livré "media_file orphan repair CLI + 5 tests". Le re-run 23h49 rapporte toujours **102 media_file sans release_id** (invariant AO inchangé). Phase 12.7 a fourni l'outillage mais n'a pas été exécutée OU le bug se ré-introduit.

**Plan correction (Phase 14.4, in-commit)** : la formulation initiale "block media_file
INSERT without release_id" était incorrecte. Le schéma autorise déjà
`release_id IS NULL` (migration 002) — l'INSERT n'est pas la source. L'investigation
montre que les 102 orphans proviennent de la **CASCADE FK** : la table
`media_file.release_id` était définie en `ON DELETE SET NULL`. Quand un
`media_release` parent est supprimé (suite à un dispatch écrasant un ancien
release, ou un cleanup de library), les `media_file` enfants se retrouvent avec
`release_id=NULL` sans aucun moyen de re-lier (le parent n'existe plus). La CLI
`library-fix-orphan-files` rapporte `items_scanned=102, fixed=0, no_release=102`
— elle ne peut pas réparer puisque le parent est manquant.

**Fix correct** :

1. **Migration 009** (`personalscraper/indexer/migrations/009_media_file_cascade_release.sql`) :
   recrée `media_file` avec FK `release_id → media_release(id) ON DELETE CASCADE`.
   Idempotent au niveau du version-gate (skip si `PRAGMA user_version >= 9`).
   Les orphans existants (NULL) sont préservés verbatim — la migration ne nettoie
   pas les données, juste le schéma.

2. **CLI extension** (`personalscraper/commands/library/fix_orphan_files.py`) : ajout
   du flag `--purge-unrecoverable`. Quand combiné avec `--apply`, supprime les
   `media_file` qui restent en `release_id IS NULL` après la passe de repair.
   Dry-run par défaut (rapporte `would_purge`).

3. **Cleanup BDD prod** : backup mandatoire puis
   `personalscraper library-fix-orphan-files --apply --purge-unrecoverable`
   contre `.data/library.db`. Run de la migration au prochain `open_db` (auto).

4. **Test de régression** (`tests/integration/test_release_cascade.py`) :
   - `test_media_file_release_fk_is_cascade_after_migration` : `PRAGMA foreign_key_list`
     montre `on_delete = CASCADE` post-migration.
   - `test_deleting_release_cascades_to_media_file` : seed media_item + release + file,
     DELETE le release → assert le file row est supprimé (cascade), pas laissé NULL.
   - `test_purge_unrecoverable_dry_run_reports_only` : `--purge-unrecoverable` sans
     `--apply` rapporte `would_purge` mais ne supprime rien.
   - `test_purge_unrecoverable_apply_deletes_orphans` : `--purge-unrecoverable --apply`
     supprime tous les rows avec `release_id IS NULL`.

**ACCEPTANCE** :

```bash
# Schéma : CASCADE en place
sqlite3 /Users/izno/dev/PersonnalScaper/.data/library.db ".schema media_file" | grep -i "ON DELETE CASCADE"
# Expected: 1 match (FK on release_id)

# Cleanup : 0 orphan restant
sqlite3 /Users/izno/dev/PersonnalScaper/.data/library.db "SELECT COUNT(*) FROM media_file WHERE release_id IS NULL"
# Expected: 0

# Tests de régression passent
pytest tests/integration/test_release_cascade.py -v
# Expected: 4 passed
```

**Safety** : `cp .data/library.db .data/library.db.bak-phase14.4-$(date +%Y%m%d-%H%M%S)`
avant le purge. La migration elle-même prend son propre snapshot
`library.db.pre-migration-9.bak` via `apply_migrations`.

**Commits** :

- `fix(tech-debt): CASCADE media_file on release delete + purge unrecoverable orphans (reopen 12.7)`
- `chore(tech-debt): apply media_file cascade migration + purge 102 unrecoverable orphans`

**SHA** : `<pending>`

---

## 14.5 — season_count_drift verify (12.8 status check)

**Scope** : Phase 12.8 (commits `c3e5f76` + `057e1a7`) a livré "season episode_count repair CLI + 5 tests". Le re-run 23h49 montre `library-reconcile season_count_drift=0` → présomption de résolution.

**Tâches** :

1. Lancer `personalscraper library-reconcile --read-only`.
2. Si `season_count_drift=0` confirmé → 14.5 DONE, référence 12.8.
3. Si > 0 → ré-exécuter la CLI repair + investigation source.

**ACCEPTANCE** :

```bash
personalscraper library-reconcile --read-only 2>&1 | grep "season_count_drift"
# Expected: season_count_drift_count=0 (ou season_count_drift=[])
```

**Commits** : `<aucun si verify verte>` ou `fix(library): season episode_count regression`.

**SHA** : `<pending>` ou référence 12.8.

---

## 14.6 — Disk residue cleanup (P2 mineur, NEW — invariants AG + AJ)

**Scope** : `pipeline-invariant-checker` (PHASE 3 du re-run) rapporte :

- **AG** : 4093 NFO sans vidéo parente sur les 4 disques (legacy ou stale).
- **AJ** : 28+ `.actors/` directories résiduels sur tous les disques.

Pollution disque, sans impact fonctionnel. Cleanup prudent : un NFO sans vidéo PEUT être légitime.

**Tâches** :

1. Script `scripts/audit/list_nfo_orphans.py` : inventorie tous les `.nfo` sans `.mkv`/`.mp4`/`.avi`/`.mov` voisin. Sortie CSV avec `path, type, has_siblings, suggested_action`.
2. Whitelist `tvshow.nfo` au niveau show (jamais delete même si toutes saisons vides).
3. Cleanup script `scripts/cleanup/remove_nfo_orphans.py --csv ... [--dry-run]` : action=delete uniquement pour entrées certaines, dry-run obligatoire avant action réelle.
4. Cleanup `.actors/` : `find ... -type d -name ".actors"` + confirm contenu = images uniquement → `rm -rf` après dry-run.
5. Pas de test de régression nécessaire (scripts FS-only, idempotents). Sample manual review en revue (10 paths random).

**ACCEPTANCE** :

```bash
find /Volumes/Disk1/medias /Volumes/Disk2/medias /Volumes/Disk3/medias /Volumes/Disk4/medias -type d -name ".actors" 2>/dev/null | wc -l
# Expected: 0

python3 scripts/audit/list_nfo_orphans.py | wc -l
# Expected: << 4093 (résidu = whitelist intentionnelle)
```

**Commits** :

- `chore(cleanup): NFO orphan audit + selective removal (invariant AG)`
- `chore(cleanup): .actors/ residue removal across disks (invariant AJ)`

**SHA** : `<pending>`

---

## 14.7 — repair_queue schema fix (P2 mineur, NEW — invariant AR)

**Scope** : `pipeline-bdd-validator` rapporte schema drift : `repair_queue` n'a pas de colonne `created_at`. Invariant AR.

**Tâches** :

1. Suivre la convention de migration existante (`personalscraper/library/migrations/NNN_*.sql` ou équivalent — vérifier).
2. `ALTER TABLE repair_queue ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`.
3. Backfill : `UPDATE repair_queue SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL`.
4. Idempotent : `PRAGMA table_info(repair_queue)` check avant ALTER.
5. **Test de régression** : `tests/integration/library/test_migrations.py` ajoute case vérifiant présence de `created_at` après migration.

**ACCEPTANCE** :

```bash
sqlite3 /Users/izno/dev/PersonnalScaper/.data/library.db ".schema repair_queue" | grep -c "created_at"
# Expected: 1
```

**Commits** :

- `fix(library): add repair_queue.created_at column (invariant AR)`
- `test(library): regression for repair_queue schema invariant`

**SHA** : `<pending>`

---

## 14.8 — release_orphans cleanup (P2 mineur, NEW)

**Scope** : `library-reconcile --read-only` du re-run rapporte 172 `release_orphans` (releases sans `media_item` parent). Signal nouveau, non couvert par les invariants AD-AV.

**Tâches** :

1. SQL audit : `SELECT id, media_item_id, release_kind, created_at FROM media_release WHERE media_item_id NOT IN (SELECT id FROM media_item)`. Identifier l'origine.
2. Vérifier le cascade FK media_release → media_item. Si pas de `ON DELETE CASCADE`, c'est la cause.
3. Script `scripts/migrations/cleanup_release_orphans.py` :
   - DELETE chaque `media_release` sans `media_item` parent.
   - Idempotent. Logs structlog.
4. Si root cause = FK manquante → migration pour wirer `ON DELETE CASCADE`.
5. **Test de régression** : `tests/integration/library/test_release_orphans.py` — insérer item+release, supprimer item, asserter release supprimé (cascade) OU détecté par `library-reconcile`.

**ACCEPTANCE** :

```bash
personalscraper library-reconcile --read-only 2>&1 | grep "release_orphans_count"
# Expected: release_orphans_count=0
```

**Commits** :

- `fix(library): cleanup release_orphans + wire ON DELETE CASCADE`
- `test(library): regression for media_release cascade integrity`

**SHA** : `<pending>`

---

## 14.9 — Pipeline-monitor agents prompt fixes (P2 mineur, NEW — tooling)

**Scope** : 2 agents du skill pipeline-monitor produisent des findings faux :

- `pipeline-state-validator` : faux positif "100% phantom ratio" en post-ENFORCE — interprète mal `ingested_torrents.json` (structure : `{hash: {name, action, date}}`, pas de `dest_path`).
- `pipeline-invariant-checker` : faux négatif sur invariant **AT** (rapport `SKIP "qBit unreachable"` alors que qBit était reachable).

**Tâches** :

1. Édit `.claude/agents/pipeline-state-validator.md` : section explicite documentant la structure de `ingested_torrents.json` (hash-keyed, pas de path filesystem), interdire le phantom-flag sur name mismatch.
2. Édit `.claude/agents/pipeline-invariant-checker.md` : pour AT, exiger `personalscraper torrents-list` (pas curl direct), distinguer exit_code=0 (OK) vs exit_code=2 (OPERATIONAL), retry simple (1×) avant conclusion SKIP.
3. Pas de test de régression direct (prompts MD). Validation par re-run pipeline-monitor en phase gate.

**ACCEPTANCE** :

```bash
grep -E "ingested_torrents\.json.*(hash|name|action|date)" /Users/izno/dev/PersonnalScaper/.claude/agents/pipeline-state-validator.md
# Expected: >= 1 match

grep -E "qbit|qBit|torrents-list" /Users/izno/dev/PersonnalScaper/.claude/agents/pipeline-invariant-checker.md | grep -E "AT|connectivity|reachable"
# Expected: >= 1 match
```

**Commits** :

- `docs(agents): clarify ingested_torrents.json structure in pipeline-state-validator`
- `docs(agents): robust qBit check for invariant AT in pipeline-invariant-checker`

**SHA** : `<pending>`

---

## 14.10 — Matrix v2.2 enrichment (P2 mineur, NEW — doc)

**Scope** : 2 events / patterns non documentés dans matrix v2.1 :

- `item_issue_persist_skipped_no_item` émis (commit 0916232) mais absent de §PROCESS:scrape.
- VERIFY `checks_total` par type non documenté (12 movies / 18 TV shows ; Mikado 11/12 ; TV shows 17/18 systémique).

**Tâches** :

1. Édit `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md` :
   - §PROCESS:scrape : add row `item_issue_persist_skipped_no_item` (DESIGN_CONFORM, "skip silent quand item DB absent pré-match").
   - §VERIFY : documenter `checks_total=12` films + `=18` TV shows, lister les checks par type (source : `personalscraper/verifier/*`).
   - Note explicite : Mikado 11/12 = film sans `-landscape.jpg`, DESIGN_CONFORM (status `valid`).
2. Bump matrix : `**Matrix version**: 2.1` → `2.2`.
3. Édit `.claude/skills/pipeline-monitor/SKILL.md` : `MATRIX_VERSION = "2.1"` → `"2.2"` + frontmatter `matrix_version: "2.2"`.
4. Édit `.claude/skills/pipeline-monitor/CHANGELOG.md` : entrée v2.2 référençant re-run 2026-05-25-23h49.
5. **Atomique** : matrix bump + skill bump dans le **même commit** (sinon assertion casse).
6. Pas de test de régression direct (doc). Validation au re-run en phase gate.

**ACCEPTANCE** :

```bash
head -5 /Users/izno/dev/PersonnalScaper/.claude/skills/pipeline-monitor/references/design-conformity-matrix.md | grep "Matrix version"
# Expected: **Matrix version**: 2.2

grep -E "MATRIX_VERSION\s*=\s*" /Users/izno/dev/PersonnalScaper/.claude/skills/pipeline-monitor/SKILL.md
# Expected: MATRIX_VERSION = "2.2"

grep -c "item_issue_persist_skipped_no_item" /Users/izno/dev/PersonnalScaper/.claude/skills/pipeline-monitor/references/design-conformity-matrix.md
# Expected: >= 1

grep -E "(checks_total.*12|checks_total.*18)" /Users/izno/dev/PersonnalScaper/.claude/skills/pipeline-monitor/references/design-conformity-matrix.md | wc -l
# Expected: >= 2
```

**Commits** :

- `docs(pipeline-monitor): matrix v2.2 — item_issue_persist + VERIFY checks_total (atomic)`

**SHA** : `<pending>`

---

## 14.11 — CI cleanup (P2 mineur, NEW — infra)

**Scope** : 2 problèmes CI identifiés hors-pipeline-monitor :

1. **Display literal** : la check GitHub affiche `CI / test (${{ matrix.python-version }})${{ ((matrix.experimental && ' [experimental]') || '') }} (pull_request)` au lieu d'un nom interpolé. Cause : le template `name:` à `.github/workflows/ci.yml:84` utilise une expression `&&`/`||` ternaire mixée avec interpolation `${{ }}`. GitHub stocke le nom littéral pour les required status checks quand l'expression matrix n'est pas évaluable côté branch-protection (et quand l'évaluation produit la string-templated avec parenthèses).

2. **Matrix sur-dimensionnée** : la CI teste 3.10, 3.11, 3.12 (non-experimental) + 3.13 (experimental). User souhaite simplifier à **3.12 uniquement** pour économiser CI.

**Cible** : un seul job `test` sur Python 3.12, sans matrix, nom statique.

**Tâches** :

1. Éditer `.github/workflows/ci.yml` job `test` :
   - Supprimer `strategy.matrix`, `experimental`, `continue-on-error`, `include`.
   - `name: test` (statique, sans interpolation).
   - `python-version: "3.12"` en dur.
   - Conserver le step `codecov` : retirer la condition `if: matrix.python-version == '3.12'` (toujours vrai maintenant). Garder `fail_ci_if_error: ${{ github.event.pull_request.head.repo.fork == false }}`.
   - Cache key : remplacer `${{ matrix.python-version }}` par `3.12`.
2. Éditer `pyproject.toml` :
   - `requires-python = ">=3.10"` → `requires-python = ">=3.12"`.
   - Retirer les classifiers `Python :: 3.10`, `:: 3.11`, `:: 3.13` (garder `:: 3` et `:: 3.12`).
3. Éditer `README.md` : "Python 3.10+" → "Python 3.12+".
4. Aligner les autres jobs (`lint`, `typecheck`, `security`, `licenses`) — actuellement sur 3.13 :
   - **Décision** : aligner sur 3.12 (cohérence avec la version testée, évite le risque de lint-on-3.13 / test-on-3.12).
   - Modifier les 4 jobs : `python-version: "3.13"` → `"3.12"`, idem cache keys.
5. `coverage-monotonic` et `design-gaps` sont déjà sur 3.12 — laisser tel quel.
6. Vérifier la syntaxe YAML : `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`.
7. **Branch protection rules** : noter dans le commit message + IMPLEMENTATION.md que les required status checks GitHub côté repo settings devront être mis à jour manuellement post-merge (ancien nom interpolé / 4 entries matrix → nouveau nom unique `test`).

**Hors scope** :

- Reformulation du workflow (split jobs, change runner, etc.).
- Ajout d'un job sur 3.13 préliminaire (futur work).
- Touches au workflow `gitleaks-full.yml` ou `dependabot.yml`.

**Test de régression** : pas applicable (config YAML). Validation par CI green sur la PR de Phase 14 + check GitHub UI montre le nom propre `test`.

**ACCEPTANCE** :

```bash
# Job name statique, pas de template literal
grep -E "^\s+name:\s+test\s*$" /Users/izno/dev/PersonnalScaper/.github/workflows/ci.yml
# Expected: 1 match (sans ${{ }})

# Pas de matrix python-version
grep -E "python-version:\s+\[" /Users/izno/dev/PersonnalScaper/.github/workflows/ci.yml
# Expected: 0 match

# pyproject demande 3.12+
grep "requires-python" /Users/izno/dev/PersonnalScaper/pyproject.toml
# Expected: requires-python = ">=3.12"

# Classifiers : 3.10/3.11/3.13 absents
grep -E "Python :: 3\.(10|11|13)" /Users/izno/dev/PersonnalScaper/pyproject.toml | wc -l
# Expected: 0

# YAML syntaxe valide
python3 -c "import yaml; yaml.safe_load(open('/Users/izno/dev/PersonnalScaper/.github/workflows/ci.yml'))"
# Expected: no exception

# README à jour
grep -E "Python 3\.(10|11|13)\+" /Users/izno/dev/PersonnalScaper/README.md | wc -l
# Expected: 0
```

**Post-merge action (manuelle, opérateur)** : GitHub repo Settings → Branches → branch protection rule sur `main` → mettre à jour les "Required status checks" pour pointer sur le nouveau nom `test` unique (supprimer les anciennes entries matrix si présentes).

**Commits** :

- `ci: simplify test matrix to Python 3.12 only + static job name`
- `chore(ci): align lint/typecheck/security/licenses jobs to Python 3.12`
- `docs: bump requires-python to 3.12+ in pyproject + README`

**SHA** : `<pending>`

---

## Phase 14 gate

Tous les sub-phases DONE + `make check` vert + post-Phase 14 re-run `/pipeline-monitor` qui DOIT montrer :

- 0 entrée critique (provider-ids #4 résolu à la source)
- 0 entrée majeure ouverte
- 0 entrée mineure À TRAITER (toutes TRAITÉ, CONNU explicite, ou NON REPRODUCTIBLE)
- Invariants AG/AJ/AO/AR/AT tous PASS
- library-reconcile : `release_orphans_count=0`, `files_without_release=0`
- Matrix v2.2 assertion validée en GATE -1
- Re-run report committé dans `docs/pipeline-runs/`
- CI green sur la PR avec nom de check `test` statique (pas de template literal)

**Phase gate commit** : `chore(tech-debt): phase 14 gate — pipeline-monitor reopen (11 sub-phases, re-run 23h49)`
