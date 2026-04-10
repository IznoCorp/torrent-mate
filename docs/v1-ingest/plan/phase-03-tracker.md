# Phase 3 — Tracker de torrents ingérés

## Objectif

Implémenter `tracker.py` : persistance JSON des torrents déjà traités.

## Sous-phases

### 3.1 — Classe IngestTracker : CRUD basique

- [ ] Implémenter `__init__` : chemin du fichier JSON, chargement lazy
- [ ] Implémenter `load()` / `save()` : lecture/écriture JSON avec gestion fichier absent ou corrompu
- [ ] Implémenter `is_ingested(hash)` : lookup dans le dict
- [ ] Implémenter `mark_ingested(hash, name, action)` : ajout + save

**Commit** : `v1.3.1: Implement IngestTracker core (load/save/mark/check)`

### 3.2 — Nettoyage des entrées obsolètes

- [ ] Implémenter `cleanup(active_hashes)` : retirer les hash qui ne sont plus dans qBit
- [ ] Retourner le nombre d'entrées supprimées (pour le log)

**Commit** : `v1.3.2: Implement tracker cleanup for removed torrents`
