# Design — Multi-Filesystem Support (FilesystemCapability Layer)

> **Status**: Draft (authored from analysis report) — pending user review then plan generation.
> **Date**: 2026-05-28
> **Roadmap item**: P2 — Multi-Filesystem Support (`multi-filesystem`)
> **Codename**: `multi-filesystem`
> **Branch**: `feat/multi-filesystem`
> **Version bump target**: 0.17.0 → 0.18.0 (minor — purely additive, no breaking config/DB change). 0.17.0 was consumed by a different feature (arch-cleanup-2); this feature shipped as **0.18.0**.
> **Source analysis**: `docs/analysis/04-filesystem-decoupling-macfuse-ntfs.md`

> **Re-scope + retrospective note (2026-05-29).** This design was authored
> before implementation and §3.4 / §4.5 / §5 / §7 originally described the
> Phase-5 FS-aware drift work as a modification to `drift.py::reconcile_file`.
> **That is not what shipped.** `reconcile_file` is dead, test-only code (no
> production caller; flagged for tech-debt-2 removal) and was left UNTOUCHED —
> it does **not** take a `FilesystemCapability`. The FS-aware tier-1 drift work
> instead landed as two new helpers in `personalscraper/indexer/fingerprint.py`
> — `normalize_tier1` and `round_mtime_ns` — consumed by the live scan modes
> `scanner/_modes/incremental.py` and `scanner/_modes/quick.py`.
>
> The **phase-8 adversarial-retrospective fixes** (post-PR-#29) then closed the
> remaining gaps, all documented inline below where they touch a section:
>
> 1. **FS-aware gating layer.** `normalize_tier1` only covered the per-file
>    compare; the gates that run _first_ (the Merkle root short-circuit, the
>    `compute_merkle_delta` bulk-change freeze guard, and the dir-mtime subtree
>    skip) still compared raw mtime. They are now FS-aware too:
>    `_walker.py::_build_disk_fingerprints` / `_sample_fresh_fingerprints` bucket
>    mtime via the disk capability, and the dir-mtime compare in incremental /
>    quick buckets both sides. NTFS / APFS / ext4 (granularity 1) stay
>    byte-identical.
> 2. **AC-05 delivered end-to-end.** The illegal-name gate now runs _after_
>    destination resolution in `dispatch/_movie.py` / `_tv.py`, using the
>    resolved `capability.illegal_name_regex` (POSIX dest → colon names allowed;
>    NTFS dest → skipped).
> 3. **Override keyed on the stable disk label.** The scanner `fs_type_overrides`
>    map is keyed on `DiskConfig.id` (== the immutable `DiskRow.label`), not on
>    the mutable `mount_path`, so a runtime remount can no longer drop the
>    operator override.
> 4. **`forbids_*` are derived.** `forbids_unix_perms` / `forbids_apple_metadata`
>    are now read-only `@property` derived from `rsync_flags` (see §4.3), not
>    stored fields that "drive" the flags.

---

## 1. Purpose & Motivation

The pipeline writes media to storage disks via `rsync` and tracks files via a
SQLite indexer. Both subsystems assume **one** filesystem: NTFS mounted through
macFUSE. That assumption is hardcoded, duplicated, and undocumented:

- The transfer layer (`dispatch/_transfer.py`) builds a **byte-identical**
  static `rsync` flag list in two places (`rsync()` and `rsync_merge()`), tuned
  exclusively for NTFS-via-macFUSE (`--no-perms --no-owner --no-group` to dodge
  macFUSE `EPERM` on `chmod`/`chown`, `--no-times --omit-dir-times` to suppress
  `utimes` warnings, `--exclude=.DS_Store --exclude=._*` because NTFS rejects
  AppleDouble files). On a native POSIX filesystem (HFS+, APFS, ext4) these flags
  silently discard metadata the indexer could rely on, and `--no-times` actively
  harms the indexer's mtime-based drift detection.
- Filesystem-type detection is implemented **three independent times** with three
  different timeout budgets and two different match styles (substring vs
  exact-token) — three places to fix on any `mount` output-format change.
- A latent **dead-branch bug** lives in Spotlight detection: it tests
  `fs_type == "macfuse"` but real macFUSE-NTFS mounts report `ufsd_NTFS`, so the
  branch never fires on production disks (masked by a `!= "apfs"` fallthrough).
- The indexer's tier-1 drift detector compares `(size, mtime_ns, ctime_ns)`
  exactly. On exFAT (2s mtime granularity, no ctime) or ext4 (ctime mutates on
  metadata ops) this would trigger **perpetual partial re-hashing**.

The concrete next storage target is **HFS+ on AppleRAID**: native macOS, full
POSIX permissions/ownership, no macFUSE, reliable ~1s mtime, AppleRAID presents
as a single volume. On HFS+ the `--no-perms/--no-owner/--no-group` flags are not
merely unnecessary — applying them blindly would be **wrong**, discarding
ownership the OS can actually honour. The pipeline must keep its current NTFS
behaviour byte-for-byte while gaining the ability to do the right thing per
filesystem.

**Solution**: a small, fully-unit-testable `FilesystemCapability` table keyed off
a detected (canonicalised) filesystem type, fronted by one cached `FsProbe` that
replaces the three duplicated parsers. The transfer and drift layers consume the
table instead of hardcoded literals. The NTFS entry reproduces today's behaviour
exactly; `"unknown"` defaults to the NTFS-safe restrictive superset.

---

## 2. Goals / Non-goals

### Goals

- Support every mainstream filesystem (APFS, HFS+, ext4, exFAT, NTFS-via-macFUSE)
  **without losing current NTFS behaviour** — the NTFS path stays byte-identical.
- Consolidate the three independent `mount`-parsers (`indexer/db.py`,
  `indexer/scanner/_spotlight.py`, `indexer/scanner/__init__.py`) into one cached
  `FsProbe` with a single canonicalisation function.
- Introduce a data-only `FilesystemCapability` strategy table keyed off canonical
  FS type: rsync flags, Unix-perms tolerance, AppleDouble/xattr handling,
  illegal-name policy, mtime/ctime drift knobs, dir-mtime reliability default.
- Make `dispatch/_transfer.py` (both `rsync()` and `rsync_merge()`) and the
  indexer tier-1 drift comparison consume the capability table.
- Fix the `ufsd_NTFS` dead-branch asymmetry in `_spotlight.try_attach`, with a
  regression test that reproduces it.
- Add an optional `DiskConfig.fs_type` override (escape hatch for unrecognised
  driver tokens such as `fuse-t`), auto-detected when absent.
- Add a `multifs` pytest marker exercising every FS path with faked
  `mount`/`stat` fixtures — **no real disks required**.

### Non-goals

- **Network filesystems (NFS/SMB)** — out of scope (per ROADMAP non-goal).
- **Changing the indexer schema** beyond additive capability metadata. No new
  columns; the storage side already tolerates NULL ctime (`drift.py:194`).
- **Migration scripts.** Per no-back-compat-before-v1, `config/disks.json5` and
  the DB evolve in place on the single mono-user instance.
- **Cross-mount `os.rename` rework.** The same-FS staging invariant
  (`_move_new` rsyncs into `dest.parent/_tmp_dispatch_*` then `os.rename`) is
  documented as a risk (§7), not refactored here.
- **A Linux `mount`/`findmnt` parser.** ext4 capability ships as **data only**;
  the `FsProbe` parser stays macOS-oriented (open question §8).
- **Ghost-inode online repair.** The unremovable-`?`-perms macFUSE-NTFS issue has
  no online code fix; surfacing it is an open question (§8), not committed scope.

---

## 3. Current state (evidence-backed, verified 2026-05-28, HEAD `1c4636eb`)

### 3.1 Dispatch transfer layer — the hardcoding hotspot

`personalscraper/dispatch/_transfer.py` (281 non-blank LOC):

- `rsync()` lines **103-115** and `rsync_merge()` lines **163-179** build the
  **byte-identical** flag prefix:
  ```
  -a --no-perms --no-owner --no-group --no-times --omit-dir-times --inplace --partial --exclude=.DS_Store --exclude=._*
  ```
  No shared constant. The NTFS rationale is documented inline in the `rsync()`
  body (lines 88-102). `--inplace`, `--partial`, and the `--checksum` omission are
  FS-agnostic cache-pressure decisions and must be kept regardless of FS.
- `force_rmtree()` (chmod+retry handler) — best-effort; `chmod` is a no-op on NTFS
  (`docs/reference/storage.md`).
- `has_ntfs_illegal_names()` line **275-290**: uses `text_utils._NTFS_ILLEGAL`,
  which is `_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*]')` (`text_utils.py:35`,
  aliased at `text_utils.py:42`).

Call sites: `_movie.py:203` (`rsync` via `dispatcher._rsync`), `_tv.py:198`
(`rsync_merge`); pre-scans `_movie.py:43`, `_tv.py:43` (`has_ntfs_illegal_names`).
The same NTFS name policy is re-enforced in `verify/checker.py:653`
(`_NTFS_ILLEGAL.search`, `Severity.ERROR`).

`Dispatcher` already holds disk configs (`dispatcher.py:81`:
`self._disk_configs = get_disk_configs(config)`), so it is the natural place to
resolve a capability per disk and thread it down. `_move_new`
(`dispatcher.py:364-396`) rsyncs into `dest.parent / f"_tmp_dispatch_{dest.name}"`
(same disk) **then** `os.rename(tmp_dir, dest)` — atomic only because tmp and dest
share a mount.

### 3.2 Three independent mount-parsers

| #   | Function                                          | File:lines                                   | Timeout                      | Match style                                           |
| --- | ------------------------------------------------- | -------------------------------------------- | ---------------------------- | ----------------------------------------------------- |
| 1   | `_find_ntfs_mount` + `_MACFUSE_FSTYPES`           | `indexer/db.py:176-228`                      | **5s** (`db.py:194`)         | **substring** (`db.py:218`: `any(t in fstype_raw …)`) |
| 2   | `detect_fs_type` / `_parse_mount_output`          | `indexer/scanner/_spotlight.py:37-112`       | **10s** (`_spotlight.py:81`) | **exact** first-token `.lower()` (`_spotlight.py:66`) |
| 3   | `_check_mount_flags` + `_RECOMMENDED_MOUNT_FLAGS` | `indexer/scanner/__init__.py:87-95, 225-306` | **10s** (`__init__.py:256`)  | re-parses parenthesised flag block                    |

`_MACFUSE_FSTYPES = frozenset({"fuse_osxfuse", "osxfuse", "macfuse", "ntfs", "fuse-t"})`
(`db.py:176`). `_RECOMMENDED_MOUNT_FLAGS` = `{noatime, noappledouble, noapplexattr,
defer_permissions, allow_other}` (`__init__.py:87-95`, exactly 5). `open_db` also
calls `_find_ntfs_mount` (`db.py:358`).

### 3.3 The dead-branch / asymmetry bug

`_parse_mount_output` returns `tokens[0].lower()` (`_spotlight.py:66`) → a real
`ufsd_NTFS` line yields `"ufsd_ntfs"`. `try_attach` checks `fs_type == "macfuse"`
(`_spotlight.py:258`) — never matches — and falls through to the
`if fs_type != "apfs"` branch (`_spotlight.py:281`, logs `reason="not_apfs"`, not
the macfuse-specific `flag_ignored_macfuse`/`skipped_macfuse` warnings). Because
`db.py` uses **substring** matching, `db.py` correctly detects real NTFS mounts
while `_spotlight` does not normalise `ufsd_ntfs`. Tests inject `fs_type_fn`
(`_spotlight.py:216,254`), so the real mount-parse path is never exercised. The
exact-token-vs-substring asymmetry is the root cause.

### 3.4 Indexer mtime/ctime coupling

- `fingerprint_tier1(stat)` returns `(stat.st_size, stat.st_mtime_ns,
stat.st_ctime_ns)` (`fingerprint.py:68-81`).
- `reconcile_file` builds `t1_current = (size, clamp_mtime_ns(mtime), ctime_ns)`
  (`drift.py:190,193`) and `t1_stored = (size_bytes, mtime_ns, ctime_ns or 0)`
  (`drift.py:194` — **already NULL-ctime tolerant** on the stored side). On
  mismatch (and not racy) it escalates to `xxh3_partial` (1 MiB default,
  `fingerprint.py:189`; called `drift.py:235`) and returns `"tier1_drift"` if
  content matches (`drift.py:258-259`).
- `clamp_mtime_ns` (`drift.py:68`) clamps only future/negative values — **not**
  low-precision/coarse mtimes.

> **Shipped reality (see the 2026-05-29 re-scope note).** The above analysed
> `reconcile_file` because it was, at design time, the assumed home of the
> tier-1 comparison. It is in fact dead/test-only code with no production caller
> and was **left untouched** — the FS-aware tier-1 comparison shipped as
> `fingerprint.normalize_tier1` (built on `round_mtime_ns`), consumed by the
> **live** scan modes `scanner/_modes/incremental.py` (per-file `existing` vs
> `current` compare) and `scanner/_modes/quick.py` (paranoia branch). See §4.5.

### 3.5 Existing per-FS adaptation (the generalisation template)

- `_verify_dir_mtime_reliable()` (`_walker.py:61-96`): writes a probe child,
  compares parent mtime, returns a boolean. Consumed at
  `scanner/__init__.py:529` (`dir_mtime_reliable`) and threaded into quick-mode.
  This is the **only** existing runtime per-FS behaviour switch — the proven
  probe→boolean→behaviour-switch template to generalise into the capability.
- `_log_stat_failed` (`_walker.py:40-53`): demotes `errno == 2` (ENOENT) ghost
  dirents to DEBUG (`reason="ghost_dirent"`), keeps others at WARNING.

### 3.6 Config and atomic-rename surface

- `DiskConfig` = `{id, path, categories}` only (`conf/models/disks.py:11-27`) —
  **no** `fs_type`.
- `conf/models/indexer.py` `db_path` validator rejects paths via
  `str(resolved).startswith("/Volumes/")` (string prefix, not FS detection); the
  comment explicitly says "macFUSE-NTFS and network mounts" but the check is a
  blunt prefix. `db.py::open_db` _also_ calls `_find_ntfs_mount` (`db.py:358`) —
  the two checks disagree on method.
- `os.rename` at **7** non-test sites: `sorter/sorter.py:191,196`;
  `dispatch/_movie.py:214,215,227`; `dispatch/dispatcher.py:396`;
  `ingest/ingest.py:237`. All assume same-FS staging; cross-FS would raise EXDEV.

### 3.7 Test baseline gaps (verified)

- **No golden test pins the exact rsync argv today** —
  `rg "no-perms|omit-dir-times" -g '*.py' tests/` returns nothing. Phase 3's
  "NTFS byte-identical" guarantee therefore has **no current baseline**; the
  golden test must be authored as the _first_ sub-task of Phase 3, against the
  current code, before any refactor.
- The `multifs` pytest marker does **not** exist. The registered markers
  (`pyproject.toml:75-83`) are: `e2e`, `roundtrip`, `e2e_torrent`,
  `e2e_idempotence`, `network`, `slow`, `darwin_only`.

### 3.8 Module-size headroom (`scripts/check-module-size.py`)

Soft warn 800, hard block 1000 non-blank LOC; **`__init__.py` is excluded**
(`scripts/check-module-size.py:22` `EXCLUDED_FILENAMES = {"__init__.py"}`). Target
files' current non-blank LOC: `_transfer.py` 281, `db.py` 588,
`scanner/__init__.py` 621, `_spotlight.py` 248, `drift.py` 520. All have headroom,
but new capability/probe logic goes into **new modules**, never inlined into the
near-ceiling `verify/checker.py` (716 non-blank).

---

## 4. Proposed design

### 4.1 Module layout

```
personalscraper/
├── indexer/
│   ├── _fs_probe.py            (NEW — one cached mount parser + canonicalisation)
│   ├── _fs_capability.py       (NEW — FilesystemCapability strategy table + lookup)
│   ├── db.py                   (MODIFY — _find_ntfs_mount delegates to _fs_probe)
│   ├── drift.py                (MODIFY — tier-1 comparison reads capability knobs)
│   └── scanner/
│       ├── _spotlight.py       (MODIFY — detect_fs_type delegates; ufsd bug fixed)
│       └── __init__.py         (MODIFY — _check_mount_flags delegates to _fs_probe)
├── dispatch/
│   ├── _transfer.py            (MODIFY — rsync()/rsync_merge() consume capability)
│   └── dispatcher.py           (MODIFY — resolve capability per dest disk once)
└── conf/
    └── models/
        ├── disks.py            (MODIFY — optional fs_type field)
        └── indexer.py          (MODIFY — db_path reject becomes capability-aware)

config.example/
└── disks.json5                 (MODIFY — commented fs_type example)
```

Two new modules only; everything else is surgical modification preserving public
import paths.

### 4.2 New module — `personalscraper/indexer/_fs_probe.py`

Single source of truth for `(mount_point, fs_type, flags)`. Target < 300 LOC.

```python
@dataclass(frozen=True)
class MountInfo:
    """One mounted filesystem as parsed from `mount`."""
    mount_point: str
    fs_type: str               # canonicalised (see canonical_fs_type)
    raw_fs_type: str           # original first token, lowercased
    flags: frozenset[str]      # parenthesised option block tokens


def canonical_fs_type(raw: str) -> str:
    """Normalise a raw `mount` fs-type token to a canonical capability key.

    Recognises NTFS-via-macFUSE under every known driver spelling
    (`ufsd_ntfs`, `ntfs`, `fuse_osxfuse`, `osxfuse`, `macfuse`, `fuse-t`) →
    `"ntfs_macfuse"`. Also `apfs`, `hfs`/`hfsplus` → `"hfsplus"`, `exfat`,
    `ext4`. Anything else → `"unknown"`. Substring-aware so `ufsd_NTFS` is
    detected (fixes the exact-token asymmetry with db.py)."""


def probe_mount(path: str) -> MountInfo | None:
    """Return the MountInfo for the volume containing `path`, or None.

    Backed by a module-level cache keyed on a single `mount` invocation
    (10s timeout). Early-returns None on non-Darwin and on subprocess
    failure/timeout. The cache holds the parsed `mount` table; a process-
    lifetime single shell-out is acceptable (mounts do not change mid-run)."""
```

Decision — **single 10s probe**: consolidating the 5s/10s/10s budgets onto one
10s shell-out relaxes `db.py`'s former 5s pre-open guard. This is an **intentional,
documented behaviour change** (not silent), and it is the only behaviour change in
the consolidation phase.

Decision — **substring canonicalisation, not exact-token**: `db.py` was already
correct via substring; the canonicaliser adopts that style so `ufsd_NTFS` maps to
`ntfs_macfuse` everywhere, eliminating the `_spotlight` dead branch at the root.

### 4.3 New module — `personalscraper/indexer/_fs_capability.py`

Pure data + lookup — the heart of the abstraction. Target < 250 LOC.

```python
@dataclass(frozen=True)
class FilesystemCapability:
    """Per-filesystem behaviour strategy. Pure data; fully unit-testable."""
    fs_type: str                              # canonical key this entry serves (compare=False)
    rsync_flags: tuple[str, ...]              # full prefix, excluding source/dest — SINGLE SOURCE OF TRUTH
    illegal_name_regex: re.Pattern[str] | None  # None = no name restriction
    tier1_uses_ctime: bool                    # include ctime in tier-1 comparison
    mtime_granularity_ns: int                 # round mtime to this before compare (1 = exact)
    dir_mtime_reliable_default: bool | None   # None = probe at runtime (_walker template)

    # forbids_* are DERIVED read-only properties, not stored fields — they read
    # straight off rsync_flags so they can never desync from the flags actually
    # passed to rsync (phase-8 retro fix; see the 2026-05-29 re-scope note):
    @property
    def forbids_unix_perms(self) -> bool:
        return "--no-perms" in self.rsync_flags

    @property
    def forbids_apple_metadata(self) -> bool:
        return "--exclude=.DS_Store" in self.rsync_flags


def capability_for(fs_type: str) -> FilesystemCapability:
    """Look up the capability for a canonical fs_type. `"unknown"` returns a
    value byte-identical to `"ntfs_macfuse"` (the NTFS-safe restrictive
    superset)."""
```

Capability entries (decisions + rationale):

(`forbids_unix_perms` / `forbids_apple_metadata` below are **derived** read-only
properties, not stored fields — the table lists the value each derives from
`rsync_flags`, not an independent knob.)

| fs_type        | rsync_flags (beyond `-a --inplace --partial`)                                                    | forbids_unix_perms (derived) | forbids_apple_metadata (derived) | illegal_name_regex | tier1_uses_ctime | mtime_granularity_ns | dir_mtime_reliable_default |
| -------------- | ------------------------------------------------------------------------------------------------ | ---------------------------- | -------------------------------- | ------------------ | ---------------- | -------------------- | -------------------------- |
| `ntfs_macfuse` | `--no-perms --no-owner --no-group --no-times --omit-dir-times --exclude=.DS_Store --exclude=._*` | True                         | True                             | `_NTFS_ILLEGAL`    | True             | 1                    | None (probe)               |
| `unknown`      | **== `ntfs_macfuse`**                                                                            | True                         | True                             | `_NTFS_ILLEGAL`    | True             | 1                    | None                       |
| `apfs`         | (none)                                                                                           | False                        | False                            | None               | True             | 1                    | True                       |
| `hfsplus`      | (none)                                                                                           | False                        | False                            | None               | True             | 1_000_000_000        | True                       |
| `exfat`        | `--exclude=.DS_Store --exclude=._*`                                                              | False                        | True                             | None               | False            | 2_000_000_000        | None                       |
| `ext4`         | (none)                                                                                           | False                        | False                            | None               | True             | 1                    | None                       |

Notes:

- The `ntfs_macfuse` `rsync_flags` tuple **must** reproduce today's literal list
  byte-for-byte (verified order in §3.1) — this is the pinned-golden invariant.
- The `unknown` fallback **must equal** `ntfs_macfuse` (mandatory restrictive
  default — a permissive default could write Unix perms / AppleDouble to a real
  NTFS disk and trigger the very EPERM/journal problems the current flags avoid).
- `hfsplus`: full POSIX perms (the concrete AppleRAID target), reliable ~1s
  mtime; `mtime_granularity_ns=1_000_000_000` documents HFS+ 1s precision so a
  sub-second jitter does not spuriously drift.
- `exfat`: no ctime, 2s mtime granularity → `tier1_uses_ctime=False`,
  `mtime_granularity_ns=2_000_000_000`; keeps the AppleDouble excludes (exFAT
  stores them but they are macOS junk).
- `ext4`: `tier1_uses_ctime=True` with a documented caveat that ctime mutates on
  metadata ops (candidate for a future granularity widening; data-only until a
  real ext4 target exists — see §8).

### 4.4 Transfer integration

Add one private builder to `_transfer.py`:

```python
def _build_rsync_cmd(
    source: Path, dest: Path, capability: FilesystemCapability,
    *, delete: bool = False, backup_dir: Path | None = None,
) -> list[str]:
    """Build the rsync argv from a capability. Single source of truth for both
    rsync() and rsync_merge() — replaces the two hardcoded literal lists."""
```

`rsync()` and `rsync_merge()` gain a `capability: FilesystemCapability` parameter
and delegate to `_build_rsync_cmd`. `has_ntfs_illegal_names` gains a
`pattern: re.Pattern[str] | None` parameter (None → no-op skip). **Public import
path `personalscraper.dispatch._transfer` and all function names stay stable.**

`Dispatcher.__init__` resolves a capability per disk once (not per file):
`{disk.id: capability_for(disk.fs_type or canonical_fs_type(probe_mount(disk.path).fs_type))}`,
and threads it through `_rsync`/`_move_new`, `_movie.py:203`, `_tv.py:198`, and the
`_movie.py:43`/`_tv.py:43` pre-scans.

### 4.5 Drift integration (AS SHIPPED — not `reconcile_file`)

> This section originally proposed threading the capability into
> `drift.py::reconcile_file`. **That did not ship.** `reconcile_file` has no
> production caller (dead/test-only; tech-debt-2 removal candidate) and was left
> untouched — it takes **no** `FilesystemCapability`. The FS-aware tier-1 work
> instead landed as the two pure helpers below, consumed by the **live** scan
> modes that actually run during `personalscraper scan`.

Two new helpers in `personalscraper/indexer/fingerprint.py`:

- `round_mtime_ns(mtime_ns, capability)` — floors an mtime to
  `capability.mtime_granularity_ns` (identity when granularity == 1).
- `normalize_tier1(size, mtime_ns, ctime_ns, capability)` — returns the
  capability-aware tier-1 tuple: `(size, round_mtime_ns(mtime), ctime_ns)` when
  `capability.tier1_uses_ctime`, else the 2-tuple `(size, round_mtime_ns(mtime))`.

Both default `capability=NTFS_MACFUSE` (granularity 1, ctime kept), so any
un-threaded caller is byte-identical to the legacy `(size, mtime_ns, ctime_ns)`
tuple.

These are consumed at the **per-file compare** by:

- `scanner/_modes/incremental.py::_walk_dir_incremental` — `existing` vs
  `current` tier-1 compare via `normalize_tier1(..., capability)`.
- `scanner/_modes/quick.py::_run_paranoia_branch` — bucketed mtime compare via
  `round_mtime_ns(..., capability)`.

**Phase-8 retro addition — the gating layer is FS-aware too.** `normalize_tier1`
only covered the per-file compare. The gates that run _first_ and decide whether
a walk happens now bucket mtime through the disk capability as well, so coarse
filesystems are consistent end-to-end:

- The **Merkle root short-circuit** and the **`compute_merkle_delta` bulk-change
  freeze guard** (`DiskBulkChangeDetected`): `_walker.py::_build_disk_fingerprints`
  buckets the DB-side `mtime_ns` and `_walker.py::_sample_fresh_fingerprints`
  buckets the FS-side `st_mtime_ns`, both via `round_mtime_ns(..., capability)`.
  Because both sides bucket with the same capability, `compute_merkle_root` and
  `compute_merkle_delta` need no internal change.
- The **dir-mtime subtree skip** in incremental and quick mode buckets **both**
  the stored `path.dir_mtime_ns` and the live FS value before comparing.

`_verify_dir_mtime_reliable` is consulted only when
`capability.dir_mtime_reliable_default is None`; otherwise the hard-wired
capability value is used directly (resolved once per disk in
`scanner/_scan_orchestrator.py`).

The `ntfs_macfuse`/`unknown`/`apfs`/`ext4` paths (ctime=True, granularity=1) are
**byte-identical** to the legacy behaviour — bucketing is the identity transform,
so the Merkle root, the delta, and the dir-mtime compare are all unchanged.

---

## 5. Phasing

Lifecycle: `/implement:feature` → branch `feat/multi-filesystem`, Conventional
Commits scope `(multi-filesystem)`, SemVer **minor** (0.17.0 → 0.18.0). Every
phase gate runs `make lint && make test && make check` (all green) and ends in a
`chore(multi-filesystem): phase N gate — …` milestone commit. No migration
scripts. Module-size ceiling respected (new modules < 800). Each fixed bug gets a
regression test.

### Phase 1 — Consolidate the 3 mount-parsers into one cached `FsProbe`

- **Objective**: single source of truth for `(mount_point, fs_type, flags)`; fix
  the `ufsd_NTFS` canonicalisation asymmetry at the root.
- **Create**: `personalscraper/indexer/_fs_probe.py` (`MountInfo`, `probe_mount`,
  `canonical_fs_type`, module-level cache, single 10s `mount` shell-out).
- **Modify**: `db.py::_find_ntfs_mount`, `_spotlight.py::detect_fs_type` /
  `_parse_mount_output`, `scanner/__init__.py::_check_mount_flags` to delegate to
  `_fs_probe`. Preserve each public name and behaviour. Document the 5s→10s
  `db.py` pre-open budget change in the commit body.
- **Sub-tasks**: (1) write `_fs_probe.py`; (2) regression test
  `tests/indexer/test_fs_probe.py` feeding a real line
  `… on /Volumes/Disk1 (ufsd_NTFS, local, noatime)` asserting
  `canonical_fs_type("ufsd_NTFS") == "ntfs_macfuse"` (reproduces the dead-branch
  root cause); (3) rewire the three callers; (4) keep existing db/scanner/spotlight
  tests green.
- **Effort**: M · **Risk**: medium (touches three live detection sites) ·
  **Deps**: none.
- **Phase gate**: `make lint && make test && make check`. Residual grep:
  `rg "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/` returns hits only
  inside `_fs_probe.py`.

### Phase 2 — Define the `FilesystemCapability` strategy table

- **Objective**: pure data + lookup.
- **Create**: `personalscraper/indexer/_fs_capability.py`
  (`FilesystemCapability`, `capability_for`, the six entries from §4.3).
- **Sub-tasks**: (1) write the dataclass + table; (2)
  `tests/indexer/test_fs_capability.py` asserting each fs_type's fields and
  `capability_for("unknown") == capability_for("ntfs_macfuse")`; (3) assert the
  `ntfs_macfuse.rsync_flags` tuple equals the literal list pinned in §3.1.
- **Effort**: M · **Risk**: low · **Deps**: Phase 1 (canonical fs_type keys).
- **Phase gate**: `make lint && make test && make check`.

### Phase 3 — Make `_transfer.rsync`/`rsync_merge` consume the capability

- **Objective**: dispatch reads flags from the dest disk's capability; NTFS output
  byte-identical.
- **FIRST sub-task (baseline)**: author `tests/dispatch/test_transfer_argv.py`
  against **current** code, pinning the exact `rsync` argv for an NTFS dest (no
  baseline exists today — §3.7). This is the equivalence anchor.
- **Modify**: `_transfer.py` — add `_build_rsync_cmd`; give `rsync()`,
  `rsync_merge()` a `capability` param; route the `.DS_Store`/`._*` excludes
  behind `capability.forbids_apple_metadata`; give `has_ntfs_illegal_names` a
  `pattern` param driven by `capability.illegal_name_regex`. Preserve public
  import path and function names.
- **Thread**: `Dispatcher` resolves `capability_for(...)` per dest disk once and
  passes it through `_rsync`/`_move_new`, `_movie.py:203`, `_tv.py:198`, and the
  `_movie.py:43`/`_tv.py:43` pre-scans.
- **Tests**: golden argv for `ntfs_macfuse` (unchanged vs baseline) and `apfs`
  (drops `--no-perms/--no-owner/--no-group/--no-times/--omit-dir-times` and the
  AppleDouble excludes); a POSIX-target test proving a `name:with:colon` dir is
  **not** skipped by the pre-scan.
- **Effort**: L · **Risk**: medium (the live move path) · **Deps**: Phases 1-2.
- **Phase gate**: `make lint && make test && make check`. Residual grep:
  `rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py` returns 0
  (flags now come only from the capability table).

### Phase 4 — Optional `DiskConfig.fs_type` override + plumb capabilities

- **Objective**: operator escape hatch for unrecognised driver tokens; no
  re-shelling to `mount` per item.
- **Modify**: `conf/models/disks.py` — add
  `fs_type: str | None = Field(default=None, …)` (auto-detect via `_fs_probe` when
  None; explicit value overrides). Update `config.example/disks.json5` with a
  **commented** example. Per no-back-compat: edit `config/disks.json5` in place if
  desired — **no migration script**.
- **Modify**: `conf/models/indexer.py` `db_path` validator — replace the
  `/Volumes/` string-prefix reject with a capability-aware check (reject only
  WAL-unsafe fs_types such as `ntfs_macfuse`), keeping `db.py::open_db`'s
  `_find_ntfs_mount` as defense-in-depth.
- **Modify**: `Dispatcher.__init__` resolves a `{disk.id: FilesystemCapability}`
  dict (override beats autodetect).
- **Tests**: config-model round-trip for `fs_type`; override-beats-autodetect;
  a legitimate-APFS-under-`/Volumes` `db_path` is **accepted**.
- **Effort**: M · **Risk**: low · **Deps**: Phases 2-3.
- **Phase gate**: `make lint && make test && make check`.

### Phase 5 — Make indexer tier-1 drift FS-aware (HIGHER RISK — defer-able)

- **Objective**: stop exFAT/ext4 perpetual re-hashing; keep NTFS byte-identical.
- **As shipped (NOT `reconcile_file`)**: add `fingerprint.round_mtime_ns` +
  `fingerprint.normalize_tier1` (both defaulting to `NTFS_MACFUSE`) and consume
  them at the live per-file compare in `scanner/_modes/incremental.py` and the
  paranoia branch of `scanner/_modes/quick.py`. `drift.py::reconcile_file` is
  dead/test-only code and was **left untouched** (tech-debt-2 removal candidate).
  Phase-8 then extended the FS-awareness to the gating layer (Merkle root/delta +
  dir-mtime subtree skip) by bucketing mtime in
  `_walker.py::_build_disk_fingerprints` / `_sample_fresh_fingerprints` and in the
  dir-mtime compares — see §4.5.
- **Tests**: `tests/indexer/test_tier1_fs_aware.py` (exFAT no-ctime / 2 s bucket →
  no spurious drift; NTFS byte-identical), `tests/indexer/test_merkle_fs_aware.py`
  (NTFS merkle root byte-identical; coarse-FS jitter does not trip the freeze),
  `tests/indexer/test_scan_fs_aware.py` (override reaches the scan side). Branch
  coverage ≥ 90% on the new branches (`make check` gate).
- **Effort**: L · **Risk**: **high** (hottest correctness path) · **Deps**:
  Phase 2.
- **Defer option**: if no current disk is non-NTFS (open question §8), this phase
  can ship inert — the capability defaults to today's NTFS behaviour with **zero
  runtime change** — and the live exFAT/ext4 paths land when a real target exists.
- **Phase gate**: `make lint && make test && make check`.

### Phase 6 — Multi-FS test harness + SH-16 ACCEPTANCE + docs

- **Objective**: exercise all FS paths without real `/Volumes` mounts; formalise.
- **Modify**: `pyproject.toml` markers — add
  `"multifs: filesystem-capability tests using faked mount/stat fixtures (no real disks)"`.
- **Create**: fixtures faking `mount` stdout per fs_type and synthetic
  `os.stat_result` variants (no ctime, coarse mtime). Tag the capability/probe/argv
  tests with `@pytest.mark.multifs`.
- **Docs**: add a "Filesystem capability" section to `docs/reference/storage.md`
  (capability table + the 5s→10s probe note); cross-reference from
  `docs/reference/indexer.md`. Add a `0.18.0` `CHANGELOG.md` entry.
- **Author** `docs/features/multi-filesystem/ACCEPTANCE.md` (§6 criteria).
- **Effort**: M · **Risk**: low · **Deps**: Phases 1-5.
- **Phase gate**: `make lint && make test && make check`; all ACCEPTANCE criteria
  PASS.

### Phase 7 — Feature PR + review (auto-invoked)

`/implement:feature-pr` (local gate + push + PR + CI poll) then
`/implement:pr-review` (review + max-3 fix cycles + squash merge), per the
standard lifecycle.

### 5.1 Phase / risk matrix

| Phase | Risk     | Reversible | New modules         | NTFS behaviour                  |
| ----- | -------- | ---------- | ------------------- | ------------------------------- |
| 1     | Medium   | Yes        | `_fs_probe.py`      | identical (+ documented 5s→10s) |
| 2     | Low      | Yes        | `_fs_capability.py` | identical (data only)           |
| 3     | Medium   | Yes        | —                   | byte-identical (golden-pinned)  |
| 4     | Low      | Yes        | —                   | identical                       |
| 5     | **High** | Yes        | —                   | identical (capability-gated)    |
| 6     | Low      | Trivial    | —                   | identical                       |

---

## 6. Acceptance criteria (SH-16 — every criterion is an executable command + expected output)

```bash
# AC-01 — FsProbe canonicalises the real ufsd_NTFS token (reproduces the dead-branch fix)
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected stdout: ntfs_macfuse   (exit 0)

# AC-02 — unknown fs_type falls back to the NTFS-safe restrictive superset
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

# AC-11 — exactly one cached mount shell-out (probe consolidation; no duplicate parsers)
rg -c "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/_fs_probe.py
# expected stdout: 1

# AC-12 — the three old call sites no longer shell out to `mount` directly
rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (exit 1 — rg found nothing)

# AC-13 — DiskConfig accepts an optional fs_type override
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"
# expected stdout: apfs   (exit 0)

# AC-14 — full quality gate green
make check
# expected: ruff/mypy/logging OK; "NNNN passed" with 0 failed/0 errors; coverage >=90%; module-size + typed-api + cli-coverage all PASS   (exit 0)

# AC-15 — version bump landed (VERSION is the single source of truth; pyproject
# uses version = {attr = "personalscraper.__version__"}, so grepping pyproject
# would print the attr line, not the number).
cat VERSION
# expected stdout contains: 0.18.0

# AC-16 — CHANGELOG entry
grep -c "0.18.0" CHANGELOG.md
# expected stdout: >=1

# AC-17 — package still imports (smoke)
python -c "import personalscraper; print('ok')"
# expected stdout: ok   (exit 0)
```

---

## 7. Risks & mitigations

| Sev      | Risk                                                                                                                                                                                                                                                         | Mitigation                                                                                                                                                                                                                                                                    |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **High** | Phase 5 alters the hottest correctness path (the live tier-1 compare in `scanner/_modes/incremental.py` + `quick.py`, and — phase-8 — the Merkle/dir-mtime gating layer; **not** the dead `reconcile_file`); a regression silently corrupts drift detection. | Capability-gated via `normalize_tier1`/`round_mtime_ns`: NTFS/APFS/ext4 keep ctime=True & granularity=1 → byte-identical (NTFS merkle root pinned by `test_merkle_fs_aware.py`). Branch coverage ≥ 90% on new branches. Defer-able (ship inert) until a non-NTFS disk exists. |
| **High** | Phase 3 changes the live `rsync` argv; an error breaks every move.                                                                                                                                                                                           | Golden-argv test authored **first** against current code; `ntfs_macfuse` argv pinned byte-for-byte. AC-03/AC-10 enforce.                                                                                                                                                      |
| Medium   | Consolidating onto one 10s probe relaxes `db.py`'s former 5s pre-open guard.                                                                                                                                                                                 | Intentional, documented in the Phase 1 commit body and `docs/reference/storage.md`; module-level cache means a single shell-out per process.                                                                                                                                  |
| Medium   | Real `mount` tokens for the installed NTFS driver (Tuxera/Paragon/fuse-t) may differ from `ufsd_NTFS`.                                                                                                                                                       | `canonical_fs_type` is substring-aware over a known token set; `unknown` → NTFS-safe superset (never silently permissive). Open question §8.1 asks the user to confirm host tokens.                                                                                           |
| Medium   | `unknown` mis-detection on a real native disk would apply NTFS-restrictive flags (lose Unix perms).                                                                                                                                                          | Acceptable trade-off: restrictive default never _corrupts_, only over-suppresses. `DiskConfig.fs_type` override (Phase 4) is the escape hatch.                                                                                                                                |
| Low      | Cross-FS `os.rename` (staging on a different FS than the disk) raises EXDEV and would silently fail `_move_new`.                                                                                                                                             | Out of scope; documented as open question §8.3. A future `assert st_dev` guard is the fix if such a config ever appears.                                                                                                                                                      |
| Low      | ext4 ctime mutates on metadata ops → re-hashing even with the table.                                                                                                                                                                                         | ext4 ships data-only; granularity-widening deferred until a real ext4 target (§8.4).                                                                                                                                                                                          |
| Low      | macFUSE-NTFS ghost-inode `?`-perms dirents remain unremovable online.                                                                                                                                                                                        | Pre-existing; demoted to DEBUG (`_walker.py:50-51`). Surfacing as a health warning is open question §8.5, not committed scope.                                                                                                                                                |

---

## 8. Open questions (decisions left for the user)

1. **Real `mount` tokens on IznoServer.** `db.py` assumes `ufsd_NTFS`. Confirm the
   exact driver strings via `mount | grep -i ntfs` before finalising the
   `canonical_fs_type` token set — guessing risks detecting production disks as
   `"unknown"` (still safe, but sub-optimal).
2. **Is multi-FS forward-looking only?** Does any current disk run a non-NTFS FS
   today? If not, Phase 5 ships inert (NTFS default, zero runtime change) and the
   live exFAT/ext4/HFS+ drift paths land when a real target appears.
3. **Cross-mount `os.rename`.** Will any future config place staging and a disk on
   different filesystems (or a union/overlay mount)? If so, `_move_new` needs an
   explicit `assert st_dev` same-FS guard (cross-FS rename raises EXDEV).
4. **ext4 detection scope.** ext4 capability ships as **data only**; `FsProbe`'s
   parser is macOS-oriented. Is a Linux `mount`/`findmnt` parser in scope, or does
   ext4 stay detection-deferred (data-only) until the project runs on Linux?
5. **Ghost-inode surfacing.** Should the capability layer DETECT and surface the
   unremovable-`?`-perms macFUSE-NTFS condition (health warning) rather than only
   demoting the log to DEBUG?
6. **ext4 reserved blocks.** Should free-space eligibility
   (`free_space_gb >= max(min_free, size*1.5)`) account for ext4's 5% root
   reservation? Minor; deferrable.

---

## 9. References

- **Source analysis**: `docs/analysis/04-filesystem-decoupling-macfuse-ntfs.md`
  (the foundation — full evidence map, every claim re-read from source).
- **ROADMAP entry**: `ROADMAP.md` §P2 — Multi-Filesystem Support
  (`multi-filesystem`), lines 136-155 (agreed scope + non-goals).
- **Structural sibling**: `docs/features/registry/DESIGN.md` (template for section
  depth, SH-16 ACCEPTANCE table, phase/risk matrix).
- **Reference docs**: `docs/reference/storage.md` (rsync flags, disk/move rules,
  NTFS/macFUSE notes), `docs/reference/indexer.md` (scanner modes, drift),
  `docs/reference/pipeline-internals.md` (idempotence, fast-skip).
- **Project rule (CLAUDE.md)**: SH-16 — ACCEPTANCE criteria must be executable
  shell commands with documented expected output.
- **Project rule (CLAUDE.md)**: module-size soft warning 800 / hard ceiling 1000
  non-blank LOC; `__init__.py` excluded by `scripts/check-module-size.py:22`.
- **Memory**: `feedback_no_backcompat_before_v1.md` (config/DB evolve in place; no
  migration scripts), `feedback_regression_test_per_bug.md` (test-per-bug:
  `test_fs_probe.py` reproduces the `ufsd_NTFS` dead branch),
  `feedback_rg_type_filter_mandatory.md` (every `rg` carries a type/glob filter).
