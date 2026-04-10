# Phase 4 — NFO generator

## Objectif

Générer des fichiers NFO XML identiques à MediaElch pour films, séries et épisodes.

## Sous-phases

### 3.4.1 — NFO film (<movie>)

- [ ] Créer `personalscraper/scraper/nfo_generator.py`
- [ ] Implémenter `generate_movie_nfo(movie_data, stream_info)` → XML string
- [ ] Tous les tags : title, originaltitle, ratings, plot, tagline, runtime, mpaa, ids, genre, country, credits, director, premiered, year, studio, trailer, fileinfo, actors, generator
- [ ] Images en ligne : `<thumb aspect="poster">` et `<fanart><thumb>`
- [ ] `<generator><appname>personalscraper</appname></generator>`
- [ ] Implémenter `write_nfo(xml_content, path)` avec encodage UTF-8
- [ ] Test : comparer le XML généré avec un NFO MediaElch réel

**Commit** : `v3.4.1: Implement movie NFO generator (MediaElch-compatible)`

### 3.4.2 — NFO série (<tvshow>) et épisode (<episodedetails>)

- [ ] Implémenter `generate_tvshow_nfo(show_data)` → XML string
- [ ] Tous les tags : title, showtitle, originaltitle, uniqueids, ratings, episode count, season count, plot, mpaa, premiered, year, status, studio, runtime, genre, tags, actors, generator
- [ ] Implémenter `generate_episode_nfo(episode_data, stream_info)` → XML string
- [ ] Tags : title, showtitle, uniqueids, ratings, season, episode, plot, aired, director, thumb, fileinfo, generator
- [ ] Tests avec des NFO MediaElch réels comme référence

**Commit** : `v3.4.2: Implement tvshow and episode NFO generators`
