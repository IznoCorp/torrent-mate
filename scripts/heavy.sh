#!/bin/sh
# A machine-wide lock for heavy runs on IznoServer (8 cores, 16 GB).
#
# WHY IT EXISTS. One Playwright browser group costs about 1.1 GB, and the
# baseline (wired memory, Plex, qBittorrent, the editor, the sessions) already
# holds about 6 GB. Eight rules in parallel therefore ask for more memory than
# the machine has, and the machine answers by compressing — which on this host
# is not reclaimed until a reboot. Two sessions each believing they are alone
# is how a load of 65 with 200 MB free happened.
#
# THE MARGIN IS THE POINT. The thresholds below are not the edge of what fits;
# they are chosen so that what fits is never the question. A run waits rather
# than squeezes, and a run that starts well and turns bad is stopped rather
# than allowed to take the machine with it.
#
# USE. Wrap anything that starts browsers, builds, or a parallel test run:
#
#   sh scripts/heavy.sh [--class browser|test|rule] "<who>" <command...>
#
# It waits for whoever holds the lock, waits again until the machine has room
# to spare, runs the command under a watchdog, and releases the lock whatever
# happens. `HEAVY_LOCK` moves the lock, which is what `tests/scripts/test_heavy.py`
# uses to exercise every path here without touching the machine's real lock.
#
# THE CLASS SAYS WHAT THE RUN COSTS. Until B-386 there was one readiness floor
# for every run, so the replay of a single rule waited behind the same room a
# two-browser harness suite needs, and a wave that wanted a `make check` to
# start asked to lower the floor by environment — which is the bypass the floor
# exists to forbid. A named class carries its own floor, and under a named
# class `HEAVY_FREE_FLOOR_MB` may only RAISE it. A run with no class keeps the
# historical floor and the historical bypass, so every existing invocation
# still works exactly as it did.

LOCK=${HEAVY_LOCK:-/private/tmp/tm-heavy/holder}

# ── Who holds it? ────────────────────────────────────────────────────────────
# `sh scripts/heavy.sh --held` prints the holder's name and exits 0, or prints
# « free » and exits 1. THE LOCK IS A DIRECTORY, and that is why this exists:
# the natural probe — `cat .../holder` — reads a directory as a file, fails, and
# under `2>/dev/null` prints NOTHING whether the lock is held or free. Two
# sessions reached for that probe independently on one night, one certified a
# machine « free » that was not, the other accused a wrapped run of running
# unwrapped, and neither output could tell them (B-326). A probe that cannot
# fail is not a probe; this one reads `who`, which only a holder writes.
if [ "${1:-}" = "--held" ]; then
    if [ -d "$LOCK" ]; then
        cat "$LOCK/who" 2>/dev/null || echo "someone"
        exit 0
    fi
    echo "free"
    exit 1
fi

# ── What class of run is this? ───────────────────────────────────────────────
RUN_CLASS=""
if [ "${1:-}" = "--class" ]; then
    RUN_CLASS=${2:?--class needs a name: browser, test or rule}
    shift 2
fi

WHO=${1:?who is asking}
shift

# ── The ceilings, with margin, read from the run's class ─────────────────────
# The arithmetic is the office's (docs/reference/frontend-steward.md
# § Instrument hygiene) and this host's: 8 cores, 16 GB, a baseline that already
# holds about 6 GB, and ONE Playwright browser group costing about 1.1 GB.
#
#   browser  a harness run: one or two browser groups.
#            2 x 1.1 GB = 2.2 GB needed -> 4096 MB, a third group's worth of
#            slack, and load 6 because two groups plus their driver want most
#            of the machine quiet. This is the historical floor, unmoved.
#   test     a parallel pytest at three workers, `make check`, or a build.
#            No browser: three workers plus their parent, or a Vite build
#            peaking near 1.5 GB -> 3072 MB, twice the peak, and load 6 for the
#            three cores it is about to take.
#   rule     a single rule replayed against the served copy: ONE browser group.
#            1.1 GB plus the static host -> 2560 MB, and load 10 on 8 cores,
#            which is no wait at all: making a one-core run wait for a quiet
#            machine is the wait nobody needs, and a wait nobody needs is how a
#            mandatory wrapper gets bypassed.
#
# The hard floor below (2048 MB, the watchdog's red line) does NOT move with the
# class: it is what the script will not let its own child run under, whatever
# the run believed it needed when it started.
case "$RUN_CLASS" in
    browser) CLASS_FLOOR_MB=4096; CLASS_LOAD_CEILING=6 ;;
    test)    CLASS_FLOOR_MB=3072; CLASS_LOAD_CEILING=6 ;;
    rule)    CLASS_FLOOR_MB=2560; CLASS_LOAD_CEILING=10 ;;
    "")      CLASS_FLOOR_MB=4096; CLASS_LOAD_CEILING=6 ;;
    *)
        echo "heavy: unknown class '$RUN_CLASS' — say browser, test or rule" >&2
        exit 64
        ;;
