# Scraping Reference

TMDB/TVDB API gotchas, NFO invariants, ffprobe mapping, and artwork rules.

## Security

Never include API keys in documentation or brainstorming files — use `.env` references only.

## TMDB API

- The `year` search parameter is **NOT** a strict filter — it boosts relevance but returns other years too. Always validate client-side.
- Images: **ALWAYS** use `include_image_language=fr,en,null` — without it, 5×-31× fewer images are returned (backdrops especially).
- TMDB uses `fr-FR` / `en-US` language codes.

## TVDB API

- **API v4 is free for personal use** (< 50k$ revenue) but requires application + attribution.
- Two key types:
  - **Negotiated Contract** (free, no PIN needed) — pipeline uses this. Login with `{"apikey": "..."}` only, no `pin` field.
  - **User Subscription** (requires PIN).
- TVDB uses **3-char** language codes (`fra`, `eng`). Always convert between TVDB (`fra`) and TMDB (`fr-FR`) systems.
- **No "landscape" type** — use "Background" (type 3 for series, 15 for movies, 1920×1080).
- TVDB source type IDs for TMDB cross-ref: `10`=movies, `12`=TV series, `15`=people, `28`=collections — use the right one.

## ffprobe Language Codes

ffprobe returns ISO 639-2/B codes (`fre`), Kodi NFO expects 639-2/T (`fra`). Always convert via `ISO_639_2_B_TO_T` mapping in `personalscraper/scraper/mediainfo.py` (20 codes differ).

## NFO Invariants

- `is_nfo_complete()` (defined in `nfo_utils.py`, imported as `_is_nfo_complete` in scraper modules) validates NFO has parsable XML + at least one `<uniqueid>` with non-empty text — used for fast-skip and corrupt NFO detection.
- Movie verify `nfo_ids` check requires both TMDB and IMDB for a pass. TV shows require either TVDB or TMDB (IMDB not required). Missing one is WARNING (check fails but non-blocking), missing both is ERROR (blocking).

## Artwork Recovery

If NFO is valid but artwork is missing, scraper extracts TMDB ID from the NFO and **re-downloads artwork without re-scraping**.

## TMDB /videos Endpoint

- Endpoint: GET /movie/{id}/videos or /tv/{id}/videos?language={lang}
- Response shape: {id, results: [{id, iso_639_1, iso_3166_1, key, name, official, published_at, site, size, type}]}
- Filtering rules applied by trailer_finder.py:
  - site must be "YouTube" (Vimeo and others are ignored)
  - Prefer official=True over official=False
  - Prefer type in {Trailer, Teaser} over other types (Clip, Featurette, etc.)
  - First language match wins (trailers.languages order)
- The key field is the YouTube video ID (e.g. "dQw4w9WgXcQ")
- Full URL: https://www.youtube.com/watch?v={key}

## MediaElch

External metadata scraper — used as manual fallback. Claude does not interact with it directly.

## File Type Detection & Sorting

The `sort` step runs **before** scraping: it classifies each staging item and
moves it into the right category subdirectory so the scraper finds movies and
TV shows where it expects them. Lives in `personalscraper/sorter/`.

### guessit cleaner (`cleaner.py`)

`NameCleaner` wraps guessit to extract `title` / `year` / `season` / `episode`
from release filenames (handles French conventions VFF/VOSTFR/TRUEFRENCH/MULTi,
embedded years like _Blade Runner 2049_, double episodes, season packs). Titles
are NFC-normalized. When guessit finds **no year**, the cleaner locates the
title/metadata boundary using known metadata fields (`_METADATA_FIELDS`:
`screen_size`, `source`, `video_codec`, `audio_codec`, `release_group`,
`language`, `container`, …) plus alt-title tokens (`VOF`, `VO`, `AD`, `NOST`,
`VF2`, `VFI`), inserts a synthetic year at that boundary, and re-runs guessit so
noise tokens stop leaking into the title. Results are `lru_cache`d per name.

### FileType detection (`file_type.py`)

