# Phase 7 — NFO generator — films

## Objectif

Générer des fichiers NFO `<movie>` XML identiques à MediaElch.

## Sous-phases

### 3.7.1 — Structure XML movie de base

- [ ] Créer `personalscraper/scraper/nfo_generator.py`
- [ ] Implémenter `NFOGenerator` class
- [ ] Implémenter `generate_movie_nfo(movie_data, stream_info=None)` → str XML
- [ ] Tags de base : title, originaltitle, year, premiered, plot, outline, tagline, runtime, mpaa
- [ ] Tags IDs : uniqueid (imdb, tmdb), id
- [ ] Tags ratings : `<ratings><rating name="themoviedb" default="true" max="10">`
- [ ] Tags classification : genre, country, studio
- [ ] Encodage UTF-8, XML declaration, standalone="yes"

**Commit** : `v3.7.1: Implement base movie NFO XML structure`

### 3.7.2 — Credits, acteurs et images inline

- [ ] Tags credits : director, credits (writers)
- [ ] Tags acteurs : `<actor><name><role><order><thumb>` pour chaque acteur du cast
- [ ] Tags images inline : `<thumb aspect="poster">` avec preview + original URLs
- [ ] Tags fanart : `<fanart><thumb preview="...">...</thumb></fanart>`
- [ ] Tag trailer (URL YouTube si disponible)

**Commit** : `v3.7.2: Add credits, actors, and inline images to movie NFO`

### 3.7.3 — Streamdetails et generator

- [ ] Intégrer `<fileinfo><streamdetails>` depuis le dict mediainfo
- [ ] Tags video : codec, aspect, width, height, durationinseconds, scantype
- [ ] Tags audio (multiples) : language, codec, channels
- [ ] Tags subtitle (multiples) : language
- [ ] Tag `<generator><appname>personalscraper</appname></generator>`
- [ ] Implémenter `write_nfo(xml_content, path)` avec encodage UTF-8

**Commit** : `v3.7.3: Add streamdetails and generator tag to movie NFO`

### 3.7.4 — Tests de conformité MediaElch

- [ ] Lire un .nfo MediaElch réel de 001-MOVIES/
- [ ] Générer un .nfo avec les mêmes données
- [ ] Comparer tag par tag : même structure, mêmes attributs
- [ ] Vérifier que Plex/Kodi parserait correctement le NFO généré

**Commit** : `v3.7.4: Add MediaElch conformity tests for movie NFO`
