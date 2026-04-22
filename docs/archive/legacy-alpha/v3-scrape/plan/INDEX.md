# V3 — SCRAPE : Plan d'implémentation

> Scraping metadata, génération NFO, artwork, renommage épisodes

## Phases

| #   | Phase                                | Fichier                                                            | Status |
| --- | ------------------------------------ | ------------------------------------------------------------------ | ------ |
| 1   | Naming patterns (fichier de config)  | [phase-01-naming-patterns.md](phase-01-naming-patterns.md)         | [x]    |
| ·   | _Contrôle de cohérence P1→P2_        |                                                                    | [x]    |
| 2   | Extraction mediainfo (streamdetails) | [phase-02-mediainfo.md](phase-02-mediainfo.md)                     | [x]    |
| ·   | _Contrôle de cohérence P2→P3_        |                                                                    | [x]    |
| 3   | Client API TMDB                      | [phase-03-tmdb-client.md](phase-03-tmdb-client.md)                 | [x]    |
| ·   | _Contrôle de cohérence P3→P4_        |                                                                    | [x]    |
| 4   | Client API TVDB                      | [phase-04-tvdb-client.md](phase-04-tvdb-client.md)                 | [x]    |
| ·   | _Contrôle de cohérence P4→P5_        |                                                                    | [x]    |
| 5   | Confidence scoring + matching films  | [phase-05-movie-matching.md](phase-05-movie-matching.md)           | [x]    |
| ·   | _Contrôle de cohérence P5→P6_        |                                                                    | [x]    |
| 6   | Matching séries (TVDB→TMDB fallback) | [phase-06-tvshow-matching.md](phase-06-tvshow-matching.md)         | [x]    |
| ·   | _Contrôle de cohérence P6→P7_        |                                                                    | [x]    |
| 7   | NFO generator — films                | [phase-07-nfo-movie.md](phase-07-nfo-movie.md)                     | [x]    |
| ·   | _Contrôle de cohérence P7→P8_        |                                                                    | [x]    |
| 8   | NFO generator — séries + épisodes    | [phase-08-nfo-tvshow.md](phase-08-nfo-tvshow.md)                   | [x]    |
| ·   | _Contrôle de cohérence P8→P9_        |                                                                    | [x]    |
| 9   | Artwork downloader                   | [phase-09-artwork.md](phase-09-artwork.md)                         | [x]    |
| ·   | _Contrôle de cohérence P9→P10_       |                                                                    | [x]    |
| 10  | Dossiers saison + renommage épisodes | [phase-10-episode-rename.md](phase-10-episode-rename.md)           | [x]    |
| ·   | _Contrôle de cohérence P10→P11_      |                                                                    | [x]    |
| 11  | Orchestrateur films                  | [phase-11-movie-orchestrator.md](phase-11-movie-orchestrator.md)   | [x]    |
| ·   | _Contrôle de cohérence P11→P12_      |                                                                    | [x]    |
| 12  | Orchestrateur séries                 | [phase-12-tvshow-orchestrator.md](phase-12-tvshow-orchestrator.md) | [x]    |
| ·   | _Contrôle de cohérence P12→P13_      |                                                                    | [x]    |
| 13  | CLI scrape + tests end-to-end        | [phase-13-cli-tests.md](phase-13-cli-tests.md)                     | [x]    |
| ·   | _Contrôle de cohérence V3→V4_        |                                                                    | [x]    |

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

- [x] Tous les patterns MediaElch reproduits exactement (32 tests, fichiers réels vérifiés)
- [x] `format()` fonctionne avec les variables de templating

### Après Phase 2 (Mediainfo via ffprobe)

- [x] `extract_stream_info()` retourne video/audio/subtitle (33 tests, mocked subprocess)
- [x] Langues converties ISO 639-2/B → T : `fre` → `fra`, `ger` → `deu` (20 codes)
- [x] Aspect ratio en decimal : `"16:9"` → `1.778` (pas la string brute)
- [x] Durée arrondie avec `round()` (cohérent MediaElch)
- [x] EAC3 + Atmos détecté → codec `"atmos"` dans le dict
- [x] Scantype présent (`"progressive"` ou `"interlaced"`)
- [x] Retourne None gracieusement si ffprobe absent (6 fallback tests)
- [x] HDR10/DolbyVision/HLG détection via color_transfer + side_data

### Après Phase 3 (TMDB client)

