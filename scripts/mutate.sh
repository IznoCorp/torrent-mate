#!/usr/bin/env bash
#
# Runs ONE mutation against ONE rule, and cannot destroy uncommitted work.
#
# WHY THIS EXISTS, AND IT IS NOT A CONVENIENCE. Every change in this repository
# lands with a rule that bites, mutation-tested: break the behaviour on purpose,
# watch the rule fall and name the right defect, restore. The restore has always
# been `git checkout -- <file>`, and that command restores from HEAD — so a
# mutation applied on top of UNCOMMITTED work takes the work with it, silently,
# leaving a tree that builds and a commit message describing something that is
# no longer there.
#
# IT HAPPENED THREE TIMES IN ONE WAVE (B-177, and twice more), and the third
# time it deleted the two headline repairs of the lot while the commit that
# claimed them was written around the hole. The register already carried the
# rule — commit before mutating, always — and carrying it was not enough.
#
# So the discipline is a tool now:
#   * it REFUSES a dirty tree, which is the whole failure mode;
#   * it restores from the INDEX, not from HEAD, so even a staged-but-uncommitted
#     state survives;
#   * it restores on any exit, including an interrupt.
#
# Usage:
#     scripts/mutate.sh <file> <python-expression-on-t> <rule> [<rule> …]
#
# The expression is evaluated with `t` bound to the file's text and must
# produce the mutated text. Example:
#
#     scripts/mutate.sh frontend/maquette/design/src/lib/relay.ts \
#       't.replace("armLiveness(silenceDeadline());", "")' \
#       frontend/maquette/harness/liveness.py
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "usage: scripts/mutate.sh <file> <expression> <rule> [<rule> …]" >&2
  exit 2
fi

TARGET="$1"; shift
EXPRESSION="$1"; shift
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f "$TARGET" ]; then
  echo "mutate: $TARGET is not a file" >&2
  exit 2
fi

# THE REFUSAL, and it is the point of the script. A dirty tree means the
# restore below would put back something other than what is being measured —
# and, far worse, that `git checkout` would have thrown work away.
if [ -n "$(git status --porcelain)" ]; then
  echo "mutate: the working tree is dirty. A mutation restores the file, and a" >&2
  echo "        restore over uncommitted work destroys it — which is how the two" >&2
  echo "        headline repairs of L10 were lost under a commit that claimed" >&2
  echo "        them. Commit first; that is the whole rule." >&2
  git status --short >&2
  exit 1
fi

BEFORE="$(mktemp)"
cp "$TARGET" "$BEFORE"
restore() {
  cp "$BEFORE" "$TARGET"
  rm -f "$BEFORE"
  echo "mutate: $TARGET restored."
}
trap restore EXIT INT TERM

python3 - "$TARGET" "$EXPRESSION" <<'PY'
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
t = target.read_text(encoding="utf-8")
mutated = eval(sys.argv[2], {"t": t})          # noqa: S307 - the caller's own edit
if mutated == t:
    print("mutate: the expression changed nothing — a mutation that does not "
          "mutate proves the rule catches nothing.", file=sys.stderr)
    raise SystemExit(1)
target.write_text(mutated, encoding="utf-8")
PY

# THE SERVED COPY IS TAKEN BEFORE IT IS REBUILT (B-256). This script rebuilds
# and re-copies `/tmp/tm-refonte` twice — once with the mutation and once to
# restore it — and it took neither the lock nor the stamp, so a suite running
# beside it read a prototype carrying somebody else's deliberate defect and said
# nothing. It is the tool this project's METHOD mandates, which makes it the one
# most likely to be running beside a suite.
python3 frontend/maquette/harness/served_copy.py --acquire "mutate.sh" "$$"
release_the_copy() {
  python3 frontend/maquette/harness/served_copy.py --release "$$"
  return 0
}
# The trap already restores the source; it gives the copy back too, on every
# path out — a mutation tool that kept the lock after a Ctrl-C would block every
# later run for an hour.
trap 'restore; release_the_copy' EXIT INT TERM

echo "mutate: $TARGET mutated. Rebuilding the served copy…"
(cd frontend/maquette/design && npm run build >/dev/null 2>&1)
python3 frontend/maquette/harness/served_copy.py --publish >/dev/null

FELL=0
for RULE in "$@"; do
  echo "── $RULE ───────────────────────────────────────────"
  # CAPTURED, NOT PIPED. Under `pipefail` a pipeline takes the FAILING stage's
  # status, so `python3 rule | grep` reported the rule's own exit — which for a
  # rule that fell is non-zero — and the script announced « no hold fell »
  # under the falls it had just printed.
  OUTPUT="$(mktemp)"
  python3 "$RULE" >"$OUTPUT" 2>&1 || true
  if grep -E "^  FAIL|violation\(s\)" "$OUTPUT"; then
    FELL=1
  else
    echo "  (no hold fell — the rule does not catch this mutation)"
  fi
  rm -f "$OUTPUT"
done

# The restore runs from the trap, and the served copy is rebuilt after it.
# ONLY THE EXIT TRAP IS CLEARED, and the release stays armed. Clearing all
# three here left the lock held through a `restore`, a full rebuild and a
# publish — thirty to sixty seconds during which a failure under `set -e`, or a
# Ctrl-C, exited with no trap and no release, and the lock survived the whole
# staleness hour. That is the outcome the comment above this block says it is
# preventing.
trap - EXIT
trap 'release_the_copy; exit 130' INT
trap 'release_the_copy; exit 143' TERM
restore
(cd frontend/maquette/design && npm run build >/dev/null 2>&1)
python3 frontend/maquette/harness/served_copy.py --publish >/dev/null

release_the_copy
[ "$FELL" -eq 1 ] || echo "mutate: NO RULE FELL. That is the finding."
exit 0
