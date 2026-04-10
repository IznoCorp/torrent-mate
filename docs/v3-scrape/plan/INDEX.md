# V3 — SCRAPE : Plan d'implémentation

> Scraping metadata, génération NFO, artwork, renommage épisodes

## Phases

| #   | Phase                                | Fichier                                                            | Status |
| --- | ------------------------------------ | ------------------------------------------------------------------ | ------ |
| 1   | Naming patterns (fichier de config)  | [phase-01-naming-patterns.md](phase-01-naming-patterns.md)         | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_        |                                                                    | [ ]    |
| 2   | Extraction mediainfo (streamdetails) | [phase-02-mediainfo.md](phase-02-mediainfo.md)                     | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_        |                                                                    | [ ]    |
| 3   | Client API TMDB                      | [phase-03-tmdb-client.md](phase-03-tmdb-client.md)                 | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_        |                                                                    | [ ]    |
| 4   | Client API TVDB                      | [phase-04-tvdb-client.md](phase-04-tvdb-client.md)                 | [ ]    |
| ·   | _Contrôle de cohérence P4→P5_        |                                                                    | [ ]    |
| 5   | Confidence scoring + matching films  | [phase-05-movie-matching.md](phase-05-movie-matching.md)           | [ ]    |
| ·   | _Contrôle de cohérence P5→P6_        |                                                                    | [ ]    |
| 6   | Matching séries (TVDB→TMDB fallback) | [phase-06-tvshow-matching.md](phase-06-tvshow-matching.md)         | [ ]    |
| ·   | _Contrôle de cohérence P6→P7_        |                                                                    | [ ]    |
| 7   | NFO generator — films                | [phase-07-nfo-movie.md](phase-07-nfo-movie.md)                     | [ ]    |
| ·   | _Contrôle de cohérence P7→P8_        |                                                                    | [ ]    |
| 8   | NFO generator — séries + épisodes    | [phase-08-nfo-tvshow.md](phase-08-nfo-tvshow.md)                   | [ ]    |
| ·   | _Contrôle de cohérence P8→P9_        |                                                                    | [ ]    |
| 9   | Artwork downloader                   | [phase-09-artwork.md](phase-09-artwork.md)                         | [ ]    |
| ·   | _Contrôle de cohérence P9→P10_       |                                                                    | [ ]    |
| 10  | Dossiers saison + renommage épisodes | [phase-10-episode-rename.md](phase-10-episode-rename.md)           | [ ]    |
| ·   | _Contrôle de cohérence P10→P11_      |                                                                    | [ ]    |
| 11  | Orchestrateur films                  | [phase-11-movie-orchestrator.md](phase-11-movie-orchestrator.md)   | [ ]    |
| ·   | _Contrôle de cohérence P11→P12_      |                                                                    | [ ]    |
| 12  | Orchestrateur séries                 | [phase-12-tvshow-orchestrator.md](phase-12-tvshow-orchestrator.md) | [ ]    |
| ·   | _Contrôle de cohérence P12→P13_      |                                                                    | [ ]    |
| 13  | CLI scrape + tests end-to-end        | [phase-13-cli-tests.md](phase-13-cli-tests.md)                     | [ ]    |
| ·   | _Contrôle de cohérence V3→V4_        |                                                                    | [ ]    |

## Dépendances entre phases

```
Phase 1 (naming patterns) ─────────────────────────────────────┐
Phase 2 (mediainfo) ───────────────────────────────────────────┤
                                                                ├──▶ Phase 7 (NFO movie) ──▶ Phase 11 (movie orch.)──┐
Phase 3 (TMDB client) ──▶ Phase 5 (movie matching) ───────────┤                                                     │
                         ┌──────────────────────────────────────┤                                                     │
Phase 4 (TVDB client) ──┤                                      ├──▶ Phase 8 (NFO tvshow) ──┐                         │
                         └──▶ Phase 6 (tvshow matching) ───────┤                            ├──▶ Phase 12 (tv orch.)─┤
                                                                ├──▶ Phase 9 (artwork) ─────┤                         │
                                                                └──▶ Phase 10 (ep rename) ──┘                         │
                                                                                                                      │
                                                                Phase 13 (CLI + tests) ◀──────────────────────────────┘
```

