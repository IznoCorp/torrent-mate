#!/usr/bin/env bash
#
# Runs the maquette's rule suite — the only thing that measures the prototype as
# it actually renders.
#
# WHY THIS EXISTS. The rules ran nowhere automatically: not in CI, not in
# `make check`, which merely printed a reminder to rebuild before running them
# by hand. The main proof mechanism of the prototype executed only when someone
# thought of it — and on 2026-08-20 a rename that looked contained broke SIX
# contracts, four of which only this suite could see. `make lint`, `make test`
# and `make check` were all green while the pipeline's stop button was dead.
#
# TWO TIERS. One headless Chrome per rule is minutes even run in parallel, and
# some rules read what only the operator's machine has — neither is a price a
# pull request can pay on every push:
#
#   --contracts   the rules that break when a NAME moves — a state id, a
#                 `data-*` value, a route, a store field. Minutes, so CI runs
#                 this on every pull request. Running them at once buys this
#                 tier almost nothing — `audit2.py` is one of the five and is
#                 nearly the whole of its cost — which is the same sentence as
#                 the floor named below, read from the other end.
#                 It also runs the repository's CHEAP guards (see below) — the
#                 ones that read what a maquette phase edits — so an invariant
#                 breach is attributable to the phase that commits it.
#   (no flag)     all of them. The gate before a wave is merged, and the only
#                 thing that proves a surface still renders what it promised.
#                 Its floor is the SLOWEST SINGLE RULE, not the total: run one
#                 at a time the suite measured 792 s on a four-core machine
#                 and 224 s run four at a time, of which `audit2.py` alone is
#                 170 s. Making the suite cheaper now means making that rule
#                 cheaper.
#   --oracle      a THIRD tier, and it duplicates neither: the rules say the
#                 BEHAVIOUR still holds, the oracle says the RENDERING did not
#                 move. `frontend/maquette/oracle.py --check`, ~25 s over 83
#                 states x 33 regions, against a committed reference.
#   --a11y        a FOURTH tier, and it duplicates none of the three: the rules
#                 say the behaviour holds, the oracle says the rendering did not
#                 move, this says the markup is USABLE — landmarks, accessible
#                 names, ARIA. `frontend/maquette/a11y.py`, axe-core over the
#                 same 83 states. It is cheap enough that CI runs it on every
#                 maquette pull request, beside `--contracts` and not inside it:
#                 an accessibility defect is not a NAME that moved, and a tier
#                 that answers two questions answers neither clearly.
#
# The suite needs the prototype BUILT and copied where the harness reads it, so
# this script does that first rather than trusting whoever runs it to remember:
# a stale `wrapped.html` measures the previous build and says nothing, which has
# cost this project two debugging sessions.
#
# Usage:
#     frontend/maquette/harness/run.sh              # every rule
#     frontend/maquette/harness/run.sh --contracts  # the name-contract subset
#     frontend/maquette/harness/run.sh --oracle     # the recorded oracle alone
#     frontend/maquette/harness/run.sh --a11y       # the accessibility audit alone
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
#   residue          an identity anchor shared by a residue rule and a typed
#                    variant, where the residue WINS and the oracle is blind
#
# `arrivals.py` guards the `data-pipe` contract too and is NOT here: it holds
# R66, which checks every figure against the run `library.db` really recorded,
# by run_uid. That database is the operator's and a CI runner has none, so the
# rule would fail there for a reason that has nothing to do with the change
# under test. It runs in the full suite, on the machine that has the data.
CONTRACTS=(page_host.py screen_addresses.py scen.py audit2.py logout.py residue.py)

