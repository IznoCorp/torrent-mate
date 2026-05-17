# Phase 4 — Drift Validator Hardening

## Goal

Renforcer `verify_tvshow_scrape_drift` check #4 pour exiger au moins un `<uniqueid>` non-vide **de la famille canonique** sur chaque sibling NFO épisode. Aujourd'hui le check ne valide que l'existence du fichier — c'est ce qui permet à `scrape_fast_skip` de se perpétuer sur des NFOs incomplets.

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

### 4.4 — Re-runner pipeline-monitor sur les 6 shows existants

**Validation manuelle** : sur les 6 shows en staging (Dexter, AmDad, Top Chef, Stranger Things '85, LOL, The Boys), le drift renforcé doit déclencher un re-scrape au prochain `personalscraper process`. Documenter le résultat dans `docs/pipeline-runs/`.

Commit : aucun (validation manuelle uniquement, capturée dans le test E2E phase 15).

## Tests to write

(voir 4.1 — tests RED, et :)

- `test_read_canonical_provider_returns_tvdb_when_default_tvdb`
- `test_read_canonical_provider_returns_tmdb_when_default_tmdb`
- `test_read_canonical_provider_raises_when_no_default`
- `test_drift_triggers_rescrape_when_canonical_uniqueid_missing` (integration)

## Acceptance criteria

- Test 4.1 (RED) passe en GREEN après fix 4.3.
- Le drift validator catch les NFOs sans uniqueid canonique → trigger re-scrape.
- Les NFOs FROM (2022) avec uniqueid tvdb + imdb continuent de pass.
- Les 6 shows actuellement avec NFOs sans uniqueid sont marqués pour re-scrape (validation manuelle 4.4).

## Migration / config touch

Aucune (validation read-only).

## DESIGN reference

§1 (Root cause layer 5 drift validator), §6.3 (existing_validator.py), §5 (idempotence — drift trigger re-scrape).
