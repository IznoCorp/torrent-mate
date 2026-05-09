# Phase 5 — TMDB Migration

**Type**: impl
**Goal**: Migrate `scraper/tmdb_client.py` (770 LOC) → `api/metadata/tmdb.py`. Delete old module, update all imports, return typed models. Use golden samples from Phase 4 for mock testing.

## Gate (prereq)

Phase 4 complete. `docs/reference/tmdb-api.md` exists. 13 golden samples in `docs/reference/_samples/tmdb/`. All particularities documented.

## Lessons from Phase 4 (real API calls)

| #   | Finding                                                                      | Impact on Phase 5                                                                             |
| --- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | Search returns `genre_ids` (list[int]), details returns `genres` (list[obj]) | `_parse_search_result` must handle int array; `_parse_media_details` must handle object array |
| 2   | TV keywords uses `results` envelope, movies use `keywords`                   | `get_keywords()` must branch on media_type                                                    |
| 3   | `softcore` field present in search + details (TMDB v3 addition)              | Ignore — not mapped to any typed model                                                        |
| 4   | Video `id` is a string, not int                                              | `Video.id` is `str` (already correct in `_base.py`)                                           |
| 5   | `release_date` may be `""` for unreleased movies                             | Parse defensively with `try/except` when extracting year                                      |
| 6   | Images in 3 arrays: `backdrops`, `posters`, `logos`                          | Merge into `list[ArtworkItem]` with correct `type` mapping                                    |
| 7   | `iso_3166_1` field on videos (country, not language)                         | Ignore — `Video` model only carries `iso_639_1`                                               |
| 8   | `append_to_response` sub-requests = 1 API call                               | Always use `append_to_response` for details                                                   |
| 9   | Episode `runtime` may be null                                                | `EpisodeInfo.runtime_minutes` is `int \| None`                                                |
| 10  | Movie `runtime` may be null (unreleased)                                     | `MediaDetails.runtime_minutes` is `int \| None`                                               |
| 11  | Empty search returns HTTP 200 with `results: []`                             | `_search_paginated` must handle empty first page gracefully                                   |
| 12  | `total_pages` capped at 500 by TMDB                                          | `_search_paginated` must respect `max_pages` param                                            |
| 13  | `include_image_language=fr,en,null` controls image filtering                 | Pass from `MetadataConfig.defaults`                                                           |

## Sub-phases

### 5.1 — Build `api/metadata/_tmdb_parsers.py`

Extract response → typed-model parsers first (pure functions, testable without HTTP).
Use golden samples from `docs/reference/_samples/tmdb/` to drive parser tests.

Parser functions:

```python
def parse_search_result(raw: dict, provider: str) -> SearchResult:
    """Map TMDB search result → SearchResult.

    Fields used: id, title (movie) / name (tv), overview, release_date (movie) /
    first_air_date (tv), poster_path, genre_ids, original_language.

    media_type: 'movie' if 'title' in raw else 'tv'.
    year: int(release_date[:4]) or int(first_air_date[:4]), None if empty string.
    poster_url: f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "".
    """

def parse_media_details(raw: dict, provider: str) -> MediaDetails:
    """Map TMDB movie/tv details → MediaDetails.

    Fields used: id, title/name, original_title/original_name, overview,
    release_date/first_air_date, runtime (may be null), genres (list of {id,name}),
    vote_average, images (merged from backdrops+posters+logos), external_ids.

    runtime_minutes: raw['runtime'] or None.
    rating: raw['vote_average'] (0-10, float).
    external_ids: {'imdb': raw.get('imdb_id', '')} + raw.get('external_ids', {}).
    images: parse_artwork(raw.get('images', {})).
    """

def parse_artwork(images_raw: dict) -> list[ArtworkItem]:
    """Merge TMDB backdrops+posters+logos → list[ArtworkItem].

    Mapping:
    - backdrops[*] → ArtworkItem(type='backdrop', url=..., language=iso_639_1 or '')
    - posters[*]  → ArtworkItem(type='poster', url=..., language=iso_639_1 or '')
    - logos[*]    → ArtworkItem(type='landscape', url=..., language=iso_639_1 or '')

    Season posters (from season endpoint) use type='season_poster', season=<number>.
    URL built as f"https://image.tmdb.org/t/p/w780{file_path}" for posters,
    w1280 for backdrops, w500 for logos.
    """

def parse_video(raw: dict) -> Video:
    """Map TMDB video object → Video.

    Fields: id (str), site ('YouTube'/'Vimeo'), key, type (Trailer/Teaser/Clip/...),
    official (bool), size (int), iso_639_1 (str).
    """

def parse_episode(raw: dict) -> EpisodeInfo:
    """Map TMDB episode object → EpisodeInfo.

    Fields: episode_number, name→title, overview, air_date, runtime→runtime_minutes.
    runtime_minutes: raw['runtime'] or None.
    """

def parse_keywords(raw_keywords: dict, media_type: str) -> list[str]:
    """Extract keyword names. Branches on envelope:
    - movie: raw['keywords'] (list of {id, name})
    - tv: raw['results'] (list of {id, name})
    Returns list of keyword name strings.
    """
```

