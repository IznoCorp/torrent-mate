# Phase 11 — Tracker Capabilities + LaCale/C411 Refactor

## Goal

Casser le `TrackerClient(Protocol)` monolithique existant (`api/tracker/_base.py:102`) en capabilities atomiques composées : `TorrentSearchable`, `CategoryListable`, `FreeleechAware`, `TorrentDetailsProvider`. Refactor `LaCaleClient` et `C411Client` pour qu'ils déclarent ce qu'ils supportent.

## Gate (prerequisites)

- Phase 1 mergée (capabilities Protocols définis).

## Sub-phases

### 11.1 — Drop `TrackerClient` monolithique

`personalscraper/api/tracker/_base.py` : supprime la classe `TrackerClient(Protocol)`. Garde les dataclasses (`TorrentResult`, etc.) intactes. Update les imports.

Commit : `refactor(provider-ids): drop monolithic TrackerClient Protocol`

### 11.2 — `LaCaleClient` compose ses capabilities

`personalscraper/api/tracker/lacale.py:61` : déclare `class LaCaleClient(TorrentSearchable, CategoryListable, FreeleechAware): ...`. Les méthodes existantes (`search`, `get_categories`) restent. Ajouter `is_freeleech(torrent_id)` si LaCale expose cette info.

Commit : `refactor(provider-ids): LaCaleClient composes capabilities`

### 11.3 — `C411Client` compose ses capabilities

`personalscraper/api/tracker/c411.py:86` : déclare `class C411Client(TorrentSearchable, CategoryListable): ...`. Pas de `FreeleechAware` si C411 ne le supporte pas (documenter pourquoi).

Commit : `refactor(provider-ids): C411Client composes capabilities`

### 11.4 — Update `TrackerRegistry` type hints

`api/tracker/_registry.py:21` : remplacer `trackers: dict[str, TrackerClient]` par `trackers: dict[str, TorrentSearchable]` (capability minimale). Les méthodes consommatrices utilisent `isinstance(p, CategoryListable)` etc. quand besoin spécifique.

Commit : `refactor(provider-ids): TrackerRegistry typed by capability`

## Tests to write

- `test_lacale_client_is_torrent_searchable_isinstance`
- `test_lacale_client_is_category_listable_isinstance`
- `test_lacale_client_is_freeleech_aware_isinstance`
- `test_c411_client_is_torrent_searchable_isinstance`
- `test_c411_client_not_freeleech_aware_isinstance` (régression — C411 ne déclare pas)
- `test_tracker_registry_accepts_capability_typed_dict`
- `test_no_more_monolithic_tracker_client_protocol_exists` (grep regression)

## Acceptance criteria

- `from personalscraper.api.tracker._base import TrackerClient` lève `ImportError` (Protocol supprimé).
- `isinstance(LaCaleClient(...), TorrentSearchable)` returns True.
- `TrackerRegistry` tests existants passent post-refactor.
- Aucune régression fonctionnelle sur `personalscraper search` / autres commandes tracker.

## Migration / config touch

Aucune (refactor type-only, pas de change config).

## DESIGN reference

§6.2 (api/tracker refactor), §4 (Composition par client).
