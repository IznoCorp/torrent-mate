# Phase 6 — Multi-FS test harness + SH-16 ACCEPTANCE + docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Register the `multifs` pytest marker, tag all filesystem-capability
tests with it, author the `ACCEPTANCE.md` (all 17 SH-16 criteria as executable
commands), update `docs/reference/storage.md` and `docs/reference/indexer.md`,
add the `0.17.0` `CHANGELOG.md` entry, and confirm every AC passes.

**NTFS invariant:** Documentation only — no code changes to transfer or drift
behaviour. The `ntfs_macfuse` capability entry documented in `storage.md`
must match the pinned flag list from Phases 2–3 exactly.

**Architecture:** Pure housekeeping phase — marker registration, test tagging,
docs, ACCEPTANCE.md. No new production modules.

**Tech Stack:** `pyproject.toml` markers, `pytest.mark`, Markdown.

---

## Gate (prerequisites from Phase 5)

Phase 5 produced:

- `reconcile_file` with `capability` parameter (default `NTFS_MACFUSE`).
- `test_drift_fs_aware.py` tests passing.
- All phases 1–5 gates green.

Verify:

```bash
make check
# expected: exit 0, all green

pytest tests/indexer/test_drift_fs_aware.py -v
# expected: all PASS
```

---

## Files

| Action | Path                                                                |
| ------ | ------------------------------------------------------------------- |
| Modify | `pyproject.toml` (add `multifs` marker)                             |
| Modify | `tests/indexer/test_fs_probe.py` (add `@pytest.mark.multifs`)       |
| Modify | `tests/indexer/test_fs_capability.py` (add `@pytest.mark.multifs`)  |
| Modify | `tests/dispatch/test_transfer_argv.py` (add `@pytest.mark.multifs`) |
| Modify | `tests/indexer/test_drift_fs_aware.py` (add `@pytest.mark.multifs`) |
| Modify | `docs/reference/storage.md` (add "Filesystem capability" section)   |
| Modify | `docs/reference/indexer.md` (add cross-reference)                   |
| Modify | `CHANGELOG.md` (add `0.17.0` entry)                                 |
| Create | `docs/features/multi-filesystem/ACCEPTANCE.md`                      |

---

## Task 1 — Register the `multifs` pytest marker

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1.1: Read the current `[tool.pytest.ini_options]` markers list**

Current markers (from `pyproject.toml`):
`e2e`, `roundtrip`, `e2e_torrent`, `e2e_idempotence`, `network`, `slow`, `darwin_only`.

- [ ] **Step 1.2: Add the `multifs` marker**

In `pyproject.toml`, append to the `markers` list:

```toml
    "multifs: filesystem-capability tests using faked mount/stat fixtures (no real disks required)",
```

The full markers list becomes:

```toml
markers = [
    "e2e: End-to-end tests requiring storage disks and/or live APIs",
    "roundtrip: Roundtrip tests — torrentify disk media, re-match via API, compare",
    "e2e_torrent: Pipeline E2E with real torrent downloads (manual only, costs ratio)",
    "e2e_idempotence: E2E idempotence tests on real staging data (manual only)",
    "network: Network tests — opt-in via TRAILER_INTEGRATION_TESTS=1 env var",
    "slow: slow tests (perf regression), off by default — run with -m slow",
    "darwin_only: macOS-only smoke tests (skipped on Linux/Windows CI runners)",
    "multifs: filesystem-capability tests using faked mount/stat fixtures (no real disks required)",
]
```

- [ ] **Step 1.3: Verify the marker is registered**

```bash
cd /Users/izno/dev/PersonnalScaper
python -c "
import tomllib
d = tomllib.load(open('pyproject.toml', 'rb'))
print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))
"
# expected: True
```

- [ ] **Step 1.4: Commit**

```bash
git add pyproject.toml
git commit -m "test(multi-filesystem): register multifs pytest marker"
```

---

## Task 2 — Tag existing capability/probe/argv/drift tests with `@pytest.mark.multifs`

**Files:**

- Modify: `tests/indexer/test_fs_probe.py`
- Modify: `tests/indexer/test_fs_capability.py`
- Modify: `tests/dispatch/test_transfer_argv.py`
- Modify: `tests/indexer/test_drift_fs_aware.py`

- [ ] **Step 2.1: Add `pytestmark` to each test file**

