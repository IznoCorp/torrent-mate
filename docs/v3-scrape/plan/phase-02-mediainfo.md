# Phase 2 — Extraction streamdetails via ffprobe

## Objectif

Extraire les infos codec/résolution/audio des fichiers vidéo pour les NFO.

> Note : Utilise `ffprobe` (subprocess) au lieu de `pymediainfo`.
> ffprobe est déjà installé (via `brew install ffmpeg`), zéro dépendance Python,
> standard de l'industrie, output JSON natif.

## Sous-phases

### 3.2.1 — Module extract_stream_info

- [ ] Créer `personalscraper/scraper/mediainfo.py`
- [ ] Implémenter `extract_stream_info(video_path)` → dict | None
- [ ] Appel subprocess : `ffprobe -v quiet -print_format json -show_streams -show_format <path>`
- [ ] Parser le JSON pour extraire :
  - Video : codec_name, width, height, display_aspect_ratio
  - Audio : codec_name, channels, tags.language (toutes les pistes)
  - Subtitle : codec_name, tags.language (toutes les pistes)
- [ ] Calculer la durée en secondes (format.duration)
- [ ] Retourner dict compatible `<streamdetails>` NFO

**Commit** : `v3.2.1: Implement streamdetails extraction via ffprobe`

### 3.2.2 — Graceful fallback et tests

- [ ] Gérer ffprobe non installé (`FileNotFoundError`) : retourner None sans crash
- [ ] Gérer fichier vidéo corrompu/illisible : retourner None + log warning
- [ ] Tests avec un .mkv réel du dossier 001-MOVIES/ ou 002-TVSHOWS/
- [ ] Tests avec subprocess mocké (pour CI sans ffprobe)

**Commit** : `v3.2.2: Add graceful fallback and ffprobe tests`