**Unit tests**: `tests/unit/test_tmdb_parsers.py` — fed with golden samples:

- `test_search_movie_parser` → golden `search_movie.json`
- `test_search_tv_parser` → golden `search_tv.json`
- `test_movie_details_parser` → golden `movie_details.json`
- `test_tv_details_parser` → golden `tv_details.json`
- `test_artwork_merges_three_arrays` → golden `movie_details.json` images
- `test_video_parser` → golden `movie_videos.json`
- `test_episode_parser` → golden `season_details.json`
- `test_keywords_movie_envelope` → golden `movie_keywords.json`
- `test_keywords_tv_envelope` → golden `tv_keywords.json`
- `test_empty_search` → golden `search_movie_empty.json`
- `test_parse_handles_empty_release_date` → fixture with `{"release_date": ""}`

**Commit**: `feat(api-unify): add TMDB response parsers with golden tests`

### 5.2 — Build `api/metadata/tmdb.py`

1. Class `TMDBClient(MetadataClient)`. `REQUIRED_CREDS = ["TMDB_API_KEY"]`.

2. Class method `policy(cls, api_key: str, *, circuit: CircuitPolicy | None = None) -> TransportPolicy`:

   ```python
   @classmethod
   def policy(cls, api_key: str, *, circuit: CircuitPolicy | None = None) -> TransportPolicy:
       return TransportPolicy(
           provider_name="TMDB",
           base_url="https://api.themoviedb.org/3",
           auth=BearerAuth(api_key),
           timeout_seconds=10,
           retry=RetryPolicy(max_attempts=4),
           circuit=circuit or CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
           rate_limit=RateLimitPolicy(requests_per_second=40),
       )
   ```

3. `__init__(self, transport: HttpTransport, language: str = "fr-FR", fallback_language: str = "en-US", prefer_local_title: bool = True)`.

4. All HTTP calls go through `self._transport.get(path, params=...)`.

5. **Drop**: `requests.Session`, `HTTPAdapter`, `Urllib3Retry`, tenacity decorators, `CircuitBreaker` instantiation, `TMDBError`.

6. All public methods return typed models. **Zero `dict[str, Any]` in signatures.**

7. `circuit` property returns `self._transport._circuit` (CircuitBreaker instance).

Methods:

| Method                                       | Endpoint                      | Returns              |
| -------------------------------------------- | ----------------------------- | -------------------- |
| `search(title, year, media_type)`            | `/search/{media_type}`        | `list[SearchResult]` |
| `get_details(media_id, media_type)`          | `/{media_type}/{id}` + append | `MediaDetails`       |
| `get_artwork_urls(media_id, media_type)`     | Reuses `get_details` images   | `list[ArtworkItem]`  |
| `get_keywords(media_id, media_type)`         | `/{media_type}/{id}/keywords` | `list[str]`          |
| `get_videos(media_id, media_type, language)` | `/{media_type}/{id}/videos`   | `list[Video]`        |
| `get_season(tv_id, season)`                  | `/tv/{id}/season/{n}`         | `SeasonDetails`      |
| `search_movie(title, year, **kwargs)`        | `/search/movie`               | `list[SearchResult]` |
| `search_tv(title, year, **kwargs)`           | `/search/tv`                  | `list[SearchResult]` |
| `get_movie(movie_id)`                        | `/movie/{id}`                 | `MediaDetails`       |
| `get_tv(tv_id)`                              | `/tv/{id}`                    | `MediaDetails`       |
| `get_tv_season(tv_id, season)`               | `/tv/{id}/season/{n}`         | `SeasonDetails`      |
| `get_image_url(path, size)`                  | N/A (static helper)           | `str`                |

`get_details` for movie uses `append_to_response=videos,images,keywords,external_ids`.
For TV, additionally includes season info if needed.

`_search_paginated()` kept as private helper, respects `max_pages` param (default 5 = 100 results).

**Commit**: `feat(api-unify): migrate TMDB client to api/metadata/tmdb.py`

### 5.3 — Extraction check at 600 LOC

If `api/metadata/tmdb.py` exceeds 600 LOC after migration, `_tmdb_parsers.py` already absorbs parsing (committed in 5.1). If still over 600:

- Extract `api/metadata/_tmdb_endpoints.py` — path constants and URL builders.
- Extract `_search_paginated` if needed.

Re-run `python3 scripts/check-module-size.py` after extraction.

**Commit (if extraction needed)**: `refactor(api-unify): extract TMDB parsers/endpoints`

### 5.4 — Update consumers + test imports

Find every importer:

```bash
rg "from personalscraper\.scraper\.tmdb_client import|from personalscraper\.scraper import tmdb_client" personalscraper/ tests/
rg "TMDBError" personalscraper/ tests/
```

Rewrite:

- `from personalscraper.scraper.tmdb_client import TMDBClient` → `from personalscraper.api.metadata.tmdb import TMDBClient`
- `from personalscraper.scraper.tmdb_client import TMDBError` → `from personalscraper.api._contracts import ApiError`
- Any `Video` import from old path → `from personalscraper.api.metadata._base import Video`
- Any consumer that did `result["title"]` on a TMDB return → `result.title` (typed model attribute access).

