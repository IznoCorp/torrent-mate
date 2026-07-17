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
- **No cross-provider ID translation in TVDBClient**: it raises `NotImplementedError` for `IDCrossRef` / `get_cross_refs` (`api/metadata/tvdb.py`). Cross-provider ID mapping is handled at the registry level via `registry.cross_ref(match, target=...)` → the source provider's `get_cross_refs()` (`api/metadata/registry/__init__.py`). See [`external-ids-flow.md`](external-ids-flow.md).

## ffprobe Language Codes

ffprobe returns ISO 639-2/B codes (`fre`), Kodi NFO expects 639-2/T (`fra`). Always convert via `ISO_639_2_B_TO_T` mapping in `personalscraper/scraper/mediainfo.py` (20 codes differ).

## NFO Invariants

- `is_nfo_complete()` (defined in `nfo_utils.py`, imported as `_is_nfo_complete` in scraper modules) validates NFO has parsable XML + at least one `<uniqueid>` with non-empty text — used for fast-skip and corrupt NFO detection.
- Movie verify `nfo_ids` check requires both TMDB and IMDB for a pass: missing one is WARNING (check fails but non-blocking), missing both is ERROR (blocking).
- TV show verify `nfo_ids` check passes when either TVDB or TMDB is present (IMDB not required); missing both is always an ERROR (no WARNING tier).

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

## Batch Confidence & Decision Queue (S5 — scrape-arbiter)

S5 (`feat/scrape-arbiter`, ticket #184) changes how the batch scraper handles
uncertain matches. Before S5, the scraper auto-accepted every match with
confidence ≥ 0.5 — wrong mid-band matches slipped through silently, and
sub-0.5 items were parked in staging forever. S5 replaces the silent
auto-accept with an async decision queue the operator drains via the web
`/decisions` page or the `personalscraper scrape-resolve` CLI.

### Threshold constants

All thresholds live in [`personalscraper/scraper/confidence.py`](../personalscraper/scraper/confidence.py):

| Constant          | Value  | Meaning                                                      |
| ----------------- | ------ | ------------------------------------------------------------ |
| `LOW_CONFIDENCE`  | `0.5`  | Below this → item is skipped; decision row is additive.      |
| `HIGH_CONFIDENCE` | `0.8`  | At or above this → auto-accept (unless ambiguous).           |
| `AMBIGUITY_DELTA` | `0.05` | Runner-up within this gap of the winner → ambiguous trigger. |

### Three triggers

Classification is centralized in
[`personalscraper/scraper/decision_triage.py`](../personalscraper/scraper/decision_triage.py)
(`classify_decision_trigger`), called by both `movie_service.py` and
`tv_service.py`:

| Trigger           | Condition                                                 | Batch behavior (S5)                                                                                                                                                              |
| ----------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `below_threshold` | Best match confidence `< 0.5` or no match at all          | **Additive.** Item keeps `skipped_low_confidence` semantics (stays in staging). A `scrape_decision` row is created alongside so the operator can pick a provider ID manually.    |
| `mid_band`        | Best match confidence `≥ 0.5` and `< 0.8`                 | **Behavior change.** Replaces the historical auto-accept — `action="queued_for_decision"`. The item enters the decision queue for operator review instead of being auto-scraped. |
| `ambiguous`       | Best match `≥ 0.8` AND runner-up `≥ 0.5` AND gap `< 0.05` | **New for TV, existing for movies.** Both candidates are ≥ `LOW_CONFIDENCE` and too close to call — `action="queued_for_decision"`. Operator breaks the tie.                     |
| _(clean)_         | Best match `≥ 0.8`, no close runner-up                    | **Unchanged.** Auto-accept proceeds to NFO/artwork write as before.                                                                                                              |

### Detailed match variants

The scraper exposes two families of match functions per media kind:

- **`match_movie`** / **`match_tvshow`** — return only the best
  `MatchResult` (or `None`). Used by the fast path and existing callers
  that do not need the candidate list.
- **`match_movie_detailed`** / **`match_tvshow_detailed`** — return
  `(MatchResult | None, list[DecisionCandidate])` — the best match plus
  a top-5 scored candidate snapshot. Used during batch enqueue (to populate
  `candidates_json`) and by the `/api/decisions/{id}/search` endpoint
  (live provider search for the operator).

Both detailed variants live in `confidence.py` and follow the same
`rapidfuzz` WRatio + year-validation scoring as their non-detailed
counterparts. The candidate list is always at most 5 entries, sorted by
descending score.

### Decision queue drain

Decisions are drained through two surfaces:

1. **Web `/decisions` page** — operator reviews candidates, optionally
   searches with a corrected title/year, picks a provider ID, and resolves.
   See [`web-ui.md`](web-ui.md#interactive-scraping-s5--scrape-arbiter).
2. **CLI** — `personalscraper scrape-resolve <staging_path> --provider
tmdb|tvdb --id <provider_id>` fetches by ID through the existing service
   paths, writes NFO + artwork into the staging folder, and marks the
   decision `resolved`.

On the next pipeline run, a resolved item (valid NFO present) is seen as
`skipped_already_done` — verify/dispatch proceed normally.

### Event emission

Per enqueued item, an
`ItemProgressed(step="scrape", status="queued_for_decision", details={trigger, confidence, candidates_count})`
event is emitted on the EventBus. The `StepReport` counts `queued_for_decision`
separately in `counts`, and the enqueued paths are listed alongside
`unmatched_paths` for operator visibility.

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

Production site: `personalscraper/trailers/discovery/trailer_finder.py:360` (illustrated
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
