# Phase 12 — Pipeline-Monitor Findings Fixes

**Run source** : `docs/pipeline-runs/2026-05-25-09h57-pipeline-run.md`
**Trigger** : opérateur a stoppé le pipeline au gate DISPATCH (zero-tolerance rule 11) suite à 12 deviations détectées. Décision : tout fixer avant de relancer.
**Effort** : 2-3 j séquentiel.
**Branch** : `fix/tech-debt` (continue).

## Hiérarchie

- **P0 critique** (1) : ACCEPTANCE_FAIL — provider-ids canonical_provider corruption (209 shows + 142 movies sans canonical_provider).
- **P1 majeur** (4) : Top Chef LCP rescrape sans rename, ENFORCE silent (×2), .env.example manquant.
- **P2 mineur** (6) : CLI lifecycle inconsistency (×2), media_file orphans, season_count_drift, item_issue persistence, BDD stale entries.
- **NON REPRODUCTIBLE** (1) : VERIFY blocked non persisté → invalidé (dispatch ré-exécute verify).

## Méthodologie

- Chaque sous-phase = 1 commit minimum + tests de régression obligatoires (`feedback_regression_test_per_bug` memory rule).
- `make check` vert avant chaque commit.
- Aucun bypass via CLI workaround (rule 12 pipeline-monitor skill).
- Re-run `/pipeline-monitor` post-Phase 12 pour confirmer que toutes les deviations passent à `TRAITÉ` ou disparaissent du run suivant.

---

## 12.1 — DEVIATION #7 (P0 critique, ACCEPTANCE_FAIL provider-ids #4)

**Scope** : 209 items `kind='show'` ont `canonical_provider='tmdb'` au lieu de `'tvdb'`. 142 items `kind='movie'` ont `canonical_provider IS NULL`. Tous ont POURTANT les bons IDs dans `external_ids_json`.

**Cause racine probable** : drift d'insertion antérieur à v0.15.0 OU bug d'écriture du scraper qui assigne mal `canonical_provider`. À auditer.

**Tâches** :

1. Audit SQL : récupérer la liste exacte des 209 shows + 142 movies avec timestamps `media_item.created_at` (si disponible) ou `updated_at`.
2. Identifier le code-path qui écrit `canonical_provider`. Vérifier que pour `kind='show'`, on écrit toujours `'tvdb'` quand `external_ids_json.tvdb.series_id` existe.
3. Écrire une migration SQL idempotente :

   ```sql
   UPDATE media_item SET canonical_provider='tvdb'
   WHERE kind='show' AND canonical_provider='tmdb'
     AND json_extract(external_ids_json, '$.tvdb.series_id') IS NOT NULL;

   UPDATE media_item SET canonical_provider='tmdb'
   WHERE kind='movie' AND canonical_provider IS NULL
     AND json_extract(external_ids_json, '$.tmdb.id') IS NOT NULL;
   ```

4. Wrapper la migration dans un CLI sous-commande `personalscraper library-fix-canonical-provider [--dry-run]`.
5. **Test de régression** :
   - `tests/integration/test_canonical_provider_repair.py` : seed la BDD avec 5 shows `canonical_provider='tmdb'` + 3 movies `NULL` (tous avec external_ids_json valides), lancer le repair, asserter 100% corrigés.
   - `tests/integration/test_canonical_provider_invariant.py` : pour chaque item scrapé via TV path, asserter `canonical_provider='tvdb'`. Pour chaque item scrapé via Movie path, asserter `canonical_provider='tmdb'`.

**ACCEPTANCE** :

```bash
# Compte de violations doit être 0 après repair
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE kind='show' AND canonical_provider='tmdb';"
# Expected: 0
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE kind='movie' AND canonical_provider IS NULL;"
# Expected: 0
```

**Commits** :

- `fix(provider-ids): canonical_provider repair for 209 shows + 142 movies (ACC #4)`
- `test(provider-ids): regression for canonical_provider invariant`

**SHA** : `<pending>`

---

