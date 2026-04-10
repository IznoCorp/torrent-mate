# Phase 8 — NFO generator — séries + épisodes

## Objectif

Générer `tvshow.nfo` (`<tvshow>`) et les NFO épisodes (`<episodedetails>`).

## Sous-phases

### 3.8.1 — NFO tvshow.nfo

- [ ] Implémenter `generate_tvshow_nfo(show_data)` → str XML
- [ ] Tags : title, showtitle, originaltitle, year, premiered, plot, status, mpaa, runtime
- [ ] Tags IDs : uniqueid (tvdb default, tmdb, imdb), id, episodeguide
- [ ] Tags ratings : `<rating name="themoviedb|tvdb">`
- [ ] Tags : genre, tag, studio, country (origin_country from API — needed by V4 for anime detection), episode count, season count
- [ ] Tags acteurs : `<actor>` avec name, role, order, thumb
- [ ] Tags images inline : `<thumb aspect="poster">`, `<fanart><thumb>`
- [ ] Tag generator

**Commit** : `v3.8.1: Implement tvshow.nfo generator`

### 3.8.2 — NFO épisode (episodedetails)

- [ ] Implémenter `generate_episode_nfo(episode_data, stream_info=None)` → str XML
- [ ] Tags : title, showtitle, season, episode, plot, outline, aired, mpaa
- [ ] Tags IDs : uniqueid (tvdb, tmdb)
- [ ] Tags ratings
- [ ] Tags : director, studio
- [ ] Tag thumb (episode screenshot URL)
- [ ] Intégrer `<fileinfo><streamdetails>` depuis mediainfo
- [ ] Tag generator

**Commit** : `v3.8.2: Implement episode NFO generator (episodedetails)`

### 3.8.3 — Tests de conformité MediaElch

- [ ] Lire un tvshow.nfo et un épisode .nfo réels de 002-TVSHOWS/
- [ ] Générer des NFO avec les mêmes données
- [ ] Comparer tag par tag avec les originaux MediaElch
- [ ] Tester avec une série multi-saisons

**Commit** : `v3.8.3: Add MediaElch conformity tests for tvshow and episode NFO`
