# ACCEPTANCE — multi-filesystem (v0.18.0)

Every criterion below is an executable shell command with a documented expected
output (SH-16 convention). Run from the repository root on
`feat/multi-filesystem`. Each block states the command and the output that must
actually occur — outputs were captured against the real implementation, not
copied from the plan.

```bash
# AC-01 — FsProbe canonicalises the real ufsd_NTFS token (dead-branch fix)
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

# AC-05 — APFS capability imposes no NTFS-illegal name restriction
python -c "from personalscraper.indexer._fs_capability import capability_for; r=capability_for('apfs').illegal_name_regex; print(r is None or r.search('a:b') is None)"
# expected stdout: True   (exit 0)

# AC-06 — exFAT disables ctime in tier-1 and sets 2 s granularity
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected stdout: False 2000000000   (exit 0)

# AC-07 — HFS+ (the AppleRAID target) keeps Unix perms and is NOT NTFS-restricted
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('hfsplus'); print(c.forbids_unix_perms, c.illegal_name_regex is None)"
# expected stdout: False True   (exit 0)

# AC-08 — multifs marker is registered
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(any('multifs' in m for m in d['tool']['pytest']['ini_options']['markers']))"
# expected stdout: True   (exit 0)

# AC-09 — all multi-FS tests pass with no real disks
python -m pytest -m multifs -q 2>&1 | tail -1
# expected: a "N passed" line with N >= 8 (currently "150 passed, 5794 deselected ..."), 0 failed, 0 errors   (exit 0)

# AC-10 — no residual literal rsync flag list remains in _transfer.py
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '
# expected stdout: 0   (flags now come only from the capability table)

# AC-11 — exactly one cached mount shell-out (probe consolidation).
# The mount call in _fs_probe.py is multiline (subprocess.run(\n    ["mount"], ...))
# so a single-line regex would wrongly return 0; use rg -U (multiline) here.
rg -U -c 'subprocess\.run\(\s*\[\s*"mount"' -g '*.py' personalscraper/indexer/_fs_probe.py
# expected stdout: 1   (exit 0)

# AC-12 — the three old call sites no longer shell out to mount directly
# Same multiline-aware pattern as AC-11, run over the three legacy parsers.
rg -U -l 'subprocess\.run\(\s*\[\s*"mount"' -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (exit 1 — rg matched nothing in any of the three files)

# AC-13 — DiskConfig accepts an optional fs_type override
python -c "from personalscraper.conf.models.disks import DiskConfig; d=DiskConfig(id='x', path='/tmp', categories=['movies'], fs_type='apfs'); print(d.fs_type)"
# expected stdout: apfs   (exit 0)

# AC-14 — full quality gate green
make check
# expected: ruff/mypy OK; "NNNN passed" with 0 failed / 0 errors; coverage gate met;
#           module-size + typed-api + registry-catch guardrails all PASS   (exit 0)

# AC-15 — version bump landed (single source of truth is the VERSION file;
# pyproject.toml uses version = {attr = "personalscraper.__version__"} so a
# `grep '^version' pyproject.toml` would print the attr line, not the number).
cat VERSION
# expected stdout: 0.18.0   (exit 0)

# AC-16 — CHANGELOG entry present for this version
grep -c "0.18.0" CHANGELOG.md
# expected stdout: 1 (>= 1)   (exit 0)

# AC-17 — package still imports (smoke)
python -c "import personalscraper; print('ok')"
# expected stdout: ok   (exit 0)

# AC-18 — re-scope proof: normalize_tier1 is the byte-identical NTFS path.
# (Phase 5 implemented fingerprint.normalize_tier1 / round_mtime_ns consumed by
# scanner/_modes/incremental.py + quick.py — NOT reconcile_file.)
python -c "from personalscraper.indexer.fingerprint import normalize_tier1; from personalscraper.indexer._fs_capability import NTFS_MACFUSE; print(normalize_tier1(10, 123, 456, NTFS_MACFUSE) == (10, 123, 456))"
# expected stdout: True   (exit 0)

# AC-19 — consistency proof: the single shared resolve_capability honours the
# explicit override and skips the probe, so the transfer layer (Dispatcher) and
# the scanner resolve the SAME capability for a disk and can never diverge.
python -c "from personalscraper.indexer._fs_capability import resolve_capability, EXFAT; print(resolve_capability('/Volumes/Disk1', 'exfat') is EXFAT)"
# expected stdout: True   (override beats probe; exit 0)
```