## 12.2 — DEVIATION #10 (P1 majeur, .env.example missing keys)

**Scope** : 3 env keys utilisées via `os.environ.get()` mais absentes de `.env.example` :

- `OMDB_API_KEY`
- `OMDB_DAILY_LIMIT`
- `LIBRARY_ANALYZER_MAX_WORKERS`

**Tâches** :

1. `rg "os.environ" --type py personalscraper/ | rg "OMDB_API_KEY|OMDB_DAILY_LIMIT|LIBRARY_ANALYZER_MAX_WORKERS"` pour confirmer les sites d'usage.
2. Ajouter les 3 keys dans `.env.example` avec doc inline + valeurs par défaut commentées.
3. **Test de régression** : `tests/test_env_example_completeness.py` (ou wire dans test existant) qui parse `.env.example` et grep le code source pour chaque `os.environ.get(...)` afin de garantir que toutes les keys sont documentées.

**ACCEPTANCE** :

```bash
# Toutes les keys utilisées dans le code DOIVENT être dans .env.example
python3 scripts/check_env_keys.py
# Expected: exit 0, message "0 missing keys"
```

**Commits** :

- `docs(env): add OMDB + LIBRARY_ANALYZER keys to .env.example`
- `test(env): regression for env_example completeness`

**SHA** : `<pending>`

---

## 12.3 — DEVIATION #2 (P1 majeur, SCRAPE rescrape sans rename)

**Scope** : Top Chef Le Concours Parallèle (2026) — `show_rescrape_drift reason=episode_naming_drift:Top.Chef.Le.Concours.Parallele.S17E10.FRENCH.1080p.WEB.H264-laRoulade.mkv` fired. Show matched (TVDB id 475278, confidence 1.0). tvshow.nfo réécrit. Mais aucun `show_season_fetched`, aucun `episode_renamed`. Le fichier S17E10 reste avec son nom raw.

**Cause racine probable** : la branche rescrape dans `personalscraper/scraper/tv_service.py` shortcircuit après tvshow.nfo write quand `artwork_exists_skip` est True, sans atteindre l'episode-rename phase.

**Tâches** :

1. Lire `personalscraper/scraper/tv_service.py` autour de la logique rescrape_drift.
2. Identifier le branchement conditionnel qui skip l'episode-rename quand artwork existe.
3. Fixer : un rescrape déclenché par `episode_naming_drift` DOIT toujours fetch les seasons et passer par l'episode-rename phase, indépendamment de l'état artwork.
4. **Test de régression** :
   - `tests/scraper/test_tv_service_rescrape_drift.py::test_rescrape_drift_episode_naming_renames_episode`
   - Seed un show avec : tvshow.nfo valide, artwork présent, Saison 17/ avec un .mkv en raw release name. Mock TVDB pour retourner les épisodes. Lancer process. Asserter que `episode_renamed` est émis et le fichier renommé en `S17E10 - <Title>.mkv`.

**ACCEPTANCE** :

```bash
# Pas d'épisodes en raw release name dans staging post-process
find "/Volumes/IznoServer SSD/A TRIER/002-TVSHOWS" -type f \( -name "*.1080p*" -o -name "*.WEB*" -o -name "*MULTi*" \) | grep -v "trailer" | wc -l
# Expected: 0
```

**Commits** :

- `fix(scraper): rescrape_drift always triggers episode-rename phase`
- `test(scraper): regression for tv_service rescrape_drift episode rename`

**SHA** : `<pending>`

---

## 12.4 — DEVIATION #3+#4 (P1 majeur, ENFORCE silent)

**Scope** : ENFORCE émet 0 structlog INFO events sur stdout. Aucun `ItemProgressed(step="enforce", ...)` event-bus emit. Pre-classifié par matrix v2.1 line 281 : "Wiring event-bus manquant côté enforce".

**Tâches** :

