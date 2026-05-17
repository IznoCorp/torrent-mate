# Phase 13 — Torrent Capabilities + QBit/Transmission Refactor

## Goal

Casser le `TorrentClient(Protocol)` monolithique existant (`api/torrent/_base.py:43`) en capabilities atomiques : `TorrentLister`, `TorrentInspector`, `AuthenticatedClient`. Refactor `QBitClient` et `TransmissionClient` pour qu'ils déclarent ce qu'ils supportent.

## Gate (prerequisites)

- Phase 1 mergée (capabilities Protocols définis).

## Sub-phases

### 13.1 — Drop `TorrentClient` monolithique

`personalscraper/api/torrent/_base.py` : supprime la classe `TorrentClient(Protocol)`. Garde la dataclass `TorrentItem`. Update les imports dans `_factory.py`.

Commit : `refactor(provider-ids): drop monolithic TorrentClient Protocol`

### 13.2 — `QBitClient` compose capabilities

`personalscraper/api/torrent/qbittorrent.py:37` : déclare `class QBitClient(TorrentLister, TorrentInspector, AuthenticatedClient): ...`. Méthodes existantes (`get_completed`, `get_all_hashes`, `get_content_path`, `login`) inchangées.

Commit : `refactor(provider-ids): QBitClient composes capabilities`

### 13.3 — `TransmissionClient` compose capabilities

`personalscraper/api/torrent/transmission.py:35` : déclare `class TransmissionClient(TorrentLister, TorrentInspector): ...`. Pas de `AuthenticatedClient` si Transmission ne requiert pas de login explicite dans le setup actuel (documenter pourquoi).

Commit : `refactor(provider-ids): TransmissionClient composes capabilities`

### 13.4 — Update `_factory.py` type hints

`personalscraper/api/torrent/_factory.py` : remplace `TorrentClient` par les capabilities adéquates dans les annotations de retour.

Commit : `refactor(provider-ids): torrent factory typed by capability`

### 13.5 — Update consommateurs `ingest/`

`personalscraper/ingest/ingest.py` et autres consommateurs : les annotations utilisent les capabilities concrètes (`TorrentLister` pour `get_completed`, `TorrentInspector` pour `get_content_path`).

Commit : `refactor(provider-ids): ingest consumers use torrent capability types`

## Tests to write

- `test_qbit_client_is_torrent_lister_isinstance`
- `test_qbit_client_is_torrent_inspector_isinstance`
- `test_qbit_client_is_authenticated_client_isinstance`
- `test_transmission_client_is_torrent_lister_isinstance`
- `test_transmission_client_not_authenticated_client_isinstance` (regression)
- `test_no_more_monolithic_torrent_client_protocol_exists`
- `test_torrent_factory_returns_capability_typed_client`
- `test_ingest_works_with_capability_typed_torrent_client` (integration)

## Acceptance criteria

- `from personalscraper.api.torrent._base import TorrentClient` lève `ImportError`.
- `isinstance(QBitClient(...), TorrentLister)` returns True.
- `personalscraper torrents-list` et `personalscraper ingest` fonctionnent post-refactor.
- Tests pass à 100%.

## Migration / config touch

Aucune (refactor type-only).

## DESIGN reference

§6.2 (api/torrent refactor), §4 (Composition par client).
