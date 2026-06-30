# Phase 05 — Fix the search endpoint (CRITICAL bug) + adapt to real shape + tmdb_id

**Root cause (live-confirmed 2026-06-20):** `Torr9Client.search()` calls `/api/v1/torrents?q=`,
which is torr9's **listing/recent** endpoint — it IGNORES `q` and returns a static recent feed.
The **real search** is `GET /api/v1/torrents/search?q=` (found in the torr9.net SPA JS bundle:
`search: e => \`${a()}/api/v1/torrents/search?q=${encodeURIComponent(e)}\``). The real endpoint
**filters correctly** with just `Accept: application/json` + Bearer (no browser headers needed):
Batman→Batman, Inception→Inception, nonsense→0 results. So torr9 was never broken; we hit the
wrong endpoint. (The phase-1 golden fixture was captured from the wrong endpoint too.)

**The real `/torrents/search` item shape differs** (richer): it HAS `seeders`/`leechers`/
`times_completed`, HAS `category_name` (a label, NO `category_id`), HAS `tmdb_id`, but has
**NO `magnet_link`** (only `info_hash` → download via `/torrents/{id}/download`, Bearer .torrent
bytes — already built + confirmed 200 application/x-bittorrent). Envelope:
`{count, current_page, limit, query, total_count, total_pages, filters, torrents:[]}` (items
still under `torrents` — extraction unchanged).

**Operator decisions (2026-06-20):** keep the phase-4 enrichment but **default it OFF** (search now
provides seeders, so enrichment is a redundant opt-in re-check); **add a `tmdb_id` field to
`TrackerResult`** (framework) populated from torr9.

The corrected golden fixture is already captured at
`docs/reference/_samples/torr9/torr9_search.json` (Inception, 3 real items, uploader redacted) —
see its values in Task 4.

---

## Task 1 — Fix the search endpoint + correct the now-wrong comments (torr9.py)

1a. In `search()`, change the endpoint:

```python
raw = self._authed_get("/api/v1/torrents/search", {"q": q})
```

(was `"/api/v1/torrents"`). Everything else in `search()` stays: `_authed_get` joins base_url +
applies Bearer + re-login-on-401; items are under `data.get("torrents")`.

1b. Fix the now-FALSE module docstring/comments that claim search has no seeders:

- The module docstring bullet "No seeders/leechers exposed — seeders=0, leechers=0 on all results"
  is WRONG → replace: torr9's **search** endpoint (`/torrents/search`) DOES expose
  `seeders`/`leechers` + `category_name` + `tmdb_id`; the **listing** endpoint (`/torrents`) does
  not — we use search. Download is the `.torrent` endpoint `/torrents/{id}/download` (search items
  carry no `magnet_link`).
- The `_parse_item` comment that says "the SEARCH payload has a numeric category_id ... but NO swarm
  data" is backwards → correct it: the SEARCH payload has `category_name` + `seeders`/`leechers`
  (no `category_id`); the LISTING payload has `category_id` + no swarm. `_parse_item` handles both
  (prefer `category_name`, fall back to `_CATEGORY_MAP[category_id]`; read `seeders`/`leechers`
  with a 0 default). KEEP `_CATEGORY_MAP` as the listing-shape fallback (do NOT delete it).

## Task 2 — Enrichment default OFF (keep the capability, opt-in)

Search now carries real seeders, so the top-K detail enrichment is a redundant re-check — keep it
but default OFF (operator decision). Change the default in all three places:

- `personalscraper/conf/models/api_config.py` `TrackerProviderConfig`: `enrich_seeders: bool = False`
  (was `True`). Update its docstring (now an opt-in seeders re-check; search already provides seeders).
- `torr9.py` `__init__`: `enrich_seeders: bool = False` (was `True`). Update the Args docstring.
- `torr9.py` `from_env`: `enrich_seeders=getattr(provider_cfg, "enrich_seeders", False)` (was `True`).
  Keep the enrichment loop + the CircuitOpenError/ApiError fail-soft exactly as-is (just default off).
  Update the enrichment-loop comment: it's now an optional re-check, not a necessity.

## Task 3 — Add `tmdb_id` to TrackerResult (framework) + populate from torr9

3a. `personalscraper/api/tracker/_base.py` `TrackerResult` dataclass: add a new optional field
(after `audio`, keep it last so positional constructions elsewhere are unaffected):

```python
    tmdb_id: int | None = None
```

Add a docstring line: `tmdb_id: TMDB id when the tracker exposes it (torr9 search), else None.`
This is additive + defaulted → lacale/c411 and all existing constructions keep working unchanged.

3b. `torr9.py` `_parse_item`: populate it. torr9's search item has `tmdb_id` (int; `0` means
"none", e.g. music). Map `0`/absent → `None`:

```python
        tmdb_raw = item.get("tmdb_id")
        tmdb_id = int(tmdb_raw) if isinstance(tmdb_raw, int | float) and int(tmdb_raw) > 0 else None
```

and pass `tmdb_id=tmdb_id` in the `TrackerResult(...)` construction. (Inside `wrap_parser_drift`, a
bad type drifts — fine.)

## Task 4 — Rewrite the search golden tests (test_torr9_client.py) for the new fixture

The fixture `docs/reference/_samples/torr9/torr9_search.json` now holds the REAL `/torrents/search`
response: envelope `{count:25, current_page:1, limit:25, query:"Inception", total_count:44,
total_pages:2, filters:{...}, torrents:[3 items]}`. The 3 items (verbatim, assert these EXACT values
— anti-vacuity):

