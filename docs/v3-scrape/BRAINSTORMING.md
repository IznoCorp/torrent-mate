# V3 — SCRAPE : Brainstorming

> Scraping automatique des métadonnées, génération NFO, téléchargement artwork, renommage épisodes

## Contexte

Après V2 (sort+clean), les médias sont dans `001-MOVIES/` et `002-TVSHOWS/` avec des noms propres
(titre + année). V3 doit :

1. Chercher le média sur TMDB (films) ou TVDB (séries, avec fallback TMDB)
2. Générer les fichiers `.nfo` au format Kodi (identique à MediaElch)
3. Télécharger l'artwork (poster, landscape, season posters)
4. Créer les dossiers `Saison XX/` et renommer les épisodes au format `S01E01 - Titre.ext`

## Décisions prises

### Sources API

- **Films** : TMDB (`https://api.themoviedb.org/3`)
- **Séries** : TVDB en priorité, fallback TMDB si pas trouvé
- Clé API TMDB : dans `/opt/YoutubeTrailerScraper/.env`
- Clé API TVDB : dans `.env` du projet (`TVDB_API_KEY=REDACTED_TVDB_API_KEY`)

### Matching et confiance

- **Auto si confiance haute** : titre exact + année match → prendre le 1er résultat
- **Interactif si flag `--interactive`** : proposer les résultats et demander confirmation
- **Sinon (mode auto sans confiance)** : ne rien faire, mettre dans le rapport/logs/notifications
- Jamais de scraping forcé sur un mauvais match

### Artwork téléchargé

| Type          | Film                    | Série                   |
| ------------- | ----------------------- | ----------------------- |
| poster        | `{Title}-poster.jpg`    | `poster.jpg`            |
| landscape     | `{Title}-landscape.jpg` | `landscape.jpg`         |
| season poster | —                       | `season{NN}-poster.jpg` |

Pas de : fanart, banner, clearlogo, clearart, discart, .actors/

### Organisation TV — dossiers saison + renommage épisodes

- V3 crée les `Saison XX/` dans chaque dossier série
- V3 renomme les épisodes au format `S01E01 - Titre Episode.ext`
- Le matching épisode se fait via l'API (TVDB/TMDB) : numéro de saison/épisode extrait du filename → titre récupéré

### Patterns de nommage (fichier de config)

- Un fichier dédié contiendra tous les patterns de nommage (dossiers, sous-dossiers, fichiers)
- Patterns par défaut reprenant exactement ceux de MediaElch
- Configurable si besoin de changer un pattern sans toucher au code

**Patterns par défaut (à confirmer avec la config MediaElch) :**

```
# Dossiers
movie_dir       = {Title} ({Year})
tvshow_dir      = {Title} ({Year})
season_dir      = Saison {Season:02d}

# Fichiers films
movie_video     = {Title}.{ext}
movie_nfo       = {Title}.nfo
movie_poster    = {Title}-poster.jpg
movie_landscape = {Title}-landscape.jpg

# Fichiers séries (show level)
tvshow_nfo      = tvshow.nfo
tvshow_poster   = poster.jpg
tvshow_landscape = landscape.jpg
season_poster   = season{Season:02d}-poster.jpg

# Fichiers épisodes
episode_video   = S{Season:02d}E{Episode:02d} - {EpisodeTitle}.{ext}
episode_nfo     = S{Season:02d}E{Episode:02d} - {EpisodeTitle}.nfo
episode_thumb   = S{Season:02d}E{Episode:02d} - {EpisodeTitle}-thumb.jpg
```

> **TODO** : récupérer la config exacte de MediaElch pour confirmer/compléter ces patterns

### Fichiers NFO — identiques à MediaElch

- Format XML Kodi standard
- **Inclure `<fileinfo><streamdetails>`** avec les infos codec/resolution/audio
- Nécessite `pymediainfo` ou `ffprobe` pour extraire les infos du fichier vidéo
- Le tag `<generator>` utilisera `personalscraper` au lieu de `MediaElch`
- 3 types de NFO :
  - `<movie>` pour les films
  - `<tvshow>` pour les séries (au niveau show)
  - `<episodedetails>` pour les épisodes

