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

ffprobe returns ISO 639-2/B codes (`fre`), Kodi NFO expects 639-2/T (`fra`). Always convert via `ISO_639_2_B_TO_T` mapping in `mediainfo.py` (20 codes differ).

## NFO Invariants

- `_is_nfo_complete()` in `scraper.py` validates NFO has parsable XML + at least one `<uniqueid>` with non-empty text — used for fast-skip and corrupt NFO detection.
- Verify `nfo_ids` check requires at least one of TMDB or IMDB (not both). Missing one is WARNING, missing both is ERROR. Some recent films (e.g. "Libre antenne") have TMDB but no IMDB yet.

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
