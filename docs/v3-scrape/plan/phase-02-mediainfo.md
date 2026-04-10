# Phase 2 — Extraction streamdetails via ffprobe

## Objectif

Extraire les infos codec/résolution/audio des fichiers vidéo pour les NFO.

> Ref : [docs/ffprobe-reference.md](../../ffprobe-reference.md)
>
> Points critiques à implémenter (découverts par tests sur vrais fichiers) :
>
> - Mapping langue ISO 639-2/B → 639-2/T (`fre`→`fra`, 20 codes — section 9)
> - Conversion aspect ratio `"16:9"` → `1.778` decimal (section 4)
> - Durée arrondie `round()` pour match MediaElch (section 8)
> - Détection Dolby Atmos dans EAC3 via `profile` (section 5)
> - Scantype depuis `field_order` (section 4)
> - Performance : ~65ms par fichier, lecture headers uniquement (section 11)

## Sous-phases

### 3.2.1 — Module extract_stream_info + mappings

- [ ] Créer `personalscraper/scraper/mediainfo.py`
- [ ] Implémenter `LANG_B_TO_T` dict (20 codes ISO 639-2/B → 639-2/T)
  - Critique : ffprobe retourne `fre`, Kodi NFO attend `fra`
  - Ref : `docs/ffprobe-reference.md` section 9 "Language Code Mapping"
- [ ] Implémenter `_normalize_language(lang)` : `LANG_B_TO_T.get(lang, lang)`
- [ ] Implémenter `_parse_aspect_ratio(ratio_str)` : `"16:9"` → `1.778`
- [ ] Implémenter `extract_stream_info(video_path)` → dict | None
- [ ] Appel subprocess : `ffprobe -v quiet -print_format json -show_streams -show_format <path>`
  - Timeout 30s pour les fichiers corrompus qui bloqueraient ffprobe
- [ ] Parser le JSON pour extraire :
  - **Video** (premier stream `codec_type=="video"`) :
    - `codec_name` (hevc, h264, av1)
    - `width`, `height`
    - `display_aspect_ratio` → convertir en decimal via `_parse_aspect_ratio()`
    - `field_order` → `"progressive"` si progressive/absent, `"interlaced"` si tt/bb/tb/bt
  - **Audio** (tous les streams `codec_type=="audio"`) :
    - `codec_name` (eac3, ac3, aac, dts)
    - `channels` (int)
    - `tags.language` → normaliser via `_normalize_language()`
    - **Dolby Atmos** : si `codec_name=="eac3"` ET `profile` contient "Atmos" → codec `"atmos"`
  - **Subtitle** (tous les streams `codec_type=="subtitle"`) :
    - `tags.language` → normaliser via `_normalize_language()`
  - **Durée** : `round(float(format["duration"]))` (cohérent avec MediaElch)
- [ ] Retourner dict compatible `<streamdetails>` NFO

**Commit** : `v3.2.1: Implement streamdetails extraction via ffprobe with codec/language mappings`

### 3.2.2 — Graceful fallback et tests

- [ ] Gérer ffprobe non installé (`FileNotFoundError`) : retourner None sans crash
- [ ] Gérer fichier vidéo corrompu/illisible (`subprocess.TimeoutExpired`, JSON invalide) : retourner None + log warning
- [ ] Gérer fichier sans piste audio ou sans sous-titres : listes vides, pas d'erreur
- [ ] Tests avec un .mkv réel de `001-MOVIES/` :
  - Comparer la sortie avec le NFO MediaElch existant (même codec, même langue, même aspect)
  - Vérifier que `fre` est bien converti en `fra`
  - Vérifier que l'aspect ratio est bien en decimal (1.778, pas "16:9")
  - Vérifier la détection Atmos si fichier avec EAC3+Atmos
- [ ] Tests avec subprocess mocké (pour CI sans ffprobe)

**Commit** : `v3.2.2: Add ffprobe tests with MediaElch NFO comparison`
