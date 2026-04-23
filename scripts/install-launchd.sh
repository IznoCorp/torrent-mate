#!/usr/bin/env bash
# Render com.personalscraper.pipeline.plist.template with machine-local paths
# and install it into ~/Library/LaunchAgents/ via launchctl.
#
# Environment overrides:
#   PERSONALSCRAPER_PYTHON   — path to python interpreter (default: $(which python3))
#   PERSONALSCRAPER_LOG_DIR  — log destination (default: $HOME/.personalscraper)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$PROJECT_ROOT/com.personalscraper.pipeline.plist.template"
PLIST_NAME="com.personalscraper.pipeline.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET="$TARGET_DIR/$PLIST_NAME"

PYTHON="${PERSONALSCRAPER_PYTHON:-$(command -v python3 || true)}"
LOG_DIR="${PERSONALSCRAPER_LOG_DIR:-$HOME/.personalscraper}"

if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: template not found at $TEMPLATE" >&2
    exit 1
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    echo "ERROR: python interpreter not found ($PYTHON). Set PERSONALSCRAPER_PYTHON." >&2
    exit 1
fi

PYTHON_BIN="$(dirname "$PYTHON")"

mkdir -p "$TARGET_DIR" "$LOG_DIR"

# Unload existing agent (ignore error if not loaded)
if [ -f "$TARGET" ]; then
    launchctl unload "$TARGET" 2>/dev/null || true
fi

# Render template. Paths may contain spaces, so use '|' as sed separator
# and rely on the placeholders being distinctive enough that no escaping is needed.
sed \
    -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
    -e "s|{{PYTHON}}|$PYTHON|g" \
    -e "s|{{PYTHON_BIN}}|$PYTHON_BIN|g" \
    -e "s|{{LOG_DIR}}|$LOG_DIR|g" \
    "$TEMPLATE" > "$TARGET"

launchctl load "$TARGET"

echo "Installed: $TARGET"
echo "  PROJECT_ROOT = $PROJECT_ROOT"
echo "  PYTHON       = $PYTHON"
echo "  LOG_DIR      = $LOG_DIR"
echo ""
echo "Inspect status: launchctl list | grep personalscraper"
echo "Trigger now:    launchctl start com.personalscraper.pipeline"
