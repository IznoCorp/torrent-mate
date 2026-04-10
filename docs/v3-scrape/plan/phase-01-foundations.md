# Phase 1 — Naming patterns + mediainfo

## Objectif

Implémenter les fondations réutilisables : patterns de nommage et extraction streamdetails.

## Sous-phases

### 3.1.1 — NamingPatterns dataclass

- [ ] Créer `personalscraper/naming_patterns.py` (niveau package, partagé)
- [ ] Implémenter `NamingPatterns` dataclass avec tous les patterns MediaElch par défaut
- [ ] Implémenter `format(pattern_name, **kwargs)` pour templating
- [ ] Implémenter `load(path)` pour charger depuis un fichier config optionnel
- [ ] Tests unitaires : vérifier chaque pattern produit le bon nom

**Commit** : `v3.1.1: Implement NamingPatterns with MediaElch defaults`

### 3.1.2 — Extraction mediainfo (streamdetails)

- [ ] Créer `personalscraper/scraper/mediainfo.py`
- [ ] Implémenter `extract_stream_info(video_path)` → dict compatible NFO
- [ ] Gérer le cas pymediainfo non installé (retourner None, pas d'erreur)
- [ ] Tests avec un fichier vidéo réel (ou mock pymediainfo)

**Commit** : `v3.1.2: Implement mediainfo extraction for NFO streamdetails`
