# Phase 11 — Aggregated DeepSeek 5-angle review fixes

**Effort** : 2-3 jours (revised post-review 2026-05-24)
**Theme** : 18 findings retenus issus d'une review parallèle 5 agents DeepSeek sur PR #24 :
durability fsync, stats counter ordering, AppleDouble filter generalization, test
discipline (`pytest.raises(Exception)`), regex generalization, module decomposition,
polish (dead code + weak mocks + flaky time).

**Source** : agrégat 5 reviewers DeepSeek v4 Pro (angles Correctness, Error handling,
Concurrency/TOCTOU, Tests, Architecture). Sidecars sauvegardés
`/tmp/pr24-review-out-{1..5}.txt` (transient).

## Coverage matrix

| Sub-phase | Findings origine                                                                   | DESIGN §          | ACC ref               |
| --------- | ---------------------------------------------------------------------------------- | ----------------- | --------------------- |
| 11.1      | M1 (A3-F1), S1 (A3-F2), S2 (A3-F3)                                                 | §11 architecture  | ACC-REV-DURABILITY    |
| 11.2      | M2 (A2-F1), M3 (A2-F2)                                                             | §13 promise/stats | ACC-REV-STATS         |
| 11.3      | M4 (A3-F4 + A5-F2 fusionnés)                                                       | §11 architecture  | ACC-REV-APPLEDOUBLE   |
| 11.4      | M5 (A4-F1)                                                                         | §14 testing       | ACC-REV-PYTEST-RAISES |
| 11.5      | S3 (A1-F1), N1 (A1-F2), N2 (A1-F4), N3 (A2-F3)                                     | §11 + §13         | ACC-REV-REGEX-MISC    |
| 11.6      | S4 (A5-F1), S5 (A5-F5)                                                             | §11 architecture  | ACC-REV-DECOMPOSITION |
| 11.7      | S6 (A4-F2), N4 (A4-F3), N5 (A4-F4), N6 (A4-F5), N7 (A5-F3), N8 (A5-F4), N9 (A3-F5) | §14 + §11         | ACC-REV-POLISH        |

**Dropped** : A1-F3 (déjà fixé par commit `d6f4b5f`).

DESIGN sections impacted : §11 architecture (atomic writes, AppleDouble extraction,
module size), §13 promise/stats lifecycle (counter ordering), §14 testing convention
(pytest.raises narrowing).

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phases 0-10 commited + gates verts (vérifier `git log --oneline | grep "phase.*gate"`)
- Branch `fix/tech-debt` propre avant chaque sub-phase (`git status --short` vide)
- PR #24 ouverte, base `main`

## Sub-phases

### 11.1 Durability — fsync sur écritures atomiques

**Sites** :

- `personalscraper/io_utils.py` (nouveau helper `atomic_write_text`)
- `personalscraper/api/metadata/_omdb_quota.py:_persist()`
- `personalscraper/scraper/nfo_generator.py:write_nfo()`
- `personalscraper/trailers/state.py:_save()`
- `tests/unit/test_io_utils.py` (test fsync sur `atomic_write_text`)
- `tests/unit/test_omdb_quota.py` (test régression : crash mid-write → state non corrompu)

**Action** :

1. Extraire `atomic_write_text(path: Path, content: str, *, encoding="utf-8") -> None` dans `io_utils.py` (calque sur `atomic_write_json` : `os.open` + `os.write` + `os.fsync(fd)` + `os.replace` + `os.fsync(dir_fd)`).
2. `_omdb_quota._persist()` → `atomic_write_json(self._state_path, dict(self._state))` (déjà JSON, juste appeler le helper existant).
3. `nfo_generator.write_nfo()` → `atomic_write_text(path, xml_content)` (string XML, pas JSON).
4. `trailers/state.py:_save()` → `atomic_write_json(self._state_file, payload)` (JSON dict).

**Tests régression** (memory: 1 test par bug) :

- `test_atomic_write_text_fsyncs_file_and_dir` : monkeypatch `os.fsync` pour compter les appels, attend 2 (fd + dir_fd).
- `test_omdb_quota_persist_uses_atomic_write_json` : patch `atomic_write_json` pour vérifier l'appel.
- `test_nfo_write_uses_atomic_write_text` : patch idem.

**Commits attendus** (3-4) :

1. `feat(tech-debt): atomic_write_text helper in io_utils (11.1)`
2. `fix(tech-debt): OMDB quota _persist uses atomic_write_json — fsync durability (11.1, M1)`
3. `fix(tech-debt): NFO write_nfo uses atomic_write_text — fsync durability (11.1, S1)`
4. `fix(tech-debt): TrailerStateStore._save uses atomic_write_json — fsync durability (11.1, S2)`