1. Lire `personalscraper/enforce/run.py` (ou équivalent — voir architecture).
2. Comparer avec PROCESS / VERIFY / INGEST qui émettent structlog + ItemProgressed.
3. Ajouter les events manquants selon matrix v2.1 §ENFORCE :
   - `enforce_start`
   - `enforce_sanitize_filename`
   - `enforce_structure_ok` / `enforce_structure_fix`
   - `enforce_coherence_ok`
   - `enforce.orphan_episode_moved`
   - `enforce_sanitize_action`
   - `enforce_complete`
4. Câbler `ItemProgressed(step="enforce", ...)` via le EventBus pour chaque item.
5. **Test de régression** :
   - `tests/enforce/test_enforce_events.py::test_enforce_emits_structlog_events`
   - `tests/enforce/test_enforce_events.py::test_enforce_emits_item_progressed_events`
   - Vérifier qu'un run enforce sur 3 items produit les events attendus dans l'ordre.

**ACCEPTANCE** :

```bash
# Lancer enforce et compter les events structured
personalscraper enforce --dry-run 2>&1 | grep -E "enforce_start|enforce_structure_ok|enforce_complete" | wc -l
# Expected: >=2 (start + complete minimum)
```

**Commits** :

- `feat(enforce): emit structlog events + ItemProgressed for monitoring`
- `test(enforce): regression for enforce event emission`

**SHA** : `<pending>`

---

## 12.5 — DEVIATION #1+#6 (P2 mineur, CLI lifecycle bracketing)

**Scope** : `personalscraper sort` et `personalscraper verify` n'émettent pas `cli.invoke.<cmd>` / `cli.complete.<cmd>` events alors que `personalscraper ingest` les émet.

**Tâches** :

1. Identifier le décorateur / fonction wrapper qui émet `cli.invoke.*` pour ingest.
2. Appliquer la même logique aux entry points `sort`, `verify`, et auditer les autres subcommands (process, enforce, dispatch, trailers, ...).
3. **Test de régression** : `tests/cli/test_cli_lifecycle_events.py` itère sur toutes les subcommands et vérifie que chacune émet `cli.invoke.<cmd>` au début et `cli.complete.<cmd> exit_code=<int>` à la fin.

**ACCEPTANCE** :

```bash
# Chaque subcommand DOIT émettre cli.invoke + cli.complete
for cmd in ingest sort process enforce verify dispatch; do
  count=$(personalscraper "$cmd" --dry-run 2>&1 | grep -cE "cli\.(invoke|complete)\.${cmd}")
  echo "$cmd: $count (expected 2)"
done
```

**Commits** :

- `fix(cli): emit cli.invoke/cli.complete for all subcommands`
- `test(cli): regression for CLI lifecycle event bracketing`

**SHA** : `<pending>`

---

## 12.6 — DEVIATION #11 (P2 mineur, item_issue persistence)

**Scope** : `episode_naming_drift` détecté par SCRAPE n'est PAS persisté dans `item_issue` rows. Conséquence : Top Chef LCP id=28 a 9 épisodes en BDD sans trace du drift. Pas d'audit trail historique.

**Tâches** :

1. Identifier le site d'émission de `show_rescrape_drift` dans tv_service.py.
2. Ajouter une écriture dans `item_issue` avec `issue_type='episode_naming_drift'`, `details_json={...}`, `detected_at=NOW`.
3. Vérifier que les drifts résolus (post-rename) sont marqués `resolved_at=NOW` (lifecycle des item_issue rows).
4. **Test de régression** : `tests/integration/test_item_issue_drift_persistence.py` simule un drift, vérifie l'insertion en BDD, puis le mark-resolved post-fix.

**ACCEPTANCE** :

```bash
# Top Chef LCP doit avoir un item_issue après le run process s'il y a un drift
sqlite3 .data/library.db "SELECT COUNT(*) FROM item_issue WHERE issue_type='episode_naming_drift';"
# Expected: >0 si drift détecté
```

**Commits** :

- `feat(indexer): persist episode_naming_drift in item_issue`
- `test(indexer): regression for item_issue drift persistence`

**SHA** : `<pending>`

---

## 12.7 — DEVIATION #8 (P2 mineur, media_file orphans)

