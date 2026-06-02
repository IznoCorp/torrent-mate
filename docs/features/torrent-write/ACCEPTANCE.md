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

Expected: all pass, 0 failed (10 passed).

---

## ACC-04 — Protocol contract tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_write_contracts.py -q
```

Expected: all pass, 0 failed (8 passed).

---

## ACC-05 — QBitClient add + limits tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent_add.py -q
```

Expected: all pass, 0 failed (14 passed).

---

## ACC-06 — TransmissionClient add tests

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_transmission_add.py -q
```

Expected: all pass, 0 failed (13 passed).

---

## ACC-07 — Capability composition

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_capabilities_composition.py -q
```

Expected: all pass including TorrentAdder/TorrentLimiter assertions (15 passed).

---

## ACC-08 — Boot fail-fast: incapable client raises `RegistryConfigError`

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_build_app_context_torrent.py -q
```

Expected: all pass, 0 failed (3 passed).

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

Expected: exits 0; all tests pass (5988 passed); 0 lint/mypy errors.

---

## ACC-13 — Smoke import

```bash
python -c "import personalscraper; print('ok')"
```

Expected: prints `ok`, exits 0.