### Langue

- Variable `.env` : `SCRAPER_LANGUAGE=fr-FR`
- Fallback en dur : `en-US`
- Appliqué à : titres, plots, genres, noms d'épisodes

## Format NFO de référence (extrait de MediaElch)

### Film

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>...</title>
  <originaltitle>...</originaltitle>
  <ratings>
    <rating name="themoviedb" default="true" max="10">
      <value>7.5</value>
      <votes>1234</votes>
    </rating>
  </ratings>
  <outline>...</outline>
  <plot>...</plot>
  <tagline>...</tagline>
  <runtime>120</runtime>
  <thumb aspect="poster" preview="...w342/...">...original/...</thumb>
  <fanart><thumb preview="...w780/...">...original/...</thumb></fanart>
  <mpaa>...</mpaa>
  <id>tt1234567</id>
  <uniqueid default="true" type="imdb">tt1234567</uniqueid>
  <uniqueid type="tmdb">12345</uniqueid>
  <genre>...</genre>
  <country>...</country>
  <credits>...</credits>
  <director>...</director>
  <premiered>2024-01-15</premiered>
  <year>2024</year>
  <studio>...</studio>
  <trailer>...</trailer>
  <fileinfo>
    <streamdetails>
      <video>
        <codec>hevc</codec>
        <aspect>1.778</aspect>
        <width>1920</width>
        <height>1080</height>
      </video>
      <audio>
        <language>fra</language>
        <codec>eac3</codec>
        <channels>6</channels>
      </audio>
      <subtitle><language>fra</language></subtitle>
    </streamdetails>
  </fileinfo>
  <actor>
    <name>...</name>
    <role>...</role>
    <order>0</order>
    <thumb>...</thumb>
  </actor>
  <generator>
    <appname>personalscraper</appname>
  </generator>
</movie>
```

### Série (tvshow.nfo)

```xml
<tvshow>
  <title>...</title>
  <uniqueid default="true" type="tvdb">...</uniqueid>
  <uniqueid type="tmdb">...</uniqueid>
  <uniqueid type="imdb">...</uniqueid>
  <ratings>...</ratings>
  <plot>...</plot>
  <premiered>...</premiered>
  <year>...</year>
  <status>...</status>
  <genre>...</genre>
  <actor>...</actor>
</tvshow>
```

### Épisode

```xml
<episodedetails>
  <title>...</title>
  <season>1</season>
  <episode>1</episode>
  <plot>...</plot>
  <aired>2024-01-15</aired>
  <director>...</director>
  <fileinfo><streamdetails>...</streamdetails></fileinfo>
</episodedetails>
```

## Endpoints API nécessaires

### TMDB (films)

```
GET /search/movie?query={title}&year={year}&language={lang}
GET /movie/{id}?language={lang}&append_to_response=credits
GET /movie/{id}/images
```

### TVDB (séries)

```
POST /login                           → token
GET  /search?query={title}&type=series
GET  /series/{id}/extended
GET  /series/{id}/episodes/default/{season}
GET  /series/{id}/artworks?type=poster
```

### Fallback TMDB (séries si TVDB échoue)

```
GET /search/tv?query={title}&first_air_date_year={year}&language={lang}
GET /tv/{id}?language={lang}&append_to_response=credits
GET /tv/{id}/season/{season}?language={lang}
GET /tv/{id}/images
```

## Contraintes techniques

1. **Rate limiting** : TMDB = 40 req/sec (généreux), TVDB = plus restrictif → retry avec backoff
2. **pymediainfo** ou **ffprobe** nécessaire pour `<streamdetails>` dans les NFO
3. **Gestion des doublons** : ne pas re-scraper un média qui a déjà ses .nfo et artwork
4. **Dry-run** : afficher ce qui serait scrapé sans rien télécharger
5. **Mode interactif** : `--interactive` pour confirmer chaque match
6. **Timeout/retry** : 3 tentatives par requête, 10s timeout
