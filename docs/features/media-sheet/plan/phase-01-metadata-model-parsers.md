# Phase 1 - Modele + parseurs

**Codename**: `media-sheet` . **Gate**: None (this is Phase 1 - no prior phase).

## Gate

> None - Phase 1. Feature branch `feat/media-sheet` is checked out, DESIGN.md is frozen (D1-D10), IMPLEMENTATION.md header exists with invariants.

## ANCHOR CORRECTION

- **DESIGN says** `_tmdb_parsers.py` / `_tvdb_parsers.py` exist, `MediaDetails` at `_base.py`.
- **Reality**: all confirmed. `MediaDetails` at `personalscraper/api/metadata/_base.py:107` (`@dataclass(frozen=True)`), last field `primary_backdrop_url` at line 155 - new fields go after this line. `parse_media_details` at `_tmdb_parsers.py:134` and `_tvdb_parsers.py:246`. Golden samples at `docs/reference/_samples/tmdb/movie_details.json` and `docs/reference/_samples/tvdb/movie_extended.json`. **No TV series golden sample exists** - must create one for TV-specific fields (`status`, `number_of_episodes`, `created_by`). `append_to_response` at `tmdb.py:241` and `:262` - currently `"videos,images,keywords,external_ids"`, needs `credits` (movies) or `aggregate_credits` (TV).

## Sub-phases

### 1.1 Extend `MediaDetails` with 4 optional fields

**Files**:
- `personalscraper/api/metadata/_base.py` (modify - add 4 fields at end of frozen dataclass, line 155)

**Implementation**:
- Append after `primary_backdrop_url` (line 155):
```python
director: str | None = None
series_status: str | None = None
episode_count: int | None = None
trailer_url: str | None = None
```
- Update docstring (lines 110-138) to document the 4 new Attributes.
- Frozen dataclass, default `None` - zero existing callers break.

**Tests**:
- No dedicated test - the dataclass is inert. Existing `test_api_metadata_base.py` tests still pass (no field list assertion).

**Gate**:
```bash
python -c "from personalscraper.api.metadata._base import MediaDetails; m=MediaDetails(provider='tmdb',provider_id='1'); assert m.director is None; print('OK')"
```

### 1.2 TMDB parser: extract director, series_status, episode_count, trailer_url

**Files**:
- `personalscraper/api/metadata/_tmdb_parsers.py` (modify - extend `parse_media_details` at line 134)
- `personalscraper/api/metadata/tmdb.py` (modify - add `credits`/`aggregate_credits` to `append_to_response` at lines 241 and 262)

**Implementation**:
- In `tmdb.py`, change line 241 and 262 `append_to_response` from `"videos,images,keywords,external_ids"` to:
  - Movies (line 241): `"videos,images,keywords,external_ids,credits"`
  - TV (line 262): `"videos,images,keywords,external_ids,aggregate_credits"`
- In `_tmdb_parsers.py` `parse_media_details`, before the `return MediaDetails(...)` statement:
  - `director`: if movie -> first `crew` member with `job == "Director"` from `raw.get("credits", {}).get("crew", [])`; if TV -> `created_by[0]["name"]` if present from `raw.get("created_by", [])`. Falls back to `None`.
  - `series_status`: `raw.get("status")` if TV (`is_tv is True`), else `None`.
  - `episode_count`: `raw.get("number_of_episodes")` if TV, else `None`.
  - `trailer_url`: from `raw.get("videos", {}).get("results", [])`, first video with `type == "Trailer"` and `site == "YouTube"` -> build `"https://www.youtube.com/watch?v=" + key`. `None` if no trailer.
- Pass the 4 new fields to the `MediaDetails(...)` constructor call (named, after existing fields). All fall back to `None` when the provider doesn't supply them - never empty string.

**IMPORTANT - ruff post-edit trap**: add the 4 fields to both the `MediaDetails(...)` constructor call AND the dataclass fields in one combined edit, or the PostToolUse ruff hook strips the new import/usage.

**Tests**:
- Create `tests/unit/api/metadata/test_tmdb_parser_media_sheet.py`:
  - Golden test with existing `docs/reference/_samples/tmdb/movie_details.json` -> asserts `director` is a non-empty string, `series_status` is `None` (movie), `episode_count` is `None` (movie), `trailer_url` is a YouTube URL or `None`.
  - Golden test with a new golden fixture `docs/reference/_samples/tmdb/tv_details.json` (capture from live TMDB `/tv/27205` with `append_to_response=videos,images,keywords,external_ids,credits,aggregate_credits`) -> asserts `series_status` is e.g. `"Ended"`, `director` from `created_by`, `episode_count` > 0.
  - Assert: fields never empty string when absent.

**Gate**:
```bash
python -m pytest tests/unit/api/metadata/test_tmdb_parser_media_sheet.py -v
```

### 1.3 TVDB parser: extract series_status, director

**Files**:
- `personalscraper/api/metadata/_tvdb_parsers.py` (modify - extend `parse_media_details` at line 246)

**Implementation**:
- In `_tvdb_parsers.py` `parse_media_details`:
  - `series_status`: `raw.get("status", {}).get("name")` when not a movie (`is_movie is False`, i.e. series) - this is the field DESIGN notes was previously discarded. `None` for movies.
  - `director`: TVDB series extended response may include `characters` array. Attempt to extract the first person with `isMovie == 0` and a director-type role. If the field shape isn't reliable under the current API version, leave `None` and document with a comment. Never invent.
  - `episode_count`: TVDB series extended doesn't carry a single `number_of_episodes` - leave `None` and document.
  - `trailer_url`: TVDB doesn't provide YouTube trailers - leave `None`.
- Pass the 4 new fields to the `MediaDetails(...)` call. Same ruff trap as 1.2.

**Tests**:
- Create `tests/unit/api/metadata/test_tvdb_parser_media_sheet.py`:
  - Golden test with existing `docs/reference/_samples/tvdb/movie_extended.json` -> asserts all 4 new fields are `None` for a movie.
  - Golden test with a new fixture `docs/reference/_samples/tvdb/series_extended.json` (capture from live TVDB `/v4/series/{id}/extended` for a known TV series) -> asserts `series_status` is a non-empty string.
  - Assert: never empty string.

**Gate**:
```bash
python -m pytest tests/unit/api/metadata/test_tvdb_parser_media_sheet.py -v
```

### 1.4 Gate - Phase 1 complete

```bash
make lint
python -m pytest tests/unit/api/metadata/ -v
python -c "from personalscraper.api.metadata._base import MediaDetails; m=MediaDetails(provider='tmdb',provider_id='1',director='Nolan',series_status='Ended',episode_count=10,trailer_url='https://youtube.com/watch?v=abc'); print('OK')"
```

**Commit**: `feat(media-sheet): extend MediaDetails with director, series_status, episode_count, trailer_url (D4)`
