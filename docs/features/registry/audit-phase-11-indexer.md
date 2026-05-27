# Phase 11 — Indexer migration audit

Scope: every site in `personalscraper/indexer/` that consumes a typed
provider client (`tmdb_client`, `tvdb_client`, `imdb_client`,
`rt_client`).

## File inventory

```bash
$ rg "tmdb_client|tvdb_client|imdb_client|rt_client" personalscraper/indexer/ --type py -l
personalscraper/indexer/scanner/_modes/backfill_ids.py
```

Only one file in `personalscraper/indexer/` consumes typed clients. The
pure helpers in `personalscraper/indexer/backfill_ids.py` operate on
raw JSON strings and need no migration.

## Call-site inventory

`personalscraper/indexer/scanner/_modes/backfill_ids.py`

| Line | Site                                                                | Capability used        | Migration target                                                                                                                                                                                  |
| ---- | ------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 461  | `client.get_tv(canonical_id)` inside `_fetch_cross_provider_ids`    | `TvDetailsProvider`    | `registry.chain(TvDetailsProvider)` filtered to the canonical provider via `provider_name` match (DESIGN §6.2 chain iteration). Single-provider chain in practice (the canonical anchor's owner). |
| 463  | `client.get_movie(canonical_id)` inside `_fetch_cross_provider_ids` | `MovieDetailsProvider` | `registry.chain(MovieDetailsProvider)` filtered to canonical provider — same constraint as above.                                                                                                 |
| 531  | `_call_rating_client(imdb_client, imdb_id)` for IMDb ratings        | `RatingProvider`       | `registry.fan_out(RatingProvider)` — iterate `result.values`, call `provider.get_rating(imdb_id)` (DESIGN §6.3).                                                                                  |
| 533  | `_call_rating_client(rt_client, imdb_id)` for RT ratings            | `RatingProvider`       | Same — merged into the same `fan_out` loop. Both façades are RatingProvider instances; the loop iterates them in priority order.                                                                  |

### IDValidator / cross-ref sites

None inside the indexer. The `_fetch_cross_provider_ids` function reads
the canonical anchor from the row's `external_ids_json` and asks the
canonical provider for its native cross-refs via `get_movie` /
`get_tv` (the response's `external_ids` mapping is already a
cross-provider IDs payload). There is no `validate_id` /
`get_cross_refs` registry call needed.

### Artwork sites

None — the backfill scope is IDs + ratings only.

## Summary of migration strategy

1. **Ratings aggregation (lines 530–534)**: replace the per-client
   `imdb_client` / `rt_client` parameters with a single
   `registry.fan_out(RatingProvider)` call. The producer list yields all
   eligible rating providers in config order; the loop drops the
   per-`gap.missing_rating_sources` gating (every eligible provider is
   tried; the merge layer in `merge_ratings_without_overwrite` then
   dedupes by `source`).

2. **Cross-provider IDs (lines 387–494)**: the canonical lookup needs
   the provider whose name matches `canonical` (`"tmdb"` or `"tvdb"`).
   Iterating `registry.chain(MovieDetailsProvider)` /
   `chain(TvDetailsProvider)` and filtering to the canonical provider
   name preserves the "canonical's authority is absolute" invariant
   (DESIGN §3) while exercising the registry's circuit-aware
   eligibility check. Falling back to a non-canonical chain peer is
   forbidden — that would create cross-contamination.

3. **CLI command (`commands/library/scan.py` lines 433–478)**: drop the
   four `try/except UnknownProviderError` blocks. Pass
   `registry=app_context.provider_registry` directly to
   `run_backfill_ids`.

4. **Internal Protocols (`_RatingClient`, `_DetailsClient`)**: keep them
   inside the function as type-narrowing aids when iterating
   `chain(...)` / `fan_out(...).values` — they document the structural
   shape the loop expects. Marked as private/internal.

## Risk

Medium. The `_fetch_cross_provider_ids` path mixes two concerns:
(a) discovering the canonical provider and (b) calling its details
endpoint. Filtering `registry.chain(...)` by `provider_name == canonical`
keeps the contract while routing through registry semantics. A
production canonical with circuit OPEN now logs a fallback event and
returns `{}` — the existing behavior was identical (`client is None`
branch).

## ACC impact

- ACC-02 (no direct provider constructor in non-registry code) — must
  remain PASS for `personalscraper/indexer/` after migration.
- ACC-09 (registry boot validates config) — unchanged.
