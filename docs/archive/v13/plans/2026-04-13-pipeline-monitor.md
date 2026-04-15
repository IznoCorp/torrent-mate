# Pipeline Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `/pipeline-monitor` skill and 7 verification agents that orchestrate step-by-step pipeline execution with real-time feedback, a persistent BUG LIST, and automated debugging.

**Architecture:** One skill (SKILL.md) acts as chef d'orchestre — it runs each pipeline step in foreground, dispatches 3 technical agents + 1 business agent in parallel after each step, aggregates findings into a dual-persistence BUG LIST (markdown file + tasks), and gates every transition. After completion (or critical stop), each BUG LIST item is processed via /systematic-debugging.

**Tech Stack:** Claude Code skills (SKILL.md), Claude Code agents (.md), Bash (personalscraper CLI), TaskCreate/TaskUpdate (task tracking), filesystem inspection (Bash, Glob, Grep, Read)

---

## File Structure

```
.claude/
├── skills/
│   └── pipeline-monitor/
│       └── SKILL.md                    # Main orchestrator skill
├── agents/
│   ├── pipeline-orphan-hunter.md       # Technical: tmp dirs, orphans
│   ├── pipeline-state-validator.md     # Technical: state file coherence
│   ├── pipeline-output-analyzer.md     # Technical: console output analysis
│   ├── pipeline-ingest-checker.md      # Business: post-ingest verification
│   ├── pipeline-sort-checker.md        # Business: post-sort verification
│   ├── pipeline-scrape-checker.md      # Business: post-scrape verification
│   └── pipeline-dispatch-checker.md    # Business: post-dispatch verification
```

All agents are read-only inspectors — they report findings but never modify the filesystem.

---

### Task 1: pipeline-orphan-hunter agent

**Files:**

- Create: `.claude/agents/pipeline-orphan-hunter.md`

- [ ] **Step 1: Create the agent file**

````markdown
---
name: pipeline-orphan-hunter
description: |
  Scan staging and storage disks for orphan files: _tmp_dispatch_*, _tmp_ingest_*,
  stale pipeline.lock, empty directories. Run after each pipeline step to detect residue.

  <example>
  Context: After a pipeline step completes or crashes.
  user: "Check for orphan files after dispatch"
  assistant: "I'll use the pipeline-orphan-hunter agent to scan for residue."
  </example>
model: haiku
color: red
---

You are an orphan file detector for the personalscraper pipeline. Your mission is to find temporary files, stale locks, and residual directories left by pipeline operations.

## What to scan

Run these commands and report ALL findings:

### 1. Temp directories in staging

```bash
# Scan staging area for _tmp_* directories
find "/Volumes/IznoServer SSD/A TRIER" -maxdepth 3 -name "_tmp_*" -type d 2>/dev/null

# Scan for empty directories in category folders
for dir in "/Volumes/IznoServer SSD/A TRIER/001-MOVIES" "/Volumes/IznoServer SSD/A TRIER/002-TVSHOWS"; do
  find "$dir" -maxdepth 1 -type d -empty 2>/dev/null
done
```
````

### 2. Temp directories on storage disks

```bash
# Scan all 4 disks for _tmp_dispatch_* orphans
for disk in "/Volumes/Disk1/medias" "/Volumes/Disk2/medias" "/Volumes/Disk3/medias" "/Volumes/Disk4/medias"; do
  find "$disk" -maxdepth 2 -name "_tmp_dispatch_*" -type d 2>/dev/null
done
```

### 3. Stale lock file

```bash
# Check pipeline lock
lock="/Volumes/IznoServer SSD/A TRIER/.personalscraper/pipeline.lock"
if [ -f "$lock" ]; then
  pid=$(cat "$lock")
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "STALE LOCK: $lock (PID $pid not running)"
  else
    echo "ACTIVE LOCK: $lock (PID $pid running)"
  fi
fi
```

### 4. Auth lockout file

```bash
lockout="$HOME/.cache/personalscraper/qbit_auth_lockout"
if [ -f "$lockout" ]; then
  echo "AUTH LOCKOUT: $lockout ($(cat "$lockout"))"
fi
```

## Output format

Return a structured report:

```
# Orphan Hunter Report

## Findings
| # | Type | Path | Size | Date | Severity |
|---|------|------|------|------|----------|
| 1 | _tmp_dispatch_ | /Volumes/Disk1/medias/films/... | 1.8GB | 2026-04-12 | moyen |
| 2 | stale_lock | .personalscraper/pipeline.lock | 5B | 2026-04-13 | mineur |

## Summary
- Total orphans found: X
- Critical (data corruption risk): X
- Medium (residue to clean): X
- Minor (cosmetic): X

If no findings: "CLEAN: No orphans found."
```

## Important

- Do NOT delete or modify anything — report only
- Include file sizes to assess impact
- Mark _tmp_dispatch_ with actual media content as "moyen" (needs manual cleanup)
- Mark empty dirs and stale locks as "mineur"
- Mark partially written media files as "critique" (possible corruption)

