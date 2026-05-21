# Phase 9 — Verify Checker Extensions

## Goal

Ajouter 3 nouveaux checks TV à `verify/checker.py` : `episode_canonical_uniqueid_present` (ERROR), `episode_xref_secondary_id_present` (WARNING), `episode_xref_imdb_id_present` (WARNING). Bloque le dispatch si canonique manquant, warning si xref incomplet.

## Gate (prerequisites)

- Phase 4 mergée (drift validator renforcé reconnaît les NFOs incomplets).
- Phase 7 mergée (DB schema permet de lire canonical_provider).

## Sub-phases

### 9.1 — Check `episode_canonical_uniqueid_present` (ERROR)

Pour chaque show TV à verify, lit `canonical_provider` depuis la DB ou le `tvshow.nfo`. Pour chaque episode NFO sibling, vérifie présence d'un `<uniqueid type=canonical_family>` non-vide. Si absent sur ≥1 épisode → ERROR bloquant dispatch.

Commit : `feat(provider-ids): verify check episode_canonical_uniqueid_present`

### 9.2 — Check `episode_xref_secondary_id_present` (WARNING)

Pour les shows scrapés (TVDB-canonical ou TMDB-fallback), vérifie que l'autre famille (xref) est présente sur les épisodes. Si manquant → WARNING non bloquant. Suggère un re-run avec `--backfill-ids`.

Commit : `feat(provider-ids): verify check episode_xref_secondary_id_present`

### 9.3 — Check `episode_xref_imdb_id_present` (WARNING)

Vérifie présence de `<uniqueid type="imdb">` sur les épisodes. WARNING si manquant — IMDb est utile pour le tracker search futur.

Commit : `feat(provider-ids): verify check episode_xref_imdb_id_present`

### 9.4 — Update verify output + counts

`checker.py` aggregate : `checks_total` augmente de 3 sur TV (15 → 18). Update les tests d'intégration et le verify output format si besoin.

Commit : `refactor(provider-ids): verify TV checks_total bumped to 18`

## Tests to write

- `test_check_episode_canonical_uniqueid_present_error_when_missing_on_any_episode`
- `test_check_episode_canonical_uniqueid_present_pass_when_all_have_canonical`
- `test_check_episode_canonical_uniqueid_present_pass_when_no_episodes_yet`
- `test_check_episode_xref_secondary_id_present_warning_when_tmdb_missing_on_tvdb_canonical`
- `test_check_episode_xref_secondary_id_present_pass_when_both_present`
- `test_check_episode_xref_imdb_id_present_warning_when_missing`
- `test_verify_total_checks_for_tv_is_18`
- `test_verify_blocked_when_canonical_uniqueid_missing` (integration)
- `test_verify_warning_only_when_xref_missing` (integration — dispatch ready malgré warning)

## Acceptance criteria

- TV show avec NFOs épisode sans canonical uniqueid → `verify status=blocked` (bloque dispatch).
- TV show avec canonical OK mais xref TMDB manquant → `verify status=valid warnings=['Missing xref tmdb on episode S01E03']` (dispatch passe).
- `verify_item_done` log inclut les 3 nouveaux checks dans `checks_passed` / `errors` / `warnings`.

## Migration / config touch

Aucune (additif, pas de breaking change verify pour les NFOs déjà valides).

## DESIGN reference

§6.4 (verify/), §5 (error handling table).
