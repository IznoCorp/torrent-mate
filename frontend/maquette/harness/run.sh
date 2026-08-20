#!/usr/bin/env bash
#
# Runs the maquette's rule suite — the only thing that measures the prototype as
# it actually renders.
#
# WHY THIS EXISTS. The 50 rules ran nowhere automatically: not in CI, not in
# `make check`, which merely printed a reminder to rebuild before running them
# by hand. The main proof mechanism of the prototype executed only when someone
# thought of it — and on 2026-08-20 a rename that looked contained broke SIX
# contracts, four of which only this suite could see. `make lint`, `make test`
# and `make check` were all green while the pipeline's stop button was dead.
#
# TWO TIERS, because 50 headless-Chrome runs cost 20-25 minutes and that is not
# a per-PR price worth paying:
#
#   --contracts   the rules that break when a NAME moves — a state id, a
#                 `data-*` value, a route, a store field. Minutes, so CI runs
#                 this on every pull request.
#   (no flag)     all of them. The gate before a wave is merged; slow on
#                 purpose, and the only thing that proves a surface still
#                 renders what it promised.
#   --oracle      a THIRD tier, and it duplicates neither: the rules say the
#                 BEHAVIOUR still holds, the oracle says the RENDERING did not
#                 move. `frontend/maquette/oracle.py --check`, ~25 s over 82
#                 states x 33 regions, against a committed reference.
#
# The suite needs the prototype BUILT and copied where the harness reads it, so
# this script does that first rather than trusting whoever runs it to remember:
# a stale `wrapped.html` measures the previous build and says nothing, which has
# cost this project two debugging sessions.
#
# Usage:
#     frontend/maquette/harness/run.sh              # all 50 rules
#     frontend/maquette/harness/run.sh --contracts  # the name-contract subset
#     frontend/maquette/harness/run.sh --oracle     # the recorded oracle alone
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
#   logout           a route renamed on one side only
#
# `arrivals.py` guards the `data-pipe` contract too and is NOT here: it holds
# R66, which checks every figure against the run `library.db` really recorded,
# by run_uid. That database is the operator's and a CI runner has none, so the
# rule would fail there for a reason that has nothing to do with the change
# under test. It runs in the full suite, on the machine that has the data.
CONTRACTS=(page_host.py screen_addresses.py scen.py audit2.py logout.py)

# The oracle runs on the same freshly built copy the rules read, which is why it
# lives behind this script rather than beside it: a stale `wrapped.html`
# measures the previous build, and an ORACLE measuring the previous build says
# « no divergence » about a change it never saw.
ORACLE_ONLY=0
if [ "${1:-}" = "--oracle" ]; then
  ORACLE_ONLY=1
  scripts=()
  label="recorded oracle only"
elif [ "${1:-}" = "--contracts" ]; then
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
# `${scripts[@]}` on an EMPTY array is an unbound variable under `set -u` with
# the bash macOS ships, so the `--oracle` tier — which runs no rule script —
# skips the loop by name rather than by expanding nothing.
for s in ${scripts[@]+"${scripts[@]}"}; do
  if ! out="$(python3 "${HERE}/${s}" 2>&1)"; then
    echo "  FAILED: $s"
    # The holds that fell — and if the filter matches nothing, the TAIL, because
    # not every rule speaks the same way. `audit2.py` uses no `common.Journal`:
    # it prints `■ R15 — 2` and `TOTAL, second pass: N violations`, so the
    # filter below returned zero lines for it and the log read « FAILED:
    # audit2.py » and stopped — verbatim the defect this block was added to fix.
    # A filter that can return nothing must have a floor.
    hits="$(echo "$out" | grep -E "FAIL|Error|Traceback|error:|violation|■" | head -12)"
    [ -z "$hits" ] && hits="$(echo "$out" | tail -12)"
    echo "$hits" | sed 's/^/      /'
    failed=$((failed + 1))
  fi
done

if [ "$failed" -gt 0 ]; then
  echo "harness: $failed of ${#scripts[@]} rule(s) FAILED — run the script alone to see which hold fell." >&2
  exit 1
fi
if [ "$ORACLE_ONLY" -eq 0 ]; then
  echo "harness: ${#scripts[@]} rule(s), no violation."
fi

# The third tier. Run last, because a rendering that moved is worth knowing about
# after the behaviour is known to hold: a fallen rule explains a moved rectangle,
# and the reverse is rarely true.
#
# NEVER ON `--contracts`, and this is not tidiness — it shipped broken once. The
# contracts subset is what CI runs on EVERY pull request, and the oracle cannot
# run there at all: its reference is a measurement, and a measurement is bound to
# the machine that took it. On the GitHub runner the same unmodified tree
# reported heights of 1477 where this one records 1474.1 — three pixels of font
# metrics, not a change to anything. Same reason `arrivals.py` is kept out of the
# subset: a hold that fails on the runner for a reason foreign to the change
# under test teaches nobody anything and gets muted.
if [ "${1:-}" != "--contracts" ]; then
  echo
  echo "Running the recorded oracle (the rendering did not move)…"
  python3 "${HERE}/../oracle.py" --check
fi