In each of the four files, add at module level (after imports):

```python
import pytest

pytestmark = pytest.mark.multifs
```

If `pytest` is already imported, just add the `pytestmark` line.

- [ ] **Step 2.2: Verify `multifs` tests are collected**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest -m multifs --collect-only -q
# expected: lists tests from test_fs_probe.py, test_fs_capability.py,
#           test_transfer_argv.py, test_drift_fs_aware.py
#           At least 8 tests collected
```

- [ ] **Step 2.3: Run the multifs suite (no real disks)**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest -m multifs -q
# expected: N passed, 0 failed, 0 errors  (N >= 8)
```

- [ ] **Step 2.4: Commit**

```bash
git add tests/indexer/test_fs_probe.py \
        tests/indexer/test_fs_capability.py \
        tests/dispatch/test_transfer_argv.py \
        tests/indexer/test_drift_fs_aware.py
git commit -m "test(multi-filesystem): tag capability/probe/argv/drift tests with multifs marker"
```

---

## Task 3 — Update `docs/reference/storage.md`

**Files:**

- Modify: `docs/reference/storage.md`

- [ ] **Step 3.1: Read the current tail of `docs/reference/storage.md`**

Find a suitable insertion point (end of the rsync flags section or end of the
NTFS/macFUSE section).

- [ ] **Step 3.2: Add the "Filesystem capability" section**

Append the following section to `docs/reference/storage.md`:

```markdown
## Filesystem capability layer (v0.17.0+)

The pipeline adapts its rsync flags and indexer drift behaviour to the
destination filesystem via a `FilesystemCapability` strategy table
(`personalscraper/indexer/_fs_capability.py`).

### FsProbe consolidation

A single cached `probe_mount(path)` call (`personalscraper/indexer/_fs_probe.py`)
replaces the three independent `mount` parsers that previously lived in
`db.py`, `scanner/_spotlight.py`, and `scanner/__init__.py`.

**Timeout:** 10 seconds (consolidated from the former 5s in `db.py` and 10s in
the scanner modules). The result is cached for the process lifetime — `mount`
output does not change mid-run.

### Capability table

| fs_type        | rsync extra flags                                              | Unix perms | Apple metadata | NTFS name check | ctime in tier-1 | mtime granularity |
| -------------- | -------------------------------------------------------------- | ---------- | -------------- | --------------- | --------------- | ----------------- |
| `ntfs_macfuse` | `--no-perms --no-owner --no-group --no-times --omit-dir-times` | blocked    | excluded       | yes             | yes             | exact (1 ns)      |
| `unknown`      | **same as `ntfs_macfuse`** (restrictive fallback)              | blocked    | excluded       | yes             | yes             | exact (1 ns)      |
| `apfs`         | _(none beyond `-a --inplace --partial`)_                       | allowed    | allowed        | no              | yes             | exact (1 ns)      |
| `hfsplus`      | _(none beyond `-a --inplace --partial`)_                       | allowed    | allowed        | no              | yes             | 1 s               |
| `exfat`        | `--exclude=.DS_Store --exclude=._*`                            | allowed    | excluded       | no              | no (no ctime)   | 2 s               |
| `ext4`         | _(none beyond `-a --inplace --partial`)_                       | allowed    | allowed        | no              | yes†            | exact (1 ns)      |

† ext4 ctime mutates on metadata ops; granularity widening is deferred until a
real ext4 target exists (DESIGN §8.4).

### NTFS flags (byte-identical to pre-0.17.0)

The full `ntfs_macfuse` rsync prefix:
```

-a --no-perms --no-owner --no-group --no-times --omit-dir-times --inplace --partial --exclude=.DS*Store --exclude=.*\*

````

These flags are pinned in `_fs_capability.py::_NTFS_RSYNC_FLAGS` and verified
by a golden test (`tests/dispatch/test_transfer_argv.py`).

### Operator override

To force a specific filesystem type for a disk (e.g. when the macFUSE driver
token is not auto-recognised):

```json5
// config/disks.json5
{
  id: "raid",
  path: "/Volumes/AppleRAID",
  categories: ["movies", "tv_shows"],
  fs_type: "hfsplus",   // override: unlocks Unix perms, disables NTFS name check
}
````

When `fs_type` is omitted, the type is auto-detected via `probe_mount`.

````

- [ ] **Step 3.3: Commit**

```bash
git add docs/reference/storage.md
git commit -m "docs(multi-filesystem): add filesystem capability section to storage.md"
````

