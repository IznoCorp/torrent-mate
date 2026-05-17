# Phase 10 — Consommateurs library / conf / trailers refactor

## Goal

Adapter tous les modules qui lisaient les anciennes colonnes `tvdb_id` / `tmdb_id` / `imdb_id` pour qu'ils consomment `external_ids_json` via Pydantic models ou `json_extract`. Supprime `OverrideRule.imdb_id` (pre-1.0 → pas de retro-compat). Adapte trailers.

## Gate (prerequisites)

- Phase 7 mergée (DB schema migré).
- Tests existants des modules consommateurs doivent passer en pré-refactor (baseline).

## Sub-phases

### 10.1 — `library/recommender.py` refactor

`personalscraper/library/recommender.py:44,63,67,158,241,267,283` : `ids: Tuple[tmdb_id, imdb_id]` lit via `external_ids_json` (Pydantic model `ExternalIds`). Match logic adaptée.

Commit : `refactor(provider-ids): library/recommender reads via external_ids_json`

### 10.2 — `library/scanner.py` refactor

Adapter les writes — déjà partiellement fait en phase 7.5, finaliser tous les call sites.

Commit : `refactor(provider-ids): library/scanner writes via external_ids_json + ratings_json`

### 10.3 — Supprimer `OverrideRule.imdb_id` + migrer config réelle

`personalscraper/conf/models/preferences.py:76-95` : supprime le champ `imdb_id: str | None`. Adapte tous les usages (`indexer/query.py:113,302,557` qui exposait `imdb_id` comme FieldSpec).

**Migration config réelle** (memory `feedback_no_backcompat_before_v1`) : adapte `config/api.json5` réel de cette instance dans le même commit. Si des `OverrideRule` y existaient avec `imdb_id`, les convertir en entries `external_ids_json` directement dans la DB (one-shot script) ou en supprimant simplement (si non utilisés).

Commit : `refactor(provider-ids): remove OverrideRule.imdb_id (pre-1.0 no retro-compat)`

### 10.4 — `trailers/scanner.py` + `trailers/orchestrator.py` refactor

`trailers/scanner.py.extract_nfo_ids` : lit `<uniqueid type="imdb">` (déjà compatible, peut-être pas de change).
`trailers/orchestrator.py:737-777` : `db_item.imdb_id` devient property `@property def imdb_id(self): return json_extract(self.external_ids_json, '$.imdb.series_id')`.

Commit : `refactor(provider-ids): trailers reads imdb_id via external_ids_json`

### 10.5 — Update `config.example/`

`config.example/api.json5` (ou équivalent qui contient `OverrideRule`) : exemple sans `imdb_id`, avec note expliquant que les overrides passent par `external_ids_json` directement.

Commit : `docs(provider-ids): config.example api.json5 without OverrideRule.imdb_id`

## Tests to write

- `test_recommender_matches_via_external_ids_json` (regression — fonctionnalité préservée)
- `test_recommender_ranks_by_imdb_id_from_external_ids_json`
- `test_scanner_writes_external_ids_and_ratings_json_for_movie`
- `test_scanner_writes_external_ids_and_ratings_json_for_tv`
- `test_override_rule_no_longer_has_imdb_id_field` (regression — ne doit plus exister)
- `test_config_loader_rejects_old_override_rule_with_imdb_id` (validation pre-1.0)
- `test_trailers_orchestrator_resolves_imdb_id_via_external_ids_json`
- `test_trailers_scanner_extract_nfo_ids_unchanged` (regression — pas de bug introduit)

## Acceptance criteria

- `grep -r "tmdb_id\|imdb_id\|tvdb_id" personalscraper/ --type py` ne montre plus de SELECT/WHERE colonne directe — tout passe par `external_ids_json`.
- `OverrideRule.imdb_id` n'existe plus.
- Trailers scanner fonctionne sur la library actuelle.
- Config réelle de l'instance migrée.

## Migration / config touch

**OBLIGATOIRE** :

- `config/api.json5` réel : supprime les `OverrideRule.imdb_id` (si présents).
- `.data/library.db` réelle : pas de change additionnel (déjà fait en phase 7).

## DESIGN reference

§6.6 (consommateurs), §2 (scope élargi), §3 décision Q3 + memory `feedback_no_backcompat_before_v1`.
