# Phase 4 — Drift Validator Hardening

## Goal

Renforcer `verify_tvshow_scrape_drift` (`existing_validator.py:94`) check #4 (l. 184-186) pour exiger au moins un `<uniqueid>` non-vide **de la famille canonique** sur chaque sibling NFO épisode. Aujourd'hui le check ne valide que l'existence du fichier — c'est ce qui permet à `scrape_fast_skip` de se perpétuer sur des NFOs incomplets.

## Gate (prerequisites)

- Phase 2 mergée (les nouveaux scrapes écrivent désormais les uniqueid correctement, donc le drift renforcé ne va pas tout refaire à chaque run).
- Phase 3 mergée (IMDb/RT façades disponibles pour les xref re-validation futures).

## Sub-phases

### 4.1 — Test RED : drift rejette NFO sans canonical uniqueid

Écrire le test qui prouve que le drift validator devrait rejeter un sibling NFO sans `<uniqueid>` :

- `test_verify_drift_rejects_episode_nfo_without_canonical_uniqueid` (RED — fail avant fix)
- `test_verify_drift_accepts_episode_nfo_with_canonical_uniqueid_only` (xref absent OK)
- `test_verify_drift_accepts_episode_nfo_with_full_uniqueids`
- `test_verify_drift_rejects_episode_nfo_with_wrong_family_uniqueid` (ex: TMDB seul sur show TVDB-canonical)

Commit : `test(provider-ids): regression tests for drift check #4 canonical uniqueid required`

### 4.2 — Lire la famille canonique depuis `tvshow.nfo`

Helper interne : `_read_canonical_provider(tvshow_nfo_path) -> Literal["tvdb", "tmdb"]`. Parse le `tvshow.nfo`, retourne le `type` du `<uniqueid default="true">`.

Commit : `feat(provider-ids): add canonical provider reader for tvshow.nfo`

### 4.3 — Étendre le check #4

`personalscraper/scraper/existing_validator.py:184-186` : remplacer la vérification "sibling NFO existe" par "sibling NFO existe ET porte au moins un `<uniqueid type=canonical_family>` non vide". Retourner `(False, "episode_nfo_missing_canonical_uniqueid")` si violation.

Commit : `fix(provider-ids): drift check #4 requires canonical uniqueid on episode NFOs`

### 4.4 — Test d'intégration drift → re-scrape sur NFOs sans uniqueid

Test automatisé qui simule le scénario des 6 shows :

- Créer un `tvshow.nfo` avec `<uniqueid type="tvdb" default="true">12345</uniqueid>` (canonical=tvdb).
- Créer un episode NFO sibling **sans** aucun `<uniqueid>`.
- Appeler `verify_tvshow_scrape_drift` → doit retourner `(False, "episode_nfo_missing_canonical_uniqueid")`.
- Vérifier que le scrape flow appelle bien le re-scrape (pas de fast-skip) quand le drift check #4 fail.

Test : `test_drift_triggers_rescrape_when_episode_nfo_lacks_canonical_uniqueid` (integration, RED avant fix 4.3, GREEN après).

Commit : `test(provider-ids): drift check #4 triggers rescrape on missing canonical uniqueid`

## Tests to write

(voir 4.1 — tests RED, et :)

- `test_read_canonical_provider_returns_tvdb_when_default_tvdb`
- `test_read_canonical_provider_returns_tmdb_when_default_tmdb`
- `test_read_canonical_provider_raises_when_no_default`
- `test_drift_triggers_rescrape_when_canonical_uniqueid_missing` (integration)

## Acceptance criteria

- Test 4.1 (RED) passe en GREEN après fix 4.3.
- Le drift validator catch les NFOs sans uniqueid canonique → trigger re-scrape (test 4.4 automatisé).
- Les NFOs FROM (2022) avec uniqueid tvdb + imdb continuent de pass.
- Le test `test_drift_triggers_rescrape_when_episode_nfo_lacks_canonical_uniqueid` échoue en RED avant le fix 4.3, puis passe en GREEN après.

## Migration / config touch

Aucune (validation read-only).

## DESIGN reference

§1 (Root cause layer 5 drift validator, post-api-unify), §6.3 (`existing_validator.py` avec lignes à jour), §5 (idempotence — drift trigger re-scrape).