- [x] Search movie retourne des résultats (vérifier que `year` ne filtre pas strictement)
- [x] Get movie avec `append_to_response=credits,images,external_ids,release_dates` retourne tout en 1 appel
- [x] `include_image_language=fr,en,null` retourne bien 5x+ plus d'images que sans
- [x] Certification FR extractible de `release_dates` (type=3 theatrical)
- [x] Rate limiting + retry fonctionnent (HTTP 429 → backoff)
- [x] Erreurs TMDB correctement parsées (`status_code` interne, pas HTTP code)
- [x] La langue fr-FR est appliquée

### Après Phase 4 (TVDB client)

- [x] Login sans PIN fonctionne (clé Negotiated Contract)
- [x] Re-login automatique sur HTTP 401
- [x] Search series retourne des résultats (champs snake_case passés en l'état)
- [x] Get series extended (`short=true`) retourne détails + `remoteIds` + `genres` + `seasons[]`
- [x] Get season episodes avec `?season=N` retourne les épisodes filtrés (pas tous)
- [x] Traductions épisodes FR via `/episodes/{id}/translations/fra`
- [x] Mapping langue 3-chars fonctionne (`fra`, `eng`)
- [x] Artwork types cachés au démarrage (get_artwork_types() avec cache)
- [x] IDs croisés TMDB extraits avec le bon source type (12 pour séries, pas 10)

### Après Phase 5 (Movie matching)

- [x] `score_match()` est précis (14 tests avec cas réels, accents FR)
- [x] Match auto si confiance >= 0.8 (HIGH_CONFIDENCE threshold)
- [x] Skip si confiance < 0.5 en mode auto (LOW_CONFIDENCE threshold)
- [x] Mode interactif fonctionne (prompt_user_choice, 3 tests)

### Après Phase 6 (TVShow matching)

- [x] TVDB search → match fonctionne (utiliser `tvdb_id` du résultat, pas `id`)
- [x] Fallback TMDB si TVDB échoue
- [x] IDs croisés IMDB (type=2) et TMDB (type=12) extraits correctement (via get_remote_ids P4)
- [x] Épisodes d'une saison récupérés avec titres FR (traduction si disponible, fallback EN)
- [x] Mode interactif pour les séries aussi (prompt_user_choice partagé)

### Après Phase 7 (NFO movie)

- [x] XML valide et parseable (test_xml_is_parseable)
- [x] Structure identique à MediaElch (comparé avec The Piano Lesson NFO réel)
- [x] `<streamdetails>` présent quand mediainfo disponible (5 tests)
- [x] Tous les IDs (IMDB, TMDB) présents (test_uniqueid_imdb, test_uniqueid_tmdb)
- [x] `<generator><appname>personalscraper</appname>` (test_generator_appname)

### Après Phase 8 (NFO tvshow + episode)

- [x] `tvshow.nfo` XML identique à MediaElch
- [x] `episodedetails` XML identique à MediaElch
- [x] IDs TVDB + TMDB + IMDB présents (TMDB source type 12 pour séries, 10 pour films)
- [x] `<streamdetails>` dans les NFO épisode

### Après Phase 9 (Artwork)

- [x] Images téléchargées au bon endroit avec les bons noms
- [x] Film : poster + landscape
- [x] Série : poster + landscape + season posters
- [x] Skip si fichier existe déjà

### Après Phase 10 (Episode rename)

- [x] Dossiers `Saison XX/` créés
- [x] Épisodes renommés `S01E01 - Titre.ext`
- [x] Sous-titres associés renommés aussi
- [x] Dry-run ne déplace rien

### Après Phase 11 (Movie orchestrator)

- [x] `scrape_movie(dir)` enchaîne : match → NFO → artwork
- [x] Skip si .nfo existe déjà
- [x] Retourne `ScrapeResult` correct

### Après Phase 12 (TVShow orchestrator)

- [x] `scrape_tvshow(dir)` enchaîne : match → tvshow.nfo → artwork → saisons → rename → episode NFO
- [x] Skip si tvshow.nfo existe déjà
- [x] Gère les séries multi-saisons
- [x] **Handoff V2→V3** : renomme `Show Name/` → `Show Name (Year)/` après matching API
- [x] **Handoff V2→V3** : gère le cas d'un dossier déjà renommé avec année (pas de re-rename)

### Après Phase 13 (CLI → V4)

- [x] `personalscraper scrape --dry-run` fonctionne end-to-end
- [x] `personalscraper scrape --interactive` propose les matchs
- [x] Les .nfo contiennent le genre (lisible par V4 genre_mapper)
- [x] Les médias non matchés sont dans le rapport