# THE REPOSITORY'S CHEAP GUARDS, run beside the rules (B-063, arbitrated by the
# operator on 2026-08-25). They read the tree in seconds and they read exactly
# what a phase touches, so a breach lands on the phase that committed it
# instead of on a fifteen-phase interval — which is the state L07 ran in, where
# `make check` was a wave gate and nothing between phases read an invariant.
#
# NOT `make check` ENTIRE. Its 10 786 tests cost fourteen minutes, and the
# operator's cadence ruling of 2026-08-24 stands for that half. What joins is
# what costs seconds.
#
# THE SELECTION IS « WHAT A MAQUETTE PHASE EDITS », and a first version of this
# list got that wrong: it held the three guards that mostly read
# `personalscraper/` and `tests/` and none of the cheap ones that read the CSS,
# the markup and the resources a phase actually touches — `legacy.css`'s own
# ceiling was absent from the tier of the very wave that edits `legacy.css`.
# The six added below cost 6 s together — twelve invocations, 31 s in all,
# measured. `check-tailwind-confinement.py` is the one deliberately left out:
# it needs a build of its own and costs 102 s.
#
# `check-mock-seeds.py` joined at L08 and it belongs here on the same test: it
# reads FILES — the engine, the register, the seeds, the contract — and it costs
# 1.1 s. It cost 66 s when written, because it started one node process per
# family over a 35 198-line file; the extractor answers `--all` in one pass now.
# A tier nobody can afford to run is a tier nobody runs.
#
# NONE OF THEM READS A DATABASE, and that was checked rather than assumed. It
# is the disqualifying property for this tier: `arrivals.py` holds R66 against
# the operator's live `library.db`, a runner has none, and the rule failed
# there for a reason foreign to every change under test — twice (B-049). These
# read files.
#
# Run in the FULL suite too, and not only here. A wave gate that reads less
# than the phase gate is the same defect this project keeps paying for from the
# other end; the suite is a superset or it is not a gate.
REPOSITORY_GUARDS=(
  "scripts/check-frontend-boundaries.py"
  "scripts/check-module-size.py"
  "scripts/check-module-size.py --root scripts"
  "scripts/check-module-size.py --root tests"
  "scripts/check-module-size.py --root frontend"
  "scripts/check-no-french.py"
  "scripts/check-code-abbreviations.py"
  "scripts/check-css-tokens.py"
  "scripts/check-legacy-css-residue.py"
  "scripts/check-compositor-css.py"
  "scripts/check-markup-contracts.py"
  "scripts/check-i18n-placeholders.py"
  "scripts/check-mock-seeds.py"
  "scripts/compare-contracts.py --check"
)
REPOSITORY_ROOT="$(cd "$HERE/../../.." && pwd)"

# The oracle runs on the same freshly built copy the rules read, which is why it
# lives behind this script rather than beside it: a stale `wrapped.html`
# measures the previous build, and an ORACLE measuring the previous build says
# « no divergence » about a change it never saw.
ORACLE_ONLY=0
A11Y_ONLY=0
if [ "${1:-}" = "--oracle" ]; then
  ORACLE_ONLY=1
  scripts=()
  label="recorded oracle only"
elif [ "${1:-}" = "--a11y" ]; then
  A11Y_ONLY=1
  scripts=()
  label="accessibility audit only"
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

# The harness reads http://127.0.0.1:8899/ — `server.py --serve`, rooted on that
# copy. Never `serve.py`, which is the password-protected design host on 8712:
# it answers 401 and the suite would measure the sign-in screen.
#
# NOT a plain `python3 -m http.server`, and that is not a preference. A page
# sits at a real path (`/media`); a plain server answers a file for a file's own
# path and 404 for everything else, so the router would render its not-found
# page and every rule, the oracle and the accessibility audit would fail at once
# for a reason having nothing to do with the change under test. `server.py`
# folds any address with no file behind it onto the document, the way a host
# serving a single-page application is expected to.
if ! lsof -nP -iTCP:8899 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting the harness host on 127.0.0.1:8899…"
  (python3 "$HERE/server.py" --serve 8899 "$SERVED" >/dev/null 2>&1 &)
  sleep 2
fi

# HOW MANY RULES AT ONCE. They are independent processes reading a STATIC file
# server, so nothing couples them: the only two that write, write to their own
# fixed paths (`violations.json` beside this script, `/tmp/tm-refonte/_r73`),
# and no rule reads another's output. What couples them is the MACHINE — each
# one launches its own Chrome — so the ceiling here is cores and memory, not
# correctness. Run serially, the suite is dozens of browser startups laid end
# to end: most of its cost, and none of its value.
#
# `TM_HARNESS_JOBS=1` restores the strictly serial run, and it is the escape
# hatch that matters: a rule that measures a settle can read a contended CPU as
# a slow animation. A rule that needs the machine to itself is a finding to
# record, not a reason to run all of them alone.
JOBS="${TM_HARNESS_JOBS:-}"
if [ -z "$JOBS" ]; then
  JOBS="$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"
fi

# Each rule writes to its own log, and the FAILURES are reported after the run
# in the rule order — never the order they happened to finish. A report whose
# order depends on scheduling cannot be diffed against the previous one.
LOGS="$(mktemp -d)"
trap 'rm -rf "$LOGS"' EXIT

