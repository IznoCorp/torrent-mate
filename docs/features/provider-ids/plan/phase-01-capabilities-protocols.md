# Phase 1 — Capabilities Protocols

## Goal

Définir tous les `Protocol` capabilities atomiques que les couches `api/metadata/`, `api/tracker/`, `api/torrent/`, `api/notify/` consommeront aux phases suivantes. **Post-api-unify : `api/_contracts.py` existe déjà** (avec `MediaType`, `ProviderName`, `AuthMode`, `ApiError`, `CircuitOpenError`) — on ajoute `HasName`. Le `MetadataProvider` Protocol monolithique existe dans `api/metadata/_base.py:259` (8 méthodes) — on le décompose en capabilities atomiques dans `_contracts.py`. Aucune implémentation client n'est modifiée dans cette phase.

## Gate (prerequisites)

- Branche `feat/provider-ids` créée et `IMPLEMENTATION.md` initialisé (phase 0 = implement:create-branch, déjà fait).
- Codebase post-api-unify : `api/metadata/_base.py` avec `MetadataProvider` Protocol monolithique, `api/tracker/_base.py` avec `TrackerClient` Protocol, `api/torrent/_base.py` avec `TorrentClient` Protocol.

## Sub-phases

### 1.1 — Global capability `api/_contracts.py` (modification, pas création)

Ajouter `HasName` (Protocol) au fichier existant `personalscraper/api/_contracts.py`. Le contenu existant (`MediaType`, `ProviderName`, `AuthMode`, `ApiError`, `CircuitOpenError`) reste intact. Ajouter aussi l'import marker pour les capabilities domain-spécifiques.

Commit : `feat(provider-ids): add HasName protocol to existing api/_contracts.py`

### 1.2 — Metadata capabilities `api/metadata/_contracts.py` (décomposition du monolithique)

11 Protocols atomiques (couvrant les 8 méthodes du `MetadataProvider` existant + 2 nouvelles) : `Searchable`, `MovieDetailsProvider`, `TvDetailsProvider`, `EpisodeFetcher`, `RatingProvider`, `IDValidator`, `IDCrossRef`, `ArtworkProvider`, `KeywordProvider`, `VideoProvider`, `RecommendationProvider`. Avec `@runtime_checkable`. Ces Protocols **remplacent** le `MetadataProvider` monolithique existant (`api/metadata/_base.py:259-324`, 8 méthodes). Le fichier `_base.py` garde les dataclasses (`SearchResult`, `MediaDetails`, `Notations`, `EpisodeInfo`, `SeasonDetails`, etc.) et le `MetadataClient` base class — seul le Protocol est migré vers `_contracts.py`.

Mapping des 8 méthodes existantes → 11 capabilities (9 capabilities dérivées + 2 nouvelles) :

| Méthode `MetadataProvider` | Capability atomique                          | Note                                |
| -------------------------- | -------------------------------------------- | ----------------------------------- |
| `search()`                 | `Searchable`                                 |                                     |
| `get_details()`            | `MovieDetailsProvider` + `TvDetailsProvider` | Split par media_type                |
| `get_artwork_urls()`       | `ArtworkProvider`                            |                                     |
| `get_keywords()`           | `KeywordProvider`                            |                                     |
| `get_videos()`             | `VideoProvider`                              |                                     |
| `get_season()`             | `EpisodeFetcher`                             |                                     |
| `get_notations()`          | `RatingProvider`                             |                                     |
| `get_recommendations()`    | `RecommendationProvider`                     |                                     |
| (pas dans le monolithique) | `IDValidator`                                | Nouveau — re-validation Q5=B        |
| (pas dans le monolithique) | `IDCrossRef`                                 | Nouveau — cross-ref entre providers |

Commit : `feat(provider-ids): add 11 atomic metadata capability protocols`

### 1.2b — Plan de migration des consommateurs de `MetadataProvider`

Lister tous les imports de `MetadataProvider` dans `personalscraper/` et `tests/`. Documenter le mapping de migration : chaque consommateur qui utilise `isinstance(x, MetadataProvider)` ou `x: MetadataProvider` sera migré vers la/les capabilities atomiques pertinentes dans les phases suivantes (5 pour le scraper, 11-14 pour tracker/torrent/notify). Ce plan n'implémente rien — il documente la séquence pour éviter les oublis.

Commit : `docs(provider-ids): migration plan for MetadataProvider consumers`

### 1.3 — Tracker capabilities `api/tracker/_contracts.py`

4 Protocols : `TorrentSearchable`, `CategoryListable`, `FreeleechAware`, `TorrentDetailsProvider`. Avec `@runtime_checkable`.

Commit : `feat(provider-ids): add tracker capability protocols`

