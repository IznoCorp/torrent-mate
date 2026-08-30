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
#                 tier almost nothing — `audit2.py` is one of the seven and is
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
#                 states x 34 regions, against a committed reference.
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
#   boot_order       the eight steps of the boot, and the five files the shell
#                    was split onto. It joined at L09 and it belongs here on
#                    this tier's own test: every phase of that lot adds to the
#                    boot, so a reordering has to land on the phase that
#                    commits it. 1.6 s, measured.
#   settle           the quiet signal, exercised against a request really held
#                    back. It is not a NAME that moved — it is the instrument
#                    every later phase's proof rests on, and a phase that
#                    breaks it must be the phase that hears about it.
#   state_surfaces   the loading and error surfaces, read by their own text and
#                    their own control rather than by a rectangle. It is here
#                    because B-108 showed the oracle recording four of them as
#                    BLANK — an instrument's blind spot needs a second reader,
#                    not a wider version of itself.
#   scroll_memory    the two viewport anchors — `data-part="viewport"` on a
#                    page and `[data-part="screen"][data-open]` on a screen.
#                    B-140 was exactly a NAME that had moved on one side only:
#                    the code read `.screen.open .port` while the main pages
#                    scrolled in `#port`, for a wave, with every gate green.
#                    5 s, measured.
#   persistence      the chrome's own nodes, and focus with them. It is here on
#                    this tier's own test: a NAME did not move, but the property
#                    it holds is one an ordinary edit destroys silently — an
#                    `innerHTML` rewrite produces buttons identical to every
#                    instrument but `isSameNode`, and the defect it closes
#                    (B-231) survived ten lots under every green gate. It joined
#                    at L15, with the tab bar's conversion. ~9 s, measured.
#   relay_states     the connection's four conditions, read the same way and on
#                    the same test: `data-part="shell/connection-mark"`, three
#                    state ids and a `data-connection` value are NAMES, and the
#                    header the dot sits in is measured by no oracle region — so
#                    a name that moved here would break nothing else visibly.
#                    It joined at L10, and §8 of the constitution is the reason
#                    it is not deferred to the wave gate: an interface that has
#                    stopped saying it is stale is the one defect this lot must
#                    never ship, and a fifteen-phase interval is not where that
#                    should be found.
#
# `arrivals.py` guards the `data-pipe` contract too and is NOT here: it holds
# R66, which checks every figure against the run `library.db` really recorded,
# by run_uid. That database is the operator's and a CI runner has none, so the
# rule would fail there for a reason that has nothing to do with the change
# under test. It runs in the full suite, on the machine that has the data.
CONTRACTS=(page_host.py screen_addresses.py scen.py audit2.py logout.py residue.py boot_order.py settle.py state_surfaces.py relay_states.py scroll_memory.py persistence.py)

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
# The six added below cost 6 s together — nineteen invocations, ~31 s in all,
# measured. `check-tailwind-confinement.py` is the one deliberately left out:
# it needs a build of its own and costs 102 s.
#
# `check-maquette-unit-tests.py` joined at L09 and it belongs here on the same
# test: 1.1 s, and it runs the maquette's own unit suite — which a maquette
# phase edits by definition. It is the RUNNER's guard as much as the suite's: a
# run that collects one file out of two is green and reports a smaller number
# nobody compares, so it holds a floor on both counts. Where the maquette's
# dependencies are absent it says SKIPPED and says that is not a pass.
#
# `check-mock-seeds.py` joined at L08 and it belongs here on the same test: it
# reads FILES — the engine, the register, the seeds, the contract — and it costs
# 1.1 s. It cost 66 s when written, because it started one node process per
# family over a 35 198-line file; the extractor answers `--all` in one pass now.
# A tier nobody can afford to run is a tier nobody runs.
#
# `check-intent-map.py` joined at L15 as B-142's instrument, and it is the one
# guard here whose subject is the CONSTITUTION rather than the tree: it holds
# every DOIT and NE-DOIT-PAS clause against the surface `product-intent-map.md`
# says serves it, and refuses a clause with no row, a named surface the tree
# does not have, an owed half with no lot, and a « served » with no proof. It
# reads FILES, in 0.1 s. It is on this tier because a clause map is amended by
# prose pull requests, which are exactly the ones the wave gate never sees.
#
# `check-viewport-directives.py` joined at L15 with B-230, and it belongs here
# for a reason the accessibility tier makes plain: axe reports `meta-viewport`
# when the directive is PRESENT on the document it audits, and B-230 was never
# present on THIS document — the dying engine added it only to a host that had
# none. So the branch was dead here and live on every other host the file could
# be served from, and the tier written to catch exactly that violation could not
# see it. It reads FILES, in 0.1 s, comments included.
#
# `check-bug-register.py` joined at L10-bis and it belongs here for a reason
# the others do not have: the register is written DURING a wave (B-084), so
# `BUGS.md` is a file every maquette phase edits, and its index is where a
# wave's own account of itself is kept. It costs 0.1 s, it reads two files and
# it holds the shape that made a count of « 48 open » out of 42.
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
  "scripts/check-maquette-unit-tests.py"
  "scripts/check-state-ownership.py"
  "scripts/check-live-relay.py"
  "scripts/check-implementation-state.py"
  "scripts/check-bug-register.py"
  "scripts/check-frame-domain.py"
  "scripts/check-viewport-directives.py"
  "scripts/check-intent-map.py"
  "scripts/check-docs-cited-paths.py"
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

