# Phase 7 — TVDB Migration

**Type**: impl
**Goal**: Migrate `scraper/tvdb_client.py` (565 LOC) → `api/metadata/tvdb.py`. Bootstrap auth at init, unwrap TVDB `data` envelope, return typed models. Also move tenacity helpers to `core/http_helpers.py` and delete `scraper/http_retry.py` + `scraper/providers.py`.

## Gate (prereq)

Phase 6 complete. `docs/reference/tvdb-api.md` exists. 11 golden samples in `docs/reference/_samples/tvdb/`. Token TTL = 30 days confirmed. All particularities documented.

## Lessons from Phase 6 (real API calls)

| #   | Finding                                                             | Impact on Phase 7                                                                   |
| --- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| 1   | ALL responses wrapped in `{"status": "success", "data": ...}`       | Provider MUST unwrap `resp["data"]` before parsing                                  |
| 2   | Language codes are 3-char (`fra`, `eng`, `spa`)                     | Migrate `_TVDB_LANG_MAP` from `scraper/_shared.py`                                  |
| 3   | Token TTL = 30 days (confirmed from JWT `exp`)                      | Bootstrap once at init, no runtime refresh                                          |
| 4   | Artwork types are numeric IDs (2=Poster, 3=Background, 7=ClearLogo) | Hardcoded mapping in parsers                                                        |
| 5   | `first_release` (not `release_date`) for movies                     | Parser must check both field names                                                  |
| 6   | `score` is integer popularity rank (e.g. 3434), not rating          | `MediaDetails.rating = None` for TVDB                                               |
| 7   | Search results include `remote_ids` array                           | Can cross-reference TMDB IMDB IDs without extra calls                               |
| 8   | Episodes paginated 100/page, 0-based with `links.next`              | Iterate pages for seasons with >100 episodes                                        |
| 9   | `/series/{id}/extended` includes ALL episodes (all seasons)         | Use `/episodes/default` with required `page` param + optional `season` filter                                     |
| 10  | Image URLs are full URLs (no base+size assembly)                    | Direct `artwork["image"]` — no URL building needed                                  |
| 11  | No keywords or notations endpoints                                  | `get_keywords()` → `NotImplementedError`, `get_notations()` → `NotImplementedError` |
| 12  | Empty search returns `{"status": "success", "data": []}`            | NOT an error — return empty list                                                    |
| 13  | Login needs `POST /login` with `{"apikey": "..."}` body             | Bootstrap transport uses `transport.post("/login", data=...)`                       |
| 14  | Error format: `{"status": "failure", "message": "..."}`             | No `status_code` — `ApiError(provider_code=0, message=data["message"])`             |

## Sub-phases

### 7.1 — Build `api/metadata/_tvdb_parsers.py`

Extract response → typed-model parsers first (pure functions, testable with golden samples).

Parser functions:

```python
def unwrap(data: dict) -> dict | list:
    """Strip TVDB envelope. Raises ApiError on 'failure' status."""

def parse_search_result(raw: dict, provider: str) -> SearchResult:
    """Map TVDB search item → SearchResult.

    Fields: name, tvdb_id (→ provider_id), type (movie|series → media_type),
    year, overview, image_url (→ poster_url), translations.
    remote_ids available for cross-reference but not mapped to SearchResult.
    """

def parse_media_details(raw: dict, provider: str, media_type: str) -> MediaDetails:
    """Map TVDB series/movie extended → MediaDetails.

    series: name, id (uuid → provider_id), overview, firstAired (→ year/release),
    averageRuntime (→ runtime_minutes), genres (array of names), score (→ skip),
    artworks (→ parse via parse_artwork), remoteIds (→ external_ids),
    nameTranslations (→ title), overviewTranslations.

    movie: name, first_release (NOT release_date!), runtime (→ runtime_minutes),
    score, artworks, remoteIds, genres.
    """

def parse_artwork(raw: dict, artwork_types: dict[int, str]) -> ArtworkItem:
    """Map TVDB artwork object → ArtworkItem.

    type mapping (confirmed from /artwork/types live call):
    1=Banner → skip, 2=Poster → poster, 3=Background → backdrop,
    5=Icon → skip, 7=Clear Logo → landscape, 15=Season Poster → season_poster

    image URL is already full URL — use directly.
    """

def parse_episode(raw: dict) -> EpisodeInfo:
    """Map TVDB episode object → EpisodeInfo.

    Fields: number (→ episode_number), name (→ title), overview,
    aired (→ air_date), runtime (→ runtime_minutes, nullable).
    """

def parse_video(raw: dict) -> Video:
    """Map TVDB trailer object → Video.

    Fields: url (extract YouTube key from URL), name, type.
    TVDB trailers are less structured than TMDB — may not have site/key.
    """

def parse_season_details(episodes_raw: list, provider: str, tv_id: str, season_num: int) -> SeasonDetails:
    """Map TVDB episodes list → SeasonDetails."""

def map_language(pipeline_code: str) -> str:
    """Map 2-char pipeline code → 3-char TVDB code. Fra → fra, en → eng, etc."""
```