- **[0]** id=13750, title="Inception 2010 BluRay 2160p HDR Hybrid DoVi x265 10bit MULTI VFF 5.1 DTS HDMA-telemO",
  info_hash="cc32af3a46e54c48ded0c74ee2a9e798d70834ea", file_size_bytes=13832185317, seeders=49,
  leechers=0, category_name="Films", tmdb_id=27205, is_freeleech=false, NO magnet_link.
- **[1]** id=40003, seeders=246, category_name="Films", tmdb_id=27205.
- **[2]** id=277217, seeders=2, category_name="Musique", tmdb_id=0 (→ parsed to None).

Rewrite the search-golden test class to assert the new shape:

- `search("Inception")` returns **3** results, all `provider=="torr9"`.
- first.title == the exact title above; first.size.bytes == 13832185317; first.info_hash == "cc32af3a46e54c48ded0c74ee2a9e798d70834ea".
- first.seeders == 49 and first.leechers == 0 (REAL swarm from search — the key proof the fix works).
- first.category == "Films" (from `category_name`, NOT `_CATEGORY_MAP`).
- first.tmdb_id == 27205.
- first.download_url == "/api/v1/torrents/13750/download" (no magnet → the .torrent endpoint).
- first.is_freeleech is False; first.download_url does NOT start with "magnet:".
- second (idx 1): seeders == 246, tmdb_id == 27205.
- third (idx 2): category == "Musique", seeders == 2, tmdb_id is None (0 → None).
- the path test: `search("x")` calls `_authed_get`/transport.get with path "/api/v1/torrents/search".
- empty-result + malformed-payload (non-dict envelope, bad size) tests still apply — adapt the
  envelope to the new shape but keep the `"shape drift"` ApiError assertions.
  DELETE/replace the OLD assertions referencing the wrong shape (Oasis/Fantastic-Four titles,
  magnet_link download_url, category ids 5/51, tracker_id "305289", sizes 20827331134/1000504347).

Also: add/adjust an enrichment test — with `enrich_seeders` now defaulting False, the default client
does NOT call get_details during search; the existing enrich-on tests must explicitly pass
`enrich_seeders=True`. Keep the get_details golden test (detail fixture unchanged) + the
CircuitOpenError fail-soft test (construct with `enrich_seeders=True`).

If `make check` surfaces other tests constructing `TrackerResult` positionally or asserting its field
set, update them for the additive `tmdb_id` (should be none — it's defaulted-last — but verify).

## Task 5 — Correct the docs

5a. `docs/reference/torr9-api.md`:

- **Search section**: the endpoint is **`GET /api/v1/torrents/search?q=`** (NOT `/torrents?q=`, which
  is the _listing/recent_ endpoint that ignores `q` — add this as an explicit warning + the root cause).
  Document the real item shape (`seeders`/`leechers`/`times_completed`, `category_name`/
  `category_icon`/`parent_category_name`, `tmdb_id`, `uploader_name`, NO `magnet_link`/`category_id`/
  `description`) and the envelope (`count`/`current_page`/`total_pages`/`total_count`/`limit`/`query`/
  `filters{category,max_age_days,search_in,tag,uploader}`). Note filtering works with just Accept:json
  - Bearer (no browser headers).
- Add an **Endpoint catalog** (from the SPA bundle): `list /torrents`, `recent /torrents/recent`,
  `search /torrents/search?q=`, `details /torrents/{id}`, `download /torrents/{id}/download`,
  `comments /torrents/{id}/comments`, `check-duplicate`, `exclus?days=`, `featured/search?query=&type=`,
  `rss/recent?passkey=`. Mark the wrong-endpoint history.
- **Download**: search items have no `magnet_link`; download is the authed `.torrent`
  `GET /torrents/{id}/download` (Bearer). The detail endpoint DOES carry `magnet_link`.
- **Categories**: search items carry `category_name` directly → `_CATEGORY_MAP` (id→label) is now only
  a fallback for the listing shape.

5b. `docs/features/torr9/DESIGN.md`: correct the API-contract Search row (endpoint `/torrents/search`,
real shape with seeders/category_name/tmdb_id, no magnet); update the "NOT exposed by SEARCH /
seeders" paragraph — the SEARCH endpoint DOES expose seeders/leechers + category_name + tmdb_id; the
N+1 enrichment is now an **optional opt-in re-check (default OFF)**, not a necessity. Note `tmdb_id`
is carried on `TrackerResult`.

## GATES (all must hold)

- `python -m pytest tests/unit/test_torr9_client.py tests/unit/test_tracker_capabilities_composition.py tests/unit/test_tracker_parser_schema_drift.py tests/integration/api/tracker/test_composition_root.py -q` → 0 failed.
- `make check` → lint + test (NNNN passed, 0 failed) + guardrails green.
- `python -c "from personalscraper.api.tracker._base import TrackerResult; import inspect; print('tmdb_id' in inspect.signature(TrackerResult).parameters)"` → True.
- `python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; print(TrackerProviderConfig().enrich_seeders)"` → False.
- `rg -t py "torrents/search" personalscraper/api/tracker/torr9.py` → matches search().

## COMMITS (Cocktail A; one per task or grouped, keep each green; NO phase-gate/empty commit; NO push)

- `fix(torr9): use the real /torrents/search endpoint (was hitting the listing endpoint that ignores q)`
- `feat(tracker): carry tmdb_id on TrackerResult; populate from torr9 search`
- `refactor(torr9): default seeders enrichment OFF (search now provides seeders) — keep opt-in`
- `test(torr9): rewrite search golden tests for the real /torrents/search shape`
- `docs(torr9): correct search endpoint + shape + endpoint catalog`
