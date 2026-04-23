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
```

## Library Maintenance

```bash
personalscraper library-scan                         # Scan library structure/metadata
personalscraper library-scan --disk Disk1            # Scan single disk
personalscraper library-clean                        # Dry-run: show what would be cleaned
personalscraper library-clean --apply                # Delete .actors/, empty dirs, junk
personalscraper library-clean --only actors --apply  # Only .actors/ dirs
personalscraper library-validate                     # Validate NFO/artwork/naming conformity
personalscraper library-validate --fix --apply       # Auto-fix what's possible
personalscraper library-analyze                      # Deep ffprobe scan (codec, audio, subs)
personalscraper library-analyze --incremental        # Skip already-analyzed files
personalscraper library-recommend                    # Generate re-download list
personalscraper library-recommend --export csv       # Export to CSV
personalscraper library-rescrape --dry-run           # Preview targeted re-scraping
personalscraper library-rescrape --only artwork      # Only re-download missing artwork
personalscraper library-rescrape --only nfo          # Only regenerate broken/missing NFOs
personalscraper library-rescrape --only episodes     # Only rename episodes via TMDB/TVDB
personalscraper library-rescrape --disk Disk1        # Single disk
personalscraper library-rescrape --max-items 50      # Limit items processed
personalscraper library-rescrape --interactive       # Confirm low-confidence matches
personalscraper library-report                       # Library health statistics
personalscraper library-report --format json         # Export as JSON
```

## Bootstrap

```bash
personalscraper init-config --from-current           # Create config.json5 from current env
```

## Aliases

```bash
media-ingest                        # → personalscraper ingest
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