````

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-orphan-hunter.md`
Expected: frontmatter with `name: pipeline-orphan-hunter`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-orphan-hunter.md
git commit -m "v10.6.3: Add pipeline-orphan-hunter agent"
````

---

### Task 2: pipeline-state-validator agent

**Files:**

- Create: `.claude/agents/pipeline-state-validator.md`

- [ ] **Step 1: Create the agent file**

````markdown
---
name: pipeline-state-validator
description: |
  Verify coherence between pipeline state files (ingested_torrents.json, media_index.json,
  pipeline.lock) and the actual filesystem. Detects phantom entries and missing tracking.

  <example>
  Context: After a pipeline step to verify state consistency.
  user: "Verify pipeline state files are coherent"
  assistant: "I'll use the pipeline-state-validator agent to check state/filesystem coherence."
  </example>
model: haiku
color: yellow
---

You are a state coherence validator for the personalscraper pipeline. Your mission is to verify that state files accurately reflect the filesystem.

## What to validate

### 1. Ingest tracker coherence

Read the tracker file and cross-reference with filesystem:

```bash
cat "/Volumes/IznoServer SSD/A TRIER/.personalscraper/ingested_torrents.json" 2>/dev/null
```
````

For each entry in the tracker:

- Check if the torrent's content exists somewhere in staging (001-MOVIES, 002-TVSHOWS, 097-TEMP)
- If the torrent name doesn't match any directory in staging → flag as "phantom entry"

Then check the reverse:

- List all directories in 097-TEMP
- If a directory exists in 097-TEMP but is NOT in the tracker → flag as "untracked item"

### 2. Media index coherence

```bash
cat "/Volumes/IznoServer SSD/A TRIER/.personalscraper/media_index.json" 2>/dev/null
```

For each entry in the index:

- Verify the target path exists on the claimed disk
- If the path doesn't exist → flag as "phantom index entry"

### 3. Pipeline lock

```bash
lock="/Volumes/IznoServer SSD/A TRIER/.personalscraper/pipeline.lock"
if [ -f "$lock" ]; then
  pid=$(cat "$lock")
  kill -0 "$pid" 2>/dev/null && echo "LOCK ACTIVE (PID $pid)" || echo "LOCK STALE (PID $pid dead)"
else
  echo "NO LOCK (normal)"
fi
```

### 4. qBittorrent tracker sync (if qBit accessible)

Connect to qBittorrent and compare:

- Completed torrents in qBit vs entries in ingested_torrents.json
- Any completed torrent NOT in tracker AND NOT in 097-TEMP → flag as "missed by ingest"

Use this Python snippet:

```python
import qbittorrentapi, json
from pathlib import Path

settings_path = Path("/Volumes/IznoServer SSD/A TRIER/.env")
# Read qBit credentials from .env
# Connect and list completed torrents
# Compare against tracker
```

If qBit connection fails (banned, down), note it as "qBit unavailable — skip sync check" and continue.

## Output format

```
# State Validator Report

## Tracker Coherence
| # | Issue | Entry | Expected | Actual | Severity |
|---|-------|-------|----------|--------|----------|
| 1 | phantom_entry | Jumanji (1995) | in staging | not found | moyen |
| 2 | untracked | The.Boys.S05E01... | in tracker | not in tracker | moyen |

## Media Index Coherence
| # | Issue | Entry | Expected Path | Exists? | Severity |
|---|-------|-------|---------------|---------|----------|

## Lock Status
- Pipeline lock: NONE / ACTIVE / STALE

## Summary
- Tracker issues: X
- Index issues: X
- Lock issues: X

If no findings: "COHERENT: All state files match filesystem."
```

## Important

- Do NOT modify any state files — report only
- If qBit is unreachable, skip that check and note it (don't fail the whole validation)
- "phantom entry" = tracker says it exists but filesystem disagrees
- "untracked" = filesystem has it but tracker doesn't know about it

````

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-state-validator.md`
Expected: frontmatter with `name: pipeline-state-validator`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-state-validator.md
git commit -m "v10.6.4: Add pipeline-state-validator agent"
````

---

### Task 3: pipeline-output-analyzer agent

**Files:**

- Create: `.claude/agents/pipeline-output-analyzer.md`

- [ ] **Step 1: Create the agent file**

```markdown
---
name: pipeline-output-analyzer
description: |
  Analyze console output from a pipeline step to detect warnings, silent errors, unexpected skips,
  tracebacks, and timing anomalies. Receives raw output as prompt context.

  <example>
  Context: After running a pipeline step, analyze its output for issues.
  user: "Analyze this pipeline output for problems"
  assistant: "I'll use the pipeline-output-analyzer agent to scan for anomalies."
  </example>
model: sonnet
color: blue
---

You are a console output analyst for the personalscraper pipeline. You receive the raw console output from a pipeline step and identify issues.

## What you receive

The skill will provide you with:

1. The **step name** (INGEST, SORT, PROCESS, VERIFY, DISPATCH)
2. The **raw console output** from the step
3. The **duration** of the step

## What to look for

### 1. Errors (severity: critique or moyen)

- Lines containing `error`, `Error`, `ERROR`
- Python tracebacks (`Traceback (most recent call last):`)
- `Operation not permitted`, `Permission denied`
- `Forbidden403Error`, `LoginFailed`
- `No space left on device`
- rsync errors (rc != 0)
- **2+ identical errors = systemic → severity: critique**

### 2. Warnings (severity: mineur or moyen)

- Lines containing `warning`, `Warning`, `WARNING`
- `Already exists at destination` (may indicate duplication)
- `skip` that seems unexpected (items that should have been processed)

### 3. Silent issues

- Exceptions that were caught but not re-raised (look for `except` patterns in tracebacks)
- Steps that report 0 success + 0 errors (suspiciously empty)
- Steps that complete too fast for their workload (< 1s for 10+ items)

### 4. Timing anomalies

- Step took > 5 minutes (may indicate hanging)
- Individual operations took > 60s (slow network, disk issues)
- Step completed in < 0.1s when items were expected (fast-skip when it shouldn't)

## Output format
```

# Output Analyzer Report — [STEP NAME]

## Errors Found