`detect_file_type(path)` classifies a single file by **extension first**, then
falls back to filename markers — there is no codec/resolution inspection at this
stage (that is ffprobe's job during scraping):

1. Non-video extension → `EBOOK` / `AUDIO` / `APP` (else `OTHER`).
2. Video extension (`VIDEO_EXTENSIONS`) → check the filename for season/episode
   markers (`_TVSHOW_PATTERN`: `S01E04`, bare `S03` season packs, `1x04`,
   `Saison NN`, `Season NN`). Marker present → `TVSHOW`; otherwise → `MOVIE`.
3. Unknown extension → `OTHER`.

The `FileType` enum and the extension frozensets live in
`personalscraper/core/media_types.py` (single source of truth). For
**directories**, `detect_dir_type(path)` returns `TVSHOW` immediately if the dir
name itself carries TV markers, else takes a **majority vote** over the video
children (non-video children like `.nfo`/`.jpg` are ignored).

### Strategy dispatch (`sorter.py` + `strategies.py`)

`Sorter.sort_item()` detects the type, then `_get_strategy(file_type)` maps it to
one of three `SortingStrategy` subclasses (no `RULES_MAP` — it is a direct
`if`/`if`/else on the enum):

- `MovieStrategy` → `{movies_dir}/Title (Year)/` (directory movies replace an
  existing same-named folder; crash-safe rename-backup-move).
- `TVShowStrategy` → `{tvshows_dir}/Show Name/` **without** the year — the year
  is appended later by the scraping step after API matching.
- `DefaultStrategy(file_type)` → the type's flat staging directory (ebooks,
  audio, apps, other).

Movie and TV strategies use the rapidfuzz matcher
(`matcher.find_matching_directory`, accent-insensitive WRatio with year /
length / adaptive-threshold guards) to merge into an existing folder instead of
creating a duplicate. Movies match with `respect_year=True`; TV shows with
`respect_year=False`.

### Category mapping (`conf/staging.py`)

Strategies resolve a `FileType` to a concrete on-disk path via
`find_by_file_type(config, file_type)` → the first `staging_dirs` entry whose
`file_type` matches → `staging_path(config, entry)`. The staging layout is
**config-driven** (the `staging_dirs` section of the config), never hardcoded;
the sorter also derives its skip-set from `staging_dirs` so already-sorted
subdirectories are not re-processed. A `FileType` with no matching staging entry
logs `sort_no_staging_entry` and falls back to the `OTHER` directory.

## Three semantics (Provider Registry)

The provider registry imposes the correct semantic per capability — a user CANNOT
change a capability's mode through config, only the ordered provider list.

| Mode    | Protocols                                                                       | Behavior                                                                                                                  | Return on exhaustion         |
| ------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| chain   | `Searchable`, `MovieDetailsProvider`, `TvDetailsProvider`, `EpisodeFetcher`     | Try providers in config order; first usable result wins.                                                                  | `raise ProviderExhausted`    |
| fan_out | `RatingProvider`                                                                | Call all eligible providers; aggregate results.                                                                           | Return empty list (no error) |
| locked  | `ArtworkProvider`, `KeywordProvider`, `VideoProvider`, `RecommendationProvider` | Use the provider that produced the original match. If it lacks the capability, translate the match's id via `IDCrossRef`. | Return `None`                |
| direct  | `IDValidator`, `IDCrossRef`                                                     | No semantic — dispatched by explicit provider name (`registry.get("tmdb").validate(id)`).                                 | N/A                          |

### Fallback triggers (chain)

A provider is skipped in `chain` iteration when:

1. **Circuit OPEN** — circuit breaker for the provider is open (logged DEBUG `registry_provider_skip` reason="circuit_open").
2. **Network exception** — timeout, 5xx, refused connection (logged WARNING `registry_provider_fail`).
3. **Empty result** — provider returns 200 with no candidates (logged DEBUG `registry_provider_skip` reason="empty_result").

Fuzzy-score-below-threshold and incomplete-field handling stay in the scrape layer
(domain logic), NOT at the registry. The registry's fallback triggers are
deterministic.

### Half-open eligibility

`HALF_OPEN` circuit state is treated as **eligible** by `chain` and `fan_out` (probe
semantics). The underlying `HttpTransport` lets exactly one request through; if it
fails, the transport raises `NetworkError`, the registry catches it and falls
through to the next provider in the same iteration. Do NOT exclude HALF_OPEN
providers — that defeats the probe.

### Configuration reference

See `docs/reference/architecture.md#provider-registry` for the module layout and
`config.example/providers.json5` for the user-facing config shape.

## Capability Cookbook

Six worked examples covering every production registry call shape. Each snippet
mirrors an actual call site (path + line) so the recipe can be traced back to
working code.

The patterns map onto the four semantics described above:

- `chain` — try providers in order, first usable result wins (Searchable,
  MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher).
- `fan_out` — call every eligible provider; aggregate results (RatingProvider).
- `locked` — bind to the provider that produced the match (Artwork, Keyword,
  Video, Recommendation); IDCrossRef escape if the bound provider can't serve.
- `direct` — `registry.get("tmdb")` / `registry.cross_ref(...)` for IDValidator,
  IDCrossRef, or non-Protocol APIs the registry doesn't model.

