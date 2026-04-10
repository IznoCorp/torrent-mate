# V3 — SCRAPE : Plan d'implémentation

> Scraping metadata, génération NFO, artwork, renommage épisodes

## Phases

| #   | Phase                                  | Fichier                                                  | Status |
| --- | -------------------------------------- | -------------------------------------------------------- | ------ |
| 1   | Naming patterns + mediainfo            | [phase-01-foundations.md](phase-01-foundations.md)       | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_          |                                                          | [ ]    |
| 2   | Clients API (TMDB + TVDB)              | [phase-02-api-clients.md](phase-02-api-clients.md)       | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_          |                                                          | [ ]    |
| 3   | Confidence scoring + matching          | [phase-03-matching.md](phase-03-matching.md)             | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_          |                                                          | [ ]    |
| 4   | NFO generator (movie, tvshow, episode) | [phase-04-nfo.md](phase-04-nfo.md)                       | [ ]    |
| ·   | _Contrôle de cohérence P4→P5_          |                                                          | [ ]    |
| 5   | Artwork downloader + episode renaming  | [phase-05-artwork-rename.md](phase-05-artwork-rename.md) | [ ]    |
| ·   | _Contrôle de cohérence P5→P6_          |                                                          | [ ]    |
| 6   | Scraper orchestrator + CLI + tests     | [phase-06-orchestrator.md](phase-06-orchestrator.md)     | [ ]    |
| ·   | _Contrôle de cohérence V3→V4_          |                                                          | [ ]    |

## Dépendances entre phases

```
Phase 1 (patterns + mediainfo) ──┐
                                  ├──▶ Phase 4 (NFO) ──┐
Phase 2 (API clients) ──▶ Phase 3 (matching) ──────────┤
                                                        ├──▶ Phase 6 (orchestrator)
                                  Phase 5 (artwork) ────┘
```

P1 et P2 sont indépendantes. P3 dépend de P2. P4 dépend de P1+P3. P5 dépend de P2. P6 dépend de tout.

## Contrôles de cohérence

### Après Phase 1 (Foundations → API clients)

- [ ] `NamingPatterns.format()` produit les bons noms de fichiers
- [ ] `extract_stream_info()` retourne les infos codec/audio/subtitle
- [ ] Les patterns correspondent exactement à ceux de MediaElch

### Après Phase 2 (API clients → Matching)

- [ ] `TMDBClient.search_movie()` retourne des résultats pour "The Boys"
- [ ] `TVDBClient.search_series()` retourne des résultats pour "Shrinking"
- [ ] Le fallback TMDB pour les séries fonctionne
- [ ] Rate limiting et retry fonctionnent

### Après Phase 3 (Matching → NFO / Artwork)

- [ ] `score_match()` donne > 0.8 pour un match exact titre + année
- [ ] `score_match()` donne < 0.5 pour un mauvais match
- [ ] Le mode interactif propose les résultats correctement

### Après Phase 4 (NFO → Artwork)

- [ ] Le XML généré est valide et parseable
- [ ] Les NFO contiennent `<streamdetails>` quand mediainfo est disponible
- [ ] Le format est identique à celui de MediaElch (tags, structure, encoding)

### Après Phase 5 (Artwork + Rename → Orchestrator)

- [ ] Les images sont téléchargées aux bons emplacements
- [ ] Les noms de fichiers artwork suivent les patterns MediaElch
- [ ] Les épisodes sont renommés au format `S01E01 - Titre.ext`
- [ ] Les dossiers `Saison XX/` sont créés correctement

### Après Phase 6 (Orchestrator → V4)

- [ ] `personalscraper scrape --dry-run` fonctionne end-to-end
- [ ] Les .nfo sont générés pour films et séries
- [ ] Le genre est lisible dans les .nfo (pour V4 genre_mapper)
- [ ] Les médias non matchés sont reportés (pour les notifications V5)
