# Phase 3 — Façades IMDb + RottenTomatoes sur OMDbAdapter

## Goal

Introduire les façades métier `IMDbClient` et `RottenTomatoesClient` qui consomment l'`OMDbAdapter` existant en backend. Le scraper ne touche plus OMDb directement — il parle IMDb et RT (sémantique métier). Respecte la séparation api/scraper et permet un swap futur du backend OMDb sans toucher au scraper.

## Gate (prerequisites)

- Phase 1 mergée (capabilities `RatingProvider`, `IDValidator`, `IDCrossRef` disponibles).
- Phase 2 mergée (fix DEV #2 OK).

## Sub-phases

### 3.1 — `OMDbAdapter` refactor (existant → internal-only)

`personalscraper/api/metadata/omdb.py` : extraire ou renommer la classe en `OMDbAdapter` pour souligner son rôle de backend HTTP partagé. Aucune fonctionnalité supprimée — juste le scope d'usage clarifié.

Commit : `refactor(provider-ids): mark OMDbAdapter as internal HTTP backend`

### 3.2 — `IMDbClient` façade

Nouveau `personalscraper/api/metadata/imdb.py`. Classe `IMDbClient` qui compose `IDValidator`, `RatingProvider`, `IDCrossRef`. Constructeur prend un `OMDbAdapter`. Méthodes :

- `validate_id(tt_id, expected_title, expected_year) -> bool` (Q5=B)
- `get_by_id(tt_id) -> dict` (full payload OMDb wrapped)
- `get_rating(tt_id) -> Notation | None`
- `get_cross_refs(tt_id) -> dict[str, str]` (extrait remote IDs si disponible)

Commit : `feat(provider-ids): add IMDbClient facade over OMDbAdapter`

### 3.3 — `RottenTomatoesClient` façade

Nouveau `personalscraper/api/metadata/rotten_tomatoes.py`. Classe `RottenTomatoesClient` qui compose `RatingProvider` uniquement. Méthode :

- `get_rating(tt_id) -> Notation | None` (extrait l'entrée "Rotten Tomatoes" du payload OMDb)

Docstring documente la limitation : pas d'ID RT distinct via OMDb. Si OMDb échoue → `ProviderFeatureUnavailable("rotten_tomatoes", "rating", reason)`.

Commit : `feat(provider-ids): add RottenTomatoesClient facade over OMDbAdapter`

### 3.4 — `_activation.py` wiring

`personalscraper/api/_activation.py` (existant) : wire les nouvelles façades. `IMDbClient` et `RottenTomatoesClient` partagent l'instance `OMDbAdapter` (single HTTP client → un seul rate limit).

Commit : `feat(provider-ids): wire IMDb and RT facades in _activation`

## Tests to write

- `test_omdb_adapter_internal_only` (vérifie pas d'imports OMDb hors api/metadata/)
- `test_imdb_client_validate_id_match` (HTTP mocked)
- `test_imdb_client_validate_id_reject_title_mismatch`
- `test_imdb_client_validate_id_reject_year_mismatch`
- `test_imdb_client_get_rating_parses_imdbrating_string`
- `test_imdb_client_get_cross_refs_returns_tmdb_id_if_available`
- `test_imdb_client_handles_omdb_404_returns_none`
- `test_rt_client_get_rating_parses_rotten_tomatoes_entry`
- `test_rt_client_handles_missing_rt_entry_returns_none`
- `test_rt_client_raises_provider_feature_unavailable_on_omdb_500`
- `test_activation_shares_omdb_adapter_between_imdb_and_rt`

## Acceptance criteria

- `IMDbClient` et `RottenTomatoesClient` existent et composent leurs capabilities.
- `isinstance(imdb_client, RatingProvider)` returns True.
- `isinstance(rt_client, RatingProvider)` returns True.
- `isinstance(rt_client, IDValidator)` returns False (RT ne déclare pas cette capability).
- Tests pass à 100%, coverage ≥ 90% sur les nouveaux modules.

## Migration / config touch

Vérifier `config.example/metadata.json5` (et la config réelle de l'instance) : si `omdb` était listé comme provider direct, l'usage migre vers les façades. Le wiring `_activation.py` reste rétrocompatible côté config — pas de nouvelle clé requise.

## DESIGN reference

§4 (Architecture, composition par client), §6.1 (Nouveaux modules api/), §6.2 (api/ refactorés).