### Example 1 — `chain(Searchable)`: search a title across providers

Use this when you need a free-text search and want the first provider that
returns a non-empty result. Iterate the chain, catch the three classified
failure shapes, emit fallback events for the registry's per-call observability,
and fall through to `ProviderExhausted` when every provider failed.

```python
from personalscraper.api.errors import ApiError, CircuitOpenError
from personalscraper.api.metadata._contracts import Searchable
from personalscraper.api.metadata.registry import (
    AttemptOutcome,
    ProviderExhausted,
    RegistryProviderName,
)

attempted: list[AttemptOutcome] = []
last_exception: Exception | None = None
for provider in registry.chain(Searchable):  # type: ignore[type-abstract]
    name = getattr(provider, "provider_name", "?")
    try:
        results = provider.search(title, year=year)
    except CircuitOpenError as exc:
        last_exception = exc
        attempted.append(AttemptOutcome(provider=RegistryProviderName(name), reason="circuit_open"))
        continue
    except (ApiError, OSError) as exc:
        last_exception = exc
        attempted.append(
            AttemptOutcome(
                provider=RegistryProviderName(name),
                reason="network",
                detail=type(exc).__name__,
            )
        )
        continue
    if not results:
        attempted.append(AttemptOutcome(provider=RegistryProviderName(name), reason="empty_result"))
        continue
    return results  # first non-empty wins
raise ProviderExhausted(
    capability="Searchable",
    attempted=attempted,
    last_exception=last_exception,
)
```

**When to use this over the alternatives.** `chain` is the right choice when
any single provider answer is acceptable (search, details lookup). Pick
`fan_out` when you need every provider's contribution (ratings aggregation),
and `locked` when the answer must come from the provider that produced the
match (artwork must match the scraped metadata source).

### Example 2 — `chain(MovieDetailsProvider)`: fetch details with fallback

Production site: `personalscraper/scraper/movie_service.py:552` (matching) and
`movie_service.py:789` (details lookup). The pattern is identical to Example 1
but illustrates the **source-of-match invariant**: when iterating for details
after a successful match, skip providers whose `provider_name` does not match
`match.source` — cross-provider id translation is delegated to
`registry.cross_ref` (Example 5), not to chain re-iteration.

```python
from personalscraper.api.metadata._contracts import MovieDetailsProvider

for provider in registry.chain(MovieDetailsProvider):  # type: ignore[type-abstract]
    provider_name = getattr(provider, "provider_name", "?")
    if provider_name != match.source:
        continue  # source-of-match invariant — id space is provider-scoped
    if not isinstance(provider, MovieDetailsProvider):
        continue  # narrow the chain-overload union back to the called Protocol
    try:
        details = provider.get_movie(str(match.api_id))
        break
    except CircuitOpenError:
        registry._emit_provider_fallback(  # noqa: SLF001 — chain-iteration site
            capability="MovieDetailsProvider",
            from_provider=provider_name,
            reason="circuit_open",
            item={"provider_id": match.api_id, "media_type": "movie"},
        )
        continue
    except (ApiError, OSError) as exc:
        registry._emit_provider_fallback(  # noqa: SLF001
            capability="MovieDetailsProvider",
            from_provider=provider_name,
            reason="network",
            exc_type=type(exc).__name__,
            item={"provider_id": match.api_id, "media_type": "movie"},
        )
        continue
```

**When to use this over the alternatives.** `chain(MovieDetailsProvider)` is
the canonical way to resolve full movie metadata after a successful search.
Calling `registry.get("tmdb").get_movie(...)` directly would bypass the
circuit-breaker eligibility check and the fallback observability — only do
that for IDValidator-style unscoped fetches (Example 6).

### Example 3 — `fan_out(RatingProvider)`: aggregate ratings

Production site: `personalscraper/indexer/scanner/_modes/backfill_ids.py:625`.
`fan_out` returns a `FanOutResult` dataclass with `values` (eligible providers,
config order) and `attempted` (one `AttemptOutcome` per provider filtered out
by the circuit breaker). Empty `values` is **not** an error — that's the
defining contrast with chain.

```python
from personalscraper.api.metadata._contracts import RatingProvider

fan_out_result = registry.fan_out(RatingProvider)  # type: ignore[type-abstract]
entries: list[dict] = []
for provider in fan_out_result.values:
    source = getattr(provider, "provider_name", type(provider).__name__)
    if source not in needed_sources:
        continue
    try:
        ratings = provider.get_rating(imdb_id)
    except CircuitOpenError:
        # Circuit tripped between fan_out eligibility check and call —
        # count as empty contribution, do NOT abort the loop.
        continue
    entries.extend(_serialise(ratings, source))

# fan_out_result.attempted is populated by the registry — useful for
# downstream telemetry / partial-result audits.
```

