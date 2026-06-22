#!/usr/bin/env bash
# bootstrap-pm2.sh — first-run PM2 bootstrap for KanbanMate (bosun §10).
set -euo pipefail

ROOT="${1:-${KANBAN_ROOT:-$HOME/.kanban-km}}"

pm2 start kanban --name kanban-km -- run --root "$ROOT"
pm2 start kanban --name kanban-km-serve -- serve --root "$ROOT"
pm2 start kanban --name kanban-km-config -- config serve --root "$ROOT"
pm2 save