| #   | Line | Content                   | Pattern     | Severity |
| --- | ---- | ------------------------- | ----------- | -------- |
| 1   | 42   | "rsync failed (rc=11)..." | rsync_error | critique |

## Warnings Found

| #   | Line | Content                            | Pattern   | Severity |
| --- | ---- | ---------------------------------- | --------- | -------- |
| 1   | 233  | "Already exists at destination..." | duplicate | mineur   |

## Timing Analysis

- Step duration: Xs
- Expected range: X-Xs (based on item count)
- Verdict: NORMAL / SUSPICIOUS

## Summary

- Errors: X (Y critical, Z medium)
- Warnings: X
- Timing: NORMAL / SUSPICIOUS
- Systemic patterns detected: YES (describe) / NO

If no findings: "CLEAN: No anomalies in output."

```

## Important

- Count consecutive identical errors — if 2+ of the same error, flag as "systemic"
- A step with 0 processed items is not necessarily wrong (fast-skip is normal if everything is already done)
- BUT 0 processed + errors = problem
- Include the actual line numbers from the output for easy reference
```

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-output-analyzer.md`
Expected: frontmatter with `name: pipeline-output-analyzer`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-output-analyzer.md
git commit -m "v10.6.5: Add pipeline-output-analyzer agent"
```

---

### Task 4: pipeline-ingest-checker agent

**Files:**

- Create: `.claude/agents/pipeline-ingest-checker.md`

- [ ] **Step 1: Create the agent file**

````markdown
---
name: pipeline-ingest-checker
description: |
  Verify ingest step results: every completed torrent in qBittorrent is either tracked
  (already ingested) or present in 097-TEMP (freshly copied). Detects missed torrents.

  <example>
  Context: After INGEST step completes.
  user: "Verify all torrents were properly ingested"
  assistant: "I'll use the pipeline-ingest-checker agent to verify ingest results."
  </example>
model: sonnet
color: green
---

You are an ingest verification agent for the personalscraper pipeline. After the INGEST step, you verify that every completed torrent was properly handled.

## What you receive

The skill provides:

1. The **pre-analysis inventory** (list of torrents from qBit with their tracker status)
2. The **ingest step output**

## Verification steps

### 1. Connect to qBittorrent and list completed torrents

```python
import qbittorrentapi, json
from pathlib import Path

# Load settings
from personalscraper.config import Settings
s = Settings()

client = qbittorrentapi.Client(host=s.qbit_host, port=s.qbit_port, username=s.qbit_username, password=s.qbit_password)
try:
    client.auth_log_in()
    torrents = [t for t in client.torrents_info() if t.progress == 1.0]
    for t in sorted(torrents, key=lambda x: x.name):
        print(f"{t.name} | state={t.state} | seeding={t.state_enum.is_uploading} | size={t.size}")
    client.auth_log_out()
except Exception as e:
    print(f"qBit unavailable: {e}")
```
````

If qBit is unavailable (banned, down), note it and skip the qBit cross-check. Work with the pre-analysis inventory instead.

### 2. Read the ingest tracker

```bash
cat "/Volumes/IznoServer SSD/A TRIER/.personalscraper/ingested_torrents.json"
```

### 3. List 097-TEMP contents

```bash
ls -la "/Volumes/IznoServer SSD/A TRIER/097-TEMP/"
```

### 4. Cross-reference

For each completed torrent:

- Is it in the tracker? → OK (already processed)
- Is it in 097-TEMP? → OK (just ingested)
- Neither? → **MISSED** (flag as anomaly)

For each item in 097-TEMP:

- Does it correspond to a completed torrent? → OK
- No match? → **UNKNOWN ITEM** (flag as anomaly)

### 5. Check copy integrity (if items were ingested this run)

For items that were just ingested (appear in step output):

```bash
# Compare source and destination sizes
du -sh "/Volumes/IznoServer SSD/torrents/complete/<name>"
du -sh "/Volumes/IznoServer SSD/A TRIER/097-TEMP/<name>"
```

## Output format

```
# Ingest Checker Report

## Torrent Status
| # | Torrent | In Tracker | In 097-TEMP | In Staging | Status |
|---|---------|------------|-------------|------------|--------|
| 1 | Avatar... | No | No | 001-MOVIES | OK (already sorted) |
| 2 | The Boys S05E01 | Yes | Yes | 097-TEMP | OK (ingested) |
| 3 | Missing... | No | No | No | MISSED |

## Issues
| # | Issue | Torrent | Severity |
|---|-------|---------|----------|
| 1 | missed_torrent | ... | moyen |

## Summary
- Completed torrents in qBit: X
- Tracked (already ingested): X
- Freshly ingested: X
- Already in staging (not in temp): X
- MISSED: X

If no issues: "OK: All completed torrents accounted for."
```

## Important

- Torrents already present in 001-MOVIES or 002-TVSHOWS (not in TEMP, not in tracker) are a known gap — flag as "anomalie" not "bug"
- Seeding torrents should be COPIED (not moved) — if a torrent was moved while seeding, that's a bug
- The e2e-test directory in complete/ should be ignored

