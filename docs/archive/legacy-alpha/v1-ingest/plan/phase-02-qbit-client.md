# Phase 2 — Wrapper qBittorrent (via qbittorrent-api)

## Objectif

Implémenter `qbit_client.py` : wrapper autour de la librairie `qbittorrent-api`.

> Ref : [docs/qbittorrent-api-reference.md](../../qbittorrent-api-reference.md)
>
> Points clés de la librairie :
>
> - Auth auto (re-login transparent si cookie SID expiré)
> - `TorrentState` enum avec helpers : `is_complete`, `is_uploading`, `is_stopped`
> - Compat v4.x (`pausedUP`) et v5.0+ (`stoppedUP`) transparente
> - Timeout par défaut 15.1s — augmenter à 30s pour le cron
> - Exceptions typées : `LoginFailed`, `APIConnectionError`

## Sous-phases

### 2.1 — Classe QBitClient wrapper

- [ ] Créer `personalscraper/ingest/qbit_client.py`
- [ ] Implémenter `__init__` avec host/port/username/password → `qbittorrentapi.Client`
  - `REQUESTS_ARGS={"timeout": 30}` (défaut 15.1s trop court pour cron)
  - `VERIFY_WEBUI_CERTIFICATE=False` (API locale)
- [ ] Context manager (`__enter__`/`__exit__`) : `auth_log_in()` / `auth_log_out()`
- [ ] Implémenter `get_completed_torrents()` via `torrents_info(status_filter='completed')`
  - Retourne `list[TorrentDictionary]` — accès par attribut : `.name`, `.hash`, `.content_path`, `.state_enum`
- [ ] Implémenter `is_seeding(torrent)` :
  - `torrent.state_enum.is_uploading` → True = en seed actif (uploading/stalledUP/forcedUP/queuedUP)
  - `torrent.state_enum.is_complete and not is_uploading` → stoppé (pausedUP/stoppedUP) = safe pour move
- [ ] Implémenter `get_content_path(torrent)` → `Path(torrent.content_path)`
  - content_path pointe vers un **fichier** (ex: `.mkv` isolé) OU un **dossier** — tester avec `is_dir()`
- [ ] Implémenter `get_all_torrent_hashes()` → `{t.hash for t in self._client.torrents_info()}`
- [ ] Gestion d'erreur :
  - `qbittorrentapi.LoginFailed` → mauvais credentials, ne pas retry
  - `qbittorrentapi.APIConnectionError` → qBit non accessible, retry possible
  - `qbittorrentapi.APIError` → catch-all pour les autres erreurs

**Commit** : `v1.2.1: Implement QBitClient wrapper around qbittorrent-api`

### 2.2 — Test contre l'API réelle

- [ ] Script de test rapide : se connecter, lister les torrents, afficher les infos
- [ ] Pour chaque torrent : afficher `name`, `hash`, `state`, `state_enum`, `content_path`, `progress`
- [ ] Vérifier la détection seeding vs completed :
  - `state_enum.is_uploading` = en seed actif → copier
  - `state_enum.is_complete and not is_uploading` = arrêté → déplacer
- [ ] Vérifier que `content_path` pointe vers des chemins existants
- [ ] Tester le context manager (login + logout)

**Commit** : `v1.2.2: Validate QBitClient against live API`