Phases 1-4 : fondations indépendantes (peuvent être parallélisées 1+2 et 3+4).
Phases 5-6 : matching (dépendent des clients API).
Phases 7-10 : génération de contenu (dépendent de matching + fondations).
Phases 11-12 : orchestrateurs (assemblent tout par type de média).
Phase 13 : CLI et tests finaux.

## Contrôles de cohérence

### Après Phase 1 (Naming patterns)

- [ ] Tous les patterns MediaElch reproduits exactement
- [ ] `format()` fonctionne avec les variables de templating

### Après Phase 2 (Mediainfo via ffprobe)

- [ ] `extract_stream_info()` retourne video/audio/subtitle sur un .mkv réel
- [ ] Retourne None gracieusement si ffprobe absent
- [ ] Le dict retourné est directement utilisable par le NFO generator

### Après Phase 3 (TMDB client)

- [ ] Search movie retourne des résultats
- [ ] Get movie details retourne titre, année, genre, cast, IDs
- [ ] Get images retourne des URLs valides
- [ ] Rate limiting + retry fonctionnent
- [ ] La langue fr-FR est appliquée

### Après Phase 4 (TVDB client)

- [ ] Login + bearer token fonctionne
- [ ] Search series retourne des résultats
- [ ] Get series extended retourne les détails
- [ ] Get season episodes retourne la liste des épisodes avec titres
- [ ] Get artworks retourne des URLs

### Après Phase 5 (Movie matching)

- [ ] `score_match()` est précis (tests avec cas réels)
- [ ] Match auto si confiance >= 0.8
- [ ] Skip si confiance < 0.5 en mode auto
- [ ] Mode interactif fonctionne (propose les choix)

### Après Phase 6 (TVShow matching)

- [ ] TVDB search → match fonctionne
- [ ] Fallback TMDB si TVDB échoue
- [ ] Épisodes d'une saison récupérés avec titres
- [ ] Mode interactif pour les séries aussi

### Après Phase 7 (NFO movie)

- [ ] XML valide et parseable
- [ ] Structure identique à MediaElch (comparer tag par tag)
- [ ] `<streamdetails>` présent quand mediainfo disponible
- [ ] Tous les IDs (IMDB, TMDB) présents
- [ ] `<generator><appname>personalscraper</appname>`

### Après Phase 8 (NFO tvshow + episode)

- [ ] `tvshow.nfo` XML identique à MediaElch
- [ ] `episodedetails` XML identique à MediaElch
- [ ] IDs TVDB + TMDB + IMDB présents
- [ ] `<streamdetails>` dans les NFO épisode

### Après Phase 9 (Artwork)

- [ ] Images téléchargées au bon endroit avec les bons noms
- [ ] Film : poster + landscape
- [ ] Série : poster + landscape + season posters
- [ ] Skip si fichier existe déjà

### Après Phase 10 (Episode rename)

- [ ] Dossiers `Saison XX/` créés
- [ ] Épisodes renommés `S01E01 - Titre.ext`
- [ ] Sous-titres associés renommés aussi
- [ ] Dry-run ne déplace rien

### Après Phase 11 (Movie orchestrator)

- [ ] `scrape_movie(dir)` enchaîne : match → NFO → artwork
- [ ] Skip si .nfo existe déjà
- [ ] Retourne `ScrapeResult` correct

### Après Phase 12 (TVShow orchestrator)

- [ ] `scrape_tvshow(dir)` enchaîne : match → tvshow.nfo → artwork → saisons → rename → episode NFO
- [ ] Skip si tvshow.nfo existe déjà
- [ ] Gère les séries multi-saisons
- [ ] **Handoff V2→V3** : renomme `Show Name/` → `Show Name (Year)/` après matching API
- [ ] **Handoff V2→V3** : gère le cas d'un dossier déjà renommé avec année (pas de re-rename)

### Après Phase 13 (CLI → V4)

- [ ] `personalscraper scrape --dry-run` fonctionne end-to-end
- [ ] `personalscraper scrape --interactive` propose les matchs
- [ ] Les .nfo contiennent le genre (lisible par V4 genre_mapper)
- [ ] Les médias non matchés sont dans le rapport
