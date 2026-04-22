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
  - Filtre : `free_space_gb >= max(min_free_gb, item_size_gb * 1.5)`
- [ ] Configuration du mapping disque → catégories (dict dans config ou fichier dédié)
- [ ] Tests unitaires

**Commit** : `v5.1.1: Implement disk scanner with config and space checking`

### 5.1.2 — Media index JSON

- [ ] Créer `personalscraper/dispatch/media_index.py`
- [ ] Implémenter `IndexEntry` dataclass
- [ ] Implémenter `MediaIndex` : load, save, rebuild, find, add, remove_stale
- [ ] `rebuild()` scanne tous les disques montés, indexe chaque dossier média
- [ ] `find()` : lookup exact dict d'abord, rapidfuzz WRatio en fallback (score >= 85)
  - Utilise `media_processor` de `personalscraper.text_utils` pour normalisation unicode + accents
  - Ref : [docs/rapidfuzz-reference.md](../../rapidfuzz-reference.md)
- [ ] `save()` : écriture atomique (write .tmp + os.rename) pour éviter corruption si crash
- [ ] Fichier index : `~/.personalscraper/media_index.json`
- [ ] Tests unitaires avec tmp_path

**Commit** : `v5.1.2: Implement JSON media index with rebuild and fuzzy find`
