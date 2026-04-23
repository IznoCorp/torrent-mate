#!/usr/bin/env bash
# Unload and remove the personalscraper launchd agent.

set -euo pipefail

PLIST_NAME="com.personalscraper.pipeline.plist"
TARGET="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ ! -f "$TARGET" ]; then
    echo "Nothing to uninstall — $TARGET does not exist."
    exit 0
fi

launchctl unload "$TARGET" 2>/dev/null || true
rm "$TARGET"

echo "Uninstalled: $TARGET"
echo "(logs under \$PERSONALSCRAPER_LOG_DIR left untouched)"
