# Phase 2 — Extraction mediainfo (streamdetails)

## Objectif

Extraire les infos codec/résolution/audio des fichiers vidéo pour les NFO.

## Sous-phases

### 3.2.1 — Module extract_stream_info

- [ ] Créer `personalscraper/scraper/mediainfo.py`
- [ ] Implémenter `extract_stream_info(video_path)` → dict
- [ ] Extraire : codec vidéo, largeur, hauteur, aspect ratio, scan type
- [ ] Extraire : pistes audio (langue, codec, channels) — toutes les pistes
- [ ] Extraire : pistes sous-titres (langue) — toutes les pistes
- [ ] Calculer la durée en secondes

**Commit** : `v3.2.1: Implement mediainfo extraction via pymediainfo`

### 3.2.2 — Graceful fallback et tests

- [ ] Gérer pymediainfo non installé : retourner None sans crash
- [ ] Gérer fichier vidéo corrompu/illisible : retourner None + log warning
- [ ] Tests avec un .mkv réel du dossier 001-MOVIES/ ou 002-TVSHOWS/
- [ ] Tests avec pymediainfo mocké (pour CI sans lib native)

**Commit** : `v3.2.2: Add graceful fallback and mediainfo tests`
