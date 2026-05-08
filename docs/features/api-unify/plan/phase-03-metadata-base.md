# Phase 3 — Metadata Family Base

**Type**: infra
**Goal**: Ship the `api/metadata/_base.py` Protocol + typed models so subsequent migration phases (TMDB, TVDB) and new providers (OMDB, Trakt) all conform to the same surface.

## Gate (prereq)

Phase 2 complete. Foundation + config in place.

## Sub-phases

### 3.1 — `api/metadata/__init__.py` + `_base.py`

Create:

- `personalscraper/api/metadata/__init__.py` (empty).
- `personalscraper/api/metadata/_base.py` containing:

**Typed models** (per DESIGN §4.2):

- `SearchResult` — provider, provider_id, title, year, media_type ("movie"|"tv"), overview, poster_url.
- `MediaDetails` — provider, provider_id, title, original_title, year, overview, genres, runtime_minutes, rating, images (list[ArtworkItem]), external_ids (dict[str, str]).
- `ArtworkItem` — type ("poster"|"landscape"|"season_poster"|"backdrop"), url, language, season.
- `Notations` — provider, source ("imdb"|"rotten_tomatoes"|"trakt"|"tmdb"|"metacritic"), score (float), votes_count.
- `Recommendation` — provider, provider_id, title, year, media_type, reason.
- `Video` — id, site ("youtube"|"vimeo"), key, type ("trailer"|"teaser"|"clip"), official, size, iso_639_1.
- `EpisodeInfo` — episode_number, title, overview, air_date, runtime_minutes.
- `SeasonDetails` — provider, tv_id, season_number, episodes (list[EpisodeInfo]).

All `@dataclass(frozen=True)` where possible. Use `Path | None` only for filesystem paths (none here).

**Protocol** (per DESIGN §4.1):

```python
@runtime_checkable
class MetadataProvider(Protocol):
    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def search(self, title: str, year: int | None = None,
               media_type: str = "movie") -> list[SearchResult]: ...
    def get_details(self, media_id: str, media_type: str = "movie") -> MediaDetails: ...
```

**Optional methods** declared as Protocol members but with a `MetadataClient` base class providing `NotImplementedError`-raising defaults:

```python
class MetadataClient:
    """Base class. Subclasses override capability methods they support;
    others raise NotImplementedError on call."""
    REQUIRED_CREDS: ClassVar[list[str]] = []

    def __init__(self, transport: HttpTransport, language: str = "fr-FR") -> None:
        self._transport = transport
        self._language = language

    @property
    def provider_name(self) -> str:
        return type(self).__name__.replace("Client", "").lower()

    def get_artwork_urls(self, media_id, media_type="movie"): raise NotImplementedError
    def get_keywords(self, media_id, media_type): raise NotImplementedError
    def get_videos(self, media_id, media_type, language): raise NotImplementedError
    def get_season(self, tv_id, season): raise NotImplementedError
    def get_notations(self, media_id, media_type): raise NotImplementedError
    def get_recommendations(self, media_id, media_type): raise NotImplementedError
```

**Commit**: `feat(api-unify): add metadata family base — Protocol + typed models`

### 3.2 — Tests for base

`tests/unit/test_api_metadata_base.py`:

- `MetadataClient.provider_name` resolves correctly for `TMDBClient`, `OMDBClient` etc. (using a fake subclass).
- `runtime_checkable` Protocol: a fake provider with required methods passes `isinstance(fake, MetadataProvider)`.
- Default `get_notations` raises `NotImplementedError` with a useful message.

**Commit**: `test(api-unify): add metadata base tests`

### 3.3 — Phase 3 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata._base import MetadataProvider, MetadataClient, SearchResult, MediaDetails, ArtworkItem, Notations, Recommendation, Video, EpisodeInfo, SeasonDetails"
```

**Commit**: `chore(api-unify): phase 3 gate — metadata base done`
