# Phase 8 — Retrospective fixes ("tout corriger")

> Post-PR-#29 adversarial-retrospective remediation. Closes the coarse-FS
> objective gap, the consistency/honesty gaps, and the doc lies. NTFS-via-macFUSE
> stays **byte-identical** throughout (granularity=1 → `round_mtime_ns` identity,
> `tier1_uses_ctime=True` → unchanged tuples). All new behaviour fires only for
> exFAT/HFS+/coarse FS. Merge is billing-blocked, so this lands pre-merge.

## NTFS invariant (the safety anchor — verify after EVERY task)

`compute_merkle_root` for an NTFS/APFS/ext4 disk must be byte-identical before/after
this phase (gran=1 ⇒ bucketing is identity). `_build_rsync_cmd(..., NTFS_MACFUSE)`
unchanged. The full existing drift/scanner/merkle suites must stay green.

---

## Task 1 — Make the three gating short-circuits FS-aware (HEADLINE; hottest path)

**Problem (retrospective, confirmed):** `normalize_tier1`/`round_mtime_ns` are
applied only at the per-file compare (`incremental.py:463`) and the quick paranoia
branch (`quick.py:149`). The gates that run FIRST and decide whether a walk happens
compare RAW mtime — so on a coarse FS the per-file FS-aware compare is never reached,
the merkle short-circuit misses, and `compute_merkle_delta` can spuriously trip
`DiskBulkChangeDetected` (freeze a healthy disk). Confirmed raw at: `merkle.py:173-174`
(root), `merkle.py:211` (delta), `incremental.py:290` + `_walker.py:697` (dir-mtime skip).

**Fix:** bucket mtime via `round_mtime_ns(mtime, capability)` at the fingerprint-build
sites so root + delta + dir-mtime all become FS-aware consistently:

- `_walker.py::_build_disk_fingerprints(conn, disk_id, capability)` — bucket `mtime_ns` when building each `FileFingerprint` (DB side).
- `_walker.py::_sample_fresh_fingerprints(conn, disk_id, mount, capability)` — bucket `st_mtime_ns` (FS side).
  Because BOTH sides bucket with the same capability, `compute_merkle_root` (hashes the bucketed tuples) and `compute_merkle_delta` (compares bucketed vs bucketed) need no internal change — but verify and, if cleaner, pass capability into `compute_merkle_delta` and bucket there.
- dir-mtime subtree skip: `incremental.py:290` and `_walker.py:697` → compare `round_mtime_ns(existing_path.dir_mtime_ns, cap) == round_mtime_ns(current_mtime_ns, cap)`.
- Thread `capability` from `_scan_one_disk` (orchestrator already resolves `disk_capability`) into `_scan_disk_quick` → `_walk_dir_quick` (plan-05 Task 2.3 was never done) and into every `_build_disk_fingerprints`/`_sample_fresh_fingerprints` call across incremental + quick.
- **Full scan**: trace where the merkle root is STORED after a full walk (finalize path / `_build_disk_fingerprints`). That store MUST bucket with the disk capability too, else the first incremental after a full scan sees a one-version root mismatch (acceptable one-time, but for NTFS it must be exactly identical). Thread capability into the full-scan root store. Default `capability=NTFS_MACFUSE` on all new params so untouched callers are byte-identical.

**Tests (regression net — the suite was structurally blind: every coarse-FS test reset merkle_root=None):**

- NTFS byte-identical: `compute_merkle_root(_build_disk_fingerprints(..., NTFS_MACFUSE))` equals the pre-phase value for the same rows (gran=1 identity). Pin it.
- Coarse-FS stability: seed a VALID `merkle_root` from a full scan on an exFAT disk, then run an incremental with sub-2s on-disk mtime jitter and UNCHANGED content → assert the merkle short-circuit HITS (root stable) OR at least no `DiskBulkChangeDetected` freeze and no spurious full re-hash. Do NOT reset merkle_root=None.
- Bulk-change freeze guard: >50% sub-bucket jitter on exFAT, unchanged content → assert NO freeze (delta below threshold because bucketed).

---

## Task 2 — Deliver AC-05 end-to-end (per-FS illegal-name relaxation)

**Problem:** `_movie.py:47` + `_tv.py:47` run `has_ntfs_illegal_names(dir, pattern=NTFS_MACFUSE.illegal_name_regex)` BEFORE dest selection, so a `:`-titled item is rejected even on an APFS dest. The per-disk `capability.illegal_name_regex` (None for POSIX) is resolved later (lines 86/111) then ignored at the gate.

**Fix:** move the illegal-name gate to AFTER dest resolution in both `_movie.py` and `_tv.py`; use the resolved `cap.illegal_name_regex` (None → `has_ntfs_illegal_names` returns False → not skipped). Preserve the skip/result-reporting semantics. For the new-media branch, the gate must run after `target_disk` is chosen (line 111). **Test (end-to-end through the dispatch path):** a `name:colon` dir → APFS dest → NOT skipped; → NTFS dest → skipped. Drive the real `_movie`/`_tv` entry, not `has_ntfs_illegal_names` directly.

---

## Task 3 — Fix the override-map key so transfer & scan cannot diverge