---

## Task 4 — Cross-reference in `docs/reference/indexer.md`

**Files:**

- Modify: `docs/reference/indexer.md`

- [ ] **Step 4.1: Find the drift / tier-1 section in `docs/reference/indexer.md`**

Search for "tier-1" or "drift" in the file to find the relevant section.

- [ ] **Step 4.2: Add a cross-reference paragraph**

In the tier-1 drift section, add:

```markdown
> **Filesystem-aware drift (v0.17.0+):** The tier-1 comparison is now
> capability-gated. On exFAT, ctime is excluded from the tuple and mtime is
> rounded to the nearest 2-second bucket to prevent perpetual re-hashing.
> On HFS+, mtime is rounded to the nearest second. NTFS and APFS behaviour is
> unchanged. See [`docs/reference/storage.md`](storage.md) — "Filesystem
> capability layer" for the full table.
```

- [ ] **Step 4.3: Commit**

```bash
git add docs/reference/indexer.md
git commit -m "docs(multi-filesystem): cross-reference filesystem capability layer from indexer.md"
```

---

## Task 5 — Add `0.17.0` CHANGELOG entry

**Files:**

- Modify: `CHANGELOG.md`

- [ ] **Step 5.1: Read the top of `CHANGELOG.md` to understand the format**

- [ ] **Step 5.2: Prepend the `0.17.0` entry**

```markdown
## [0.17.0] — 2026-05-29

### Added

- **Multi-filesystem support** (`FilesystemCapability` strategy table): the
  pipeline now adapts rsync flags and indexer drift behaviour per destination
  filesystem type. Supported: NTFS-via-macFUSE (unchanged), APFS, HFS+,
  exFAT, ext4 (data-only).
- `FsProbe` (`personalscraper/indexer/_fs_probe.py`): single cached `mount`
  shell-out replacing three independent parsers. Fixes the `ufsd_NTFS`
  dead-branch asymmetry in `_spotlight.try_attach`.
- `DiskConfig.fs_type` optional override: escape hatch for unrecognised
  macFUSE driver tokens.
- `multifs` pytest marker: capability/probe/argv/drift tests tagged; no real
  disks required.

### Fixed

- `_spotlight.try_attach` dead branch: `ufsd_NTFS` mounts were not recognised
  as macFUSE volumes due to exact-token vs substring asymmetry. Now fixed via
  `canonical_fs_type` in `FsProbe`.
- `IndexerConfig.db_path` validator: the blunt `/Volumes/` prefix reject now
  correctly accepts APFS volumes mounted under `/Volumes/`.

### Changed

- Probe timeout for `db.py` pre-open check: 5 s → 10 s (single cached
  shell-out shared with scanner modules). Intentional; documented in
  `docs/reference/storage.md`.
- `reconcile_file` gains an optional `capability` parameter (default:
  `NTFS_MACFUSE` — byte-identical to pre-0.17.0 behaviour).

### Internal

- `rsync()` and `rsync_merge()` in `_transfer.py` now read flags from
  `FilesystemCapability.rsync_flags` instead of hardcoded literals.
  NTFS argv is pinned by a golden test.
```

- [ ] **Step 5.3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(multi-filesystem): add 0.17.0 CHANGELOG entry"
```

---

## Task 6 — Author `docs/features/multi-filesystem/ACCEPTANCE.md`

**Files:**

- Create: `docs/features/multi-filesystem/ACCEPTANCE.md`

- [ ] **Step 6.1: Create `docs/features/multi-filesystem/ACCEPTANCE.md`**

````markdown
# ACCEPTANCE — multi-filesystem (v0.17.0)

Every criterion is an executable shell command with documented expected output
(SH-16 convention). Run from the repository root on `feat/multi-filesystem`.

```bash
# AC-01 — FsProbe canonicalises the real ufsd_NTFS token (dead-branch fix)
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected stdout: ntfs_macfuse   (exit 0)

# AC-02 — unknown fs_type falls back to NTFS-safe restrictive superset
python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"
# expected stdout: True   (exit 0)

# AC-03 — NTFS rsync flags are byte-identical to the legacy hardcoded list
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected stdout: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']