failed=0
# The `--oracle` and `--a11y` tiers run no rule script, and an empty array is
# both an unbound variable under `set -u` with the bash macOS ships AND empty
# input to `xargs`, which GNU runs once and BSD runs never. They are therefore
# skipped BY NAME rather than by expanding nothing — one condition, not two
# mirrored ones, so the announcement cannot drift from what actually runs.
if [ "$ORACLE_ONLY" -eq 1 ] || [ "$A11Y_ONLY" -eq 1 ]; then
  echo "Running the ${label}…"
else
  echo "Running the ${label}, ${JOBS} at a time…"
  # `-n 1` rather than `-I`: it needs no replacement string, so there is one
  # less flag whose exact behaviour has to hold across the GNU and BSD xargs
  # this script runs under. The rule name arrives as `$1` — `$0` is the `_`
  # placeholder `bash -c` consumes — and the two paths through the environment.
  printf '%s\n' "${scripts[@]}" \
    | HARNESS_DIR="$HERE" HARNESS_LOGS="$LOGS" xargs -P "$JOBS" -n 1 bash -c '
        rule="$1"
        # No `else`: the `if` exits 0 whichever way the rule went, so a fallen
        # rule does not abort `xargs` and take the rules after it with it.
        # Absence of the `.ok` marker IS the failure, read back below.
        if python3 "$HARNESS_DIR/$rule" > "$HARNESS_LOGS/$rule.out" 2>&1; then
          : > "$HARNESS_LOGS/$rule.ok"
        fi
      ' _

  for s in "${scripts[@]}"; do
    [ -f "${LOGS}/${s}.ok" ] && continue
    echo "  FAILED: $s"
    # The holds that fell — and if the filter matches nothing, the TAIL, because
    # not every rule speaks the same way. `audit2.py` uses no `common.Journal`:
    # it prints `■ R15 — 2` and `TOTAL, second pass: N violations`, so the
    # filter below returned zero lines for it and the log read « FAILED:
    # audit2.py » and stopped — verbatim the defect this block was added to fix.
    # A filter that can return nothing must have a floor.
    out="$(cat "${LOGS}/${s}.out")"
    hits="$(echo "$out" | grep -E "FAIL|Error|Traceback|error:|violation|■" | head -12)"
    [ -z "$hits" ] && hits="$(echo "$out" | tail -12)"
    echo "$hits" | sed 's/^/      /'
    failed=$((failed + 1))
  done
fi

# The repository's guards, after the rules and before the two audits. They read
# FILES — the module tree, the ceilings, the language rule — so they need no
# browser and no served copy, and they are skipped on the two single-purpose
# tiers: `--oracle` answers « did the rendering move » and `--a11y` answers « is
# the markup usable », and a tier that answers two questions answers neither
# clearly.
if [ "$ORACLE_ONLY" -eq 0 ] && [ "$A11Y_ONLY" -eq 0 ]; then
  echo
  echo "Running the repository's cheap guards (${#REPOSITORY_GUARDS[@]})…"
  for guard in "${REPOSITORY_GUARDS[@]}"; do
    # Word-splitting is WANTED here: an entry carries its own flags.
    # shellcheck disable=SC2086
    if ! (cd "$REPOSITORY_ROOT" && python3 $guard > "$LOGS/guard.out" 2>&1); then
      echo "  FAILED: python3 $guard"
      sed 's/^/      /' < "$LOGS/guard.out"
      failed=$((failed + 1))
    fi
  done
fi

if [ "$failed" -gt 0 ]; then
  echo "harness: $failed check(s) FAILED — run the script or the guard alone to see which hold fell." >&2
  exit 1
fi
if [ "$ORACLE_ONLY" -eq 0 ] && [ "$A11Y_ONLY" -eq 0 ]; then
  echo "harness: ${#scripts[@]} rule(s) and ${#REPOSITORY_GUARDS[@]} repository guard(s), no violation."
fi

# The FOURTH tier. Before the oracle, because the two answer different questions
# and this one is the cheaper of them to act on: a control with no accessible
# name is a defect wherever the rectangles landed.
#
# NEVER ON `--contracts`, for the same reason the oracle is kept out of it — but
# not for the same cost. The contracts subset answers « did a NAME move without
# all of its ends? », and an accessibility violation is not that question. CI
# runs this tier as its own step, beside the contracts one.
if [ "${1:-}" != "--contracts" ] && [ "$ORACLE_ONLY" -eq 0 ]; then
  echo
  echo "Running the accessibility audit (the markup is usable)…"
  python3 "${HERE}/../a11y.py" --check
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
if [ "${1:-}" != "--contracts" ] && [ "$A11Y_ONLY" -eq 0 ]; then
  echo
  echo "Running the recorded oracle (the rendering did not move)…"
  python3 "${HERE}/../oracle.py" --check
fi
