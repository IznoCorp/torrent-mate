# Phase 17 — Protocol provider_id accepts `str | int`

Created as the follow-up to Phase 7 sub-phase 7.4 concern. Two cast() sites in `personalscraper/scraper/existing_validator.py` (lines 914, 954) keep the concrete `TMDBClient` cast (instead of migrating to `MovieDetailsProvider` / `TvDetailsProvider`) because the Protocol method signatures narrow `provider_id: str` while the NFO-parsed IDs are `int`. This phase aligns the Protocol signature with reality so those sites can use the capability Protocol.

## Gate

- Phase 7 + 8 complete.
- Phase 16 complete (chain semantics fully aligned to DESIGN).

## Goal

Update `MovieDetailsProvider.get_movie(provider_id)` and `TvDetailsProvider.get_tv(provider_id)` signatures to accept `int | str`. Update the 2 cast() sites in `existing_validator.py` to use the Protocol type via `registry.locked(...)` direct dispatch.

## Scope

- `personalscraper/api/metadata/_contracts.py` — `MovieDetailsProvider.get_movie` + `TvDetailsProvider.get_tv` signatures.
- `personalscraper/api/metadata/tmdb.py` — `TMDBClient.get_movie` + `get_tv` signatures (currently accept `int`).
- `personalscraper/api/metadata/tvdb.py` — `TVDBClient.get_series` (if it's the TvDetailsProvider impl) signature.
- `personalscraper/scraper/existing_validator.py` — sites lines 914, 954 — replace cast with Protocol-typed dispatch.
- Tests that mock `get_movie` / `get_tv` — verify they remain compatible.

## Sub-phases

### 17.1 — Audit current signatures

```bash
rg --type py "def get_movie\(" personalscraper/api/metadata/
rg --type py "def get_tv\(" personalscraper/api/metadata/
rg --type py "def get_series\(" personalscraper/api/metadata/
```

Document: each concrete impl's current type, the Protocol's current type, the actual ID values passed at runtime (int from NFO XML, str from TMDB API JSON, etc.).

Commit: `docs(scraper): audit get_movie / get_tv signatures across providers (Phase 17 prep)`

### 17.2 — Widen Protocol signatures to `int | str`

In `personalscraper/api/metadata/_contracts.py`:

```python
class MovieDetailsProvider(Protocol):
    def get_movie(self, provider_id: int | str) -> MediaDetails: ...

class TvDetailsProvider(Protocol):
    def get_tv(self, provider_id: int | str) -> MediaDetails: ...
```

In concrete impls, accept `int | str` and coerce internally (likely str → int via `int(provider_id)` since IDs are integer in transport JSON).

Commit: `refactor(api): widen MovieDetailsProvider/TvDetailsProvider provider_id to int | str`

### 17.3 — Migrate existing_validator cast() sites

Replace:

```python
tmdb_client = cast("TMDBClient", self._registry.get("tmdb"))
details = tmdb_client.get_movie(provider_id)
```

With:

```python
provider = cast("MovieDetailsProvider", self._registry.get("tmdb"))
details = provider.get_movie(provider_id)
```

Or, if `locked(MovieDetailsProvider, match)` is more appropriate for the ID-bound canonical refetch semantics, use that instead.

Commit: `refactor(scraper): existing_validator artwork-recovery sites use Protocol-typed dispatch`

### 17.4 — Re-run ACC-02 strict

```bash
rg -e 'cast\("TMDBClient"|cast\("TVDBClient"' personalscraper/scraper/ -t py
```

Expected: 4 remaining sites (lines 629, 646, 732, 749 — the episode-bound TVDB/TMDB sites that genuinely require TVDB-specific methods not in the Protocols). Document these 4 as the final hard exemption — they call `_fetch_season_episodes_tvdb` / `get_tv_season` which aren't in `EpisodeFetcher` Protocol.

Update `ACCEPTANCE.md` ACC-02 exemption note: 4 documented sites (not 6).

Commit: `docs(registry): tighten ACC-02 exemption to 4 remaining episode-specific cast sites`

## Phase gate

- `cast("TMDBClient"|"TVDBClient", ...)` count in `personalscraper/scraper/existing_validator.py`: 4 (down from 6).
- All 4 remaining sites are episode-fetching paths that call methods outside the EpisodeFetcher Protocol.
- ACC-02 exemption tightened to reflect reality.
- `make test` exit 0.

## ACC criteria touched

- ACC-02 — exemption count tightens from 6 to 4 documented direct-dispatch sites.

## Cost estimate

- 17.1: ~10 min audit.
- 17.2: ~15 min DeepSeek.
- 17.3: ~10 min DeepSeek.
- 17.4: ~5 min docs.
- Total: ~40 min.

## Risk

Low. Widening a parameter type is backward-compatible. Risk: tests that mock with a specific type may break — caught by `make test`.

## Future work (out of this phase)

The 4 remaining `cast()` sites (episode flows) could theoretically be eliminated by extending the `EpisodeFetcher` Protocol with TVDB-specific methods OR by moving those code paths to use `registry.locked("tvdb", EpisodeFetcher)`. That's a larger refactor with semantic implications (episode chain fallback would silently switch canonical source — same concern as Phase 7.4 audit).