# AC-04 — APFS drops the NTFS-only metadata-suppression flags
python -c "from personalscraper.indexer._fs_capability import capability_for; f=capability_for('apfs').rsync_flags; print('--no-perms' not in f and '--no-times' not in f)"
# expected stdout: True   (exit 0)

# AC-05 — APFS capability permits NTFS-illegal characters (no needless skip)
python -c "from personalscraper.indexer._fs_capability import capability_for; r=capability_for('apfs').illegal_name_regex; print(r is None or r.search('a:b') is None)"
# expected stdout: True   (exit 0)

# AC-06 — exFAT capability disables ctime in tier-1 and sets 2s granularity
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected stdout: False 2000000000   (exit 0)

# AC-07 — HFS+ (the AppleRAID target) keeps Unix perms and is NOT NTFS-restricted
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('hfsplus'); print(c.forbids_unix_perms, c.illegal_name_regex is None)"
# expected stdout: False True   (exit 0)

# AC-08 — multifs marker is registered
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))"
# expected stdout: True   (exit 0)

# AC-09 — all multi-FS tests pass with no real disks
pytest -m multifs -q 2>&1 | tail -1
# expected: a "N passed" line (N>=8), 0 failed, 0 errors   (exit 0)

# AC-10 — no residual literal rsync flag list remains in _transfer.py
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '
# expected stdout: 0   (flags now come only from the capability table)

# AC-11 — exactly one cached mount shell-out (probe consolidation)
rg -c "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/_fs_probe.py
# expected stdout: 1

# AC-12 — the three old call sites no longer shell out to mount directly
rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (exit 1 — rg found nothing)

# AC-13 — DiskConfig accepts an optional fs_type override
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"
# expected stdout: apfs   (exit 0)

# AC-14 — full quality gate green
make check
# expected: ruff/mypy/logging OK; "NNNN passed" with 0 failed/0 errors; coverage >=90%; module-size + typed-api + cli-coverage all PASS   (exit 0)

# AC-15 — version bump landed
grep -m1 '^version' pyproject.toml 2>/dev/null || cat VERSION
# expected stdout contains: 0.17.0

# AC-16 — CHANGELOG entry
grep -c "0.17.0" CHANGELOG.md
# expected stdout: >=1

# AC-17 — package still imports (smoke)
python -c "import personalscraper; print('ok')"
# expected stdout: ok   (exit 0)
```
````

````

- [ ] **Step 6.2: Run all AC commands and confirm every one passes**

```bash
cd /Users/izno/dev/PersonnalScaper

# AC-01
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"

# AC-02
python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"

# AC-03
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"

# AC-08
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))"

# AC-09
pytest -m multifs -q 2>&1 | tail -1

# AC-10
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '

# AC-11
rg -c "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/_fs_probe.py

# AC-12
rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py

# AC-13
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"

# AC-14
make check

# AC-17
python -c "import personalscraper; print('ok')"
````

- [ ] **Step 6.3: Commit ACCEPTANCE.md**

```bash
git add docs/features/multi-filesystem/ACCEPTANCE.md
git commit -m "docs(multi-filesystem): author ACCEPTANCE.md — all 17 SH-16 criteria as executable commands"
```

---

## Task 7 — Phase gate + milestone commit

- [ ] **Step 7.1: Full quality gate**

```bash
make lint && make test && make check
# expected: exit 0, all green
```

- [ ] **Step 7.2: AC-08 + AC-09 spot check**

```bash
# AC-08
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))"
# expected: True

# AC-09
pytest -m multifs -q 2>&1 | tail -1
# expected: "N passed, 0 failed" (N >= 8)
```

- [ ] **Step 7.3: Milestone commit**

```bash
git add -u
git commit -m "chore(multi-filesystem): phase 6 gate — multifs marker, ACCEPTANCE.md, storage.md + indexer.md docs, CHANGELOG 0.17.0"
```

---

## Acceptance criteria for this phase

```bash
# AC-08
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))"
# expected: True

# AC-09
pytest -m multifs -q 2>&1 | tail -1
# expected: N passed (N>=8), 0 failed, 0 errors

# AC-15
grep -m1 '^version' pyproject.toml 2>/dev/null || cat VERSION
# expected: contains 0.17.0

# AC-16
grep -c "0.17.0" CHANGELOG.md
# expected: >=1

# AC-14
make check
# expected: exit 0

# AC-17
python -c "import personalscraper; print('ok')"
# expected: ok
```
