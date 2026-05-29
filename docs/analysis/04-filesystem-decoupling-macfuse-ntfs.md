# Filesystem Decoupling — macFUSE/NTFS Coupling and the Missing FilesystemCapability Layer

> **Metadata** — date: 2026-05-28 · version: 0.16.0 · branch: `feat/registry` · project status: pre-v1.0, single mono-user instance, NOT in production · report scope: filesystem-type coupling in the `dispatch` and `indexer` subsystems (rsync flags, mount detection, mtime/ctime drift, atomic rename, NTFS name policy) · confidence level: **high** (every claim below was re-read from source; fact-check corrections incorporated).

---

## 1. Executive summary (TL;DR)

- **There is no filesystem-capability abstraction.** NTFS-via-macFUSE behaviour is hardcoded in the transfer layer, and filesystem-type detection is duplicated across **three** independent `mount`-parsers (`indexer/db.py`, `indexer/scanner/_spotlight.py`, `indexer/scanner/__init__.py`) with three different timeout budgets (5s / 10s / 10s).
- **The single most concentrated coupling site is `personalscraper/dispatch/_transfer.py`.** `rsync()` (lines 103-118) and `rsync_merge()` (lines 163-179) build **byte-identical** static flag lists that are correct *only* for NTFS-via-macFUSE, with no shared constant — any change requires editing two places.
- **A latent dead-branch bug exists in Spotlight detection.** `_spotlight.try_attach` (line 258) tests `fs_type == "macfuse"`, but real macFUSE-NTFS mounts report `ufsd_NTFS` as the first token, so `detect_fs_type` returns `"ufsd_ntfs"` — the `macfuse` branch never fires on production disks. It is masked because the `!= "apfs"` fallthrough (line 281) also refuses Spotlight, so behaviour is *correct by accident*. By contrast, `db.py::_find_ntfs_mount` uses **substring** matching (`db.py:218`) and therefore *does* detect `ufsd_ntfs` correctly — the asymmetry (substring vs exact-token) is the true root cause.
- **The indexer's tier-1 drift detector is mtime/ctime-coupled.** `fingerprint_tier1` = `(st_size, st_mtime_ns, st_ctime_ns)` (`fingerprint.py:81`); `drift.py::reconcile_file` escalates to a 2 MiB partial hash on any tier-1 mismatch. On exFAT (2s mtime granularity, no ctime) or ext4 (ctime changes on metadata ops) this would cause **perpetual re-hashing**. The storage layer already tolerates a NULL ctime (`drift.py:194` uses `stored.ctime_ns or 0`); only the live-side comparison needs a per-FS knob.
- **`_verify_dir_mtime_reliable` (`_walker.py:61-96`) is the one existing per-FS runtime adaptation** (probe → boolean → behaviour switch) and is the proven template for a generalised capability layer.

**Verdict:** This is real, well-localised architectural debt. The fix is a **minor** feature (additive, no breaking config change): consolidate the three mount-parsers into one cached `FsProbe`, introduce a `FilesystemCapability` table whose NTFS entry is byte-identical to today, then make `_transfer` and `drift` consume it. Phases 1-4 are low-risk consolidation that keep NTFS output byte-identical; Phase 5 (indexer drift) is the only high-risk change and can be deferred behind a capability that defaults to current NTFS behaviour.

---

## 2. Current state (evidence-backed)

### 2.1 Dispatch transfer layer — the hardcoding hotspot

`personalscraper/dispatch/_transfer.py` (332 LOC) is the single concentrated FS-coupling site.

- `rsync()` lines **103-118** and `rsync_merge()` lines **163-179** build **identical** flag lists:
  `-a --no-perms --no-owner --no-group --no-times --omit-dir-times --inplace --partial --exclude=.DS_Store --exclude=._*`. No shared constant; the NTFS rationale is documented inline in the `rsync()` docstring (lines 88-101). `--no-perms/--no-owner/--no-group` work around macFUSE EPERM on chmod/chown; `--no-times/--omit-dir-times` suppress utimes warnings; the `.DS_Store`/`._*` excludes prevent NTFS rejection of AppleDouble files. `--inplace` and the `--checksum`-omission are FS-agnostic cache-pressure decisions (keep them regardless of FS).