**ACC** : ACC-REV-DURABILITY (voir ACCEPTANCE.md).

### 11.2 Observability — stats counters incrémentés APRÈS DB write

**Sites** :

- `personalscraper/indexer/scanner/_modes/backfill_ids.py:919-922` (init_canonical, `stats.populated_default/_fallback`)
- `personalscraper/indexer/scanner/_modes/backfill_ids.py:907,909` (seeding path, `no_default_uniqueid/unsupported_no_fallback`)
- `personalscraper/indexer/scanner/_modes/backfill_ids.py:357-358` (`_backfill_one`, `stats.ids_added_count/_ratings_added_count`)
- `tests/indexer/scanner/test_backfill_ids.py` (tests régression simulant OperationalError mid-pass)

**Action** :

1. Dans `init_canonical_from_nfo` et `_backfill_one`, introduire un flag local `write_succeeded: bool = False`, l'armer après `conn.execute` réussi, puis incrémenter les compteurs sous `if write_succeeded:`.
2. Garder le `dry_run` path qui incrémente comme aujourd'hui (pas de DB write attendu).

**Tests régression** :

- `test_init_canonical_stats_rollback_on_operational_error` : patch `conn.execute` pour lever `OperationalError` sur la N+1ᵉ row, vérifie que `stats.populated_default` reflète exactement les N rows réussies.
- `test_backfill_one_stats_not_inflated_on_db_failure` : idem pour `ids_added_count`.

**Commits attendus** (2-3) :

1. `fix(tech-debt): init_canonical stats counters after DB write — accurate observability on failure (11.2, M2)`
2. `fix(tech-debt): _backfill_one stats counters after UPDATE — accurate observability (11.2, M3)`
3. `test(tech-debt): regression — stats counters reflect actual DB writes on OperationalError (11.2)`

**ACC** : ACC-REV-STATS.

### 11.3 AppleDouble — extraire helper partagé + appliquer aux 11 sites

**Sites prod** (7 inlines `startswith("._")` + 4 globs NFO non-protégés) :

- canonique : `personalscraper/indexer/scanner/_exclusions.py:55` (déjà existant `_should_exclude`)
- inlines à remplacer : `library/disk_cleaner.py:337,559`, `library/analyzer.py:752`, `library/rescraper.py:185,441`, `library/scanner.py:297`, `enforce/file_sanitizer.py:119`, `commands/library/fix_nfo.py:272`
- globs NFO non-protégés : `verify/verifier.py:273` (`_find_nfo`), `enforce/coherence_checker.py:95,120`, `verify/fixer.py:121`, `process/dedup.py:52`

**Sites tests** :

- `tests/verify/test_verifier.py` : régression "AppleDouble shadow first alphabetically"
- `tests/enforce/test_coherence_checker.py` : idem

**Action** :

1. Promouvoir un helper public `is_apple_double(name: str) -> bool` dans `personalscraper/_fs_utils.py` (nouveau module) OU élargir l'API publique de `_exclusions.py` (préférer la 2ᵉ si elle ne crée pas de cycle d'import — vérifier `rg "from .*_exclusions" -g '*.py'`).
2. Refactoriser `glob_nfo_candidates()` dans `nfo_utils.py` pour appeler `is_apple_double`.
3. Remplacer les 7 inlines par `is_apple_double(name)` (les 2 cas dans `disk_cleaner` combinent `_JUNK_FILES` — adapter).
4. Remplacer les 4 globs NFO bruts par `glob_nfo_candidates(dir)` :
   - `verifier._find_nfo()` : `candidates = glob_nfo_candidates(media_dir); return candidates[0] if candidates else None`
   - `coherence_checker._check_*` : `nfos = glob_nfo_candidates(...)`
   - `verify/fixer.py:121` : itérer sur `glob_nfo_candidates(...)`
   - `process/dedup.py:52` : `has_nfo = 1 if glob_nfo_candidates(folder) else 0`

**Tests régression** :

- `test_verifier_find_nfo_skips_apple_double_shadow` : créer dir avec `._Title (2010).nfo` + `Title (2010).nfo`, asserter retour = vrai NFO (sans le `._`).
- `test_coherence_checker_skips_apple_double_in_movie_dir` : idem pour `_check_movie`.

**Commits attendus** (3-4) :

