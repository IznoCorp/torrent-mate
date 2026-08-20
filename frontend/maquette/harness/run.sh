#!/usr/bin/env bash
#
# Runs the maquette's rule suite — the only thing that measures the prototype as
# it actually renders.
#
# WHY THIS EXISTS. The 51 rules ran nowhere automatically: not in CI, not in
# `make check`, which merely printed a reminder to rebuild before running them
# by hand. The main proof mechanism of the prototype executed only when someone
# thought of it — and on 2026-08-20 a rename that looked contained broke SIX
# contracts, four of which only this suite could see. `make lint`, `make test`
# and `make check` were all green while the pipeline's stop button was dead.
#
# TWO TIERS, because 51 headless-Chrome runs cost 20-25 minutes and that is not
# a per-PR price worth paying:
#
#   --contracts   the rules that break when a NAME moves — a state id, a
#                 `data-*` value, a route, a store field. Minutes, so CI runs
#                 this on every pull request.
#   (no flag)     all of them. The gate before a wave is merged; slow on
#                 purpose, and the only thing that proves a surface still
#                 renders what it promised.
#
# The suite needs the prototype BUILT and copied where the harness reads it, so
# this script does that first rather than trusting whoever runs it to remember:
# a stale `wrapped.html` measures the previous build and says nothing, which has
# cost this project two debugging sessions.
#
# Usage:
#     frontend/maquette/harness/run.sh              # all 51 rules
#     frontend/maquette/harness/run.sh --contracts  # the name-contract subset
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DESIGN="$(cd "$HERE/../design" && pwd)"
SERVED="/tmp/tm-refonte"

# The rules that read a NAME someone chose — a state id, a `data-*` value, a
# route, a store field — and therefore fall the moment one of them moves
# without all of its ends. Each earned its place by catching a real break:
#   page_host        the store's field values, read through a subscript
#   screen_addresses a composite key, `add:<mode>`
#   scen             a state id built from a template
#   audit2           a state id built by string concatenation in JavaScript
#   arrivals         `data-pipe` markup against the engine that reads it
#   logout           a route renamed on one side only
CONTRACTS=(page_host.py screen_addresses.py scen.py audit2.py arrivals.py logout.py)

if [ "${1:-}" = "--contracts" ]; then
  scripts=("${CONTRACTS[@]}")
  label="contract subset (${#CONTRACTS[@]} rules)"
else
  scripts=()
  for s in "$HERE"/*.py; do
    [ "$(basename "$s")" = common.py ] && continue   # shared plumbing, not a rule
    scripts+=("$(basename "$s")")
  done
  label="full suite (${#scripts[@]} rules)"
fi

echo "Building the prototype — a stale copy measures the previous build…"
(cd "$DESIGN" && npm run build >/dev/null)
mkdir -p "$SERVED"
cp "$DESIGN/dist/index.html" "$SERVED/wrapped.html"
rm -rf "$SERVED/vite"
[ -d "$DESIGN/dist/vite" ] && cp -R "$DESIGN/dist/vite" "$SERVED/vite"
ln -sfn "$DESIGN/assets" "$SERVED/assets"

# The harness reads http://127.0.0.1:8899/wrapped.html — a PLAIN http.server
# rooted on that copy. Never `serve.py`, which is the password-protected design
# host on 8712: it answers 401 and the suite would measure the sign-in screen.
if ! lsof -nP -iTCP:8899 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting the harness host on 127.0.0.1:8899…"
  (cd "$SERVED" && python3 -m http.server 8899 --bind 127.0.0.1 >/dev/null 2>&1 &)
  sleep 2
fi

echo "Running the ${label}…"
failed=0
for s in "${scripts[@]}"; do
  if ! python3 "${HERE}/${s}" >/dev/null 2>&1; then
    echo "  FAILED: $s"
    failed=$((failed + 1))
  fi
done

if [ "$failed" -gt 0 ]; then
  echo "harness: $failed of ${#scripts[@]} rule(s) FAILED — run the script alone to see which hold fell." >&2
  exit 1
fi
echo "harness: ${#scripts[@]} rule(s), no violation."