- `force_rmtree()` lines 35-74: chmod+retry `onexc`/`onerror` handler for macOS-protected dirs. `docs/reference/storage.md:27` notes chmod is a no-op on NTFS so this is best-effort.
- `has_ntfs_illegal_names()` lines 275-290: uses `text_utils._NTFS_ILLEGAL` (`text_utils.py:35,42` = `re.compile(r'[<>:"/\\|?*]')`).

Call sites: `_movie.py:203` (`rsync`), `_tv.py:198` (`rsync_merge`), pre-scans `_movie.py:43` and `_tv.py:43` (`has_ntfs_illegal_names`). The same NTFS name policy is re-enforced in `verify/checker.py:636` (`_check_ntfs_safe_names`, Severity.ERROR).

The `Dispatcher` already holds the disk configs (`dispatcher.py:81`: `self._disk_configs = get_disk_configs(config)`), so it is the natural place to resolve a capability per disk and thread it down.

### 2.2 Three independent mount-parsers (core architectural debt)

| # | Function | File:lines | Timeout | Match style |
|---|----------|-----------|---------|-------------|
| 1 | `_find_ntfs_mount` + `_MACFUSE_FSTYPES` | `indexer/db.py:176-228` | **5s** (`db.py:194`) | **substring** (`db.py:218`: `any(t in fstype_raw …)`) |
| 2 | `detect_fs_type` / `_parse_mount_output` | `indexer/scanner/_spotlight.py:89-112` (parse 37-67) | **10s** (`_spotlight.py:81`) | **exact** first-token `.lower()` (`_spotlight.py:66`) |
| 3 | `_check_mount_flags` + `_RECOMMENDED_MOUNT_FLAGS` | `indexer/scanner/__init__.py:225-306` (flags 87-95) | **10s** (`__init__.py:256`) | re-parses parenthesised flag block |

`_MACFUSE_FSTYPES = {fuse_osxfuse, osxfuse, macfuse, ntfs, fuse-t}` (`db.py:176`). `_RECOMMENDED_MOUNT_FLAGS = {noatime, noappledouble, noapplexattr, defer_permissions, allow_other}` (`__init__.py:87-95`, exactly 5). All three early-return on non-Darwin (`_spotlight.py:102`, `__init__.py:248`; `db.py` returns `None` on subprocess failure).

### 2.3 The dead-branch / asymmetry bug

`_parse_mount_output` returns `tokens[0].lower()` (`_spotlight.py:66`) → a real `ufsd_NTFS` line yields `"ufsd_ntfs"`. `try_attach` checks `fs_type == "macfuse"` (`_spotlight.py:258`), which never matches; flow falls through to the `fs_type != "apfs"` branch (`_spotlight.py:281`, logs `reason="not_apfs"`, NOT the macfuse-specific `flag_ignored_macfuse`/`skipped_macfuse` warnings). Because `db.py` uses **substring** matching, `db.py` *correctly* detects real NTFS mounts while `_spotlight` does not normalise `ufsd_ntfs`. Tests inject `fs_type_fn` (`_spotlight.py:254`), so the real mount-parse path is **never exercised**.

### 2.4 Indexer mtime/ctime coupling

- `fingerprint_tier1` = `(st_size, st_mtime_ns, st_ctime_ns)` (`fingerprint.py:68-81`).
- `reconcile_file` builds `t1_current` from clamped mtime + raw ctime (`drift.py:193`) and `t1_stored` from `(size, mtime_ns, ctime_ns or 0)` (`drift.py:194` — **already NULL-ctime tolerant**, a partial pre-existing accommodation). On mismatch it escalates to `xxh3_partial` (2 MiB I/O, `drift.py:234-235`) and returns `tier1_drift` if content matches (`drift.py:259`).
- `clamp_mtime_ns` (`drift.py:68-103`) clamps only future (`> now_ns`) and negative values — **not** low-precision/coarse mtimes. `_safe_mtime_ns` wraps it (`_db_writes.py:35-47`).

### 2.5 Existing per-FS adaptation and ghost inodes

- `_verify_dir_mtime_reliable` (`_walker.py:61-96`): writes a probe child, compares parent mtime, returns a boolean consumed at `scanner/__init__.py:381` and threaded to `_modes/quick.py` as `dir_mtime_reliable`. This is the only runtime per-FS behaviour switch.
- `_log_stat_failed` (`_walker.py:40-53`): demotes `errno==2` (ENOENT) ghost dirents to debug (`reason="ghost_dirent"`), keeps EACCES/EIO at warning. The known unremovable-`?`-perms issue has **no** online code workaround (offline `umount + ntfsfix` only, per project memory).

