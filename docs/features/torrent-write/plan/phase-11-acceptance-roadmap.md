# Phase 11 — Executable `ACCEPTANCE.md` + ROADMAP Flip

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Write `docs/features/torrent-write/ACCEPTANCE.md` (every criterion is a shell command + expected output). Flip RP1 status in `ROADMAP.md`. 1 commit. NOTE: the LaCale → Vague 2 ROADMAP reclassification was already committed on this branch (26e378ff) — do NOT re-apply it.

**Tech Stack:** Markdown, shell

---

## Gate

- Reference docs updated (`qbittorrent-api.md`, `transmission-api.md`, `architecture.md`).
- `make check` passes.

---

## Files

- Create: `docs/features/torrent-write/ACCEPTANCE.md`
- Modify: `docs/ROADMAP.md` (or wherever ROADMAP.md lives — find it first)

---

## Steps

- [ ] **1. Find ROADMAP.md**

```bash
find /Users/izno/dev/PersonnalScaper/docs -name "ROADMAP.md" | head -5
```

- [ ] **2. Locate the RP1 entry and note its current status marker**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -n "RP1\|torrent-write\|Torrent Write" docs/ROADMAP.md | head -10
```

- [ ] **3. Create `docs/features/torrent-write/ACCEPTANCE.md`**

````markdown
# ACCEPTANCE — torrent-write (RP1)

Every criterion is an executable shell command with a documented expected
output. Re-exercise all criteria before squash merge.

---

## ACC-01 — Contract imports

```bash
python -c "
from personalscraper.api.torrent import TorrentAdder, TorrentLimiter
from personalscraper.api.torrent._base import TorrentSource, TorrentLimits
print('ok')
"
```
````

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

Expected: all pass, 0 failed.

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

Expected: all pass including new TorrentAdder/TorrentLimiter assertions.

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

Expected: exits 0; all tests pass; 0 lint/mypy errors.

---

## ACC-13 — Smoke import

```bash
python -c "import personalscraper; print('ok')"
```

Expected: prints `ok`, exits 0.

````

- [ ] **4. Flip RP1 status in `ROADMAP.md`**

Change the RP1 line from its current status (e.g. `[P1, prérequis]`) to `[DONE]`. Add `feat/torrent-write` as the delivery reference. Do NOT modify any other line (especially the LaCale reclassification from 26e378ff).

Example diff:

```diff
-| RP1 | Torrent Write Capability | [P1, prérequis] | ...
+| RP1 | Torrent Write Capability | [DONE] feat/torrent-write | ...
````

Exact text depends on the current file content (read it first in step 2).

- [ ] **5. Run all ACC criteria**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_source.py tests/unit/test_torrent_write_contracts.py tests/unit/test_qbittorrent_add.py tests/unit/test_transmission_add.py tests/unit/test_torrent_capabilities_composition.py tests/unit/test_build_app_context_torrent.py tests/unit/test_no_inline_qbit_fallback.py -q 2>&1 | tail -10
```

Expected: all pass.

- [ ] **6. Final full quality gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -10
```

Expected: exits 0.

- [ ] **7. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add docs/features/torrent-write/ACCEPTANCE.md docs/ROADMAP.md && git commit -m "docs(torrent-write): add executable ACCEPTANCE.md and flip RP1 to DONE in ROADMAP"
```

---

## Phase gate (final)

- [ ] Smoke test:

```bash
python -c "import personalscraper; print('ok')"
```

- [ ] All ACC criteria green (run the pytest bundle from step 5 above).

- [ ] Gate commit:

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(torrent-write): phase 11 gate — docs, acceptance, ROADMAP complete"
```