1. `refactor(tech-debt): extract is_apple_double helper, glob_nfo_candidates delegates (11.3)`
2. `refactor(tech-debt): replace 7 inline startswith('._') with is_apple_double (11.3)`
3. `fix(tech-debt): 4 NFO glob callers use glob_nfo_candidates — AppleDouble safety (11.3, M4)`
4. `test(tech-debt): regression — NFO selection skips AppleDouble shadow (11.3)`

**ACC** : ACC-REV-APPLEDOUBLE.

### 11.4 Test discipline — narrow `pytest.raises(Exception)` → spécifique

**Sites** (4 instances confirmées par `rg "pytest\.raises\(Exception\)" tests/`) :

- `tests/unit/test_api_metadata_base.py:90` → `FrozenInstanceError`
- `tests/unit/test_audit_design_coverage.py:377` → `FrozenInstanceError`
- `tests/integration/test_transport_policy.py:87,90` → `ApiError` (circuit-breaker)

**Action** :

1. Importer `FrozenInstanceError` depuis `dataclasses` ou `ApiError` depuis `personalscraper.api._contracts`.
2. Remplacer `pytest.raises(Exception)` par `pytest.raises(<Specific>)` aux 4 sites.
3. Vérifier que les tests passent toujours (`pytest tests/unit/test_api_metadata_base.py tests/unit/test_audit_design_coverage.py tests/integration/test_transport_policy.py -x`).

**Tests régression** : non requis (le narrowing EST le test).

**Commits attendus** (1) :

1. `test(tech-debt): narrow pytest.raises(Exception) to specific types at 4 sites (11.4, M5)`

**ACC** : ACC-REV-PYTEST-RAISES.

### 11.5 Regex generalization + small bug fixes

**Sites** :

- `personalscraper/indexer/repos/item_repo.py:23` : `_CANONICAL_RE` regex
- `personalscraper/commands/library/gc.py:110` : commit redondant en autocommit
- `personalscraper/api/metadata/_omdb_quota.py:_archive_corrupt_state` : log trompeur quand fichier déjà supprimé
- `personalscraper/api/transport/_http.py:_request_outer:L137` : `except Exception` du circuit-breaker compte les bugs internes
- `tests/indexer/repos/test_item_repo.py` : test cas `"Movie  (2020)"`, `"Movie(2020)"`

**Action** :

1. `_CANONICAL_RE = re.compile(r"\s*\(\d{4}\)$")` — accepte 0+ espaces avant `(`.
2. `gc.py:110` : soit envelopper le DELETE dans `BEGIN`/`COMMIT` explicite, soit ajouter commentaire défensif `# autocommit mode: commit() is intentionally a no-op, kept for future-proofing if open_db switches to transactional`.
3. `_archive_corrupt_state` : `if not self._state_path.exists(): log.info("omdb_quota_corrupt_already_removed", path=...); return` AVANT `os.replace`.
4. `_request_outer:L137` : narrow `except Exception` → `except (ApiError, requests.RequestException) as exc:` (les `TypeError`/`AttributeError`/etc. propagent sans incrémenter le circuit-breaker).

**Tests régression** :

- `test_canonical_title_strips_double_space_year` (item_repo).
- `test_canonical_title_strips_no_space_year` (item_repo).
- `test_circuit_breaker_ignores_internal_typeerror` (transport) — patch un client pour lever `TypeError`, vérifie que `circuit.record_failure` n'est PAS appelé.

**Commits attendus** (3) :

1. `fix(tech-debt): _canonical_title regex accepts variable whitespace before (YYYY) (11.5, S3)`
2. `fix(tech-debt): _archive_corrupt_state distinct log when source already removed (11.5, N2)`
3. `fix(tech-debt): circuit-breaker narrows to ApiError/RequestException — ignore internal bugs (11.5, N3)`
   - inclut N1 (`gc.py` commit clarification) si scope tient.

**ACC** : ACC-REV-REGEX-MISC.

### 11.6 Module decomposition — `scan()` 755 lines + `tv_service.py` 998 LOC

**⚠️ DISPATCH** : cette sous-phase route **Opus 1M directement** (pas DeepSeek). Cross-cutting + nouveau module + jugement architectural — réf. `references/scope-sizing.md`.

**Sites** :

- `personalscraper/indexer/scanner/__init__.py:341-1095` (`scan()`, 755 lignes)
- nouveau `personalscraper/indexer/scanner/_scan_orchestrator.py`
- `personalscraper/scraper/tv_service.py` (998 non-blank LOC)
- nouveau `personalscraper/scraper/_tvdb_convert.py`
- tests existants doivent rester verts sans modification