### 2.6 Config and atomic rename

- `DiskConfig` = `{id, path, categories}` only (`conf/models/disks.py:11-27`) — **no** `fs_type`. `config/disks.json5` lists 4 disks under `/Volumes/Disk[1-4]/medias` with no FS hint.
- `conf/models/indexer.py:187` rejects `db_path` via `str(resolved).startswith("/Volumes/")` (string prefix, not FS detection); `db.py::open_db` (357-360) *also* calls `_find_ntfs_mount` — the two checks disagree on method.
- `os.rename` appears at **7** non-test sites: `sorter.py:191,196`; `_movie.py:214,215,227`; `ingest.py:237`; `dispatcher.py:396`. `_move_new` (`dispatcher.py:379-396`) rsyncs into `dest.parent/_tmp_dispatch_*` (same disk) **then** `os.rename` — atomic only because tmp and dest share a mount. `ingest.py:200` docstring already notes "atomic rename on the same filesystem".

### 2.7 Test baseline gaps (verified)

- **No golden test pins the exact rsync argv today** (`rg "no-perms|omit-dir-times" -g '*.py' tests/` returns nothing). Phase 3's "NTFS byte-identical" guarantee therefore has **no current baseline** — the golden test must be authored as the *first* step of Phase 3 against the current code, before any refactor.
- The `multifs` pytest marker does **not** exist; only `darwin_only` exists (`pyproject.toml`).

---

## 3. Problems & risks

| Sev | Problem | Evidence |
|-----|---------|----------|
| **High** | rsync flag list hardcoded for NTFS-macFUSE and duplicated verbatim across two functions; no shared constant. On APFS/ext4 the flags discard metadata the indexer could rely on; `--no-times` actively harms tier-1 mtime drift. | `_transfer.py:103-118` & `163-179` |
| **High** | FS-type detection implemented 3× with independent parsers, 3 timeout budgets, 2 match styles (substring vs exact). 3 places to fix on `mount` format change. | `db.py:176-228`, `_spotlight.py:89-112`, `__init__.py:225-306` |
| **High** | Tier-1 drift compares ctime + exact mtime → exFAT/ext4 targets cause perpetual partial re-hashing. No per-FS knob on the live-side comparison. | `fingerprint.py:81`, `drift.py:193-235` |
| **Medium** | Spotlight `macfuse` branch is dead on real disks (`ufsd_NTFS` → `ufsd_ntfs` ≠ `macfuse`); macfuse-specific warnings never fire; untested. | `_spotlight.py:66,258,281` |
| **Medium** | NTFS-illegal-name pre-scan + AppleDouble excludes are unconditional → on an APFS/ext4 target, legal names (`:` etc.) would be needlessly skipped. | `_movie.py:43`, `_tv.py:43`, `verify/checker.py:636`, `_transfer.py:113-114,275-290` |
| **Medium** | `DiskConfig` has no `fs_type` and no override; FS knowledge is runtime-only (no escape hatch for unrecognised tokens like fuse-t). | `conf/models/disks.py:11-27` |
| **Low** | `db_path` `/Volumes` rejection is a string-prefix heuristic; a legitimate APFS volume under `/Volumes` would be wrongly rejected. | `conf/models/indexer.py:187` |
| **Low** | `os.rename` atomic-commit invariant relies on same-FS staging; undocumented; cross-FS rename raises EXDEV and would silently fail the commit. | `dispatcher.py:379-396`, 7 `os.rename` sites |

---

## 4. Implementation plan

**Codename suggestion:** `fs-capability`
**SemVer:** **minor** (Y+1 → 0.17.0) — purely additive, no breaking config/DB change.
**Branch:** `feat/fs-capability`
**Commits:** Conventional, scope `(fs-capability)`. Phase gates (`make lint && make test && make check` all green), squash merge.
**Hard rules honoured:** no migration scripts (config/DB evolve in place); module-size ceiling 1000 LOC (new modules stay < 800); regression-test-per-bug; Google-style docstrings.

