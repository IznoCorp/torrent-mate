#!/usr/bin/env bash
#
# Runs the maquette's rules against a fresh build of the prototype.
#
# The prototype is built and published where the rules read it first: a stale
# `wrapped.html` measures the previous build and says nothing.
#
# Usage:
#     frontend/maquette/harness/run.sh                      # every rule (the lot-close gate)
#     frontend/maquette/harness/run.sh --rules a.py b.py    # the named rules only (a phase gate)
#     frontend/maquette/harness/run.sh --ci --shard 2/4     # a CI runner's share of the suite
#
# Fan-out: `TM_HARNESS_JOBS`, by default half the processors — one headless
# Chrome per rule, and the machine's other half stays free for what else runs
# on it.
# `TM_HARNESS_LOG_DIR` keeps the per-rule logs and a `durations.tsv`.
#
# Where it writes: `served_copy.py` decides. With the scratch volume mounted
# (`/Volumes/TMScratch`), the served copy, every Chrome profile (TMPDIR) and the
# logs go there, off the system disk, as prevention (`served_copy.py` says
# why); without it (CI), `/tmp` as before.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DESIGN="$(cd "$HERE/../design" && pwd)"
SERVED="$(python3 "$HERE/served_copy.py" --root)"
SCRATCH="$(python3 "$HERE/served_copy.py" --scratch)"
if [ -n "$SCRATCH" ]; then
  mkdir -p "$SCRATCH/tmp" "$SCRATCH/logs"
  export TMPDIR="$SCRATCH/tmp"
fi

# Rules that read what only the operator's machine has (the live config, the
# installed PWA): left out under --ci.
CI_EXCLUDED=(entry.py pwa.py settings.py address.py)

CI_MODE=0
RULES_ONLY=0
SHARD=""
NAMED_RULES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ci) CI_MODE=1 ;;
    --rules) RULES_ONLY=1 ;;
    --shard)
      SHARD="${2:-}"
      if ! [[ "$SHARD" =~ ^([1-9][0-9]*)/([1-9][0-9]*)$ ]] || [ "${BASH_REMATCH[1]}" -gt "${BASH_REMATCH[2]}" ]; then
        echo "run.sh: --shard reads i/n with 1 <= i <= n — refused: $SHARD" >&2
        exit 64
      fi
      shift
      ;;
    -*)
      echo "run.sh: unknown option $1 (known: --rules, --ci, --shard i/n)" >&2
      exit 64
      ;;
    *)
      if [ "$RULES_ONLY" -ne 1 ]; then
        echo "run.sh: rule names are read after --rules — refused: $1" >&2
        exit 64
      fi
      if [ ! -f "$HERE/$(basename "$1")" ]; then
        echo "run.sh: no rule named $1 beside $HERE/run.sh" >&2
        exit 2
      fi
      NAMED_RULES+=("$(basename "$1")")
      ;;
  esac
  shift
done

if [ "$RULES_ONLY" -eq 1 ]; then
  if [ "${#NAMED_RULES[@]}" -eq 0 ]; then
    echo "run.sh: --rules names no rule — a run of nothing would read as a green one" >&2
    exit 64
  fi
  scripts=("${NAMED_RULES[@]}")
  label="${#scripts[@]} named rule(s)"
else
  scripts=()
  for s in "$HERE"/*.py; do
    rule="$(basename "$s")"
    case "$rule" in
      common.py|desktop_frame_page.py|factories.py|navigation_edges.py|server.py|served_copy.py) continue ;;
    esac
    if [ "$CI_MODE" -eq 1 ]; then
      case " ${CI_EXCLUDED[*]} " in
        *" $rule "*) continue ;;
      esac
    fi
    scripts+=("$rule")
  done
  label="full suite (${#scripts[@]} rules)"
  if [ -n "$SHARD" ]; then
    index="${SHARD%/*}"
    count="${SHARD#*/}"
    share=()
    position=0
    for rule in "${scripts[@]}"; do
      [ $((position % count)) -eq $((index - 1)) ] && share+=("$rule")
      position=$((position + 1))
    done
    scripts=("${share[@]}")
    label="${label}, shard ${SHARD}: ${#scripts[@]} rules"
  fi
fi

KEEP_LOGS=0
if [ -n "${TM_HARNESS_LOG_DIR:-}" ]; then
  if [ -e "$TM_HARNESS_LOG_DIR" ] && [ -n "$(ls -A "$TM_HARNESS_LOG_DIR" 2>/dev/null)" ]; then
    echo "run.sh: TM_HARNESS_LOG_DIR=$TM_HARNESS_LOG_DIR is not empty — an earlier run's markers would read as this run's verdicts" >&2
    exit 64
  fi
  mkdir -p "$TM_HARNESS_LOG_DIR"
  KEEP_LOGS=1
fi

cleanup() {
  python3 "$HERE/served_copy.py" --release "$$"
  [ -n "${LOGS:-}" ] && [ "$KEEP_LOGS" -eq 0 ] && rm -rf "$LOGS"
  return 0
}

# The copy is taken BEFORE it is rebuilt, so two runs never measure each
# other's build (B-256).
python3 "$HERE/served_copy.py" --acquire "${label}" "$$"
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

echo "Building the prototype…"
(cd "$DESIGN" && npm run build >/dev/null)
python3 "$HERE/served_copy.py" --publish >/dev/null
STAMP_TOKEN="$(python3 "$HERE/served_copy.py" --token)"
if [ -z "$STAMP_TOKEN" ]; then
  echo "run.sh: the served copy carries no stamp after publishing it." >&2
  exit 1
fi

