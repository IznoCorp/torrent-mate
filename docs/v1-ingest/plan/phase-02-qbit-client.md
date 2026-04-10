# Phase 2 — Client API qBittorrent

## Objectif

Implémenter `qbit_client.py` : authentification, listing et inspection des torrents.

## Sous-phases

### 2.1 — Classe QBitClient : connexion et auth

- [ ] Implémenter `__init__` avec host/port/username/password
- [ ] Implémenter `login()` : POST `/api/v2/auth/login`, récupérer le cookie SID
- [ ] Implémenter `logout()` : POST `/api/v2/auth/logout`
- [ ] Context manager (`__enter__`/`__exit__`) pour auto-login/logout
- [ ] Gestion d'erreur : connexion refusée, mauvais credentials

**Commit** : `v1.2.1: Implement QBitClient auth (login/logout)`

### 2.2 — Listing des torrents complétés

- [ ] Implémenter `get_completed_torrents()` : GET `/api/v2/torrents/info` avec filtre `progress=1.0`
- [ ] Implémenter `is_seeding(torrent)` : inspecter le champ `state`
- [ ] Implémenter `get_torrent_hash(torrent)` et `get_content_path(torrent)`
- [ ] Implémenter `get_all_torrent_hashes()` : pour le nettoyage du tracker

**Commit** : `v1.2.2: Implement torrent listing and status inspection`

### 2.3 — Test manuel contre l'API réelle

- [ ] Script de test rapide : se connecter, lister les torrents, afficher les infos
- [ ] Vérifier que les 6 torrents actuels sont correctement détectés
- [ ] Valider la détection seeding vs completed

**Commit** : `v1.2.3: Validate QBitClient against live API`