### Phase 1 — Consolidate the 3 mount-parsers into one cached `FsProbe`
- **Objective:** single source of truth for `(mount_point, fs_type, flags)`; fix the `ufsd_NTFS` asymmetry.
- **Create:** `personalscraper/indexer/_fs_probe.py` (keep < 300 LOC). Expose `probe_mount(path: str) -> MountInfo | None` and a module-level cache keyed on a single `mount` invocation (10s timeout). `MountInfo` = frozen dataclass `{mount_point: str, fs_type: str, flags: frozenset[str]}`. Add `canonical_fs_type(raw: str) -> str` normalising `ufsd_NTFS/ntfs/fuse_osxfuse/osxfuse/macfuse/fuse-t` → `"ntfs_macfuse"`; `apfs`; `exfat`; `ext4`; else `"unknown"`.
- **Modify:** rewrite `db.py::_find_ntfs_mount`, `_spotlight.py::detect_fs_type`, `__init__.py::_check_mount_flags` to delegate to `_fs_probe`. Preserve each public name and behaviour. **Note the timeout change:** `db.py` currently uses 5s; collapsing onto a single 10s probe relaxes the pre-open latency budget — document this explicitly in the DESIGN as an intentional behaviour change.
- **Regression test (mandatory):** `tests/indexer/test_fs_probe.py` feeding a real `mount` line `… on /Volumes/Disk1 (ufsd_NTFS, local, noatime)` and asserting `canonical_fs_type` → `"ntfs_macfuse"` (reproduces the dead-branch root cause before the Phase 2 fix).
- **Effort:** M · **Risk:** medium · **Deps:** none.

### Phase 2 — Define the `FilesystemCapability` strategy table
- **Objective:** pure data + lookup; the heart of the abstraction.
- **Create:** `personalscraper/indexer/_fs_capability.py` — frozen dataclass `FilesystemCapability` fields: `rsync_flags: tuple[str, ...]`, `forbids_unix_perms: bool`, `forbids_apple_metadata: bool`, `illegal_name_regex: re.Pattern | None`, `tier1_uses_ctime: bool`, `mtime_granularity_ns: int`, `dir_mtime_reliable_default: bool | None` (None = probe). Provide `capability_for(fs_type: str) -> FilesystemCapability`.
- **Constraints:** the `ntfs_macfuse` entry **must** reproduce today's exact flag list and `_NTFS_ILLEGAL` regex byte-for-byte. The `"unknown"` fallback **must equal** `ntfs_macfuse` (safest restrictive superset). `apfs`: `forbids_unix_perms=False`, `forbids_apple_metadata=False`, `illegal_name_regex=None`, `tier1_uses_ctime=True`, `mtime_granularity_ns=1`. `exfat`: `tier1_uses_ctime=False`, `mtime_granularity_ns=2_000_000_000`. `ext4`: `tier1_uses_ctime=True` with a note that ctime mutates on metadata ops (candidate for granularity widening).
- **Test:** `tests/indexer/test_fs_capability.py` asserts each fs_type's fields; assert `capability_for("unknown") == capability_for("ntfs_macfuse")`.
- **Effort:** M · **Risk:** low · **Deps:** Phase 1 (canonical fs_type).

### Phase 3 — Make `_transfer.rsync`/`rsync_merge` consume capability
- **Objective:** dispatch reads flags from the **dest disk's** capability; NTFS output byte-identical.
- **FIRST sub-task (baseline):** author the golden-argv test `tests/dispatch/test_transfer_argv.py` against **current** code, pinning the exact `rsync` argv for an NTFS dest. (No baseline exists today — confirmed.)
- **Modify:** `_transfer.py` — add a single private builder `_build_rsync_cmd(source, dest, capability, *, delete=False, backup_dir=None)`; replace both literal lists. Move `has_ntfs_illegal_names` and the `.DS_Store`/`._*` excludes behind `capability.forbids_apple_metadata` / `capability.illegal_name_regex`. Add a `capability` param to `rsync()`/`rsync_merge()`.
- **Thread:** `Dispatcher` resolves `capability_for(canonical_fs_type(...))` for the dest disk once per dispatch (not per file) and passes it through `_movie.py:203`, `_tv.py:198`, and the `_movie.py:43`/`_tv.py:43` pre-scans. **Preserve public import path** `personalscraper.dispatch._transfer` and keep function names stable.
- **Tests:** golden argv for `ntfs_macfuse` (unchanged) and `apfs` (drops `--no-perms/--no-owner/--no-group/--no-times/--omit-dir-times` and the AppleDouble excludes); a POSIX-target test proving a `name:with:colon` dir is NOT skipped.
- **Effort:** L · **Risk:** medium · **Deps:** Phases 1-2.