**Unit tests**: `tests/unit/test_tvdb_parsers.py` — fed with golden samples:

- `test_unwrap_success` — envelope stripping
- `test_unwrap_failure_raises_api_error` — error → ApiError
- `test_search_series_parser` → golden `search_series.json`
- `test_search_movie_parser` → golden `search_movie.json`
- `test_series_extended_parser` → golden `series_extended.json`
- `test_movie_extended_parser` → golden `movie_extended.json`
- `test_episode_parser` → golden `episodes_default.json`
- `test_artwork_type_mapping` → golden `artwork_types.json`
- `test_empty_search` → golden `search_empty.json`
- `test_lang_map_fr_to_fra` → `map_language("fr") == "fra"`
- `test_lang_map_en_to_eng` → `map_language("en") == "eng"`
- `test_lang_map_unknown_fallback` → `map_language("xx") == "eng"`

**Commit**: `feat(api-unify): add TVDB response parsers with golden tests`

### 7.2 — Build `api/metadata/tvdb.py`

1. Class `TVDBClient(MetadataClient)`. `REQUIRED_CREDS = ["TVDB_API_KEY"]`.

2. Bootstrap login at init:

```python
def __init__(self, api_key: str, language: str = "fr-FR") -> None:
    bootstrap_policy = TransportPolicy(
        provider_name="tvdb-bootstrap",
        base_url="https://api4.thetvdb.com/v4",
        auth=NoAuth(),
        timeout_seconds=15,
    )
    with HttpTransport(bootstrap_policy) as bootstrap:
        resp = bootstrap.post("/login", data={"apikey": api_key})
    jwt = resp["data"]["token"]

    main_policy = TVDBClient.policy(jwt)
    super().__init__(transport=HttpTransport(main_policy), language=language)
    self._artwork_types: dict[int, str] | None = None
```

3. Class method `policy(cls, jwt_token, *, circuit=None) → TransportPolicy`:

```python
return TransportPolicy(
    provider_name="TVDB",
    base_url="https://api4.thetvdb.com/v4",
    auth=BearerAuth(jwt_token),
    timeout_seconds=15.0,
    retry=RetryPolicy(max_attempts=4),
    circuit=circuit or CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
    rate_limit=RateLimitPolicy(requests_per_second=20),
)
```

4. Drop `TVDBError`, `requests`, manual retry, etc.

5. Migrate `_TVDB_LANG_MAP` from `scraper/_shared.py` into `api/metadata/tvdb.py`.

6. **Response unwrapping**: Every response goes through `unwrap()`:

```python
def _get(self, path, params=None):
    raw = self._transport.get(path, params=params)
    return unwrap(raw)  # strips {"status": "success", "data": ...}
```

7. Lazy-load artwork types (cache after first fetch from `/artwork/types`).

8. All public methods return typed models.

Methods:

| Method                                       | Endpoint                                     | Returns              |
| -------------------------------------------- | -------------------------------------------- | -------------------- |
| `search(title, year, media_type)`            | `GET /search`                                | `list[SearchResult]` |
| `get_details(media_id, media_type)`          | `GET /{type}/{id}/extended`                  | `MediaDetails`       |
| `get_artwork_urls(media_id, media_type)`     | Reuses extended response                     | `list[ArtworkItem]`  |
| `get_season(tv_id, season)`                  | `GET /series/{id}/episodes/default?season=N` | `SeasonDetails`      |
| `get_videos(media_id, media_type, language)` | From extended `trailers`                     | `list[Video]`        |
| `get_keywords(...)`                          | Not supported → `NotImplementedError`        | —                    |
| `get_notations(...)`                         | Not supported → `NotImplementedError`        | —                    |
| `search_series(title, year)`                 | `GET /search?type=series`                    | `list[SearchResult]` |
| `get_series(series_id)`                      | `GET /series/{id}/extended`                  | `MediaDetails`       |
| `get_movie(movie_id)`                        | `GET /movies/{id}/extended`                  | `MediaDetails`       |
| `get_series_episodes(series_id, season)`     | `GET /series/{id}/episodes/default`          | `SeasonDetails`      |
| `map_language(pipeline_code)`                | Static                                       | `str`                |

**Commit**: `feat(api-unify): migrate TVDB client to api/metadata/tvdb.py`

### 7.3 — Extraction check at 600 LOC

If `api/metadata/tvdb.py` exceeds 600 LOC after migration, `_tvdb_parsers.py` already absorbs parsing (committed in 7.1). If still over 600:

- Extract `_tvdb_endpoints.py` — path constants.

**Commit (if needed)**: `refactor(api-unify): extract TVDB parsers/endpoints`

### 7.4 — Update consumers + delete old modules

Find all importers:

