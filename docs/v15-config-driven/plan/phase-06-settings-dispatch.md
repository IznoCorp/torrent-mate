# Phase 6 — `config.py` allégé + Dispatch refactor

## Objectif

Purger `config.py` (Settings) des paths disques + data_dir ; refactorer `dispatch/` pour utiliser `Config.disks` au lieu de `DISK_CATEGORIES` hardcodé.

## Sous-phases

### 6.1 — `config.py` : retirer disk1_dir..disk4_dir + data_dir

- [ ] Modifier `personalscraper/config.py::Settings` :
  - Retirer `disk1_dir`, `disk2_dir`, `disk3_dir`, `disk4_dir` (déménagés vers `Config.disks`)
  - Retirer `data_dir_name` et la logique de résolution (déménagé vers `Config.paths.data_dir`)
  - Retirer `torrent_complete_dir`, `staging_dir` (déménagés vers `Config.paths`)
  - Garder : `tmdb_api_key`, `tvdb_api_key`, `qbittorrent_*`, `telegram_*`, `min_free_space_disk_gb`, autres seuils numériques
- [ ] Warning : cet allègement casse les imports existants qui utilisent `Settings.disk1_dir` etc. → ces call sites seront fixés par les phases suivantes
- [ ] Tests `tests/test_config.py` : adapter (supprimer tests des champs retirés)

**Commit** : `v15.6.1: Strip Settings of disk paths and data_dir (moved to Config)`

### 6.2 — `dispatch/disk_scanner.py` : supprimer DISK_CATEGORIES

- [ ] Modifier `personalscraper/dispatch/disk_scanner.py` :
  - Supprimer `DISK_CATEGORIES` dict hardcodé
  - Supprimer validator import-time `for _disk, _cats in DISK_CATEGORIES.items()`
  - `get_disk_configs(config: Config) -> list[DiskConfig]` (nouveau signature — prend Config, retourne les `DiskConfig` Pydantic)
  - `get_disk_status(config: DiskConfig) -> DiskStatus` inchangé (déjà consomme un DiskConfig)
- [ ] `DiskConfig` n'est plus défini ici (dataclass) — importer depuis `conf.models`
- [ ] `DiskStatus` garde sa dataclass (pur runtime state, pas config)
- [ ] Tests adaptés pour nouveau signature

**Commit** : `v15.6.2: disk_scanner uses Config.disks instead of hardcoded DISK_CATEGORIES`

### 6.3 — `dispatch/dispatcher.py` : utilise Config + resolver

- [ ] Modifier `personalscraper/dispatch/dispatcher.py` :
  - Constructor `Dispatcher(config: Config, settings: Settings, index: MediaIndex, dry_run: bool = False)` (ajoute Config)
  - `dispatch_movie(movie_dir, category_id)` : prend maintenant category_id (pas label)
  - Utilise `resolver.folder_for(config, disk, category_id)` pour construire dest
  - Utilise `resolver.pick_disk_for(config, category_id, free_space_by_id, settings.min_free_space_disk_gb, item_size_gb)` au lieu de `choose_disk`
  - Supprime `choose_disk()` (fonctionnalité maintenant dans resolver)
- [ ] Tests dispatcher : adapter signatures, assert comportement identique

**Commit** : `v15.6.3: dispatcher uses Config + resolver for routing`

### 6.4 — `dispatch/media_index.py` : index par IDs

- [ ] Modifier `personalscraper/dispatch/media_index.py` :
  - `IndexEntry.category` : désormais category_id (pas label)
  - `IndexEntry.disk` : désormais disk_id (pas nom "Disk1")
  - Serialization JSON : format unchanged (clés/valeurs strings)
  - À la lecture (`MediaIndex.load`) : détecter V14 format (label FR) vs V15 (ID) et convertir à la volée via `V14_LABEL_TO_ID`
  - Premier write en V15 → format migré, `.v14.bak` créé
- [ ] Tests : load V14 JSON → migré vers IDs, load V15 JSON → passthrough, write toujours en IDs

**Commit** : `v15.6.4: media_index stores and loads category/disk IDs with V14 auto-migration`

### 6.5 — Autres consommers de Settings déplacés

- [ ] Grep `settings.disk[1-4]_dir|settings.torrent_complete_dir|settings.staging_dir|settings.data_dir` dans tout le codebase
- [ ] Pour chaque occurrence, remplacer par :
  - `config.paths.torrent_complete_dir`, `config.paths.staging_dir`, `config.paths.data_dir`
  - `config.disk_by_id(id).path` ou `config.disks` iteration
- [ ] Ajuster les signatures des fonctions qui recevaient `Settings` pour recevoir `Config` (ou les deux quand secrets + structure nécessaires)

**Commit** : `v15.6.5: Migrate all Settings.disk/paths consumers to Config`

## Tests de cohérence P6→P7

- [ ] `config.py::Settings` ne contient plus de disk paths ni data_dir (grep pour vérifier)
- [ ] `dispatch/disk_scanner.py` n'a plus `DISK_CATEGORIES`
- [ ] Tous les callers V14 de `get_disk_configs(settings)` adaptés à `get_disk_configs(config)`
- [ ] `Dispatcher.dispatch_movie` et `dispatch_tvshow` acceptent `category_id` et utilisent le resolver
- [ ] Tests dispatch passent (+ les 2 tests `TestDispatchExisting` fixés récemment doivent continuer à passer)
- [ ] mypy strict : 0 erreur sur `dispatch/*`