# THE HOST ON 8899 MUST SERVE THIS COPY. One left by a run that served another
# root — the one in /tmp, before the scratch volume — would answer every rule
# with a build the stamp does not vouch for, silently. It is replaced when no
# suite holds its root, and the run is refused when one does.
HOST_PID="$(lsof -nP -t -iTCP:8899 -sTCP:LISTEN 2>/dev/null | head -1 || true)"
if [ -n "$HOST_PID" ]; then
  HOST_COMMAND="$(ps -o command= -p "$HOST_PID" 2>/dev/null || true)"
  case "$HOST_COMMAND" in
    *"server.py --serve 8899 $SERVED") ;;
    *"server.py --serve 8899 "*)
      HOST_ROOT="${HOST_COMMAND##*--serve 8899 }"
      HOST_HOLDER="$(cat "$HOST_ROOT/.lock/pid" 2>/dev/null || true)"
      if [ -n "$HOST_HOLDER" ] && kill -0 "$HOST_HOLDER" 2>/dev/null; then
        echo "run.sh: the host on 8899 serves $HOST_ROOT, which a suite holds (pid $HOST_HOLDER) — wait for it" >&2
        exit 1
      fi
      echo "Replacing the harness host on 8899, which served $HOST_ROOT…"
      kill "$HOST_PID"
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        lsof -nP -iTCP:8899 -sTCP:LISTEN >/dev/null 2>&1 || break
        sleep 1
      done
      ;;
    *)
      echo "run.sh: 8899 is held by something that is not the harness host: ${HOST_COMMAND:-pid $HOST_PID}" >&2
      exit 1
      ;;
  esac
fi
if ! lsof -nP -iTCP:8899 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting the harness host on 127.0.0.1:8899…"
  (python3 "$HERE/server.py" --serve 8899 "$SERVED" >/dev/null 2>&1 &)
  sleep 2
fi

RULE_TIMEOUT_SECONDS="${TM_RULE_TIMEOUT_SECONDS:-600}"
BOUND="$(command -v timeout || command -v gtimeout || true)"
[ -n "$BOUND" ] || echo "run.sh: no timeout command on this machine — rules run unbounded" >&2
PROCESSORS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
JOBS="${TM_HARNESS_JOBS:-$(( (PROCESSORS + 1) / 2 ))}"
if [ "$KEEP_LOGS" -eq 1 ]; then
  LOGS="$(cd "$TM_HARNESS_LOG_DIR" && pwd)"
elif [ -n "$SCRATCH" ]; then
  LOGS="$(mktemp -d "$SCRATCH/logs/run.XXXXXX")"
else
  LOGS="$(mktemp -d)"
fi

echo "Running the ${label}, ${JOBS} at a time…"
printf '%s\n' "${scripts[@]}" \
  | HARNESS_DIR="$HERE" HARNESS_LOGS="$LOGS" STAMP_TOKEN="$STAMP_TOKEN" \
    HARNESS_BOUND="$BOUND" HARNESS_RULE_TIMEOUT="$RULE_TIMEOUT_SECONDS" \
    xargs -P "$JOBS" -n 1 bash -c '
      rule="$1"
      status=0
      started="$(date +%s)"
      if [ -n "$HARNESS_BOUND" ]; then
        "$HARNESS_BOUND" --kill-after=10 "$HARNESS_RULE_TIMEOUT" \
          python3 "$HARNESS_DIR/$rule" > "$HARNESS_LOGS/$rule.out" 2>&1 || status=$?
      else
        python3 "$HARNESS_DIR/$rule" > "$HARNESS_LOGS/$rule.out" 2>&1 || status=$?
      fi
      echo "$(( $(date +%s) - started ))" > "$HARNESS_LOGS/$rule.seconds"
      if [ "$status" -eq 0 ]; then
        : > "$HARNESS_LOGS/$rule.ok"
      elif [ -n "$HARNESS_BOUND" ] && { [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; }; then
        echo "TIMED OUT after ${HARNESS_RULE_TIMEOUT} s" >> "$HARNESS_LOGS/$rule.out"
        : > "$HARNESS_LOGS/$rule.timedout"
      fi
      after="$(python3 "$HARNESS_DIR/served_copy.py" --token)"
      if [ "$after" != "$STAMP_TOKEN" ]; then
        {
          echo "SERVED COPY REPLACED MID-RUN — B-256."
          echo "  started against: $STAMP_TOKEN"
          echo "  now serving:     ${after:-no stamp at all}"
        } >> "$HARNESS_LOGS/$rule.out"
        rm -f "$HARNESS_LOGS/$rule.ok"
      fi
    ' _

failed=0
for s in "${scripts[@]}"; do
  [ -f "${LOGS}/${s}.ok" ] && continue
  if [ -f "${LOGS}/${s}.timedout" ]; then
    echo "  TIMED OUT: $s"
  else
    echo "  FAILED: $s"
  fi
  # A traceback is printed whole: its frames name the call that failed (B-571).
  python3 "$HERE/../../../scripts/harness_excerpt.py" < "${LOGS}/${s}.out" | sed 's/^/      /'
  failed=$((failed + 1))
done

if [ "$KEEP_LOGS" -eq 1 ]; then
  for s in "${scripts[@]}"; do
    verdict="failed"
    [ -f "${LOGS}/${s}.ok" ] && verdict="ok"
    [ -f "${LOGS}/${s}.timedout" ] && verdict="timed-out"
    printf '%s\t%s\t%s\n' "$s" "$(cat "${LOGS}/${s}.seconds" 2>/dev/null || echo "")" "$verdict"
  done > "${LOGS}/durations.tsv"
  echo "  per-rule logs and durations kept in ${LOGS}"
fi

if [ "$failed" -gt 0 ]; then
  echo "harness: $failed of ${#scripts[@]} rule(s) FAILED." >&2
  exit 1
fi
echo "harness: ${#scripts[@]} rule(s), no violation."