### Phase 4 — Optional `DiskConfig.fs_type` override + plumb capabilities
- **Objective:** operator escape hatch; no re-shelling to `mount` per item.
- **Modify:** `conf/models/disks.py` add `fs_type: str | None = Field(default=None, …)` (auto-detect via `_fs_probe` when None; explicit value overrides). Update `config.example/disks.json5` with a **commented** example. Per no-backcompat-before-v1: edit `config/disks.json5` in place if desired, **no migration script**.
- **Modify:** `Dispatcher.__init__` (`dispatcher.py:81`) resolves a `FilesystemCapability` per disk into a dict and passes it to transfer calls; optionally surface `fs_type` in `disk_scanner.get_disk_status` for diagnostics.
- **Modify:** `conf/models/indexer.py:187` — replace the `/Volumes/` string-prefix reject with a capability-aware check (reject only WAL-unsafe fs_type), keeping `db.py::open_db` as defense-in-depth.
- **Tests:** config-model test for `fs_type` round-trip + override-beats-autodetect.
- **Effort:** M · **Risk:** low · **Deps:** Phases 2-3.

### Phase 5 — Make indexer tier-1 drift FS-aware (HIGH RISK — defer-able)
- **Objective:** stop exFAT/ext4 from triggering perpetual re-hashing; keep NTFS byte-identical.
- **Modify:** `drift.py::reconcile_file` — when `capability.tier1_uses_ctime is False`, drop ctime from the tier-1 tuple comparison (the stored side already tolerates NULL ctime via `ctime_ns or 0` at `drift.py:194`, so only the live tuple build needs the conditional); when `capability.mtime_granularity_ns > 1`, round both stored and live mtime to the granularity before comparing. Generalise `_verify_dir_mtime_reliable` into the capability (`dir_mtime_reliable_default`; probe only when None).
- **Tests:** simulate exFAT `stat_result` (no ctime, 2s mtime) → assert NO spurious `tier1_drift`; assert NTFS path (`tier1_uses_ctime=True`, granularity 1) is **unchanged** vs current. Needs branch coverage ≥ 90% on the new branches (`make check` gate).
- **Effort:** L · **Risk:** **high** (touches the hottest correctness path) · **Deps:** Phase 2.
- **Defer option:** if no current disk is non-NTFS (open question), Phase 5 can ship as a capability that defaults to today's NTFS behaviour with **zero runtime change**, deferring the live exFAT/ext4 paths until a real target exists.

### Phase 6 — Multi-FS test harness + SH-16 ACCEPTANCE
- **Objective:** exercise all FS paths without real `/Volumes` mounts.
- **Modify:** `pyproject.toml` markers block — add `multifs: filesystem-capability tests using faked mount/stat fixtures (no real disks)`.
- **Create:** fixtures faking `mount` stdout per fs_type and synthetic `stat_result` variants (no ctime, coarse mtime). Golden-test rsync argv per fs_type; unit-test `capability_for` for every fs_type.
- **Author** `ACCEPTANCE.md` criteria as executable shell commands (see §5).
- **Effort:** M · **Risk:** low · **Deps:** Phases 1-5 (tests land alongside each phase; this phase formalises the marker + ACCEPTANCE).

---

## 5. Acceptance criteria (SH-16 — every criterion is an executable command + expected output)

```bash
# AC-01 — FsProbe canonicalises the real ufsd_NTFS token (reproduces the dead-branch bug fix)
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected: ntfs_macfuse

# AC-02 — unknown fs_type falls back to the NTFS-safe superset
python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"
# expected: True

# AC-03 — NTFS rsync flags are byte-identical to the legacy hardcoded list
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']

# AC-04 — APFS drops the NTFS-only metadata-suppression flags
python -c "from personalscraper.indexer._fs_capability import capability_for; f=capability_for('apfs').rsync_flags; print('--no-perms' not in f and '--no-times' not in f)"
# expected: True

# AC-05 — APFS capability permits NTFS-illegal characters (no needless skip)
python -c "from personalscraper.indexer._fs_capability import capability_for; r=capability_for('apfs').illegal_name_regex; print(r is None or r.search('a:b') is None)"
# expected: True

# AC-06 — exFAT capability disables ctime in tier-1 and sets 2s granularity
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected: False 2000000000

# AC-07 — multifs marker is registered
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))"
# expected: True

# AC-08 — all multi-FS tests pass with no real disks
pytest -m multifs -q
# expected: tail line "N passed" (N>=8), 0 failed, 0 errors

# AC-09 — full quality gate green
make check
# expected: ruff/mypy/logging OK; "NNNN passed" with 0 failed/0 errors; coverage >=90%; module-size + typed-api + pragma + cli-coverage + no-broad-registry-catch all PASS

# AC-10 — no residual literal rsync flag list remains in _transfer.py
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '
# expected: 0   (flags now come only from the capability table)

# AC-11 — DiskConfig accepts an optional fs_type override
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"
# expected: apfs

# AC-12 — package still imports (smoke)
python -c "import personalscraper; print('ok')"
# expected: ok
```