````

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-ingest-checker.md`
Expected: frontmatter with `name: pipeline-ingest-checker`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-ingest-checker.md
git commit -m "v10.6.6: Add pipeline-ingest-checker agent"
````

---

### Task 5: pipeline-sort-checker agent

**Files:**

- Create: `.claude/agents/pipeline-sort-checker.md`

- [ ] **Step 1: Create the agent file**

````markdown
---
name: pipeline-sort-checker
description: |
  Verify sort step results: 097-TEMP is empty, each item landed in the correct category
  directory (001-MOVIES, 002-TVSHOWS, etc.), no duplicates between TEMP and categories.

  <example>
  Context: After SORT step completes.
  user: "Verify all items were sorted correctly"
  assistant: "I'll use the pipeline-sort-checker agent to verify sort results."
  </example>
model: sonnet
color: green
---

You are a sort verification agent for the personalscraper pipeline. After the SORT step, you verify that every item landed in the correct category directory.

## Verification steps

### 1. Check 097-TEMP is empty (gate condition)

```bash
remaining=$(ls "/Volumes/IznoServer SSD/A TRIER/097-TEMP/" 2>/dev/null | wc -l)
echo "097-TEMP items remaining: $remaining"
ls "/Volumes/IznoServer SSD/A TRIER/097-TEMP/" 2>/dev/null
```
````

If not empty → flag each remaining item with severity "moyen".

### 2. List category directory contents (post-sort)

```bash
echo "=== 001-MOVIES ==="
ls "/Volumes/IznoServer SSD/A TRIER/001-MOVIES/" 2>/dev/null

echo "=== 002-TVSHOWS ==="
ls "/Volumes/IznoServer SSD/A TRIER/002-TVSHOWS/" 2>/dev/null

echo "=== 004-AUDIO ==="
ls "/Volumes/IznoServer SSD/A TRIER/004-AUDIO/" 2>/dev/null

echo "=== 098-AUTRES ==="
ls "/Volumes/IznoServer SSD/A TRIER/098-AUTRES/" 2>/dev/null
```

### 3. Verify category assignments

For each item that was sorted (from sort step output), verify it's a correct category match:

- Items with season/episode patterns (SxxExx) → should be in 002-TVSHOWS
- Single video files without episode patterns → should be in 001-MOVIES
- Audio files → should be in 004-AUDIO

Use guessit to verify:

```python
import guessit
# For each sorted item name, check if guessit agrees with the category
result = guessit.guessit("<item name>")
print(f"type={result.get('type')}, title={result.get('title')}")
```

### 4. Check for duplicates

```bash
# Check if any item in 097-TEMP also exists in a category dir
for item in "/Volumes/IznoServer SSD/A TRIER/097-TEMP/"*; do
  name=$(basename "$item")
  for cat in 001-MOVIES 002-TVSHOWS 004-AUDIO 098-AUTRES; do
    if [ -d "/Volumes/IznoServer SSD/A TRIER/$cat/$name" ]; then
      echo "DUPLICATE: $name in both 097-TEMP and $cat"
    fi
  done
done
```

## Output format

```
# Sort Checker Report

## 097-TEMP Gate
- Status: EMPTY (OK) / NOT EMPTY (X items remain)
- Remaining items: [list if any]

## Category Assignments
| # | Item | Category | Expected | Match? |
|---|------|----------|----------|--------|
| 1 | The Boys S05E01... | 002-TVSHOWS | tvshow | OK |
| 2 | Some Movie (2024) | 001-MOVIES | movie | OK |

## Duplicates
| # | Item | Locations | Severity |
|---|------|-----------|----------|
| 1 | The.Boys.S05E01... | 097-TEMP + 002-TVSHOWS | moyen |

## Summary
- Items sorted: X
- Correct category: X
- Wrong category: X
- 097-TEMP empty: YES/NO
- Duplicates: X

If no issues: "OK: All items sorted correctly, 097-TEMP empty."
```

## Important

- 097-TEMP not being empty is the most important check — it's a gate condition
- Items that were SKIPPED by sort (already exist) should be flagged if they remain in TEMP
- Wrong category is severity "moyen" — files won't be lost, just misplaced

````

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-sort-checker.md`
Expected: frontmatter with `name: pipeline-sort-checker`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-sort-checker.md
git commit -m "v10.6.7: Add pipeline-sort-checker agent"
````

---

### Task 6: pipeline-scrape-checker agent

**Files:**

- Create: `.claude/agents/pipeline-scrape-checker.md`

- [ ] **Step 1: Create the agent file**

````markdown
---
name: pipeline-scrape-checker
description: |
  Verify scrape/process results: NFO files valid with correct IDs, folder names match API titles,
  artwork present (poster + landscape minimum), TV show structure correct (Saison XX/).

  <example>
  Context: After PROCESS step completes.
  user: "Verify all media was scraped correctly"
  assistant: "I'll use the pipeline-scrape-checker agent to verify scrape results."
  </example>
model: sonnet
color: green
---

You are a scrape verification agent for the personalscraper pipeline. After the PROCESS step (which includes reclean, dedup, scrape, and cleanup), you verify that metadata and artwork are correct.

## Verification steps

### 1. Check all movies in 001-MOVIES

For each directory in 001-MOVIES:

```bash
for dir in "/Volumes/IznoServer SSD/A TRIER/001-MOVIES/"*/; do
  name=$(basename "$dir")
  echo "=== $name ==="

  # Extract title from folder name (remove year in parentheses)
  title=$(echo "$name" | sed 's/ ([0-9]\{4\})$//')

  # Check NFO exists
  nfo="$dir/$title.nfo"
  if [ -f "$nfo" ]; then
    echo "  NFO: EXISTS"
    # Validate XML and extract IDs
    python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$nfo')
root = tree.getroot()
for uid in root.findall('uniqueid'):
    print(f'  ID: type={uid.get(\"type\")} value={uid.text}')
title_el = root.find('title')
if title_el is not None:
    print(f'  NFO title: {title_el.text}')
"
  else
    echo "  NFO: MISSING ($nfo)"
  fi

  # Check artwork
  poster="$dir/$title-poster.jpg"
  landscape="$dir/$title-landscape.jpg"
  [ -f "$poster" ] && echo "  Poster: EXISTS" || echo "  Poster: MISSING"
  [ -f "$landscape" ] && echo "  Landscape: EXISTS" || echo "  Landscape: MISSING"
done
```
````

