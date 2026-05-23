# launchd-plists/

User-facing launchd agent property lists for personalscraper recurring jobs.

These plists are templates: edit the `REPLACE_ME` placeholder in each file to
match your home directory before copying to `~/Library/LaunchAgents/`.

A second convention lives at `docs/reference/launchd/` for the nightly indexer
agents (`personalscraper-index-quick.plist`, `personalscraper-index-enrich.plist`,
`personalscraper-index-rotate.plist`). New cron-style agents land here under
`launchd-plists/` going forward.

## Available agents

| Plist                                    | Schedule              | Command                                | Purpose                                                                |
| ---------------------------------------- | --------------------- | -------------------------------------- | ---------------------------------------------------------------------- |
| `com.personalscraper.backfill-ids.plist` | Weekly (Sunday 03:00) | `personalscraper library-backfill-ids` | Backfill cross-provider IDs + ratings on library items (SH-3, DEV #28) |

## Install (per-user agent)

```bash
# 1. Ensure the log directory exists (launchd does NOT create it).
mkdir -p ~/.cache/personalscraper

# 2. Copy the plist and replace REPLACE_ME with your home directory short name.
cp launchd-plists/com.personalscraper.backfill-ids.plist ~/Library/LaunchAgents/
sed -i '' "s|/Users/REPLACE_ME|$HOME|g" ~/Library/LaunchAgents/com.personalscraper.backfill-ids.plist

# 3. Confirm `personalscraper` path matches the plist (default /usr/local/bin/personalscraper).
which personalscraper

# 4. Load the agent.
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.personalscraper.backfill-ids.plist

# 5. Optional: trigger a manual run to verify wiring.
launchctl kickstart -k gui/$(id -u)/com.personalscraper.backfill-ids
tail -f ~/.cache/personalscraper/backfill-ids.log
```

## Remove

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.personalscraper.backfill-ids.plist
rm ~/Library/LaunchAgents/com.personalscraper.backfill-ids.plist
```

## Prerequisites

`library-backfill-ids` requires that `personalscraper library-init-canonical`
has been run at least once (to seed `canonical_provider`) and that `.env`
contains the relevant API credentials (`TMDB_API_KEY`, `TVDB_API_KEY`,
`OMDB_API_KEY`). The agent will exit non-zero with a descriptive error if
any prerequisite is missing.