# THE SERVED COPY IS TAKEN BEFORE IT IS REBUILT (B-256). Until this line, two
# sessions could each rebuild `$SERVED` while the other was reading it, and on
# 2026-08-30 two rules fell over a build they were never started against. The
# dangerous direction is the other one: a rule PASSES over the wrong prototype
# just as silently. The lock refuses the second builder; the stamp written after
# the copy is what catches a reader the lock cannot cover.
#
# The trap releases it whatever happens — an interrupt included. `$LOGS` does
# not exist yet, and `cleanup` is written so that removing something absent is
# not an error rather than so that two traps have to stay in step.
cleanup() {
  python3 "$HERE/served_copy.py" --release "$$"
  [ -n "${LOGS:-}" ] && rm -rf "$LOGS"
  return 0
}
# ACQUIRE FIRST, THEN ARM THE TRAP, and the order is the whole correctness of
# it: armed first, a REFUSED acquisition would exit through `cleanup` and hand
# away the lock of the session that is legitimately holding the copy. The
# release also refuses to give back a lock recording another pid, so this is
# belt and braces on a mistake that would be invisible.
#
# The pid the lock records is THIS SHELL's, never the helper's — the helper
# exits a millisecond later, and a lock recording a dead process is a lock the
# staleness check would break under a suite that is still running.
python3 "$HERE/served_copy.py" --acquire "${label}" "$$"
trap cleanup EXIT

echo "Building the prototype — a stale copy measures the previous build…"
(cd "$DESIGN" && npm run build >/dev/null)
mkdir -p "$SERVED"
cp "$DESIGN/dist/index.html" "$SERVED/wrapped.html"
rm -rf "$SERVED/vite"
[ -d "$DESIGN/dist/vite" ] && cp -R "$DESIGN/dist/vite" "$SERVED/vite"
ln -sfn "$DESIGN/assets" "$SERVED/assets"

# WHICH BUILD IS NOW IN THE COPY. Written after the copy and never before: a
# stamp naming a build that is still being copied would be the very false
# reading this is here to end.
python3 "$HERE/served_copy.py" --stamp >/dev/null
STAMP_TOKEN="$(python3 "$HERE/served_copy.py" --token)"

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
    | HARNESS_DIR="$HERE" HARNESS_LOGS="$LOGS" STAMP_TOKEN="$STAMP_TOKEN" \
      xargs -P "$JOBS" -n 1 bash -c '
        rule="$1"
        # No `else`: the `if` exits 0 whichever way the rule went, so a fallen
        # rule does not abort `xargs` and take the rules after it with it.
        # Absence of the `.ok` marker IS the failure, read back below.
        if python3 "$HARNESS_DIR/$rule" > "$HARNESS_LOGS/$rule.out" 2>&1; then
          : > "$HARNESS_LOGS/$rule.ok"
        fi
        # THE STAMP, AROUND EVERY RULE (B-256). This reading is what covers the
        # twelve rules that import nothing from `common.py` — `audit2.py`, the
        # rule that started the incident, among them. It runs whichever way the
        # rule went: a rule that PASSED over a swapped copy is the case that
        # matters, and it is the one a verdict-shaped check would skip.
        after="$(python3 "$HARNESS_DIR/served_copy.py" --token)"
        if [ "$after" != "$STAMP_TOKEN" ]; then
          {
            echo "SERVED COPY REPLACED MID-RUN — B-256."
            echo "  started against: $STAMP_TOKEN"
            echo "  now serving:     ${after:-no stamp at all}"
            echo "  This reading spans two builds and means nothing either way."
          } >> "$HARNESS_LOGS/$rule.out"
          rm -f "$HARNESS_LOGS/$rule.ok"
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
