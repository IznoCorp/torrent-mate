# Phase 2 — Wrapper qBittorrent (via qbittorrent-api)

## Objectif

Implémenter `qbit_client.py` : wrapper autour de la librairie `qbittorrent-api`.

> Note : On utilise `qbittorrent-api` (pip) plutôt qu'un client HTTP maison.
> La librairie gère automatiquement : auth/re-login, headers CSRF, compatibilité
> qBit v4.x (`pausedUP`) et v5.0+ (`stoppedUP`), `TorrentState` enum.

## Sous-phases

### 2.1 — Classe QBitClient wrapper

- [ ] Créer `personalscraper/ingest/qbit_client.py`
- [ ] Implémenter `__init__` avec host/port/username/password → `qbittorrentapi.Client`
- [ ] Context manager (`__enter__`/`__exit__`) : `auth_log_in()` / `auth_log_out()`
- [ ] Implémenter `get_completed_torrents()` via `torrents_info(status_filter='completed')`
- [ ] Implémenter `is_seeding(torrent)` via `torrent.state_enum.is_uploading`
- [ ] Implémenter `get_content_path(torrent)` → `Path(torrent.content_path)`
- [ ] Implémenter `get_all_torrent_hashes()` → `{t.hash for t in ...}`
- [ ] Gestion d'erreur : `LoginFailed`, `APIConnectionError`

**Commit** : `v1.2.1: Implement QBitClient wrapper around qbittorrent-api`

### 2.2 — Test contre l'API réelle

- [ ] Script de test rapide : se connecter, lister les torrents, afficher les infos
- [ ] Vérifier que les torrents actuels sont correctement détectés
- [ ] Valider la détection seeding vs completed via `state_enum`

**Commit** : `v1.2.2: Validate QBitClient against live API`
