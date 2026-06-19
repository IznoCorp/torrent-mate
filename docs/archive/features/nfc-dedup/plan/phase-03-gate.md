# Phase 03 — Live remediation + bugfix gate

## Gate

Phases 1 and 2 must be merged-ready on `fix/nfc-dedup`:

- `personalscraper/indexer/repos/item_repo.py` — `_canonical_title` NFC-normalizes.
- `personalscraper/commands/library/dedup_titles.py` — `library-dedup-titles` exists.
- `tests/indexer/test_canonical_title_nfc.py` — 2 regression tests.
- `tests/integration/test_dedup_titles.py` — 4 command tests.
- `make test` passes with 0 failures.

## Goal

Run the live remediation on `.data/library.db`, repair the 2 true orphans
(ids 504 and 1438), re-exercise ACC-1..ACC-6, then commit the gate.

**The operator (main session) performs the live DB steps.** This phase documents
the exact procedure and records the expected outputs.

## Files

- No new source files.
- Gate commit touches nothing in `personalscraper/` or `tests/` — it is a
  `chore(nfc-dedup)` milestone commit that records the green gate.

---

### Sub-phase 3.1 — Live remediation + ACC re-exercise + gate commit

**Commit:** `chore(nfc-dedup): phase 3 gate — live remediation + ACC-1..ACC-6 green`

#### Step 1 — Checkpoint before touching production DB

- [ ] Verify the branch is up-to-date and clean:

```bash
git status
git log --oneline -5
```

Expected: working tree clean; the phase-1 and phase-2 commits are present.

#### Step 2 — ACC-1: `_canonical_title` NFC-normalizes

- [ ] Run:

```bash
python -c "import unicodedata as u; from personalscraper.indexer.repos.item_repo import _canonical_title; print(_canonical_title(u.normalize('NFD','Fantômes (1996)')) == u.normalize('NFC','Fantômes'))"
```

Expected: `True`

#### Step 3 — ACC-2: dry-run mutates nothing

- [ ] Run:

```bash
B=$(sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item"); \
personalscraper library-dedup-titles --dry-run >/dev/null 2>&1; \
A=$(sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item"); \
echo "$B == $A"
```

Expected: `<N> == <N>` (both numbers identical, e.g. `1909 == 1909`).

Review the dry-run output (without `>/dev/null`) to confirm the 14 expected
duplicate groups are reported and survivor selection looks correct before
proceeding to `--apply`.

#### Step 4 — Apply dedup

- [ ] Run:

```bash
personalscraper library-dedup-titles --apply
```

Expected: JSON output with `"apply": true`, `"deleted": 14` (or the current
count of duplicate orphans), `"duplicate_groups": 14`.

#### Step 5 — ACC-3: NULL-valid count drops to 2

- [ ] Run:

```bash
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE date_metadata_refreshed IS NULL AND nfo_status='valid'"
```

Expected: `2` (only ids 504 and 1438 remain).

#### Step 6 — ACC-4: zero duplicate groups remain

- [ ] Run:

```bash
python -c "
import sqlite3, unicodedata as u, re
c=sqlite3.connect('.data/library.db'); g={}
for i,t,k,y in c.execute('SELECT id,title,kind,year FROM media_item'):
    key=(u.normalize('NFC',re.sub(r'\s*\(\d{4}\)\s*$','',t)).lower(),k,y); g.setdefault(key,[]).append(i)
print(sum(1 for v in g.values() if len(v)>1))"
```

Expected: `0`

#### Step 7 — Repair true orphan id=504

Orphan 504: folder name has trailing ` ()` garbage; NFO filename carries extra
year token. Baseline: rename the folder and its NFO on disk, then re-stage.

- [ ] Identify the on-disk folder:

```bash
sqlite3 .data/library.db "SELECT ia.value FROM item_attribute ia JOIN media_item mi ON mi.id=ia.item_id WHERE mi.id=504 AND ia.key='dispatch_path'"
```

- [ ] On disk, rename the folder to remove trailing ` ()` and rename the NFO
      inside to `<folder-title>.nfo` (exact folder name without extension). Then
      re-run the scanner in quick mode to pick up the corrected NFO:

```bash
personalscraper library-scan --mode quick
```

- [ ] Verify:

```bash
sqlite3 .data/library.db "SELECT nfo_status, date_metadata_refreshed FROM media_item WHERE id=504"
```

Expected: `nfo_status='valid'`, `date_metadata_refreshed` is non-NULL.

#### Step 8 — Repair true orphan id=1438

Orphan 1438: NFO filename carries a year suffix not present in the folder name
(e.g. `L'Exoconference (2014).nfo` vs expected `L'Exoconference.nfo`).

- [ ] Identify the on-disk folder:

```bash
sqlite3 .data/library.db "SELECT ia.value FROM item_attribute ia JOIN media_item mi ON mi.id=ia.item_id WHERE mi.id=1438 AND ia.key='dispatch_path'"
```

- [ ] On disk, rename the NFO inside the folder to match `<folder-title>.nfo`
      exactly. Then re-run:

```bash
personalscraper library-scan --mode quick
```

- [ ] Verify:

```bash
sqlite3 .data/library.db "SELECT nfo_status, date_metadata_refreshed FROM media_item WHERE id=1438"
```

Expected: `nfo_status='valid'`, `date_metadata_refreshed` is non-NULL.

#### Step 9 — ACC-6: both true orphans valid + refreshed

- [ ] Run:

```bash
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE id IN (504,1438) AND nfo_status='valid' AND date_metadata_refreshed IS NOT NULL"
```

Expected: `2`

#### Step 10 — ACC-3 final: NULL-valid count is now 0

- [ ] Run:

```bash
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE date_metadata_refreshed IS NULL AND nfo_status='valid'"
```

Expected: `0`

#### Step 11 — ACC-5: regression suite green

- [ ] Run:

```bash
make test 2>&1 | tail -3
```

Expected: `NNNN passed` with 0 failed / 0 errors.

#### Step 12 — Full gate check

- [ ] Run:

```bash
make check 2>&1 | tail -5
```

Expected: zero lint errors, zero test failures, zero module-size violations.

#### Step 13 — Residual import check

- [ ] Verify no stale imports reference any removed module:

```bash
rg "dedup_titles\|library.dedup" --type py personalscraper/ tests/ 2>/dev/null | grep -v "^personalscraper/commands/library/dedup_titles.py" | grep -v "test_dedup_titles"
```

Expected: zero matches (only the source file and test file itself).

#### Step 14 — Smoke import

- [ ] Run:

```bash
python -c "import personalscraper"
```

Expected: no output, exit 0.

#### Step 15 — Gate commit

- [ ] Run:

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore(nfc-dedup): phase 3 gate — live remediation + ACC-1..ACC-6 green

library-dedup-titles --apply removed 14 NFD orphan duplicate rows.
True orphans 504 + 1438 repaired via on-disk NFO rename + quick scan.
NULL-valid count: 1909-era 13 → 0. All 6 ACC criteria pass.
EOF
)"
```