**When to use this over the alternatives.** `fan_out` is the only correct
semantic when the goal is to _combine_ answers (each provider contributes
distinct ratings). Using `chain` would silently drop every rating after the
first non-empty one. The `RegistryFanOutCompleted` event fires automatically
on every call — subscribers can audit partial-result coverage without the
caller threading a flag.

### Example 4 — `locked(ArtworkProvider, match)`: identity-locked fetch

Production site: `personalscraper/scraper/trailer_finder.py:360` (illustrated
here with `VideoProvider`; `ArtworkProvider`/`KeywordProvider` follow the same
shape). `locked` returns a `LockedProvider[C]` carrying the resolved
`bound_id` (already cross-referenced if the match's own provider lacks the
capability). `None` signals total resolution failure — the registry emits
`LockedCapabilityUnresolved` for that case before returning.

```python
from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._contracts import VideoProvider
from personalscraper.api.metadata.registry import ProviderMatch, RegistryProviderName

match = ProviderMatch(
    provider=RegistryProviderName("tmdb"),
    id=str(tmdb_id),
    media_type=MediaType("movie"),
)
locked = registry.locked(VideoProvider, match)  # type: ignore[type-abstract, type-var]
if locked is None:
    return []  # LockedCapabilityUnresolved already emitted by the registry
videos = locked.provider.get_videos(locked.bound_id, MediaType("movie"), language="fr-FR")
```

**When to use this over the alternatives.** `locked` is the right choice for
capabilities where the answer must come from the **same provider as the
scraped match** (artwork that matches the TMDB-source metadata; keywords from
the TMDB taxonomy; trailers from TMDB's `/videos` endpoint). `chain` would let
a different provider's id contaminate the result. The IDCrossRef escape lives
inside `locked` itself — callers never call `cross_ref` manually for locked
capabilities.

### Example 5 — `cross_ref(match, target="tvdb")`: translate provider IDs

Production wire-up: invoked implicitly by `registry.locked()` step 2 (see
`registry/__init__.py:562`), and available as a direct call for callers that
need only the foreign id without a Protocol dispatch.

```python
from personalscraper.api.metadata.registry import ProviderMatch, RegistryProviderName
from personalscraper.api._contracts import MediaType

match = ProviderMatch(
    provider=RegistryProviderName("tmdb"),
    id=str(tmdb_id),
    media_type=MediaType("tv"),
)
tvdb_id = registry.cross_ref(match, target="tvdb")
if tvdb_id is None:
    # No translation path — match's provider has no IDCrossRef, or the
    # IDCrossRef call returned nothing for the target, or the target is
    # absent from the IDCrossRef section. Fail-soft and skip.
    return None
```

**When to use this over the alternatives.** Use the direct `cross_ref` only
when you need the raw foreign id (e.g. to seed an `external_ids` payload or
to enqueue a backfill task on a different provider). For dispatch of a
capability call on the foreign provider, prefer `locked()` — it does the
translation **and** returns the right provider in one call.

### Example 6 — `get("tmdb")`: direct dispatch for unscoped capabilities

Production sites: `personalscraper/scraper/tv_service_episodes.py:397`
(TMDB-specific episode hydration) and IDValidator usage in scraper internals.

```python
tmdb_client = registry.get("tmdb")
# `tmdb_client` is the raw provider instance. Use this for IDValidator,
# IDCrossRef, or provider-specific endpoints not modelled by a registry
# Protocol. The circuit breaker still applies on the HTTP layer, but
# eligibility is NOT pre-filtered as it is with chain/fan_out.
```

**When to use this over the alternatives.** Reserved for two cases: (1) the
capability is `direct` per the semantics table (IDValidator, IDCrossRef);
(2) the code path is provider-specific and the registry cannot model it
generically (e.g. `_fetch_videos_strict` duck-typing on TMDB in
`trailer_finder.py:373`). In all other cases the chain/fan_out/locked
operations are preferred — they carry the circuit-eligibility filter, event
emission, and graceful fallback.

### See also

- `docs/reference/indexer.md#registry-integration` — backfill_ids walkthrough
  combining `fan_out(RatingProvider)` and `chain(MovieDetailsProvider |
TvDetailsProvider)`.
- `docs/reference/external-ids-flow.md` — cross-provider id flow at the
  pipeline level (where `cross_ref` is the underlying mechanic).
- `docs/reference/architecture.md#provider-registry` — module layout and boot
  sequence.
