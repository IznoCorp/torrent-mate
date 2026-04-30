#!/usr/bin/env bash
# index-rotate.sh
# ----------------
# Shell wrapper called by personalscraper-index-rotate.plist.
# Selects the disk to fully index based on the current ISO weekday (1=Mon … 7=Sun).
#
# Rotation schedule:
#   Monday    (1) → Disk1   full scan
#   Tuesday   (2) → Disk2   full scan
#   Wednesday (3) → Disk3   full scan
#   Thursday  (4) → Disk4   full scan
#   Friday    (5) → quick mode (no disk argument — all disks, Merkle short-circuit)
#   Saturday  (6) → quick mode
#   Sunday    (7) → quick mode
#
# The disk labels (Disk1 … Disk4) must match the labels defined in config.json5.
# Edit DISK_MAP below if your disk labels differ or you have more/fewer disks.
#
# Usage (called automatically by launchd):
#   /bin/bash /path/to/index-rotate.sh
#
# Manual test:
#   DOW=1 /bin/bash index-rotate.sh   # simulate Monday (Disk1)
#   DOW=5 /bin/bash index-rotate.sh   # simulate Friday (quick fallback)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit to match your disk labels from config.json5
# ---------------------------------------------------------------------------

# Map ISO weekday (1=Mon … 4=Thu) to disk label.
# Days 5, 6, 7 fall through to the quick-mode fallback below.
declare -A DISK_MAP=(
    [1]="Disk1"
    [2]="Disk2"
    [3]="Disk3"
    [4]="Disk4"
)

# Absolute path to the personalscraper binary.
# Adjust if installed in a virtualenv or via pyenv.
PERSONALSCRAPER="${PERSONALSCRAPER:-/usr/local/bin/personalscraper}"

# Lock wait: 0 means "exit immediately if another instance holds the lock".
WAIT_FOR_LOCK="${WAIT_FOR_LOCK:-0}"

# ---------------------------------------------------------------------------
# Weekday selection
# ---------------------------------------------------------------------------

# Allow DOW override for manual testing; otherwise use today's ISO weekday.
DOW="${DOW:-$(date +%u)}"

if [[ -v DISK_MAP[$DOW] ]]; then
    DISK_LABEL="${DISK_MAP[$DOW]}"
    echo "[index-rotate] weekday=${DOW} → full scan on disk '${DISK_LABEL}'"
    exec "${PERSONALSCRAPER}" library index \
        --mode full \
        --disk "${DISK_LABEL}" \
        --wait-for-lock "${WAIT_FOR_LOCK}"
else
    # Friday, Saturday, Sunday — fall back to a cheap quick scan.
    echo "[index-rotate] weekday=${DOW} → quick scan (no disk filter)"
    exec "${PERSONALSCRAPER}" library index \
        --mode quick \
        --wait-for-lock "${WAIT_FOR_LOCK}"
fi
