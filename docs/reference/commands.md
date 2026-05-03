# Commands Reference

Complete CLI reference for `personalscraper` and related tools.

## PersonalScraper CLI

```bash
personalscraper ingest              # Ingest completed torrents from qBittorrent
personalscraper ingest --dry-run    # Preview without moving
personalscraper sort                # Sort media files into category folders
personalscraper scrape              # Scrape metadata from TMDB/TVDB
personalscraper verify              # Quality check before dispatch
personalscraper dispatch            # Move to storage disks
personalscraper process             # Reclean + dedup + scrape + cleanup
personalscraper enforce             # Enforce staging conventions
personalscraper run                 # Full pipeline
personalscraper run --dry-run       # Preview full pipeline
personalscraper run --skip-trailers            # Skip the trailers step
personalscraper run --continue-on-trailer-error  # Continue to dispatch even on trailer errors
```

## Library Maintenance

### Indexer (DB-backed)

```bash
personalscraper library-index                                # Full indexer scan (all disks)
personalscraper library-index --mode quick                   # Quick: Merkle short-circuit + dir-mtime
personalscraper library-index --mode incremental             # Changed-files-only
personalscraper library-index --mode enrich                  # Mediainfo + NFO + artwork on un-enriched files
personalscraper library-index --mode enrich --backfill-streams  # Fill only missing migration-004 columns (hdr_format / is_atmos / is_default / forced / format) on already-enriched rows
personalscraper library-index --disk Disk1 --mode full       # Restrict to one disk
personalscraper library-index --dry-run                      # Plan only, no DB writes
personalscraper library-index --rebuild                      # Drop and rebuild from scratch
personalscraper library-index --confirm-bulk-change          # Confirm large Merkle delta
personalscraper library-index --budget 1800                  # Wall-clock cap (seconds; default from indexer.scan.budget_seconds)
personalscraper library-index --no-budget                    # Disable budget for manual full enrich passes
personalscraper library-index --wait-for-lock 60             # Wait N seconds for the writer lock instead of failing immediately
personalscraper library-status                               # Latest indexer scan run summary
personalscraper library-verify                               # Re-stat every indexed file; enqueue mismatches
personalscraper library-verify --disk Disk1                  # Verify one disk
personalscraper library-search "<query>"                     # Flex-attr query (e.g. nfo_status:invalid)
personalscraper library-search "<query>" --limit 200         # Cap result count (default 50)
personalscraper library-show <item_id>                       # Pretty-print all data for one item
personalscraper library-repair                               # Drain repair queue (default budget)
personalscraper library-repair --budget 120                  # Drain with explicit time budget (s)
personalscraper library-reconcile                            # Detect index ↔ FS divergences (DB-only, no rescan)
personalscraper library-reconcile --scope enrich             # Restrict to one detector (repeatable)
personalscraper library-reconcile --enqueue-repairs          # Push findings into repair_queue (drained by library-repair)
personalscraper library-ghost-audit                           # Audit disks for NTFS-via-macFUSE ghost directory entries
personalscraper library-ghost-audit --disk Disk1              # Audit only one disk
personalscraper library-relink                                # Dry-run: show media_file rows with missing release links
personalscraper library-relink --apply                        # Persist release link updates
```

### Disk-walking commands

```bash
personalscraper library-clean                                # Dry-run: show what would be cleaned
personalscraper library-clean --apply                        # Delete .actors/, empty dirs, junk
personalscraper library-clean --only actors --apply          # Only .actors/ dirs
personalscraper library-validate                             # Validate NFO/artwork/naming conformity (FS walk)
personalscraper library-validate --from-index                # Fast pre-screen from indexer DB (NFO + poster/landscape only, no structural checks)
personalscraper library-validate --fix --apply               # Auto-fix what's possible
personalscraper library-analyze                              # Deep ffprobe scan (codec, audio, subs)
personalscraper library-analyze --from-index                 # Read streams from indexer DB instead of ffprobe (much faster, HDR/Atmos approximated)
LIBRARY_ANALYZER_MAX_WORKERS=8 personalscraper library-analyze   # Override the 4-worker cap (use on SSD libraries)
personalscraper library-recommend                            # Run ffprobe analysis inline + generate re-download list
personalscraper library-recommend --from-index               # Use indexer DB streams instead of ffprobe
personalscraper library-recommend --export csv               # Export to CSV
personalscraper library-rescrape --dry-run                   # Preview targeted re-scraping
personalscraper library-rescrape --only artwork              # Only re-download missing artwork
personalscraper library-rescrape --only nfo                  # Only regenerate broken/missing NFOs
personalscraper library-rescrape --only episodes             # Only rename episodes via TMDB/TVDB
personalscraper library-rescrape --disk Disk1                # Single disk
personalscraper library-rescrape --max-items 50              # Limit items processed
personalscraper library-rescrape --interactive               # Confirm low-confidence matches
personalscraper library-report                               # Library health statistics (DB-backed)
personalscraper library-report --format json                 # Export as JSON
```

## Trailers

personalscraper trailers scan [--disk D] [--category C] [--since YYYY-MM-DD] [--limit N] [--level show|season|both] [--season N] [--no-refresh]
personalscraper trailers download [--dry-run] [--disk D] [--category C] [--since YYYY-MM-DD] [--limit N] [--level season] [--season N] [--no-refresh]
personalscraper trailers verify [--disk D] [--category C] [--deep] [--since YYYY-MM-DD] [--level show|season|both] [--season N]
personalscraper trailers purge [--dry-run] [--disk D] [--since YYYY-MM-DD] [--level show|season|both] [--season N] [--include-state]

Exit codes: 0 ok, 1 error, 2 bad argument.

Common filters: `--disk` and `--category` are accepted by scan, download, and verify.
`--since`, `--level`, and `--season` are accepted by all four commands.
`--limit` and `--no-refresh` are only accepted by scan and download.

## Bootstrap & Inspection

```bash
personalscraper init-config                          # Create config/ directory from the config.example/ template (interactive)
personalscraper init-config --yes                    # Non-interactive — accept all defaults
personalscraper init-config --force                  # Overwrite existing config/ directory (backs up to .bak)
personalscraper info                                 # Display version, config paths, disk status
```

## Config Migration

```bash
personalscraper config migrate-category --from OLD --to NEW  # Rename a category id across config + on-disk paths
```

## Disk Space Check

```bash
df -h /Volumes/Disk{1,2,3,4}
```

## Scheduling (launchd)

```bash
# Install
cp com.personalscraper.pipeline.plist ~/Library/LaunchAgents/

# Load (register with launchd)
launchctl load ~/Library/LaunchAgents/com.personalscraper.pipeline.plist

# Unload
launchctl unload ~/Library/LaunchAgents/com.personalscraper.pipeline.plist

# Manual trigger
launchctl start com.personalscraper.pipeline

# Status
launchctl list | grep personalscraper
```

Default schedule: daily at 3am (see `com.personalscraper.pipeline.plist`).

## Make Targets

```bash
make test         # Unit tests (~6s)
make lint         # ruff check
make format       # ruff format + fix
make install-dev  # Editable install with dev deps
```
