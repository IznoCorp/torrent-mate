# multi-filesystem — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-filesystem support (HFS+/AppleRAID, exFAT, ext4, APFS, NTFS-via-macFUSE) by replacing three duplicated mount-parsers and two hardcoded rsync flag lists with a unified `FsProbe` + `FilesystemCapability` strategy table — without altering the current NTFS-via-macFUSE behaviour by a single byte.

**Branch:** `feat/multi-filesystem`
**Codename:** `multi-filesystem`
**SemVer bump:** `0.16.0 → 0.17.0` (minor — purely additive, no breaking config/DB change)
**Design doc:** `docs/features/multi-filesystem/DESIGN.md`

**CRITICAL INVARIANT (all phases):** The NTFS-via-macFUSE rsync flags must remain byte-identical to today's hardcoded list throughout every phase. The `ntfs_macfuse` `FilesystemCapability` entry is the golden anchor. `"unknown"` falls back to `ntfs_macfuse` (restrictive default — never permissive).

---

## Phases

| #   | Phase                                                         | File                                                               | Status |
| --- | ------------------------------------------------------------- | ------------------------------------------------------------------ | ------ |
| 1   | Consolidate 3 mount-parsers into one cached FsProbe           | [phase-01-fs-probe.md](phase-01-fs-probe.md)                       | [ ]    |
| 2   | Define the FilesystemCapability strategy table                | [phase-02-fs-capability.md](phase-02-fs-capability.md)             | [ ]    |
| 3   | Make `_transfer.rsync`/`rsync_merge` consume the capability   | [phase-03-transfer-capability.md](phase-03-transfer-capability.md) | [ ]    |
| 4   | Optional `DiskConfig.fs_type` override + plumb capabilities   | [phase-04-diskconfig-override.md](phase-04-diskconfig-override.md) | [ ]    |
| 5   | Make indexer tier-1 drift FS-aware (HIGHER RISK — defer-able) | [phase-05-drift-fs-aware.md](phase-05-drift-fs-aware.md)           | [ ]    |
| 6   | Multi-FS test harness + SH-16 ACCEPTANCE + docs               | [phase-06-test-harness-docs.md](phase-06-test-harness-docs.md)     | [ ]    |
| 7   | Feature PR + review (auto-invoked)                            | [phase-07-feature-pr.md](phase-07-feature-pr.md)                   | [ ]    |

---

## Risk matrix

| Phase | Risk     | New modules         | NTFS behaviour                       |
| ----- | -------- | ------------------- | ------------------------------------ |
| 1     | Medium   | `_fs_probe.py`      | identical (+ documented 5s→10s note) |
| 2     | Low      | `_fs_capability.py` | identical (data only)                |
| 3     | Medium   | —                   | byte-identical (golden-pinned)       |
| 4     | Low      | —                   | identical                            |
| 5     | **High** | —                   | identical (capability-gated)         |
| 6     | Low      | —                   | identical                            |

---

## Gate command (every phase)

```bash
make lint && make test && make check
```

---

## SH-16 Acceptance criteria (summary)

Full executable commands in `docs/features/multi-filesystem/ACCEPTANCE.md` (authored in Phase 6).
Quick reference: AC-01 through AC-17 from DESIGN §6.

Key checks:

- `canonical_fs_type("ufsd_NTFS")` → `ntfs_macfuse` (AC-01)
- `capability_for("unknown") == capability_for("ntfs_macfuse")` (AC-02)
- NTFS rsync flags byte-identical (AC-03)
- No literal `--no-perms` in `_transfer.py` (AC-10)
- Single `subprocess.run(["mount"]` call in the codebase (AC-11, AC-12)
- `DiskConfig` accepts `fs_type` field (AC-13)
- `make check` green (AC-14)
- Version `0.17.0` present (AC-15)
- `CHANGELOG.md` entry (AC-16)
- `import personalscraper` smoke (AC-17)
