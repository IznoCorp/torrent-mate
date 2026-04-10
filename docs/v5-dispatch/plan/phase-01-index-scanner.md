# Phase 1 — Media index JSON + disk scanner

## Objectif

Implémenter l'index des médias et le scanner de disques.

## Sous-phases

### 5.1.1 — Disk scanner et configuration

- [ ] Créer `personalscraper/dispatch/disk_scanner.py`
- [ ] Implémenter `DiskConfig` et `DiskStatus` dataclasses
- [ ] Implémenter `get_disk_configs(settings)` : construire les configs depuis .env
- [ ] Implémenter `get_disk_status(config)` : espace libre, monté ou non
- [ ] Implémenter `choose_disk(disks, category, min_free_gb, item_size_gb=0)` : meilleur disque
  - Filtre : `free_space >= min_free_gb + item_size_gb`
- [ ] Configuration du mapping disque → catégories (dict dans config ou fichier dédié)
- [ ] Tests unitaires

**Commit** : `v5.1.1: Implement disk scanner with config and space checking`

### 5.1.2 — Media index JSON

- [ ] Créer `personalscraper/dispatch/media_index.py`
- [ ] Implémenter `IndexEntry` dataclass
- [ ] Implémenter `MediaIndex` : load, save, rebuild, find, add, remove_stale
- [ ] `rebuild()` scanne tous les disques montés, indexe chaque dossier média
- [ ] `find()` : normalisation unicode + fuzzy matching
- [ ] Fichier index : `~/.personalscraper_media_index.json`
- [ ] Tests unitaires avec tmp_path

**Commit** : `v5.1.2: Implement JSON media index with rebuild and fuzzy find`