---

## 6. Trade-offs & alternatives

- **Capability table vs per-FS subclasses.** A flat frozen-dataclass table (chosen) is fully unit-testable with no disks and trivially diffable; subclasses add indirection for no behavioural gain at this scale. Rejected.
- **`unknown` = NTFS-safe superset (chosen) vs `unknown` = permissive.** A permissive default could write Unix perms / AppleDouble files to a real NTFS disk and trigger the very EPERM/journal problems the current flags avoid. The restrictive default is mandatory; this is a stated risk.
- **Runtime detection (kept) vs config-declared fs_type (added as optional override).** Runtime is the right default (a disk can be reformatted without a config edit). The optional `DiskConfig.fs_type` is an escape hatch only (fuse-t / unrecognised tokens).
- **Single 10s probe vs per-call timeouts.** Consolidation collapses 5s/10s/10s to one 10s budget. This slightly relaxes `db.py`'s pre-open guard latency — accepted and documented, not silent.
- **Defer Phase 5.** Because the project is mono-user/pre-prod and may be NTFS-only today, Phase 5 can ship inert (NTFS-default capability) and the live exFAT/ext4 drift paths added when a real target appears — lowers risk on the hottest path.

---

## 7. Effort & sequencing

- **Quick wins (low risk, ship first):** Phase 1 (consolidate + fix `ufsd` bug) and Phase 2 (capability table). Together they remove the duplication and the latent dead branch with no behavioural change to dispatch.
- **Core value:** Phase 3 (rsync consumes capability) — gate-critical, but bounded by the golden-argv test that must be written **before** the refactor.
- **Operator ergonomics:** Phase 4 (config override) — small, low risk.
- **Heavy lift / defer-able:** Phase 5 (drift core) — highest risk; defer behind an inert NTFS default unless a non-NTFS disk exists.
- **Formalisation:** Phase 6 (marker + ACCEPTANCE) — tests land alongside each phase; this phase only formalises.
- **Recommended order:** 1 → 2 → 3 → 4 → 6, with 5 last (or deferred). Total ≈ **L-XL** across ~6 small new/modified modules; the bulk is test authoring, not production code.

---

## 8. Open questions

1. **Real `mount` tokens on IznoServer.** `db.py` assumes `ufsd_NTFS`. Run `mount | grep -i ntfs` on the host to confirm the exact strings for the installed driver (Tuxera/Paragon/fuse-t) before finalising the canonical-token table — guessing risks mis-detecting production disks as `"unknown"`.
2. **Is multi-FS forward-looking only?** Does any current disk run a non-NTFS FS today? If not, Phase 5 can ship inert (NTFS default, zero runtime change).
3. **Cross-mount `os.rename`.** Will any future config place staging and a disk on different filesystems (or a union/overlay mount)? If so, `_move_new` needs an explicit `assert st_dev` same-FS guard — cross-FS `os.rename` raises EXDEV and would silently fail the commit.
4. **Ghost-inode surfacing.** The unremovable-`?`-perms issue has no online code fix. Should the capability layer at least DETECT and surface it (health warning) rather than only demoting the log to debug?
5. **Non-Darwin parsing.** `mount` output format differs entirely off macOS; the `ext4` capability is presented as cross-platform but `FsProbe`'s parser is macOS-oriented. Scope decision: is a Linux `mount`/`findmnt` parser in-scope, or is ext4 support data-only (capability table) with detection deferred?
6. **ext4 reserved blocks.** Should free-space eligibility (`free_space_gb >= max(min_free, size*1.5)`) account for ext4's 5% root reservation? Minor.
