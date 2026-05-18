# External IDs Flow — provider-ids feature

Reference for the cross-provider ID + multi-source ratings pipeline
introduced by the `provider-ids` feature. Load on demand when
touching the scrape, backfill, dispatch, or verify paths.

## Data shapes

### `media_item.external_ids_json`

```jsonc
{
  "tvdb": { "series_id": "9001", "episode_id": null },
  "tmdb": { "series_id": "5005", "episode_id": null },
  "imdb": { "series_id": "tt0944947", "episode_id": null },
}
```

- Migration **005** (`personalscraper/indexer/migrations/005_external_ids_json.sql`)
  added this column with `NOT NULL DEFAULT '{}'`.
- The legacy flat columns `tmdb_id` / `imdb_id` / `tvdb_id` were
  **dropped** in the same migration after a one-shot backfill via
  `json_object`.
- Pydantic models in
  :mod:`personalscraper.indexer.external_ids` (`ExternalIds`,
  `ProviderIds`) provide a typed handle for serialisation.

### `media_item.ratings_json`

```jsonc
{
  "entries": [
    { "source": "imdb", "score": "8.5/10", "votes": 1000000 },
    { "source": "rotten_tomatoes", "score": "91%", "votes": 0 },
  ],
}
```

- `RatingEntry.source` is a Literal of `imdb` / `rotten_tomatoes` /
  `metacritic` / `themoviedb` / `trakt`.
- `score` is stored as a string so NFO-formatted values
  (`"8.5/10"`, `"87%"`, `"74/100"`) survive a round-trip.

### `media_item.canonical_provider`

`"tvdb"` for TV shows, `"tmdb"` for movies, `NULL` for legacy rows
that never re-scraped under the new flow. The verify checker reads
this to enforce that every episode NFO carries the matching
`<uniqueid type=canonical default="true">`.

## Nominal scrape flow (TVDB-canonical TV show)

```
1. TVDB.search(title, year) → SearchResult(provider_id=N)
2. TVDB.get_series_episodes(N, season) → list[EpisodeInfo]
   - parser populates ep.external_ids = {"tvdb": <id>, "imdb": <id?>}
3. _build_episode_map writes payload {"title", "still_path",
   "tvdb_episode_id", "tmdb_episode_id"?, "imdb_episode_id"?}
4. _xref_enrichment calls TMDB for the same (season, episode) tuples,
   merges missing tmdb_episode_id without overwriting canonical
5. match_episode_files passes the *_episode_id keys through to the
   matched dict
6. _generate_episode_nfos writes the per-episode NFOs with
   <uniqueid type=tvdb default="true"> + <uniqueid type=tmdb> +
   <uniqueid type=imdb>
7. _resolve_external_ids re-validates IMDb via OMDb (Q5=B) and
   fetches IMDb + Rotten Tomatoes ratings
```

## Fallback flow (TMDb-canonical when TVDB unavailable)

Symmetric to the nominal flow with the canonical / xref roles
swapped. The NFO writer uses `canonical_provider` to flag the
default uniqueid correctly.

## Backfill flow

```
personalscraper indexer backfill-ids [--show=NAME] [--dry-run]
```

Calls
:func:`personalscraper.indexer.scanner._modes.backfill_ids.run_backfill_ids`
which iterates every `media_item` row, detects gaps via
:func:`personalscraper.indexer.backfill_ids.detect_gaps`, fetches the
missing pieces through the IMDb / Rotten Tomatoes façades, and
merges them with the safe-merge helpers that refuse to overwrite the
canonical family or already-populated values. Emits
`BackfillStarted` / `BackfillItemCompleted` / `BackfillSkipped` /
`BackfillCompleted` events on the bus.

## Invariants

- **No cross-contamination** — DESIGN §3 : `<uniqueid type="tvdb">`
  always contains a real TVDB ID. The xref enrichment never replaces
  the canonical family.
- **Append-only ratings** — the backfill never overwrites an existing
  rating row for a source ; refreshing requires an explicit delete.
- **Idempotence** — a second backfill pass on a fully-populated row
  produces zero updates (DESIGN §5).

## Related docs

- `docs/reference/indexer-json-shapes.md` — JSON column shapes.
- `docs/reference/scraping.md` — TMDB / TVDB / OMDb invariants.
- `docs/reference/event-bus.md` — event catalog including the four
  `Backfill*` events.