esac

FREE_FLOOR_MB=${HEAVY_FREE_FLOOR_MB:-$CLASS_FLOOR_MB}
LOAD_CEILING=${HEAVY_LOAD_CEILING:-$CLASS_LOAD_CEILING}

# The watchdog's red line. Crossed for three samples in a row — 45 seconds, so
# a transient dip during a build's peak does not count — the wrapped command is
# stopped. It kills only what this script started; nothing else on the machine
# is ever touched, and the run can simply be launched again.
HARD_FLOOR_MB=${HEAVY_HARD_FLOOR_MB:-2048}
HARD_STRIKES=3

free_megabytes() {
    # macOS first, then Linux, and NOTHING when neither answers. A wrapper that
    # runs on one operating system is a wrapper the repository's own CI cannot
    # execute: `vm_stat` is Darwin's, the runners are Linux, and the first
    # version of this hung there for the same reason it hung on a missing lock
    # parent — it waited for a number it could never obtain.
    if command -v vm_stat > /dev/null 2>&1; then
        vm_stat | awk '
            /page size of/ { size = $8 }
            /Pages free/ { free = $3 }
            /Pages inactive/ { inactive = $3 }
            END { gsub(/\./, "", free); gsub(/\./, "", inactive);
                  if (size && (free + inactive) > 0)
                      print int((free + inactive) * size / 1048576) }'
    elif [ -r /proc/meminfo ]; then
        awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo
    fi
}

one_minute_load() {
    # The locale writes the decimal with a comma and separates the three
    # averages with commas too, so the first field arrives as « 2,57, ».
    uptime | sed 's/.*load averages*: *//' | awk '{ print $1 }' |
        tr ',' '.' | sed 's/\.$//'
}

at_least() {
    awk -v have="$1" -v want="$2" 'BEGIN { print (have >= want) ? 1 : 0 }'
}

at_most() {
    awk -v have="$1" -v want="$2" 'BEGIN { print (have <= want) ? 1 : 0 }'
}

# ── A named class cannot be talked down ──────────────────────────────────────
# Naming a class is a statement about what the run costs, so the environment may
# RAISE its floor and never lower it. Without this the class would be a label on
# a number anybody could set to 1, which is the bypass B-386 records being asked
# for. `HEAVY_LOCK` is untouched by this: moving the lock is how the test suite
# exercises every path here without touching the machine's own, and it changes
# no threshold.
if [ -n "$RUN_CLASS" ]; then
    if [ "$(at_least "$FREE_FLOOR_MB" "$CLASS_FLOOR_MB")" = 0 ]; then
        echo "heavy: refusing HEAVY_FREE_FLOOR_MB=${FREE_FLOOR_MB} — class $RUN_CLASS wants ${CLASS_FLOOR_MB}MB free and the environment may only raise a class's floor" >&2
        exit 64
    fi
    if [ "$(at_most "$LOAD_CEILING" "$CLASS_LOAD_CEILING")" = 0 ]; then
        echo "heavy: refusing HEAVY_LOAD_CEILING=${LOAD_CEILING} — class $RUN_CLASS runs at load $CLASS_LOAD_CEILING or below and the environment may only lower a class's ceiling" >&2
        exit 64
    fi
fi

echo "heavy: wants ${FREE_FLOOR_MB}MB free and load ${LOAD_CEILING} or below (class ${RUN_CLASS:-none})" >&2