Construction site: the old `TMDBClient(api_key=...)` becomes:

```python
policy = TMDBClient.policy(api_key=os.environ["TMDB_API_KEY"])
transport = HttpTransport(policy)
client = TMDBClient(transport=transport, language=cfg.metadata.defaults.language)
```

Explicit consumer work:

- **`personalscraper/scraper/orchestrator.py`**: main TMDB construction site. Rewrite `TMDBClient(...)` to use `TMDBClient.policy(api_key, circuit=CircuitPolicy(...))` + `HttpTransport(policy)`. Preserve `circuit_breaker_threshold` / `circuit_breaker_cooldown` from `conf/models/scraper.py`.
- **`personalscraper/library/rescraper.py`**: update type imports and construction.
- **`personalscraper/trailers/orchestrator.py`**: preserve trailers-specific TMDB circuit from `config.trailers.circuit_breakers.tmdb_videos`. Pass custom `CircuitPolicy` to `TMDBClient.policy(...)`.
- **Any consumer using dict-shaped TMDB results** → convert to typed attribute access.

Update test files in the same commit.

**Commit**: `refactor(api-unify): rewire TMDB consumers and tests to api/metadata/tmdb`

### 5.5 — Delete `scraper/tmdb_client.py`

```bash
git rm personalscraper/scraper/tmdb_client.py
```

Also delete `scraper/providers.py` IF its only consumer was `tmdb_client.py` and `tvdb_client.py`. Otherwise wait for Phase 7. Verify:

```bash
rg "from personalscraper\.scraper\.providers import" personalscraper/ tests/
```

If still imported by `tvdb_client.py` (Phase 7 not yet done), `providers.py` stays.

**Commit**: `refactor(api-unify): delete scraper/tmdb_client.py`

### 5.6 — Phase 5 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.tmdb import TMDBClient; assert TMDBClient.REQUIRED_CREDS == ['TMDB_API_KEY']"
! rg "tmdb_client" personalscraper/ tests/ --files-with-matches
! rg "TMDBError" personalscraper/ tests/
```

Coverage delta vs Phase 4 baseline: ≥ 0.

**Commit**: `chore(api-unify): phase 5 gate — tmdb migration done`

## Field mapping cheat sheet (real API → typed model)

| Raw TMDB field                               | Typed Model field                 | Notes                                               |
| -------------------------------------------- | --------------------------------- | --------------------------------------------------- |
| `results[*].id` (int)                        | `SearchResult.provider_id` (str)  | Convert: `str(raw["id"])`                           |
| `results[*].title` / `name`                  | `SearchResult.title`              | `title` for movies, `name` for TV                   |
| `results[*].release_date` / `first_air_date` | `SearchResult.year`               | `int(d[:4])` if d else `None`                       |
| `results[*].poster_path`                     | `SearchResult.poster_url`         | Build full URL or keep raw path                     |
| `results[*].overview`                        | `SearchResult.overview`           | Direct mapping                                      |
| `results[*].genre_ids`                       | _(not mapped to SearchResult)_    | Genre IDs, not names. Omit from `SearchResult`.     |
| `id` (int)                                   | `MediaDetails.provider_id` (str)  | `str(raw["id"])`                                    |
| `title` / `name`                             | `MediaDetails.title`              |                                                     |
| `original_title` / `original_name`           | `MediaDetails.original_title`     |                                                     |
| `runtime` (int or null)                      | `MediaDetails.runtime_minutes`    | `raw["runtime"] or None`                            |
| `genres[*].name`                             | `MediaDetails.genres` (list[str]) | Extract names: `[g["name"] for g in raw["genres"]]` |
| `vote_average`                               | `MediaDetails.rating`             | float, 0-10 scale                                   |
| `images.backdrops`                           | `ArtworkItem(type="backdrop")`    | w1280                                               |
| `images.posters`                             | `ArtworkItem(type="poster")`      | w780                                                |
| `images.logos`                               | `ArtworkItem(type="landscape")`   | w500                                                |
| `videos.results[*].id`                       | `Video.id`                        | str                                                 |
| `videos.results[*].key`                      | `Video.key`                       |                                                     |
| `videos.results[*].site`                     | `Video.site`                      | "YouTube" or "Vimeo"                                |
| `videos.results[*].type`                     | `Video.type`                      | "Trailer"/"Teaser"/"Clip"/etc.                      |
| `videos.results[*].official`                 | `Video.official`                  | bool                                                |
| `videos.results[*].size`                     | `Video.size`                      | int                                                 |
| `keywords.keywords[*].name` (movie)          | `list[str]`                       | Movie envelope                                      |
| `keywords.results[*].name` (TV)              | `list[str]`                       | TV envelope — DIFFERENT                             |
| `episodes[*].episode_number`                 | `EpisodeInfo.episode_number`      |                                                     |
| `episodes[*].name`                           | `EpisodeInfo.title`               |                                                     |
| `episodes[*].runtime`                        | `EpisodeInfo.runtime_minutes`     | `raw["runtime"] or None`                            |
