# Phase 1 — Capabilities Protocols

## Goal

Définir tous les `Protocol` capabilities atomiques que les couches `api/metadata/`, `api/tracker/`, `api/torrent/`, `api/notify/` consommeront aux phases suivantes. **Aucune implémentation client n'est touchée dans cette phase** — uniquement la définition des contrats + tests `isinstance`.

## Gate (prerequisites)

- Branche `feat/provider-ids` créée et `IMPLEMENTATION.md` initialisé (phase 0 = implement:create-branch, déjà fait).

## Sub-phases

### 1.1 — Global capability `api/_contracts.py`

Définir `HasName` (Protocol) + import marker pour les capabilities domain-spécifiques.

Commit : `feat(provider-ids): add api/_contracts.py with HasName protocol`

### 1.2 — Metadata capabilities `api/metadata/_contracts.py`

7 Protocols : `Searchable`, `MovieDetailsProvider`, `TvDetailsProvider`, `EpisodeFetcher`, `RatingProvider`, `IDValidator`, `IDCrossRef`. Avec `@runtime_checkable` pour permettre `isinstance()`.

Commit : `feat(provider-ids): add metadata capability protocols`

### 1.3 — Tracker capabilities `api/tracker/_contracts.py`

4 Protocols : `TorrentSearchable`, `CategoryListable`, `FreeleechAware`, `TorrentDetailsProvider`. Avec `@runtime_checkable`.

Commit : `feat(provider-ids): add tracker capability protocols`

### 1.4 — Torrent capabilities `api/torrent/_contracts.py`

3 Protocols : `TorrentLister`, `TorrentInspector`, `AuthenticatedClient`. Avec `@runtime_checkable`.

Commit : `feat(provider-ids): add torrent capability protocols`

### 1.5 — Notify capabilities `api/notify/_contracts.py`

2 Protocols : `Notifier`, `HealthBeacon`. Avec `@runtime_checkable`.

Commit : `feat(provider-ids): add notify capability protocols`

### 1.6 — Helpers `api/_helpers.py` + `ProviderFeatureUnavailable`

Helpers `gather_ratings(providers, provider_id)`, `gather_cross_refs(providers, canonical_id)`. Exception métier `ProviderFeatureUnavailable(provider, feature, reason)` pour cas runtime structurels.

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

- Les 5 fichiers `_contracts.py` existent dans `api/`, `api/metadata/`, `api/tracker/`, `api/torrent/`, `api/notify/`.
- Tous les Protocols sont `@runtime_checkable`.
- `from personalscraper.api.metadata import RatingProvider; isinstance(some_obj, RatingProvider)` fonctionne.
- Tests pass à 100%.
- **Aucun client refactoré dans cette phase** — uniquement les contrats.

## Migration / config touch

Aucune (phase de fondation pure, pas de schema, pas de config).

## DESIGN reference

§4 (Architecture overview), §4 (Capabilities runtime-checkable), §4 (Helpers consommateurs).