**Scope** : 102 `media_file` rows sans `release_id` (invariant AO violé). Probable artifact d'ingest/dispatch incomplet ou DB recovery.

**Tâches** :

1. SQL audit : identifier les 102 rows + leur contexte (path, filename, item_id, ts).
2. Pour chaque ligne sans release_id : tenter de retrouver le release parent par path ou par item_id.
3. CLI `personalscraper library-fix-orphan-files [--dry-run]` qui répare ou archive les rows.
4. **Test de régression** : seed BDD avec 5 media_file orphan rows, lancer fix, asserter 100% rattachés ou archivés.

**ACCEPTANCE** :

```bash
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_file WHERE release_id IS NULL;"
# Expected: 0 après fix
```

**Commits** :

- `fix(indexer): repair media_file orphan rows (invariant AO)`
- `test(indexer): regression for media_file orphan repair`

**SHA** : `<pending>`

---

## 12.8 — DEVIATION #9 (P2 mineur, season_count_drift)

**Scope** : 3 `season.episode_count` ≠ actual count : item IDs 2163#1 (12→13), 3655#5 (0→16), 3656#6 (0→16). Invariant AP violé.

**Tâches** :

1. SQL : recompter les episodes pour chaque season concernée.
2. UPDATE `season.episode_count` selon le compte réel.
3. Ajouter un trigger SQL ou hook applicatif qui maintient `episode_count` cohérent à chaque INSERT/DELETE sur `media_file` ou `episode`.
4. **Test de régression** : seed 1 season avec drift, lancer repair, asserter `episode_count` corrigé. Insérer un nouvel épisode, asserter `episode_count` incrémenté.

**ACCEPTANCE** :

```bash
# Tous les seasons doivent avoir episode_count cohérent
personalscraper library-reconcile --read-only 2>&1 | grep "season_count_drift" | grep "0"
# Expected: ligne avec count=0
```

**Commits** :

- `fix(indexer): repair season episode_count drift (invariant AP)`
- `test(indexer): regression for season episode_count coherence`

**SHA** : `<pending>`

---

## 12.9 — DEVIATION #12 (P2 mineur, BDD stale entries)

**Scope** : Mikado (id=518) en BDD avec `nfo_status='valid'`, `canonical_provider='tmdb'`, `external_ids_json` populated. Mais le run actuel produit `movie_no_tmdb_results` pour Mikado. Désynchronisation BDD ↔ état staging.

**Tâches** :

1. Vérifier si l'entrée Mikado id=518 vient d'une scrape antérieure réussie (probable, scraped 2026-05-24) qui a depuis été "perdue" sur staging puis re-ingest.
2. Implémenter une logique : si un item en staging produit `movie_no_confident_match` mais a une entry BDD avec `nfo_status='valid'`, restaurer l'NFO + artwork depuis la BDD plutôt que de marquer unmatched.
3. **Test de régression** : seed BDD avec un item complet, supprimer NFO+artwork du staging, relancer process, asserter que les fichiers sont restaurés depuis BDD.

**ACCEPTANCE** :

```bash
# Si BDD a une entry valid pour un item, scrape ne doit pas marquer unmatched
sqlite3 .data/library.db "SELECT nfo_status FROM media_item WHERE title='Mikado';"
# Expected: valid (et le NFO doit être restauré sur staging)
```

**Commits** :

- `feat(scraper): restore NFO from BDD when item in staging matches a valid BDD entry`
- `test(scraper): regression for BDD-backed NFO restore`

**SHA** : `<pending>`

---

## Phase gate

Tous les sub-phases DONE + `make check` vert + post-Phase 12 re-run `/pipeline-monitor` qui DOIT montrer :

- 0 entrée critique
- 0 entrée majeure ouverte
- Top Chef LCP S17E10 dispatché correctement
- 209 shows `canonical_provider='tvdb'` (0 violation provider-ids ACC #4)

**Phase gate commit** : `chore(tech-debt): phase 12 gate — pipeline-monitor fixes (12 deviations)`
