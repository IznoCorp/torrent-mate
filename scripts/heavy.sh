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
#   sh scripts/heavy.sh "<who>" <command...>
#
# It waits for whoever holds the lock, waits again until the machine has room
# to spare, runs the command under a watchdog, and releases the lock whatever
# happens. `HEAVY_LOCK` moves the lock, which is what `tests/scripts/test_heavy.py`
# uses to exercise every path here without touching the machine's real lock.

LOCK=${HEAVY_LOCK:-/private/tmp/tm-heavy/holder}
WHO=${1:?who is asking}
shift

# ── The ceilings, with margin ────────────────────────────────────────────────
# 4 GB free is three browser groups' worth of room for a run that will take
# one or two: the slack is deliberate. A load of 6 on 8 cores already means
# most cores are busy, so a heavy run waits for the machine to be genuinely
# quiet rather than merely survivable.
FREE_FLOOR_MB=${HEAVY_FREE_FLOOR_MB:-4096}
LOAD_CEILING=${HEAVY_LOAD_CEILING:-6}

# The watchdog's red line. Crossed for three samples in a row — 45 seconds, so
# a transient dip during a build's peak does not count — the wrapped command is
# stopped. It kills only what this script started; nothing else on the machine
# is ever touched, and the run can simply be launched again.
HARD_FLOOR_MB=${HEAVY_HARD_FLOOR_MB:-2048}
HARD_STRIKES=3

free_megabytes() {
    vm_stat | awk '
        /page size of/ { size = $8 }
        /Pages free/ { free = $3 }
        /Pages inactive/ { inactive = $3 }
        END { gsub(/\./, "", free); gsub(/\./, "", inactive);
              print int((free + inactive) * size / 1048576) }'
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
