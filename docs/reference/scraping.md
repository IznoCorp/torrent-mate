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