### 1.4 — Torrent capabilities `api/torrent/_contracts.py`

5 Protocols atomiques (couvrant les 7 méthodes du `TorrentClient` existant) : `TorrentLister`, `TorrentInspector`, `AuthenticatedClient`, `TorrentStateInspector`, `TorrentController`. Avec `@runtime_checkable`.

Mapping des 7 méthodes → 5 capabilities :

| Méthode `TorrentClient`      | Capability atomique     | Note                              |
| ---------------------------- | ----------------------- | --------------------------------- |
| `get_completed()`            | `TorrentLister`         |                                   |
| `get_all_hashes()`           | `TorrentLister`         |                                   |
| `get_content_path(torrent)`  | `TorrentInspector`      |                                   |
| `login()`                    | `AuthenticatedClient`   | Optionnelle (Transmission absent) |
| `is_seeding(torrent)`        | `TorrentStateInspector` | Read state                        |
| `pause(hash)`                | `TorrentController`     | Write state                       |
| `resume(hash)`               | `TorrentController`     | Write state                       |
| `delete(hash, delete_files)` | `TorrentController`     | Write state                       |

Commit : `feat(provider-ids): add 5 atomic torrent capability protocols`

### 1.5 — Notify capabilities `api/notify/_contracts.py` (migration des Protocols existants)

**Les 2 Protocols `Notifier` et `HealthChecker` existent déjà dans `api/notify/_base.py:17,35`** — bien séparés, déjà capability-style. Cette sub-phase les **déplace** vers `_contracts.py` pour cohérence avec les autres domaines + ajoute `@runtime_checkable`.

Protocols (noms et signatures EXISTANTS — pas réinventer) :

- `Notifier` (déjà à `_base.py:17`) : `send(message, parse_mode="HTML") -> bool`, `send_report(report: PipelineReport) -> bool`.
- `HealthChecker` (déjà à `_base.py:35`) : `ping_start()`, `ping_success()`, `ping_fail()`.

Action : `git mv` les 2 Protocols depuis `_base.py` vers `_contracts.py`, ajouter `@runtime_checkable`, re-exporter depuis `_base.py` pour rétrocompat des imports existants pendant la transition (les imports `from personalscraper.api.notify._base import Notifier` continuent de marcher).

Commit : `refactor(provider-ids): move Notifier and HealthChecker protocols to _contracts.py`

### 1.6 — Helpers `api/_helpers.py` + `ProviderFeatureUnavailable`

Helpers :

- `gather_ratings(providers, provider_id) -> list[Notations]` — collecte les ratings via `isinstance(p, RatingProvider)`, retourne le type `Notations` existant (`api/metadata/_base.py:149`).
- `gather_cross_refs(providers, canonical_id) -> dict[str, dict[str, str]]` — collecte les cross-refs via `isinstance(p, IDCrossRef)`.

Exception métier `ProviderFeatureUnavailable(provider, feature, reason)` pour cas runtime structurels.

Commit : `feat(provider-ids): add api helpers and ProviderFeatureUnavailable`

## Tests to write (TDD — tests d'abord, puis code)

- `test_has_name_protocol_isinstance_check`
- `test_metadata_capability_protocols_runtime_checkable` (un test par Protocol)
- `test_tracker_capability_protocols_runtime_checkable`
- `test_torrent_capability_protocols_runtime_checkable`
- `test_notify_capability_protocols_runtime_checkable`
- `test_gather_ratings_filters_non_rating_providers`
- `test_gather_cross_refs_returns_dict_by_provider_name`
- `test_provider_feature_unavailable_carries_provider_and_feature`

## Acceptance criteria

- Les 5 fichiers `_contracts.py` existent dans `api/` (modifié), `api/metadata/` (nouveau), `api/tracker/` (nouveau), `api/torrent/` (nouveau), `api/notify/` (nouveau).
- Tous les Protocols sont `@runtime_checkable`.
- `from personalscraper.api.metadata._contracts import RatingProvider; isinstance(some_obj, RatingProvider)` fonctionne.
- Le `MetadataProvider` Protocol monolithique dans `_base.py` est déprécié (commentaire + warning si importé) mais pas encore supprimé — les consommateurs existants l'utilisent encore.
- Tests pass à 100%.
- Un plan de migration documente tous les imports de `MetadataProvider` à migrer dans les phases suivantes.
- **Aucun client refactoré dans cette phase** — uniquement les contrats.

## Migration / config touch

Aucune (phase de fondation pure, pas de schema, pas de config).

## DESIGN reference

§4 (Architecture overview), §4 (Capabilities runtime-checkable), §4 (Helpers consommateurs), §6.1 (api/\_contracts.py modifié, pas créé), §6.2 (MetadataProvider décomposé).