**Action** :

1. **scan() extraction** : déplacer dans `_scan_orchestrator.py` les fonctions privées :
   - `_scan_with_budget(...)` — boucle budget + timing
   - `_scan_disks(...)` — itération disques + dispatch workers
   - `_emit_completed(...)` — émission `LibraryScanCompleted`
   - garder `scan()` dans `__init__.py` comme orchestrateur ~40 lignes qui appelle les 3.
2. **tv_service.py extraction** : déplacer `_tvdb_series_to_show_data()` (~150 lignes) + helpers privés dans `_tvdb_convert.py`. Import : `from personalscraper.scraper._tvdb_convert import _tvdb_series_to_show_data`.
3. Vérifier `python3 scripts/check-module-size.py` post-extraction : aucun module au-dessus de 850 LOC non-blank dans le scope touché.
4. `make test` complet doit passer (aucune signature publique changée).

**Tests régression** : non requis (refactor sans changement de comportement).

**Commits attendus** (4-6) :

1. `refactor(tech-debt): extract _scan_with_budget into _scan_orchestrator (11.6, S4)`
2. `refactor(tech-debt): extract _scan_disks into _scan_orchestrator (11.6, S4)`
3. `refactor(tech-debt): extract _emit_completed into _scan_orchestrator (11.6, S4)`
4. `refactor(tech-debt): scan() reduced to orchestration shell (~40 LOC) (11.6, S4)`
5. `refactor(tech-debt): extract _tvdb_series_to_show_data into _tvdb_convert (11.6, S5)`

**ACC** : ACC-REV-DECOMPOSITION.

### 11.7 Test + code polish

**Sites tests** :

- `tests/test_output_emit.py:78-94, 101-121` : convertir save/restore manuel en `monkeypatch.setitem`.
- `tests/library/test_analyzer.py:735` : `assert mock_extract.called` → `assert_called_once_with(<path>)`.
- `tests/verify/test_verify_item_done_event.py:65-70` : renommer pour clarifier "import-gate" OU grep AST de `emit(VerifyItemDone(`.
- `tests/unit/test_omdb_quota.py:56` : utiliser `freezegun` pour stabiliser l'assertion date.

**Sites prod** :

- `personalscraper/scraper/models.py:31-32` : supprimer bloc `if TYPE_CHECKING: pass`.
- `personalscraper/indexer/scanner/_modes/backfill_ids.py:51,58` : retirer `@runtime_checkable` des Protocols `_RatingClient` / `_DetailsClient`.
- `personalscraper/indexer/scanner/_db_writes.py:130-184` : `_upsert_file_row` → `INSERT ... ON CONFLICT(path_id, filename) DO UPDATE`.

**Action** : faire chaque item indépendamment, commit par site (pas de batch).

**Tests régression** :

- `_upsert_file_row` : test concurrent path_id collision (théorique mais le ON CONFLICT le rend safe-by-design).

**Commits attendus** (3-4) :

1. `test(tech-debt): polish — monkeypatch + assert_called_once_with + freezegun (11.7, S6/N4/N6)`
2. `chore(tech-debt): rm dead TYPE_CHECKING block in scraper/models (11.7, N7)`
3. `refactor(tech-debt): drop unused @runtime_checkable on backfill_ids Protocols (11.7, N8)`
4. `refactor(tech-debt): _upsert_file_row uses ON CONFLICT DO UPDATE (11.7, N9)`

**ACC** : ACC-REV-POLISH.

## Phase gate

Avant le commit gate `chore(tech-debt): phase 11 gate — review fixes` :

1. `make lint` (ruff + mypy) — zéro erreur.
2. `make test` — tous tests verts (vérifier le summary `NNNN passed, 0 failed, 0 errors`).
3. `make check` (lint + test + module-size + typed-api).
4. `python3 scripts/check-module-size.py` — aucun module au-dessus de 1000 LOC dans le scope touché.
5. `rg "pytest\.raises\(Exception\)" tests/ --type py` — zéro match (sweep complet).
6. `rg 'startswith\("\._"\)' personalscraper/ --type py | wc -l` — ≤ 1 (seulement dans `_fs_utils.py` ou `_exclusions.py`).
7. Toutes ACCEPTANCE ACC-REV-\* validées (commande + sortie attendue).
8. `git log --oneline | head -25` montre les ~20 commits attendus de la phase.

**Commit gate** : `chore(tech-debt): phase 11 gate — review fixes (18 findings)`
