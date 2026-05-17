# Design — Provider-IDs (Multi-Provider IDs Propagation + Capabilities Refactor)

**Codename**: `provider-ids`
**SemVer**: minor (0.14.0 → 0.15.0)
**Branch target**: `feat/provider-ids`
**Date**: 2026-05-17
**Status**: Design validated — ready for `/implement:plan`

## 1. Problem Statement

Le pipeline scrape TV n'écrit aucun `<uniqueid>` sur les NFOs épisode pour la majorité des shows. Diagnostiqué pendant le run pipeline-monitor 2026-05-17-09h24 — 6 shows en staging (Dexter New Blood, American Dad!, Top Chef, Stranger Things Tales from '85, LOL Qui rit sort !, The Boys) ont des sibling NFOs sans `<uniqueid>`. FROM (2022), généré par un code path historique différent, est le seul à porter `<uniqueid type="tvdb">` + `<uniqueid type="imdb">` correctement.

**Root cause tracée (5 layers, validée post-api-unify HEAD `323c1b4`)** :

| Layer                | File:Line                                                                                          | Défaut                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Provider fetcher     | `personalscraper/scraper/tv_service.py:742-772` (`_build_episode_map`)                             | Payload épisode réduit à `{"title", "still_path"}` — IDs jetés au fetch                                  |
| Episode matcher      | `personalscraper/scraper/episode_manager.py:153-158,177-183,202-208` (`match_episode_files`)       | Ne propage que `season`, `episode`, `api_title`, `still_path`, `fallback`                                |
| NFO generator caller | `personalscraper/scraper/tv_service.py:874-887` (`_generate_episode_nfos`)                         | Hardcode `"id": "", "tvdb_id": ""` dans `episode_data`                                                   |
| NFO renderer         | `personalscraper/scraper/nfo_generator.py:401-419` (`generate_episode_nfo`)                        | Omet correctement `<uniqueid>` quand vide — seule couche conforme au design, mais reçoit des `""`        |
| Drift validator      | `personalscraper/scraper/existing_validator.py:184-186` (check #4 de `verify_tvshow_scrape_drift`) | Ne valide que l'existence du sibling NFO, pas son contenu → drift passe → `scrape_fast_skip` se perpétue |

Le défaut est **structurel** (data jetée à la source), pas local. Fix superficiel impossible.

## 2. Scope (élargi au-delà du fix DEV #2)

Cette feature ne se limite pas au fix du bug. Elle pose les fondations architecturales de la gestion **multi-provider** sur tout `personalscraper/api/`. Elle inclut :

1. **Fix DEV #2** : propagation des IDs TVDB/TMDB/IMDB depuis le fetch jusqu'au NFO épisode.
2. **Hiérarchie scrape strictement séparée** : TVDB primaire → TMDB info+fallback → IMDb info. Pas de cross-contamination entre familles d'IDs (mémoire `feedback_multi_provider_ids_separation`).
3. **Ratings collectés au scrape** : OMDb fournit IMDb rating + RT rating + Metacritic rating. Stockés en DB et copiés dans le NFO (format Plex prioritaire, compat Kodi).
4. **Schéma DB unifié** : `external_ids_json` (unique source de vérité) + `ratings_json` + `canonical_provider`. Drop des colonnes legacy `tmdb_id`/`imdb_id`/`tvdb_id`.
5. **Capabilities composées** : refonte des contrats `api/` en `Protocol`s atomiques. Plus de Protocol monolithique. Tous les sous-packages `api/metadata/`, `api/tracker/`, `api/torrent/`, `api/notify/` adoptent le modèle. Aucun module laissé derrière.
6. **Tracker registry priority-aware** : extension de `TrackerRegistry` existant pour supporter une priorité par type de média (`priority_by_media_type` dans `config/tracker.json5`).
7. **Backfill auto + CLI manuelle** : commande `personalscraper indexer --backfill-ids` qui scanne toute la library pour combler les gaps IDs et ratings. Auto-trigger après `process` quand un gap est détecté sur le show scrapé.

## 3. User Specification (verbatim, normalisée)

Trois familles d'identifiants stockées **séparément** : **TVDB**, **TMDB**, **IMDb**. Chaque famille couvre l'ID série et les IDs épisode (quand applicable).

### Hiérarchie scrape (TV)

1. **TVDB primaire** : recherche série + fetch épisodes. Si succès → source canonique du scrape (title, plot, aired, etc.). NFOs depuis TVDB.
2. **TMDB info+fallback** : recherche série + épisodes **après** le canonical fetch (sequential, Q1). IDs stockés (DB + NFO `<uniqueid type="tmdb">`) mais pas de re-scrape — TVDB reste canonique.
3. **TMDB canonical fallback** : si TVDB échoue (404, no match, circuit open après retry), TMDB devient le canonical.
4. **IMDb info** : ID toujours recherché via TVDB `remote_ids` ou TMDB `external_ids`, **re-validé** via OMDb (Q5=B). Jamais source canonique de scrape. Sert au tracker search, dédup, recommender futur.
5. **RT info** : rating récupéré via OMDb. Pas d'ID RT distinct exposé par OMDb (documenté). Stocké dans `ratings_json`.

### Invariants

- **Pas de cross-contamination** : `<uniqueid type="tvdb">` contient un ID TVDB authentique. Un fix qui écrirait un ID TMDB sous tag `tvdb` est un bug.
- **Absence non-bloquante** : missing une famille = warning verify (pas error) tant que la canonique est présente.
- **Idempotence par famille** : chaque step pipeline (sort/clean/scrape/verify/dispatch/indexer) peut **reprendre, créer, ou corriger** les IDs d'une famille manquante **sans écraser** une famille existante. Re-runner `process` sur un show TVDB-canonical qui a déjà ses TMDB xref ne re-scrape pas.

### Décisions brainstorm (6 open questions résolues)

| #   | Question                    | Décision                                                                                |
| --- | --------------------------- | --------------------------------------------------------------------------------------- |
| Q1  | Concurrency xref            | **Sequential** (TVDB canonical d'abord, puis xref TMDB)                                 |
| Q2  | Backfill scheduling         | **Hybride** : auto post-`process` si gap + CLI `personalscraper indexer --backfill-ids` |
| Q3  | DB schema                   | **Colonne `external_ids_json`** unique (drop colonnes legacy)                           |
| Q4  | Legacy NFO repair           | **Réécriture NFO + update DB** ensemble (Kodi/Plex lisent le NFO)                       |
| Q5  | TVDB↔TMDB xref trust        | **Toujours re-valider** via appel TMDB/IMDb get (2 appels), confirme title/year         |
| Q6  | `<uniqueid default="true">` | **Famille canonique** (celle qui a scrapé) reçoit `default="true"`                      |

## 4. Architecture overview

### Couches

```
┌──────────────────────────────────────────────────────────────┐
│  scraper/           (orchestration, business logic)          │
│  ─ tv_service.py       — fetch+xref+nfo (TV)                 │
│  ─ movie_service.py    — fetch+xref+nfo (Movies)             │
│  ─ episode_manager.py  — match files ↔ episodes              │
│  ─ existing_validator  — drift checks                        │
│  ─ nfo_generator.py    — NFO XML rendering                   │
└──────────────────────┬───────────────────────────────────────┘
                       │ (consume capabilities, never HTTP directly)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  api/                (transport + capability contracts)      │
│  ─ _contracts.py     — Protocols partagés (HasName, etc.)    │
│  ─ metadata/                                                  │
│      _contracts.py   — Searchable, Tv/MovieDetailsProvider,  │
│                         EpisodeFetcher, RatingProvider,       │
│                         IDValidator, IDCrossRef               │
│      tvdb.py         — TVDbClient (compose 5 capabilities)   │
│      tmdb.py         — TMDbClient (compose 6 capabilities)   │
│      imdb.py         — IMDbClient (compose 3 capabilities)   │
│      rotten_tomatoes.py — RTClient (compose 1 capability)    │
│      omdb.py         — OMDbAdapter (backend, internal only)  │
│  ─ tracker/                                                   │
│      _contracts.py   — TorrentSearchable, CategoryListable,  │
│                         FreeleechAware, TorrentDetailsProvider│
│      _registry.py    — TrackerRegistry (priority-aware)      │
│      lacale.py / c411.py — composent capabilities            │
│  ─ torrent/                                                   │
│      _contracts.py   — TorrentLister, TorrentInspector,      │
│                         AuthenticatedClient                   │
│      qbittorrent.py / transmission.py — composent            │
│  ─ notify/                                                    │
│      _contracts.py   — Notifier, HealthChecker (migrés de _base) │
│      telegram.py / healthchecks.py — composent               │
└──────────────────────────────────────────────────────────────┘
```

**Règle d'or** : le code dans `scraper/` ne touche jamais HTTP directement. Il consomme uniquement des capabilities. Si un client est remplacé (OMDb → API IMDb officielle), seule la classe client change, le scraper reste intact.

### Capabilities (Protocols runtime-checkable)

Définies dans `api/_contracts.py` (global) et `api/{metadata,tracker,torrent,notify}/_contracts.py` (par domaine).

**Metadata** :

```python
class HasName(Protocol):
    provider_name: str

class Searchable(Protocol):
    def search(self, title: str, year: int | None = None) -> list[SearchResult]: ...

class MovieDetailsProvider(Protocol):
    def get_movie(self, provider_id: str) -> MovieDetails: ...

class TvDetailsProvider(Protocol):
    def get_tv(self, provider_id: str) -> TvDetails: ...

class EpisodeFetcher(Protocol):
    def get_episodes(self, series_id: str, season: int) -> list[EpisodeDetails]: ...

class RatingProvider(Protocol):
    def get_rating(self, provider_id: str) -> Notation | None: ...

class IDValidator(Protocol):
    def validate_id(self, provider_id: str, expected_title: str,
                    expected_year: int | None) -> bool: ...

class IDCrossRef(Protocol):
    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        """Returns {'tmdb': 'M', 'imdb': 'ttN', ...}"""
        ...

class ArtworkProvider(Protocol):
    def get_artwork_urls(self, media_id: str, media_type: MediaType) -> list[ArtworkItem]: ...

class KeywordProvider(Protocol):
    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]: ...

class VideoProvider(Protocol):
    def get_videos(self, media_id: str, media_type: MediaType, language: str) -> list[Video]: ...

class RecommendationProvider(Protocol):
    def get_recommendations(self, media_id: str, media_type: MediaType) -> list[Recommendation]: ...
```

Les 11 capabilities couvrent les 9 méthodes du `MetadataProvider` monolithique existant + 2 nouvelles (IDValidator, IDCrossRef).

**Tracker** :

```python
class TorrentSearchable(Protocol):
    def search(self, query: str, year: int | None = None,
               media_type: str | None = None) -> list[TorrentResult]: ...

class CategoryListable(Protocol):
    def get_categories(self) -> dict[str, str]: ...

class FreeleechAware(Protocol):
    def is_freeleech(self, torrent_id: str) -> bool: ...

class TorrentDetailsProvider(Protocol):
    def get_details(self, torrent_id: str) -> TorrentDetails: ...
```

**Torrent** :

```python
class TorrentLister(Protocol):
    def get_completed(self) -> list[TorrentItem]: ...
    def get_all_hashes(self) -> set[str]: ...

class TorrentInspector(Protocol):
    def get_content_path(self, torrent: TorrentItem) -> Path: ...

class AuthenticatedClient(Protocol):
    def login(self) -> None: ...
```

**Notify** (Protocols **déjà existants** dans `api/notify/_base.py:17,35` — la feature les migre vers `_contracts.py` avec `@runtime_checkable`, **sans rename ni changement de signature**) :

```python
class Notifier(Protocol):
    def send(self, message: str, parse_mode: str = "HTML") -> bool: ...
    def send_report(self, report: PipelineReport) -> bool: ...

class HealthChecker(Protocol):
    def ping_start(self) -> None: ...
    def ping_success(self) -> None: ...
    def ping_fail(self) -> None: ...
```

### Composition par client

```python
class TVDbClient(Searchable, TvDetailsProvider, EpisodeFetcher, IDValidator,
                 IDCrossRef, ArtworkProvider): ...
class TMDbClient(Searchable, MovieDetailsProvider, TvDetailsProvider,
                 EpisodeFetcher, IDValidator, IDCrossRef,
                 ArtworkProvider, KeywordProvider, VideoProvider, RecommendationProvider): ...
class IMDbClient(IDValidator, RatingProvider, IDCrossRef): ...  # via OMDb
class RottenTomatoesClient(RatingProvider): ...                  # via OMDb
class OMDbAdapter: ...                                            # backend interne

class LaCaleClient(TorrentSearchable, CategoryListable, FreeleechAware): ...
class C411Client(TorrentSearchable, CategoryListable): ...

class QBitClient(TorrentLister, TorrentInspector, AuthenticatedClient): ...
class TransmissionClient(TorrentLister, TorrentInspector): ...

class TelegramNotifier(Notifier): ...       # nom réel: TelegramNotifier (telegram.py:49)
class HealthcheckClient(HealthChecker): ...  # nom Protocol réel: HealthChecker (pas HealthBeacon)
```

### Helpers consommateurs

```python
# api/_helpers.py (nouveau, optionnel)
def gather_ratings(providers: list[Any], provider_id: str) -> list[Notations]:
    """Collect ratings from all RatingProvider-capable providers.

    Returns the raw ``Notations`` dataclass instances (existing type from
    ``api.metadata._base``). The scraper layer normalizes them into the
    internal ``Notation`` format for NFO generation.
    """
    results: list[Notations] = []
    for p in providers:
        if isinstance(p, RatingProvider):
            ratings = p.get_rating(provider_id)
            if ratings:
                results.extend(ratings)
    return results

def gather_cross_refs(providers: list[Any], canonical_id: str) -> dict[str, dict[str, str]]:
    return {p.provider_name: p.get_cross_refs(canonical_id)
            for p in providers if isinstance(p, IDCrossRef)}
```

**Cas exception typée** : `ProviderFeatureUnavailable(provider, feature, reason)` levée par un client _qui déclare_ une capability mais où une donnée précise est absente structurellement (ex : OMDb retourne un payload sans entrée Rotten Tomatoes pour ce film). Le caller catch et continue. Pour la simple absence de donnée (RT rating null), `return None` suffit.

**Note — `Notation` vs `Notations`** : Le codebase existant a une dataclass `Notations` (pluriel) dans `api/metadata/_base.py:149` utilisée pour la désérialisation des réponses API (champs : `provider`, `source`, `score`, `votes_count`). Cette feature introduit `Notation` (singulier) comme type **interne** pour le flux NFO/generator (champs : `source`, `value`). La conversion `Notations → Notation` se fait dans le scraper (normalisation du format avant passage au NFO generator). Les deux types coexistent : `Notations` reste dans `api/metadata/_base.py` (API layer), `Notation` est défini dans `scraper/` ou `api/_helpers.py` (business layer).

## 5. Data flow (nominal + fallback)

### Nominal — Show TVDB-canonical

```
1. TVDb.search("Show Name", year) → SearchResult(tvdb_series_id=N, remote_ids={tmdb:M, imdb:"ttN"})
2. TMDb.get_tv(M) → re-valid title/year → confirm tmdb_series_id (Q5=B)
3. IMDb.validate_id("ttN", title, year) → confirm imdb_series_id (Q5=B)
   IMDb.get_rating("ttN") → Notation(source="imdb", value="8.5/10")
4. RT.get_rating("ttN") → Notation(source="rotten_tomatoes", value="87%") | None
5. scraper.tv.scrape_tvshow_canonical(provider=tvdb):
   - TVDb.get_tv(N) + TVDb.get_episodes(N, season) pour chaque saison
   - écrit tvshow.nfo :
       <uniqueid type="tvdb" default="true">N</uniqueid>
       <uniqueid type="imdb">ttN</uniqueid>
       <ratings>
         <rating name="themoviedb" default="true" max="10"><value>...</value></rating>
         <rating name="imdb" max="10"><value>8.5</value></rating>
         <rating name="rottentomatoes" max="100"><value>87</value></rating>
       </ratings>
   - écrit Saison NN/SxxExx - Title.nfo :
       <uniqueid type="tvdb" default="true">EP_N</uniqueid>
       <uniqueid type="imdb">ttEP</uniqueid>  (si TVDB le fournit)
6. scraper.tv._xref_enrichment (sequential, Q1) :
   - TMDb.get_tv_season(M, season) pour chaque saison déjà fetchée
   - merge tmdb_episode_id dans matched dict (json_set "$.tmdb.episode_id" if not exists)
   - réouvre chaque episode NFO, ajoute :
       <uniqueid type="tmdb">EP_M</uniqueid>  (pas default)
7. Persist DB (atomique avec write NFO) :
   media_item.external_ids_json = {
     "tvdb": {"series_id": "N", "episode_id": "EP_N"},
     "tmdb": {"series_id": "M", "episode_id": "EP_M"},
     "imdb": {"series_id": "ttN", "episode_id": "ttEP"}
   }
   media_item.ratings_json = {
     "imdb": "8.5/10",
     "rottentomatoes": "87%",
     "themoviedb": "8.0"
   }
   media_item.canonical_provider = "tvdb"
```

### Fallback — TVDB échoue

```
1'. TVDb.search FAIL (404 / no match / circuit-open)
2'. TMDb.search("Show Name", year) → tmdb_series_id (canonical bascule)
3'. IMDb.validate_id (depuis TMDb.external_ids.imdb_id)
    IMDb.get_rating
4'. RT.get_rating
5'. scraper.tv.scrape_tvshow_canonical(provider=tmdb) :
    - TMDb.get_tv + TMDb.get_tv_season
    - écrit NFOs avec <uniqueid type="tmdb" default="true">
6'. xref TVDB sequential : tente TVDb.search par titre, si succès enrichit avec tvdb_id
7'. Persist : canonical_provider = "tmdb", default uniqueid sur tmdb (Q6=A)
```

### Idempotence

- Re-runner `process` sur le même show : `scrape_fast_skip` si toutes familles canoniques OK ET drift validator pass.
- Si une famille xref manque (ex : tmdb_episode_id absent mais tvdb OK et canonical tvdb) : le backfill auto post-process la comble sans re-scraper.
- Le drift validator renforcé (voir §6.5) catch les NFOs sans canonical uniqueid → trigger re-scrape complet.

### Error handling

| Cas                                              | Comportement                                | Log                                                 |
| ------------------------------------------------ | ------------------------------------------- | --------------------------------------------------- |
| TVDb search 404                                  | Bascule TMDb canonical                      | INFO `tvdb_search_no_match`                         |
| TVDb circuit open                                | Bascule TMDb canonical                      | WARNING `tvdb_circuit_open_fallback_tmdb`           |
| TVDb + TMDb fail simultanés                      | Skip ce show, log error, continue           | ERROR `show_match_failed` (existant)                |
| TMDb re-valid step 2 fail                        | `tmdb_series_id` non-écrit, scrape continue | WARNING `tmdb_id_validation_skipped` (existant)     |
| IMDb re-valid step 3 fail                        | `imdb_series_id` non-écrit, scrape continue | WARNING `imdb_id_validation_skipped` (nouveau)      |
| RT rating step 4 fail                            | `rt_rating` None, scrape continue           | INFO `rt_rating_unavailable` (nouveau)              |
| xref TMDb step 6 fail (TVDB-canonical OK)        | NFOs canoniques valides, xref tmdb manquant | WARNING `xref_tmdb_unavailable` (nouveau)           |
| Backfill auto post-scrape fail                   | Scrape principal OK, retry au prochain run  | WARNING `backfill_ids_post_scrape_failed` (nouveau) |
| OMDb API key absent                              | IMDb + RT skip silencieux, scrape continue  | ERROR `omdb_unavailable` (1×/run)                   |
| Drift validator catch missing canonical uniqueid | Trigger re-scrape complet                   | INFO `drift_episode_nfo_missing_canonical_uniqueid` |

## 6. Modules modifiés et ajoutés

### 6.1 Nouveaux modules `api/`

- `personalscraper/api/_contracts.py` : **modifié** — ajout de `HasName` (Protocol). Le fichier existe déjà (post-api-unify) avec `MediaType`, `ProviderName`, `AuthMode`, `ApiError`, `CircuitOpenError`. On ajoute `HasName` sans toucher au contenu existant.
- `personalscraper/api/_helpers.py` : helpers `gather_*` (optionnel).
- `personalscraper/api/metadata/_contracts.py` : capabilities atomiques (7 Protocols). **Remplacement** du `MetadataProvider` Protocol monolithique existant (`api/metadata/_base.py:259`) par des capabilities composables. Le `MetadataClient` base class existant reste mais ses méthodes NotImplementedError sont conservées pour la rétrocompatibilité transitoire.
- `personalscraper/api/metadata/imdb.py` : `IMDbClient(IDValidator, RatingProvider, IDCrossRef)`. Wraps `OMDbAdapter`. Méthodes : `validate_id`, `get_by_id`, `get_rating`, `get_cross_refs`.
- `personalscraper/api/metadata/rotten_tomatoes.py` : `RottenTomatoesClient(RatingProvider)`. Wraps `OMDbAdapter`. Méthodes : `get_rating`. Documente la limitation (pas d'ID RT distinct via OMDb).
- `personalscraper/api/tracker/_contracts.py` : capabilities tracker.
- `personalscraper/api/torrent/_contracts.py` : capabilities torrent.
- `personalscraper/api/notify/_contracts.py` : capabilities notify. **Pas de création** — `api/notify/_base.py:17,35` contient déjà `Notifier(Protocol)` et `HealthChecker(Protocol)`. La sub-phase 1.5 les **migre** vers `_contracts.py` (git mv code + re-export depuis `_base.py` pour compat des imports existants), ajoute `@runtime_checkable`. Noms et signatures inchangés.

### 6.2 Modules `api/` refactorés

- `api/metadata/omdb.py` : devient strict `OMDbAdapter` (backend HTTP partagé). Plus consommé hors façades. Le module existant est déjà un client HTTP standalone — on le renomme/clarifie.
- `api/metadata/_base.py` : le `MetadataProvider` Protocol monolithique (9 méthodes, l. 259-324) est **décomposé** en capabilities atomiques dans `_contracts.py`. Le `MetadataClient` base class et les dataclasses (`SearchResult`, `MediaDetails`, `Notations`, `EpisodeInfo`, `SeasonDetails`, etc.) restent dans `_base.py`.
- `api/metadata/tvdb.py` : `TVDbClient` déclare maintenant 5 Protocols (via les nouvelles capabilities). Méthode `get_cross_refs(series_id)` extrait `remote_ids` du `get_series_details`.
- `api/metadata/tmdb.py` : `TMDbClient` déclare 6 Protocols. `get_cross_refs(series_id)` extrait `external_ids` (`imdb_id`, `tvdb_id`).
- `api/tracker/_base.py` : supprime `TrackerClient` Protocol monolithique (l. 102-129). Garde les dataclasses (`TrackerResult`, etc.) et `wrap_parser_drift`.
- `api/tracker/lacale.py` / `c411.py` : déclarent les capabilities qu'ils supportent (actuellement classes Python simples sans héritage de Protocol).
- `api/tracker/_registry.py.TrackerRegistry` : étendu pour `priority_by_media_type` (voir §6.7). Le `TrackerRegistry` existant (90 LOC) est typé avec `TorrentSearchable` au lieu de `TrackerClient`.
- `api/torrent/_base.py` : supprime `TorrentClient` Protocol monolithique (l. 42-67). Garde `TorrentItem` dataclass.
- `api/torrent/qbittorrent.py` / `transmission.py` : déclarent les capabilities.
- `api/notify/_base.py` : contient déjà `Notifier(Protocol)` et `HealthChecker(Protocol)` (lignes 17 et 35). **Pas de suppression** — migration vers `_contracts.py` + re-export pour rétrocompat des imports existants. Aucun rename, aucune nouvelle méthode.
- `api/notify/telegram.py:49` (`TelegramNotifier`) et `api/notify/healthchecks.py:46` (`HealthcheckClient`) : déclarent explicitement les Protocols qu'ils implémentaient déjà en duck-type.

### 6.3 Modules `scraper/` refactorés

- `scraper/tv_service.py` :
  - `_build_episode_map` (l. 742-772) : payload épisode étendu avec `tvdb_episode_id` et `imdb_episode_id` (depuis `remote_ids` TVDB épisode) pour le fetch TVDB, et `tmdb_episode_id` + `imdb_episode_id` (depuis TMDb `external_ids` épisode) pour le fetch TMDb.
  - **Nouvelle méthode** `_xref_enrichment(api_episodes, canonical_provider, series_ids, season_nums)` : sequential post-canonical, fetch xref opposite provider, json_set if not exists dans le matched dict.
  - **Nouvelle méthode** `_resolve_external_ids(canonical_provider, series_ids)` : appelle TVDb / TMDb / IMDb / RT pour validation + récup ratings série. Retourne `(external_ids_dict, ratings_dict)`.
  - `_generate_episode_nfos` (l. 818-905) : remplace les `"id": "", "tvdb_id": ""` hardcodés (l. 874-887) par les IDs propagés depuis `info`.
- `scraper/movie_service.py` : symétrique (résolution multi-provider + ratings pour films).
- `scraper/episode_manager.py.match_episode_files` (l. 153-158, 177-183, 202-208) : passthrough des `*_episode_id` keys du dict source vers le matched dict.
- `scraper/existing_validator.py.verify_tvshow_scrape_drift` check #4 (l. 184-186) : parse chaque sibling NFO, exige au moins un `<uniqueid>` non-vide de la famille canonique (lue dans `tvshow.nfo`). Retourne `(False, "episode_nfo_missing_canonical_uniqueid")` si violation.
- `scraper/nfo_generator.py` :
  - `generate_episode_nfo` (l. 389-479) : `default="true"` selon canonical (Q6=A), lit les IDs propagés. La logique uniqueid existante (l. 401-419) est déjà bien structurée — elle attend juste des valeurs non-vides.
  - `_add_ratings` (l. 534-554) : accepte une **liste** de `Notation` au lieu d'un seul dict — un `<rating>` enfant par source disponible. `themoviedb` garde `default="true"` (compat MediaElch existante).

### 6.4 Modules `verify/`

- `verify/checker.py` (l. 184 et autour) : 3 nouveaux checks TV :
  - `episode_canonical_uniqueid_present` (**ERROR** — bloque dispatch)
  - `episode_xref_secondary_id_present` (WARNING — TMDB manquant sur TVDB-canonical ou inverse)
  - `episode_xref_imdb_id_present` (WARNING — IMDb manquant)

### 6.5 Modules `indexer/`

- `indexer/schema.py` (l. 188-207) :
  - **Drop** colonnes legacy `tvdb_id`, `tmdb_id`, `imdb_id` sur `media_item`.
  - **Ajoute** :
    - `external_ids_json TEXT NOT NULL DEFAULT '{}'`
    - `ratings_json TEXT NULL`
    - `canonical_provider TEXT NULL CHECK(canonical_provider IN ('tvdb', 'tmdb'))`
  - Index : `CREATE INDEX idx_external_ids_tvdb ON media_item(json_extract(external_ids_json, '$.tvdb.series_id'))` (et équivalents tmdb, imdb).
- **Pas de script de migration générique** (mémoire `feedback_no_backcompat_before_v1`). À la place : la phase de modification du schéma inclut la modif **directe** de `library.db` réelle de l'unique instance dans le même PR — soit par reset+rescrape, soit par script ad-hoc one-shot consommé puis supprimé.
- `indexer/query.py` (l. 113, 302, 557) : `FieldSpec` adaptés à `json_extract`. Tous les `SELECT tmdb_id` / `WHERE tmdb_id = ?` deviennent `json_extract(external_ids_json, '$.tmdb.series_id')`.
- **Nouveau mode** `indexer/scanner/_modes/backfill_ids.py` :
  - Scanne `media_item`, détecte gaps IDs **et** ratings.
  - Appelle façades api/metadata pour combler (capability-based : `if isinstance(p, RatingProvider)` etc.).
  - Réécrit NFO si gap (Q4=A) au format Plex prioritaire.
  - Update DB transactionnellement avec le write NFO.
- **Nouvelle commande CLI** `personalscraper indexer --backfill-ids [--show=NAME] [--ratings-only] [--ids-only]` (Q2 partie manuelle).
- **Auto-trigger** dans `scraper/run.py` post-scrape OK d'un show : si gap détecté → fire backfill ciblé sur ce show (Q2 partie auto).

### 6.6 Modules `library/`, `conf/`, `trailers/` (consommateurs)

- `library/recommender.py` (l. 44, 63, 67, 158, 241, 267, 283) : `ids: Tuple[tmdb_id, imdb_id]` lit via `external_ids_json`.
- `library/scanner.py` : write via `external_ids_json` + `ratings_json`.
- `conf/models/preferences.py` (l. 76-95) : **supprime** `OverrideRule.imdb_id` (champ défini mais non utilisé dans le reste du codebase — pas de fichier `config/api.json5`). Si des overrides utilisateur existent dans `config/preferences.json5`, ils sont migrés directement dans la DB en une entrée par item. Adapte `indexer/query.py:113,302,557` qui référence `imdb_id` comme FieldSpec.
- `trailers/scanner.py.extract_nfo_ids` : lit `<uniqueid type="imdb">` (déjà compatible).
- `trailers/orchestrator.py.db_item.imdb_id` : devient property qui fait `json_extract(external_ids_json, '$.imdb.series_id')`.

### 6.7 Tracker registry priority-aware

`api/tracker/_registry.py.TrackerRegistry` :

- Constructor étendu : `__init__(trackers, priority, priority_by_media_type=None)`.
- Méthode `search_all(query, media_type=None)` :
  - Si `media_type` fourni ET `media_type in self._priority_by_media_type` → utilise cet ordre.
  - Sinon → utilise `self._priority` (comportement existant).
- Caller (auto-download futur ou commandes manuelles) passe `media_type` selon le classifier existant.

`config.example/tracker.json5` étendu :

```json5
{
  tracker: {
    providers: { lacale: {...}, c411: {...} },
    priority: ["lacale", "c411"],
    priority_by_media_type: {
      // override de la priorité par défaut pour ce type de média
      // tous types non listés → fall through sur `priority` global
      movie_french: ["c411", "lacale"],
      anime_jp: ["lacale", "c411"],
      tv_show_us: ["lacale"],
    },
    max_total_results: 50,
    max_per_tracker: 30,
    timeout_per_tracker: 15,
  },
}
```

Les slugs `media_type` sont alignés sur le classifier existant. Si la liste exhaustive de slugs n'existe pas encore, on la définit en accord avec le classifier dans le même PR.

## 7. NFO format (Plex prioritaire)

Format `<ratings>` multi-source, compatible Plex ET Kodi :

```xml
<episodedetails>
  <title>...</title>
  <uniqueid type="tvdb" default="true">N</uniqueid>
  <uniqueid type="tmdb">M</uniqueid>
  <uniqueid type="imdb">ttN</uniqueid>
  <ratings>
    <rating name="themoviedb" default="true" max="10">
      <value>8.0</value><votes>1000</votes>
    </rating>
    <rating name="imdb" max="10">
      <value>8.5</value><votes>50000</votes>
    </rating>
    <rating name="rottentomatoes" max="100">
      <value>87</value>
    </rating>
    <rating name="metacritic" max="100">
      <value>74</value>
    </rating>
  </ratings>
  <season>1</season>
  <episode>1</episode>
  ...
</episodedetails>
```

**Choix `default="true"`** :

- `<uniqueid default="true">` : sur la famille canonique (Q6=A).
- `<rating default="true">` : sur `themoviedb` (compat MediaElch existante, vote_count fiable).

Si une famille / source manque : le `<uniqueid>` ou `<rating>` correspondant est simplement absent.

## 8. Migration locale (BDD + config)

Conformément à `feedback_no_backcompat_before_v1` (mémoire) : aucun script de migration générique. À la place, à chaque phase du plan qui touche schema ou config :

1. **Modification schema `library.db`** : **Plan A (préféré) = reset+rescrape** : supprimer `library.db` et re-run `library-index --full` + `personalscraper process` sur tous les shows. **Plan B (fallback) = script SQL one-shot** : inclus dans le PR, exécuté, puis supprimé du tree par un commit suivant (utilisé seulement si le rescrape est trop coûteux). Backup obligatoire avant migration (7.2).
2. **Modification config** : la phase met à jour `config.example/*.json5` **et** `config/*.json5` réel de cette instance dans le même commit batch.
3. **Modification format NFO** : la phase accepte le re-scrape forcé via drift validator renforcé. Pas de coexistence ancien/nouveau format.

Le plan d'implémentation décompose ces modifications en phases séquencées (voir §10) pour permettre un rollback par phase si un bug est détecté pendant `/implement:phase`.

## 9. Testing strategy

**Coverage cible** : ≥ 90% lignes touchées (policy `test-coverage` v0.12.0), 100% branches d'erreur.

### Catégories de tests (~14)

**Unit (par module)** :

1. `api/metadata/imdb.py` : validate_id (match / reject), get_rating (parse), get_cross_refs, OMDb 404 → None.
2. `api/metadata/rotten_tomatoes.py` : get_rating (parse), missing RT entry → None.
3. `scraper/episode_manager.py` : propagate tvdb/tmdb/imdb episode_id, phantom remap preserves IDs, fallback no IDs.
4. `scraper/tv_service.py` : payload includes IDs, xref sequential (assertion order), xref failure does not break canonical, resolve_external_ids re-valid via api (Q5=B), nfo canonical default (Q6=A), fallback TVDB→TMDB.
5. `scraper/nfo_generator.py` : multi-source ratings in one `<ratings>`, themoviedb default true preserved, uniqueid default canonical.
6. `scraper/existing_validator.py` : drift rejects episode NFO without canonical uniqueid (regression DEV #2), accepts canonical only, accepts full.
7. `verify/checker.py` : 3 nouveaux checks (ERROR / WARNING).
8. `indexer/schema.py` + ad-hoc migration : copie tmdb_id → external_ids_json, drop legacy cols, idempotent on partial state.
9. `indexer/query.py` : json_extract WHERE, FieldSpec returns json path.
10. `indexer/scanner/_modes/backfill_ids.py` : detect missing xref / IDs / ratings, rewrite NFO when gap, no-op when complete, never overwrite canonical.

**Tracker registry priority-aware** :

- `test_tracker_registry_uses_per_media_type_priority_when_match`
- `test_tracker_registry_falls_back_to_global_priority_when_media_type_missing`
- `test_tracker_registry_skips_disabled_provider_in_priority`

**Capabilities Protocol** :

- `test_isinstance_rating_provider_runtime_check`
- `test_gather_ratings_filters_non_rating_providers`
- `test_gather_cross_refs_returns_dict_by_provider`

**Integration (HTTP mocked via `respx` / `vcr`)** : 11. `scraper full pipeline tvdb canonical with xref tmdb imdb rt` 12. `scraper full pipeline tmdb fallback when tvdb fails` 13. `process idempotent no changes on second run` 14. `process backfills xref on show with canonical only` 15. `existing recommender queries still work post external_ids_json`

**E2E** : 16. `e2e/test_provider_ids_e2e.py` : 1 fixture show (~3 episodes) + 1 cas backfill.

**Regression bug-reproducing** (mémoire `feedback_regression_test_per_bug`) : 17. `test_regression_dev2_episode_nfo_without_uniqueid_triggers_drift_rescrape` (fail before fix, pass after) 18. `test_regression_dev2_tvdb_fetch_propagates_episode_id`

### TDD sequencing (à détailler dans le plan)

| Phase | Focus                                                       | Tests                                | Code                                                                     |
| ----- | ----------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------ |
| 1     | Capabilities Protocol (api/\_contracts.py + per-domain)     | Protocol isinstance + gather helpers | Définir Protocols, ne pas encore appliquer                               |
| 2     | metadata fetchers — fix propagation IDs (REGRESSION DEV #2) | #17, #18, #4 partial                 | \_tvdb_fetch, \_tmdb_fetch, match_episode_files, \_generate_episode_nfos |
| 3     | metadata façades imdb/rt                                    | #1, #2                               | api/metadata/imdb.py, rotten_tomatoes.py                                 |
| 4     | drift validator renforcé                                    | #6                                   | verify_tvshow_scrape_drift check #4                                      |
| 5     | xref enrichment + resolve_external_ids                      | #4 full                              | tv_service.\_xref_enrichment, \_resolve_external_ids                     |
| 6     | NFO ratings multi-source                                    | #5                                   | nfo_generator.\_add_ratings + generate_episode_nfo Q6                    |
| 7     | DB schema + migration locale                                | #8, ad-hoc SQL one-shot              | indexer/schema.py, indexer/query.py                                      |
| 8     | backfill mode + CLI + auto-trigger                          | #10                                  | indexer/scanner/\_modes/backfill_ids.py, CLI, run.py auto                |
| 9     | verify checker 3 nouveaux checks                            | #7                                   | verify/checker.py                                                        |
| 10    | consommateurs (library, conf, trailers)                     | #15                                  | recommender, scanner, preferences, trailers/orchestrator                 |
| 11    | tracker capabilities + LaCale/C411                          | #11 tracker                          | api/tracker/\_contracts, refactor lacale/c411                            |
| 12    | tracker registry priority-aware                             | tracker registry tests               | TrackerRegistry extension, config tracker.json5                          |
| 13    | torrent capabilities + QBit/Transmission                    | #11 torrent                          | api/torrent/\_contracts, refactor qbittorrent/transmission               |
| 14    | notify capabilities + Telegram/Healthchecks                 | #11 notify                           | api/notify/\_contracts, refactor                                         |
| 15    | integration + e2e                                           | #11-16                               | wire all together                                                        |

Le plan détaillera les sub-phases par phase.

## 10. Risks & mitigations

| Risque                                                         | Mitigation                                                                                                           |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Re-scrape des 6 shows existants surcharge TVDB/TMDB rate limit | Circuit breaker existant + étalement temporel                                                                        |
| OMDb API key absente / invalide                                | RatingProvider catch → None returned, scrape continue. ERROR loggé 1×/run                                            |
| Capabilities augmente boilerplate                              | Helpers `gather_*` + Protocols runtime-checkable + isinstance filters                                                |
| Test surface explose (4 sous-packages × N capabilities)        | Tests par capability (un Protocol = un mock minimal), pas full client end-to-end pour chaque combo                   |
| Refactor Tracker/Torrent/Notify scope creep                    | Plan séquencé par sous-package (phases 11-14), chaque phase mergeable indépendamment si on doit split la PR          |
| Migration BDD/config oubliée sur une phase                     | Checklist explicite dans chaque phase du plan : "applique aussi la modif à `library.db` et/ou `config/*.json5` réel" |
| Backfill mode tape trop d'APIs en batch                        | Respect circuit breaker existant, `max_total_results` similaire, CLI `--show=NAME` pour scope ciblé                  |

## 11. Out-of-scope confirmés

- Provider SensCritique / Allociné (futur — capabilities prêtes pour l'extension, créer juste `SensCritiqueClient(RatingProvider)`).
- API IMDb officielle paid (Cinemagoer, IMDbPro) — futur swap du backend OMDb sans toucher `IMDbClient`.
- Recommender qui consomme les ratings — futur cycle dédié.
- Cron daily auto-trigger backfill — CLI manuelle + auto post-scrape suffisent.
- Async fetch parallel (Q1 = sequential strict).

## 12. Acceptance criteria

Une fois cette feature mergée :

1. Les 6 shows en staging actuels (Dexter, AmDad, Top Chef, Stranger Things '85, LOL Qui rit sort !, The Boys) doivent avoir leurs sibling NFOs épisode avec `<uniqueid type="tvdb">` ou `<uniqueid type="tmdb">` selon canonical, après re-scrape déclenché par drift validator renforcé.
2. `personalscraper process` sur un nouveau show TV produit des NFOs épisode avec au minimum la famille canonique + IMDb cross-ref.
3. `personalscraper indexer --backfill-ids` scanne toute la library et comble les gaps IDs et ratings sans toucher les familles canoniques.
4. La BDD `library.db` ne contient plus les colonnes legacy `tmdb_id`/`imdb_id`/`tvdb_id`. Les requêtes existantes (`library-search`, `library-report`, trailer scan, override rules) fonctionnent via `external_ids_json`.
5. `OverrideRule.imdb_id` n'existe plus dans `config/api.json5`. La config réelle de l'instance a été migrée dans le même PR.
6. `api/metadata/`, `api/tracker/`, `api/torrent/`, `api/notify/` exposent des capabilities `Protocol` composées. Aucun Protocol monolithique restant.
7. `TrackerRegistry.search_all(query, media_type="movie_french")` utilise `priority_by_media_type` quand présent.
8. Tests pass à 100%, coverage ≥ 90% sur les lignes touchées.
9. `personalscraper` CLI inchangée côté contract (commands, flags) — sauf ajout `personalscraper indexer --backfill-ids`.
10. Le pipeline-run dispatch attendant (8 items en staging actuellement) peut être relancé avec succès post-merge.

## 13. References

- Pipeline run source : `docs/pipeline-runs/2026-05-17-09h24-pipeline-run.md`
- Préparation draft : `docs/superpowers/roadmap/provider-ids/specs/DESIGN.md` (à supprimer au create-branch)
- ROADMAP entry : `ROADMAP.md` §P1 "Multi-Provider IDs Propagation (provider-ids)"
- Mémoires :
  - `feedback_multi_provider_ids_separation` — séparation stricte des familles
  - `feedback_no_backcompat_before_v1` — pas de retro-compat pre-1.0
  - `feedback_regression_test_per_bug` — test régression par bug
- Skill matrix conformité : `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md`
- Refs lazy-loaded : `docs/reference/scraping.md`, `docs/reference/indexer-json-shapes.md`, `docs/reference/tvdb-api.md`, `docs/reference/tmdb-api.md`
- Code refs (validé post-api-unify main `323c1b4`) :
  - `personalscraper/scraper/tv_service.py:742-772` `_build_episode_map`
  - `personalscraper/scraper/tv_service.py:818-905` `_generate_episode_nfos` (hardcoded `""` at 874-887)
  - `personalscraper/scraper/episode_manager.py:97-210` `match_episode_files` (matches at 153-158, 177-183, 202-208)
  - `personalscraper/scraper/existing_validator.py:94-186` `verify_tvshow_scrape_drift` (check #4 at 184-186)
  - `personalscraper/scraper/nfo_generator.py:389-554` `generate_episode_nfo` + `_add_ratings`
  - `personalscraper/api/metadata/_base.py:259-324` `MetadataProvider` Protocol (monolithique, 9 méthodes)
  - `personalscraper/api/tracker/_base.py:102-129` `TrackerClient` Protocol (monolithique)
  - `personalscraper/api/torrent/_base.py:42-67` `TorrentClient` Protocol (monolithique)
  - `personalscraper/api/tracker/_registry.py:1-90` `TrackerRegistry.search_all`
  - `personalscraper/conf/models/preferences.py:76-95` `OverrideRule.imdb_id`
  - `config.example/tracker.json5` priorité tracker