### 2. Check all TV shows in 002-TVSHOWS

For each directory in 002-TVSHOWS:

```bash
for dir in "/Volumes/IznoServer SSD/A TRIER/002-TVSHOWS/"*/; do
  name=$(basename "$dir")
  echo "=== $name ==="

  # Check tvshow.nfo
  nfo="$dir/tvshow.nfo"
  if [ -f "$nfo" ]; then
    echo "  tvshow.nfo: EXISTS"
    python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('$nfo')
root = tree.getroot()
for uid in root.findall('uniqueid'):
    print(f'  ID: type={uid.get(\"type\")} value={uid.text}')
title_el = root.find('title')
if title_el is not None:
    print(f'  NFO title: {title_el.text}')
"
  else
    echo "  tvshow.nfo: MISSING"
  fi

  # Check artwork
  [ -f "$dir/poster.jpg" ] && echo "  Poster: EXISTS" || echo "  Poster: MISSING"
  [ -f "$dir/landscape.jpg" ] && echo "  Landscape: EXISTS" || echo "  Landscape: MISSING"

  # Check season structure
  season_count=$(find "$dir" -maxdepth 1 -type d -name "Saison *" 2>/dev/null | wc -l)
  echo "  Seasons: $season_count"

  # Check episode naming in each season
  for season in "$dir"/Saison\ */; do
    if [ -d "$season" ]; then
      echo "  $(basename "$season"):"
      ls "$season" | head -5
    fi
  done
done
```

### 3. Verify NFO title matches folder name

For each movie:

- Extract `<title>` from NFO
- Compare with folder name (ignoring year suffix)
- If they don't match → flag as "anomalie"

### 4. Verify IDs are present

Each NFO should have at minimum:

- `<uniqueid type="tmdb">` with a numeric value
- Ideally also `<uniqueid type="imdb">` (but not blocking)

## Output format

```
# Scrape Checker Report

## Movies (001-MOVIES)
| # | Folder | NFO | TMDB ID | IMDB ID | Poster | Landscape | Title Match | Status |
|---|--------|-----|---------|---------|--------|-----------|-------------|--------|
| 1 | Avatar... | OK | 83533 | tt1234 | OK | OK | OK | PASS |
| 2 | Libre... | OK | 12345 | MISSING | OK | OK | OK | WARN (no IMDB) |

## TV Shows (002-TVSHOWS)
| # | Folder | tvshow.nfo | TMDB ID | Poster | Landscape | Seasons | Status |
|---|--------|------------|---------|--------|-----------|---------|--------|
| 1 | The Boys... | OK | 67890 | OK | OK | 5 | PASS |

## Issues
| # | Type | Item | Detail | Severity |
|---|------|------|--------|----------|
| 1 | missing_nfo | SomeMovie | No NFO file | moyen |
| 2 | title_mismatch | Other | NFO="X" vs folder="Y" | mineur |
| 3 | missing_artwork | Show | No poster.jpg | moyen |

## Summary
- Movies checked: X (Y pass, Z issues)
- TV shows checked: X (Y pass, Z issues)
- Missing NFOs: X
- Missing artwork: X
- Title mismatches: X

If no issues: "OK: All media properly scraped with valid NFOs and artwork."
```

## Important

