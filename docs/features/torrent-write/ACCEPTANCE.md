# ACCEPTANCE — torrent-write (RP1)

Every criterion is an executable shell command with a documented expected
output. Re-exercise all criteria before squash merge.

---

## ACC-01 — Contract imports

```bash
python -c "
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter
from personalscraper.api.torrent._base import TorrentSource, TorrentLimits
print('ok')
"
```

Expected: prints `ok`, exits 0.

---

## ACC-02 — `TorrentItem.tags` field defaults to `[]`

```bash
python -c "
from personalscraper.api.torrent._base import TorrentItem
i = TorrentItem(hash='h', name='n', size_bytes=0, progress=0.0, state='up')
assert i.tags == [], f'expected [], got {i.tags!r}'
print('ok')
"
```

Expected: prints `ok`, exits 0.

---

## ACC-03 — `TorrentSource` and `TorrentLimits` tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_source.py -q
```

Expected: all pass, 0 failed. (Absolute count omitted intentionally — the suite
gains regression tests every review cycle; assert `0 failed`, not a brittle total.)

---

## ACC-04 — Protocol contract tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_write_contracts.py -q
```

Expected: all pass, 0 failed.

---

## ACC-05 — QBitClient add + limits tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent_add.py -q
```

Expected: all pass, 0 failed.

---

## ACC-06 — TransmissionClient add tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_transmission_add.py -q
```

Expected: all pass, 0 failed.

---

## ACC-07 — Capability composition

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_capabilities_composition.py -q
```

Expected: all pass including TorrentAdder/TorrentLimiter assertions; 0 failed.

---

## ACC-08 — Boot fail-fast: incapable client raises `RegistryConfigError`

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_build_app_context_torrent.py -q
```

Expected: all pass, 0 failed.

---

## ACC-09 — D9: no torrent config → `torrent_client=None`, no error

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_build_app_context_torrent.py::TestBuildAppContextTorrent::test_no_active_torrent_client_gives_none -v
```

Expected: `1 passed`.

---

## ACC-10 — No inline `QBitClient()` fallbacks in ingest or pipeline

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "QBitClient\(" personalscraper/ingest/ingest.py personalscraper/commands/pipeline.py
```

Expected: no matches, exit code 1.

---

## ACC-11 — D8: limits on Transmission raises `UnsupportedCapabilityError`

```bash
python -c "
from unittest.mock import patch
with patch('transmission_rpc.Client'):
    from personalscraper.api.torrent.transmission import TransmissionClient
    c = TransmissionClient('h', 9091, 'u', 'p')
from personalscraper.api.torrent._base import TorrentSource, TorrentLimits
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
try:
    c.add(TorrentSource.from_magnet('magnet:?xt=urn:btih:aabb'),
          limits=TorrentLimits(ratio=1.0))
    raise AssertionError('should have raised')
except UnsupportedCapabilityError:
    print('ok')
"
```

Expected: prints `ok`, exits 0.

---

## ACC-12 — Full quality gate

```bash
cd /Users/izno/dev/PersonnalScaper && make check
```

Expected: exits 0; 0 failed / 0 errors; 0 lint/mypy errors. (Absolute pass count
omitted — assert the gate, not a total that drifts as tests are added.)

---

## ACC-13 — Smoke import

```bash
python -c "import personalscraper; print('ok')"
```

Expected: prints `ok`, exits 0.

---

## ACC-14 — D9 scoping: read-only command never builds the torrent client (review #1/#2/#5)

```bash
cd /Users/izno/dev/PersonnalScaper && pytest "tests/unit/test_build_app_context_torrent.py::TestBuildAppContextTorrent::test_read_only_command_skips_torrent_build" -q
```

Expected: `1 passed`. With a torrent client configured (`active="qbittorrent"`)
but `build_torrent_client` left at its default, `_build_app_context` must NOT
call the factory (no daemon connect / login / auth-lockout) and
`torrent_client` stays `None`. Guards against the boot-coupling regression where
read-only commands (`library *`, `trailers`, `maintenance`) connected to the
torrent daemon at boot.

---

## ACC-15 — Dispatch matches an existing folder by external ID (phase 15, out-of-scope addition)

```bash
cd /Users/izno/dev/PersonnalScaper && pytest \
  "tests/dispatch/test_media_index.py::TestProviderIdMatch" \
  "tests/integration/test_design_dispatch.py::TestTvShowMergeContract::test_existing_folder_matched_by_provider_id_when_name_differs" -q
```

Expected: exits 0; 0 failed. A staging show/movie sharing its canonical provider
id (TVDB for shows, TMDB for movies) with an on-disk folder of a _different_
normalized name resolves to the existing folder — so the move rule merges /
replaces into it instead of creating a duplicate (the `Rick et Morty (2006)` vs
`Rick and Morty (2013)`, TVDB 275274 split). Placeholder ids (`0` / `None`) never
false-match, an exact-name hit is not shadowed by the id pass, and an ambiguous
id (two folders sharing one id) resolves deterministically without crashing.

---

## ACC-16 — Metadata search NFC-normalizes the query (phase 16, out-of-scope addition)

```bash
cd /Users/izno/dev/PersonnalScaper && pytest \
  "tests/unit/test_tmdb_client.py::TestSearchMovie::test_query_is_nfc_normalized" \
  "tests/unit/test_tvdb_client.py::TestSearchMovieTvdb::test_query_is_nfc_normalized" -q
```

Expected: exits 0; 0 failed. A title passed in NFD form (decomposed accents, as
delivered by the macOS / NTFS-via-macFUSE filesystem — `a` + U+0302 instead of
`â`) is NFC-normalized before being sent to TMDB / TVDB search. Without this,
accented French titles (e.g. `L'âge de glace`) returned zero results and silently
failed to match, even though the provider has the film.

---

## ACC-17 — Rescrape honours TVDB-primary via the shared fetch (phase 17, out-of-scope addition)

```bash
cd /Users/izno/dev/PersonnalScaper && pytest \
  "tests/maintenance/test_rescraper.py::TestRescrapeItem::test_tvdb_only_show_scrapes_via_tvdb_not_tmdb" -q
```

Expected: exits 0; 0 failed. A TVDB-matched show is fetched from TVDB
(`get_series`) via the shared `fetch_show_data`, never feeding the TVDB id to
`tmdb.get_tv` (which 404'd and aborted the whole item for old TVDB-only shows
like Hey Arnold! / Tintin). The source-of-match invariant now lives in ONE place
shared by the initial scrape (`tv_service`) and the maintenance rescraper, so the
TVDB-primary / TMDB-fallback discipline cannot diverge between them.