# ── Make sure the lock CAN be taken ──────────────────────────────────────────
# `/private/tmp` is purged at boot and this host reboots weekly, so the lock's
# parent is absent on the first heavy run of every week. With a bare `mkdir`
# that failed `ENOENT` on every pass, the stale-lock breaker below could never
# fire (it tests a path that does not exist), and the script span forever
# announcing a holder nobody held. A wrapper the office is REQUIRED to use must
# not be the thing that stops it.
parent=$(dirname "$LOCK")
mkdir -p "$parent" 2>/dev/null || true
if [ ! -d "$parent" ] || [ ! -w "$parent" ]; then
    echo "heavy: cannot use $parent as the lock's home — running unlocked" >&2
    exec "$@"
fi

# ── Take the lock ────────────────────────────────────────────────────────────
announced=0
while :; do
    if mkdir "$LOCK" 2>/dev/null; then
        echo "$WHO" > "$LOCK/who"
        break
    fi
    holder=$(cat "$LOCK/who" 2>/dev/null || echo "someone")
    # A lock older than 45 minutes is a session that died holding it.
    if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +45 2>/dev/null)" ]; then
        echo "heavy: breaking a stale lock held by $holder" >&2
        rm -rf "$LOCK"
        continue
    fi
    [ "$announced" -eq 0 ] && echo "heavy: waiting for $holder to finish" >&2
    announced=1
    sleep 3
done

# Interrupted, the wrapper must take DOWN what it started, not merely let go of
# the lock: a run stopped by hand that leaves its browsers behind is the exact
# residue the ceiling exists to prevent, and the operator has had to clear it.
# `child` is empty until the run begins, so the same handler serves both phases.
child=""
release() {
    [ -n "$child" ] && { kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null; }
    rm -rf "$LOCK"
}
trap 'release; exit 130' INT TERM
trap release EXIT

# ── Wait for room to spare ───────────────────────────────────────────────────
announced=0
while :; do
    free=$(free_megabytes)
    load=$(one_minute_load)
    if [ -z "$free" ] || [ -z "$load" ]; then
        echo "heavy: this machine reports neither free memory nor load — running unmeasured" >&2
        break
    fi
    if [ "$(at_least "$free" "$FREE_FLOOR_MB")" = 1 ] &&
       [ "$(at_most "$load" "$LOAD_CEILING")" = 1 ]; then
        break
    fi
    [ "$announced" -eq 0 ] &&
        echo "heavy: holding off — ${free}MB free, load $load (wants ${FREE_FLOOR_MB}MB and $LOAD_CEILING)" >&2
    announced=1
    sleep 5
done

# ── Run it, watched ──────────────────────────────────────────────────────────
echo "heavy: $WHO starts (${free}MB free, load $load)" >&2
# Job control puts the child in its OWN process group, so the watchdog can
# signal the whole tree. Signalling the direct child alone left the browsers
# and workers it had forked — which are the very things the ceiling exists to
# stop — running after the rescue said it had stopped them.
set -m
"$@" &
child=$!
set +m

# The watchdog samples memory every 15 s, but it notices the child finishing
# within a second: a wrapper that slept a fixed 15 s before looking would tax
# every quick command with a tail nobody would accept, and the tax is what
# makes a rule get bypassed.
strikes=0
ticks=0
while kill -0 "$child" 2>/dev/null; do
    sleep 1
    ticks=$((ticks + 1))
    [ "$((ticks % 15))" -eq 0 ] || continue
    kill -0 "$child" 2>/dev/null || break
    free=$(free_megabytes)
    [ -z "$free" ] && continue
    if [ "$(at_least "$free" "$HARD_FLOOR_MB")" = 0 ]; then
        strikes=$((strikes + 1))
        echo "heavy: ${free}MB free — strike $strikes of $HARD_STRIKES" >&2
        if [ "$strikes" -ge "$HARD_STRIKES" ]; then
            echo "heavy: STOPPING $WHO's run — the machine is out of room" >&2
            kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null
            sleep 5
            kill -KILL -"$child" 2>/dev/null || kill -KILL "$child" 2>/dev/null
            wait "$child" 2>/dev/null
            exit 75
        fi
    else
        strikes=0
    fi
done

wait "$child"
status=$?
echo "heavy: $WHO done (exit $status)" >&2
exit $status
