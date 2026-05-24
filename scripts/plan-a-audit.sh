#!/usr/bin/env bash
# Plan A backfill audit — coverage checkpoint snapshot.
#
# Usage:
#   bash scripts/plan-a-audit.sh              # one-shot snapshot
#   watch -n 30 'bash scripts/plan-a-audit.sh' # auto-refresh every 30s
#
# Run in a separate terminal while `personalscraper library-backfill-ids` is in progress.

set -euo pipefail
DB="${1:-.data/library.db}"

if [[ ! -f "$DB" ]]; then
  echo "ERROR: DB not found at $DB" >&2
  exit 1
fi

echo "=================================================="
echo "Plan A audit — $(date '+%Y-%m-%d %H:%M:%S')"
echo "DB: $DB"
echo "=================================================="

python3 - "$DB" <<'PY'
import sqlite3, sys, json

db = sys.argv[1]
conn = sqlite3.connect(db)
c = conn.cursor()

# 1. Total
c.execute("SELECT COUNT(*) FROM media_item")
total = c.fetchone()[0]
print(f"\nTotal media_item: {total}")

# 2. external_ids progression
c.execute("SELECT COUNT(*) FROM media_item WHERE external_ids_json != '{}'")
filled = c.fetchone()[0]
pct = 100 * filled / total if total else 0
bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
print(f"external_ids populated:  {filled:>5}/{total} ({pct:5.1f}%) [{bar}]")

# 3. ratings progression
c.execute("SELECT COUNT(*) FROM media_item WHERE ratings_json IS NOT NULL AND ratings_json != '{}'")
rated = c.fetchone()[0]
pct = 100 * rated / total if total else 0
bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
print(f"ratings populated:       {rated:>5}/{total} ({pct:5.1f}%) [{bar}]")

# 4. canonical_provider
print("\nCanonical provider breakdown:")
c.execute("SELECT canonical_provider, COUNT(*) FROM media_item GROUP BY canonical_provider ORDER BY 2 DESC")
for cp, n in c.fetchall():
    print(f"  {str(cp):<8}: {n}")

# 5. recent activity (last hour)
c.execute("SELECT COUNT(*) FROM media_item WHERE date_metadata_refreshed > strftime('%s', 'now', '-1 hour')")
last_hour = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM media_item WHERE date_metadata_refreshed > strftime('%s', 'now', '-5 minute')")
last_5min = c.fetchone()[0]
print(f"\nActivity:")
print(f"  refreshed in last 1h:    {last_hour}")
print(f"  refreshed in last 5min:  {last_5min}")

# 6. Per-kind / canonical breakdown of REMAINING work
print("\nRemaining work (external_ids_json = '{}'):")
c.execute("""
    SELECT kind, canonical_provider, COUNT(*)
    FROM media_item
    WHERE external_ids_json = '{}'
    GROUP BY kind, canonical_provider
    ORDER BY 3 DESC
""")
for kind, cp, n in c.fetchall():
    print(f"  {kind:<6} canonical={str(cp):<6}: {n}")

# 7. Pace estimate (if any activity in last 5 min)
if last_5min > 0:
    pace_per_hour = last_5min * 12
    c.execute("SELECT COUNT(*) FROM media_item WHERE external_ids_json = '{}'")
    remaining = c.fetchone()[0]
    if pace_per_hour > 0:
        eta_hours = remaining / pace_per_hour
        print(f"\nETA (at current pace of ~{pace_per_hour} items/h): {eta_hours:.1f}h for remaining {remaining} items")

conn.close()
PY

echo ""
echo "=================================================="
