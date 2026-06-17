# Phase 3 — gate

**Covers**: AC-7 + re-exercise of AC-1..AC-6

## Gate

Phase 2 done: `date_metadata_refreshed` is populated from the scan epoch for
valid-NFO items. `make check` is green.

---

### 3.1 — Final `make check` + acceptance re-exercise

**Commit**: `chore(rescrape-target): phase 3 gate — make check green + ACC re-exercise`

**Checklist** (run in order; all must pass before the commit):

```bash
# 1. Lint + type-check
make lint

# 2. Full test suite
make test

# 3. Combined gate (lint + test + module-size + typed-api guardrails)
make check

# 4. Smoke import
python -c "import personalscraper"

# 5. Residual import grep (additive feature — no deletions, but verify)
rg "item_id" --type py personalscraper/maintenance/rescraper.py
rg "item_id" --type py personalscraper/commands/library/analyze.py
rg "scan_epoch" --type py personalscraper/indexer/scanner/_modes/_item_stage.py
```

**AC-1 — targeted select (dry-run reports exactly 1 candidate)**

```bash
personalscraper library-rescrape --item-id 1600 --dry-run
# Expected: output lists exactly 1 item (item 1600), not the full library.
```

NOTE: AC-1 targets item 1600 (La Linea) in the live indexer DB. If the test
environment does not contain item 1600, substitute a real on-disk item id
(query with `sqlite3 <db_path> "SELECT id, title FROM media_item LIMIT 5"`).

**AC-2 — bypass predicate (item 1600 is nfo_status='valid' yet is re-scraped)**

AC-2 is verified by the same dry-run as AC-1: the candidate is returned even
though `nfo_status='valid'`, proving the predicate was bypassed. Confirm by
checking the dry-run log says "1 candidate" and no "skipping valid" message.

**AC-3 — real targeted re-scrape (La Linea corrected, no other NFO touched)**

```bash
# Record mtime of a nearby item before the run
BEFORE=$(stat -f "%m" "/Volumes/<disk>/path/to/OtherItem/tvshow.nfo")

personalscraper library-rescrape --item-id 1600
# Expected: La Linea (tvdb:80915) NFO updated; title/year corrected.

# Verify no other NFO was touched
AFTER=$(stat -f "%m" "/Volumes/<disk>/path/to/OtherItem/tvshow.nfo")
[ "$BEFORE" = "$AFTER" ] && echo "OK: other item untouched" || echo "FAIL"
```

NOTE: substitute a real sibling item path from the same disk. If item 1600 is
absent, pick a real item from `library-rescrape --dry-run` output.

**AC-4 — mutual exclusion errors clearly**

```bash
personalscraper library-rescrape --item-id 1600 --disk disk_2 --dry-run
# Expected: error message referencing mutual exclusion; exit code != 0.
```

**AC-5 — scanner populates date_metadata_refreshed for valid-NFO items**

```bash
# Run a scan (dry-run=False required to write to DB)
personalscraper library-index --mode full --dry-run false 2>/dev/null || \
  personalscraper library-index --mode quick

# Query a valid-NFO item
DB=$(python -c "from personalscraper.conf.loader import load_config; c=load_config(); print(c.indexer.db_path)")
sqlite3 "$DB" \
  "SELECT id, title, nfo_status, date_metadata_refreshed \
   FROM media_item WHERE nfo_status='valid' LIMIT 3;"
# Expected: date_metadata_refreshed is non-NULL for valid-NFO rows.

# Query an invalid-NFO item
sqlite3 "$DB" \
  "SELECT id, title, nfo_status, date_metadata_refreshed \
   FROM media_item WHERE nfo_status != 'valid' LIMIT 3;"
# Expected: date_metadata_refreshed is NULL for invalid/missing-NFO rows.
```

**AC-6 — incremental: dry-run (no filter) lists only non-valid items**

```bash
personalscraper library-rescrape --dry-run 2>&1 | grep -c "candidate"
# Expected: count is << 1909 (only items with nfo_status != 'valid'),
# NOT the full library.
```

**AC-7 — make check green**

```bash
make check
# Expected: 0 failures, 0 errors.
```