```bash
rg "from personalscraper\.scraper\.tvdb_client import|TVDBError" personalscraper/ tests/
rg "_TVDB_LANG_MAP" personalscraper/ tests/
```

Rewrite:

- `TVDBClient` → `from personalscraper.api.metadata.tvdb import TVDBClient`
- `TVDBError` → `from personalscraper.api._contracts import ApiError`
- `_TVDB_LANG_MAP` → moved into `tvdb.py` (not exported; call `client.map_language()` instead)

Delete:

- `scraper/tvdb_client.py`
- `scraper/providers.py` (now zero consumers)
- `_TVDB_LANG_MAP` from `scraper/_shared.py` (if only used by TVDB)

```bash
git rm personalscraper/scraper/tvdb_client.py
git rm personalscraper/scraper/providers.py
```

**Commit**: `refactor(api-unify): rewire TVDB consumers and delete tvdb_client / providers`

### 7.5 — Move tenacity helpers to `core/http_helpers.py` + rewire `artwork.py`

`scraper/http_retry.py` exposes `build_retry_logger` + `make_retryable_predicate` still consumed by `scraper/artwork.py`. After tvdb_client.py deletion, `artwork.py` is the only consumer.

1. Create `personalscraper/core/http_helpers.py` with ONLY the two helpers and their direct dependencies (`_RETRYABLE_STATUS_CODES`, `_retry_after_from_exception`).
2. Update `scraper/artwork.py`: import from `core/http_helpers`.
3. Verify no other consumer:

```bash
rg "from personalscraper\.scraper\.http_retry import" personalscraper/ tests/
```

**Commit**: `refactor(api-unify): move tenacity helpers to core/http_helpers.py and rewire artwork.py`

### 7.6 — Delete `scraper/http_retry.py`

```bash
git rm personalscraper/scraper/http_retry.py
```

**Commit**: `refactor(api-unify): delete scraper/http_retry.py`

### 7.7 — Phase 7 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.tvdb import TVDBClient; assert TVDBClient.REQUIRED_CREDS == ['TVDB_API_KEY']"
python -c "from personalscraper.core.http_helpers import build_retry_logger, make_retryable_predicate"
! rg "tvdb_client" personalscraper/ tests/ --files-with-matches
! rg "TVDBError" personalscraper/ tests/
! rg "scraper.http_retry" personalscraper/ tests/ --files-with-matches
! rg "scraper.providers" personalscraper/ tests/ --files-with-matches
```

**Commit**: `chore(api-unify): phase 7 gate — tvdb migration done`

## Field Mapping Cheat Sheet (real API → typed model)

| Raw TVDB Field                | Typed Model Field                 | Notes                                                    |
| ----------------------------- | --------------------------------- | -------------------------------------------------------- |
| `data[*].name`                | `SearchResult.title`              |                                                          |
| `data[*].tvdb_id` (int)       | `SearchResult.provider_id` (str)  | `str(raw["tvdb_id"])`                                    |
| `data[*].type`                | `SearchResult.media_type`         | `series→tv`, `movie→movie`                               |
| `data[*].year`                | `SearchResult.year`               | Already int                                              |
| `data[*].overview`            | `SearchResult.overview`           |                                                          |
| `data[*].image_url`           | `SearchResult.poster_url`         | Full URL, use directly                                   |
| `data.name`                   | `MediaDetails.title`              |                                                          |
| `data.firstAired`             | `MediaDetails.year`               | Extract `int(d[:4])`                                     |
| `data.first_release`          | `MediaDetails.year`               | Movie variant! Not `release_date`                        |
| `data.averageRuntime`         | `MediaDetails.runtime_minutes`    | Series only; may be null                                 |
| `data.runtime`                | `MediaDetails.runtime_minutes`    | Movie only; may be null                                  |
| `data.genres[]` (names)       | `MediaDetails.genres` (list[str]) | Direct array of genre name strings                       |
| `data.score` (int)            | _(skip)_                          | Popularity rank, not user rating                         |
| `data.artworks[*].image`      | `ArtworkItem.url`                 | Full URL, use directly                                   |
| `data.artworks[*].type` (int) | `ArtworkItem.type` (str)          | Map: 2→poster, 3→backdrop, 7→landscape, 15→season_poster |
| `data.remoteIds[]`            | `MediaDetails.external_ids`       | `{src["name"]: src["id"]}` for TMDB/IMDB                 |
| `data.episodes[*].number`     | `EpisodeInfo.episode_number`      |                                                          |
| `data.episodes[*].name`       | `EpisodeInfo.title`               |                                                          |
| `data.episodes[*].aired`      | `EpisodeInfo.air_date`            | ISO date string                                          |
| `data.episodes[*].runtime`    | `EpisodeInfo.runtime_minutes`     | Nullable                                                 |
| `data.trailers[*].url`        | `Video.key`                       | Extract YouTube ID from URL                              |