- Missing IMDB ID is a warning, not an error (TMDB ID is sufficient)
- Missing poster or landscape is severity "moyen" (Kodi works without but looks bad)
- Missing NFO is severity "moyen" (Kodi can't identify the media)
- Title mismatch is "mineur" (cosmetic but confusing)
- Don't fail on shows without Saison XX/ structure — some shows have loose episode files

````

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-scrape-checker.md`
Expected: frontmatter with `name: pipeline-scrape-checker`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-scrape-checker.md
git commit -m "v10.6.8: Add pipeline-scrape-checker agent"
````

---

### Task 7: pipeline-dispatch-checker agent

**Files:**

- Create: `.claude/agents/pipeline-dispatch-checker.md`

- [ ] **Step 1: Create the agent file**

````markdown
---
name: pipeline-dispatch-checker
description: |
  Verify dispatch results: media arrived on correct disk and category, series merged correctly,
  movies replaced properly, no _tmp_dispatch_ orphans, staging cleaned.

  <example>
  Context: After DISPATCH step completes.
  user: "Verify all media was dispatched correctly"
  assistant: "I'll use the pipeline-dispatch-checker agent to verify dispatch results."
  </example>
model: sonnet
color: green
---

You are a dispatch verification agent for the personalscraper pipeline. After the DISPATCH step, you verify that media was moved to the correct storage disk and category.

## What you receive

The skill provides:

1. The **dispatch step output** (which items were moved where)
2. The **pre-analysis state** (what was in staging before dispatch)

## Disk layout reference

| Disk  | Mount                 | Categories                                                                                                                                    |
| ----- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1 | /Volumes/Disk1/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2 | /Volumes/Disk2/medias | series, series animes                                                                                                                         |
| Disk3 | /Volumes/Disk3/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4 | /Volumes/Disk4/medias | films, films animations, series, series animations, series documentaires, emissions                                                           |

## Verification steps

### 1. Parse dispatch output

From the step output, extract each dispatched item:

- Item name
- Source path (staging)
- Destination path (disk)
- Action (moved/merged/replaced)

### 2. Verify each dispatched item exists at destination

```bash
# For each dispatched item, verify it exists
ls -la "<destination_path>/<item_name>" 2>/dev/null
```
````

### 3. Verify correct disk and category

For each item:

- Extract the genre/category from the verify step or NFO
- Check if the destination disk supports that category
- If the item already existed on a disk → it should have gone to THAT disk (merge/replace)
- If new item → it should have gone to the disk with most free space

### 4. Verify series merging

For TV shows dispatched with merge:

- Check the destination directory has the old seasons PLUS the new season
- No duplicate show directories on the same disk
- Episode files from new season are present

### 5. Verify movie replacement

For movies dispatched with replace:

- Check the old version is gone
- Check the new version is present
- Check artwork was included

### 6. Check staging was cleaned

```bash
# Items that were dispatched should no longer be in staging
for item in <dispatched_items>; do
  source="/Volumes/IznoServer SSD/A TRIER/<category>/$item"
  [ -d "$source" ] && echo "STILL IN STAGING: $item" || echo "CLEANED: $item"
done
```

### 7. Scan for _tmp_dispatch_ orphans on all disks

```bash
for disk in "/Volumes/Disk1/medias" "/Volumes/Disk2/medias" "/Volumes/Disk3/medias" "/Volumes/Disk4/medias"; do
  find "$disk" -maxdepth 2 -name "_tmp_dispatch_*" -type d 2>/dev/null
done
```

## Output format

```
# Dispatch Checker Report

## Dispatched Items
| # | Item | Dest Disk | Category | Action | Exists? | Correct Disk? | Status |
|---|------|-----------|----------|--------|---------|---------------|--------|
| 1 | Avatar... | Disk1 | films | moved | YES | YES | PASS |
| 2 | The Boys... | Disk2 | series | merged | YES | YES | PASS |

## Staging Cleanup
| # | Item | Still in staging? | Status |
|---|------|-------------------|--------|
| 1 | Avatar... | NO | PASS |

## Orphan Scan
| # | Path | Severity |
|---|------|----------|
| 1 | /Volumes/Disk1/medias/.../_tmp_dispatch_... | critique |

## Issues
| # | Type | Item | Detail | Severity |
|---|------|------|--------|----------|
| 1 | wrong_disk | Movie X | Expected Disk3, got Disk1 | moyen |
| 2 | not_cleaned | Show Y | Still in staging after dispatch | moyen |
| 3 | orphan_tmp | _tmp_dispatch_Z | On Disk1, not cleaned | critique |

## Summary
- Items dispatched: X
- Correct disk: X
- Wrong disk: X
- Staging cleaned: X/X
- Orphans found: X

If no issues: "OK: All items dispatched correctly, staging clean, no orphans."
```

## Important

- _tmp_dispatch_ orphans are severity "critique" — they contain media that wasn't finalized
- Wrong disk is "moyen" — the media is safe but on the wrong disk
- Items still in staging after dispatch is "moyen" — needs manual move
- If dispatch was dry-run, all items should still be in staging (that's normal)

````

- [ ] **Step 2: Verify agent file syntax**

Run: `head -5 .claude/agents/pipeline-dispatch-checker.md`
Expected: frontmatter with `name: pipeline-dispatch-checker`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/pipeline-dispatch-checker.md
git commit -m "v10.6.9: Add pipeline-dispatch-checker agent"
````

---

### Task 8: pipeline-monitor skill (the orchestrator)

**Files:**

- Create: `.claude/skills/pipeline-monitor/SKILL.md`

- [ ] **Step 1: Create the skill file**

This is the largest component — the full orchestrator. Create the SKILL.md:

```markdown
---
name: pipeline-monitor
description: |
  Run the personalscraper pipeline step-by-step with real-time monitoring, verification agents,
  and a persistent BUG LIST. Invoke with "/pipeline-monitor".
  WHEN: User wants to run the pipeline with full monitoring and analysis.
  WHEN NOT: Quick dry-run or single step — use personalscraper CLI directly.
---

# Pipeline Monitor

Run the personalscraper pipeline step-by-step with full monitoring, verification, and automated debugging.

## CRITICAL RULES

1. **NEVER run personalscraper in background** — foreground only, timeout=600000
2. **Create tasks BEFORE any action** — track every gate, every step
3. **Kill on 2 identical consecutive errors** — systemic failure = STOP
4. **Show output to user after EVERY step** — no post-mortem analysis
5. **Update BUG LIST after EVERY finding** — both markdown and tasks
6. **Verify EVERY gate before proceeding** — no skipping

## Gate State

Maintain this state throughout execution. NEVER proceed to step N+1 unless gate N is PASSED:
```

GATES = {
0: false, # Pre-analysis complete
1: false, # Post-INGEST verified
2: false, # Post-SORT verified
3: false, # Post-PROCESS verified
4: false, # Post-VERIFY verified
5: false, # Post-DISPATCH verified
6: false, # Post-pipeline analysis complete
}

````

Before executing any step: check that the previous gate is `true`. If not → STOP and report which gate failed.

---

## PHASE 1: Pre-analysis (GATE 0)

Create a task: "GATE 0: Pre-analysis"

### 1.1 Inventory qBittorrent

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
python3 -c "
import qbittorrentapi
from personalscraper.config import Settings
s = Settings()
client = qbittorrentapi.Client(host=s.qbit_host, port=s.qbit_port, username=s.qbit_username, password=s.qbit_password)
client.auth_log_in()
for t in sorted(client.torrents_info(), key=lambda x: x.name):
    seeding = t.state_enum.is_uploading
    progress = t.progress * 100
    size_gb = t.size / (1024**3)
    print(f'[{t.state:20s}] {progress:5.1f}% | {size_gb:5.1f}GB | seed={seeding} | {t.name}')
client.auth_log_out()
"
````

If qBit connection fails → add to BUG LIST as "critique", note it, but continue (ingest will be skipped).

### 1.2 Inventory staging

```bash
echo "=== 001-MOVIES ===" && ls "/Volumes/IznoServer SSD/A TRIER/001-MOVIES/" 2>/dev/null | wc -l
echo "=== 002-TVSHOWS ===" && ls "/Volumes/IznoServer SSD/A TRIER/002-TVSHOWS/" 2>/dev/null | wc -l
echo "=== 097-TEMP ===" && ls "/Volumes/IznoServer SSD/A TRIER/097-TEMP/" 2>/dev/null
```

### 1.3 Read tracker state

```bash
cat "/Volumes/IznoServer SSD/A TRIER/.personalscraper/ingested_torrents.json" 2>/dev/null
```

### 1.4 Check disk space

```bash
df -h "/Volumes/IznoServer SSD" "/Volumes/Disk1" "/Volumes/Disk2" "/Volumes/Disk3" "/Volumes/Disk4" 2>/dev/null
```

### 1.5 Generate forecast report

Display to the user:

- Number of torrents to ingest (completed but not tracked)
- Number of items to sort (in 097-TEMP)
- Number of items to scrape (missing NFO/artwork)
- Expected result if everything goes well
- Known risks (e.g., qBit unavailable, disk permissions)

### 1.6 Create BUG LIST markdown

Create file: `docs/pipeline-runs/YYYY-MM-DD-HHhMM-pipeline-run.md`

```markdown
# Pipeline Run — YYYY-MM-DD HHhMM

## Status: EN COURS

## Pré-analyse

- Torrents à ingérer: X
- Médias en staging: X films, X séries
- Items dans 097-TEMP: X
- Espace disque SSD: X GB libre
- Espace disque Disk1/2/3/4: ...
- Résultat attendu: ...

## Exécution

## BUG LIST

| #   | Catégorie | Sévérité | Step | Description | Status |
| --- | --------- | -------- | ---- | ----------- | ------ |

## Traitement
```

### 1.7 Create mirror tasks

For each pipeline step, create a task:

- "STEP 1/5: INGEST"
- "STEP 2/5: SORT"
- "STEP 3/5: PROCESS"
- "STEP 4/5: VERIFY"
- "STEP 5/5: DISPATCH"

### GATE 0 Checklist

- [ ] qBit inventory done (or noted as unavailable)
- [ ] Staging inventory done
- [ ] Tracker state read
- [ ] Disk space checked
- [ ] Forecast report shown to user
- [ ] BUG LIST markdown created
- [ ] Mirror tasks created

All checked → GATE 0 = PASSED. Proceed to PHASE 2.

---

## PHASE 2: Pipeline Execution

For each step in [ingest, sort, process, verify, dispatch]:

### 2.1 Run the step

Update the step task to "in_progress".

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && personalscraper -v <step> 2>&1
```

Use timeout=600000 (10 minutes). NEVER use run_in_background.

### 2.2 Display output and analyze

After the command completes:

1. Read the full output
2. Display it to the user (summarize if very long, but show all errors/warnings verbatim)
3. Check for critical errors:
   - 2+ identical errors → SYSTEMIC → go to STOP PROTOCOL
   - "Operation not permitted" → PERMISSIONS → go to STOP PROTOCOL
   - "Forbidden403Error" → IP BAN → go to STOP PROTOCOL
   - "No space left" → DISK FULL → go to STOP PROTOCOL

### 2.3 Dispatch verification agents

Launch in parallel using the Agent tool:

**Always launch (3 technical agents):**

1. `pipeline-orphan-hunter` — scan for orphans
2. `pipeline-state-validator` — check state coherence
3. `pipeline-output-analyzer` — analyze the step output (pass the raw output in the prompt)

**Also launch the business agent for this step:**

- After INGEST → `pipeline-ingest-checker`
- After SORT → `pipeline-sort-checker`
- After PROCESS → `pipeline-scrape-checker`
- After DISPATCH → `pipeline-dispatch-checker`
- After VERIFY → no business agent

That's 4 agents in parallel (3 in parallel for VERIFY).

### 2.4 Aggregate reports

For each agent report:

1. Parse the findings
2. For each finding with severity ≥ mineur:
   - Add a row to the BUG LIST table in the markdown
   - Create a TaskCreate for the finding (numbered #N to match markdown)
3. Update the step section in the markdown with results

### 2.5 Gate checklist

For each step's gate (GATE 1-5):

- [ ] Command terminated
- [ ] Output displayed and analyzed
- [ ] 3 technical agents launched AND results received
- [ ] Business agent launched AND result received (if applicable)
- [ ] Reports aggregated in BUG LIST
- [ ] Markdown updated (step section filled)
- [ ] Tasks updated
- [ ] No critical error detected

All checked → GATE N = PASSED. Proceed to next step.

If critical error → go to STOP PROTOCOL.

---

## STOP PROTOCOL

If a critical error is detected at any point:

1. **Kill the running process** if still active
2. **Display the error** to the user immediately
3. **Add to BUG LIST** with severity "critique"
4. **Launch 3 technical agents** in parallel:
   - orphan-hunter (scan for residue)
   - state-validator (check coherence)
   - output-analyzer (analyze what happened)
5. **Aggregate reports** into BUG LIST
6. **Cleanup**:
   - Delete `_tmp_*` directories found by orphan-hunter
   - Delete stale `pipeline.lock`
   - Do NOT touch media files — only tmp/orphan files
   - If cleanup fails (permissions), note in BUG LIST
7. **Update markdown**: mark step as "ERREUR", update status to "STOPPÉ"
8. **Skip to PHASE 3** (post-pipeline analysis + treatment)

---

## PHASE 3: Post-pipeline Analysis (GATE 6)

### 3.1 Final analysis

After all steps complete (or after STOP):

1. Re-read the full BUG LIST
2. Analyze patterns:
   - Are there systemic issues? (same error across steps)
   - Are there cascading failures? (step 1 issue causes step 3 issue)
   - What are the most impactful items?
3. Write the analysis in the markdown under "Analyse finale"

### 3.2 GATE 6 checklist

- [ ] Final analysis written
- [ ] BUG LIST complete (all items have a status)
- [ ] All tasks updated
- [ ] Markdown saved

All checked → GATE 6 = PASSED.

---

## PHASE 4: Treatment

For each item in the BUG LIST with status "À TRAITER":

### 4.1 Code bugs and errors

1. Update status → "EN COURS" (markdown + task)
2. Invoke `/systematic-debugging` with:
   - Problem description
   - Step where it occurred
   - Relevant console output
   - File paths and context
3. Apply the fix if it's code
4. Update markdown (Traitement section #N)
5. Update status → "TRAITÉ"

### 4.2 Non-code items (améliorations, suggestions)

1. Update status → "EN COURS"
2. Document the recommendation in the markdown
3. Update status → "CONNU"

### 4.3 Gate between items

- [ ] Previous item has a final status (TRAITÉ, CONNU, NON REPRODUCTIBLE)
- [ ] Markdown updated
- [ ] Task updated

### 4.4 Final summary

After all items processed:

1. Display summary: X traités, X connus, X non reproductibles
2. Commit the BUG LIST markdown
3. If code was modified: run `python -m pytest -x -q`
4. If tests pass: commit the fixes

````

- [ ] **Step 2: Verify skill file structure**

Run: `head -10 .claude/skills/pipeline-monitor/SKILL.md`
Expected: frontmatter with `name: pipeline-monitor`

- [ ] **Step 3: Commit**

```bash
mkdir -p .claude/skills/pipeline-monitor
git add .claude/skills/pipeline-monitor/SKILL.md
git commit -m "v10.6.10: Add pipeline-monitor skill — orchestrator for monitored pipeline runs"
````

---

### Task 9: Update CLAUDE.md and verify setup

**Files:**

- Modify: `.claude/CLAUDE.md` (add pipeline-monitor to component docs)
- Modify: `CLAUDE.md` (already has Pipeline Monitoring Rules — verify consistency)

- [ ] **Step 1: Add pipeline-monitor to .claude/CLAUDE.md**

In the Component Systems section, add after the PR Review section:

```markdown
### Pipeline Monitoring

- `/pipeline-monitor` — Step-by-step pipeline execution with real-time monitoring, 7 verification agents, persistent BUG LIST, and automated debugging
- Agents: `pipeline-orphan-hunter`, `pipeline-state-validator`, `pipeline-output-analyzer`, `pipeline-ingest-checker`, `pipeline-sort-checker`, `pipeline-scrape-checker`, `pipeline-dispatch-checker`
```

- [ ] **Step 2: Verify all 7 agent files exist**

```bash
for agent in pipeline-orphan-hunter pipeline-state-validator pipeline-output-analyzer pipeline-ingest-checker pipeline-sort-checker pipeline-scrape-checker pipeline-dispatch-checker; do
  [ -f ".claude/agents/$agent.md" ] && echo "OK: $agent" || echo "MISSING: $agent"
done
```

Expected: all 7 show "OK"

- [ ] **Step 3: Verify skill directory exists**

```bash
[ -f ".claude/skills/pipeline-monitor/SKILL.md" ] && echo "OK: skill" || echo "MISSING: skill"
```

Expected: "OK: skill"

- [ ] **Step 4: Verify hook is registered**

```bash
grep "block_background_pipeline" .claude/settings.json
```

Expected: hook entry found

- [ ] **Step 5: Run config-health-checker agent**

Launch the `config-health-checker` agent to verify all components are properly cross-referenced.

- [ ] **Step 6: Commit**

```bash
git add .claude/CLAUDE.md
git commit -m "v10.6.11: Document pipeline-monitor skill and agents in CLAUDE.md"
```

---

### Task 10: End-to-end smoke test

**Files:** None (verification only)

- [ ] **Step 1: Verify skill is listed**

```bash
# The skill should appear in the available skills list
ls .claude/skills/pipeline-monitor/SKILL.md
```

- [ ] **Step 2: Verify agents are discoverable**

```bash
ls .claude/agents/pipeline-*.md | wc -l
```

Expected: 7

- [ ] **Step 3: Test the hook blocks background execution**

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"personalscraper run","run_in_background":true}}' | python3 .claude/hooks/block_background_pipeline.py
```

Expected: `{"decision": "block", "reason": "BLOCKED: ..."}`

- [ ] **Step 4: Test the hook allows foreground execution**

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"personalscraper run","run_in_background":false}}' | python3 .claude/hooks/block_background_pipeline.py
```

Expected: `{"continue": true}`

- [ ] **Step 5: Verify docs/pipeline-runs/ directory can be created**

```bash
mkdir -p "docs/pipeline-runs" && echo "OK" || echo "FAILED"
```

- [ ] **Step 6: Final commit**

```bash
git add -f docs/pipeline-runs/.gitkeep 2>/dev/null; touch docs/pipeline-runs/.gitkeep && git add -f docs/pipeline-runs/.gitkeep
git commit -m "v10.6.12: Add pipeline-runs directory for BUG LIST persistence"
```