**Problem:** CLI builds `{str(d.path): d.fs_type}` (`scan.py:264`); scanner looks up `ctx.fs_type_overrides.get(disk.mount_path)` (`orchestrator:347`) where `disk.mount_path` is the DB value (mutable at runtime, NULL on unmount). The "never diverge" claim is false; the test (`test_scan_fs_aware.py:635`) seeds the same literal both sides so it can't catch divergence.

**Fix:** key the override on a STABLE disk identity. Investigate `_bootstrap_disks_from_config` to find the link (likely `DiskConfig.id` ↔ `DiskRow.label`/`uuid`). Options, pick the robust one: (a) build the map keyed by `disk.id`/`uuid` in the CLI by joining cfg.disks→DiskRows; or (b) pass `cfg.disks` into `scan()` and resolve the override per-DiskRow in the orchestrator (mirroring the dispatcher, which already resolves from DiskConfig). **Test:** a DiskRow whose `mount_path` DIFFERS from `str(DiskConfig.path)` (simulate remount) still gets its operator override applied on the scan side — built via the real CLI key-builder, not a hand-seeded dict.

---

## Task 4 — Remove the dead boolean fields (single source of truth = rsync_flags)

`forbids_unix_perms` / `forbids_apple_metadata` have zero production consumers and their docstrings falsely claim they "drive" rsync flags. Convert to computed `@property` derived from `rsync_flags` (`'--no-perms' in self.rsync_flags`, `'--exclude=.DS_Store' in self.rsync_flags`) so they can NEVER desync, OR delete them. Update the table entries, the docstrings (DESIGN §4.3 claims too), and the tests that assert them.

---

## Task 5 — Close the remaining test gaps

- Dispatcher resolve_capability E2E: construct a Dispatcher with a `DiskConfig.fs_type` + faked `probe_mount`, assert the rsync argv for that disk uses the resolved (not default) flags. (Symmetric to the scanner override coverage.)
- `canonical_fs_type` negative boundary: assert a benign token containing a substring but not NTFS stays `unknown` where intended; document the deliberately-greedy `ntfs`/`fuse` substring behaviour (safe direction).
- Full→incremental no-op handoff on a coarse FS: real full scan on exFAT, then incremental with ZERO on-disk changes (merkle intact) → no OSHash recompute, no repair (pins idempotent flooring).
- Refresh `ACCEPTANCE.md` AC-09 captured count (112 → current) or drop the hard number.

---

## Task 6 — Reconcile the docs with what actually shipped (do LAST, after code is final)

- **DESIGN.md** (never touched on the branch — `git log main..HEAD -- DESIGN.md` empty): rewrite §152/§354/§461/§590 to describe `normalize_tier1`/`round_mtime_ns` consumed by `incremental.py`/`quick.py` + the now-FS-aware gating layer (Task 1); state `reconcile_file` is untouched dead code (tech-debt-2). Fix the version header + §5/§6 + AC-15/AC-16: `0.16.0→0.17.0` ⇒ `0.17.0→0.18.0`. Update the §4.3 boolean-field description (Task 4). Add a dated re-scope + retro-fix note.
- **phase-05 plan**: remove the stale "out of scope here" override paragraph (Task 5 of phase-05 delivered it).
- **phase-06 plan**: `test_drift_fs_aware.py` → `test_tier1_fs_aware.py`/`test_scan_fs_aware.py`; drop the reconcile_file gate; `17 criteria` → 19; `0.17.0` → `0.18.0`.
- **indexer.md**: "the walker resolves" → "the scan orchestrator resolves (via resolve_capability); incremental/quick consume normalize_tier1"; "DB must reside on the internal APFS disk" → "any WAL-safe (non-NTFS/non-unknown) volume, incl. APFS under /Volumes/".
- **storage.md**: update the quick-mode FS-awareness description after Task 1 (gating now FS-aware); fix the "rsync extra flags" column nit.
- **CHANGELOG 0.18.0**: add the gating FS-aware fix, AC-05 end-to-end, override-key fix.
- Re-run `audit_design_coverage.py --strict` + `update_feature_map.py --check` (both must exit 0).

---

## Task 7 — Gate + push + record

`make lint && make test && make check` exit 0; `pytest -m multifs` green; NTFS merkle-root byte-identical pin green; design-gaps both exit 0. Push. Record as PR-review cycle 3 in IMPLEMENTATION.md.

---

## Acceptance criteria (this phase)

```bash
# AC-G1 — gating layer is FS-aware (capability reaches merkle/walker)
rg -c "round_mtime_ns|capability" -g '*.py' personalscraper/indexer/scanner/_walker.py
# expected: >0 (was 0)

# AC-G2 — NTFS merkle root byte-identical (gran=1 identity) — via the new pin test
pytest tests/indexer/ -k "merkle and ntfs" -q

# AC-05E — colon name allowed on APFS dest, skipped on NTFS dest (end-to-end test)
pytest tests/dispatch/ -k "illegal_name and (apfs or posix)" -q

# AC-DIV — scanner override survives a mount_path != config path
pytest tests/indexer/ -k "override and diverg" -q

# AC-14 full gate
make check
# expected: exit 0

# design-gaps
python3 scripts/audit_design_coverage.py --strict; echo "AUDIT=$?"
python3 scripts/update_feature_map.py --check; echo "FM=$?"
# expected: AUDIT=0 FM=0
```
