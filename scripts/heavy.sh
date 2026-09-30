#!/bin/sh
# A machine-wide lock for heavy runs on IznoServer: one heavy run at a time.
#
# USE. Wrap anything that starts browsers, builds, or a parallel test run:
#
#   sh scripts/heavy.sh [--class browser|test|rule] "<who>" <command...>
#   sh scripts/heavy.sh --held      # prints the holder, or « free » (exit 1)
#
# It waits until the machine has room (free memory above the class's floor,
# load under its ceiling), then for whoever holds the lock, runs the command
# under a memory watchdog, and releases the lock whatever happens. A run that
# drops the machine under HARD_FLOOR_MB for 45 s is stopped: only what this
# script started is ever touched. `HEAVY_LOCK` moves the lock.

LOCK=${HEAVY_LOCK:-/private/tmp/tm-heavy/holder}

# The lock is a directory; `who` is written only by a holder.
if [ "${1:-}" = "--held" ]; then
    if [ -d "$LOCK" ]; then
        cat "$LOCK/who" 2>/dev/null || echo "someone"
        exit 0
    fi
    echo "free"
    exit 1
fi

RUN_CLASS=""
if [ "${1:-}" = "--class" ]; then
    RUN_CLASS=${2:?--class needs a name: browser, test or rule}
    shift 2
fi
WHO=${1:?who is asking}
shift

case "$RUN_CLASS" in
    browser|"") CLASS_FLOOR_MB=4096; CLASS_LOAD_CEILING=6 ;;
    test)       CLASS_FLOOR_MB=3072; CLASS_LOAD_CEILING=6 ;;
    rule)       CLASS_FLOOR_MB=2560; CLASS_LOAD_CEILING=10 ;;
    *)
        echo "heavy: unknown class '$RUN_CLASS' — say browser, test or rule" >&2
        exit 64
        ;;
esac
FREE_FLOOR_MB=${HEAVY_FREE_FLOOR_MB:-$CLASS_FLOOR_MB}
LOAD_CEILING=${HEAVY_LOAD_CEILING:-$CLASS_LOAD_CEILING}
HARD_FLOOR_MB=${HEAVY_HARD_FLOOR_MB:-2048}
HARD_STRIKES=3

# Reclaimable memory: free + inactive + speculative pages. Wired and
# compressed memory are not coming back, so they never count as room.
free_megabytes() {
    if command -v vm_stat > /dev/null 2>&1; then
        vm_stat | awk '
            /page size of/ { size = $8 }
            /Pages free/ { free = $3 }
            /Pages inactive/ { inactive = $3 }
            /Pages speculative/ { speculative = $3 }
            END { gsub(/\./, "", free); gsub(/\./, "", inactive); gsub(/\./, "", speculative);
                  if (size && (free + inactive + speculative) > 0)
                      print int((free + inactive + speculative) * size / 1048576) }'
    elif [ -r /proc/meminfo ]; then
        awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo
    fi
}

one_minute_load() {
    uptime | sed 's/.*load averages*: *//' | awk '{ print $1 }' |
        tr ',' '.' | sed 's/\.$//'
}

at_least() {
    awk -v have="$1" -v want="$2" 'BEGIN { print (have >= want) ? 1 : 0 }'
}

at_most() {
    awk -v have="$1" -v want="$2" 'BEGIN { print (have <= want) ? 1 : 0 }'
}

# 0 when the run fits, 1 when it does not, 2 when the machine reports nothing.
room_fits() {
    free=$(free_megabytes)
    load=$(one_minute_load)
    if [ -z "$free" ] || [ -z "$load" ]; then
        return 2
    fi
    [ "$(at_least "$free" "$FREE_FLOOR_MB")" = 1 ] && [ "$(at_most "$load" "$LOAD_CEILING")" = 1 ]
}

echo "heavy: wants ${FREE_FLOOR_MB}MB free and load ${LOAD_CEILING} or below (class ${RUN_CLASS:-none})" >&2

parent=$(dirname "$LOCK")
mkdir -p "$parent" 2>/dev/null || true
if [ ! -d "$parent" ] || [ ! -w "$parent" ]; then
    echo "heavy: cannot use $parent as the lock's home — running unlocked" >&2
    exec "$@"
fi

child=""
release() {
    [ -n "$child" ] && { kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null; }
    rm -rf "$LOCK"
}

# Wait for room, then for the lock; the lock is taken only by a run about to
# start, and given back if the room moved while it waited.
while :; do
    room_announced=0
    while :; do
        room_fits
        rc=$?
        [ "$rc" -eq 2 ] &&
            echo "heavy: this machine reports neither free memory nor load — running unmeasured" >&2
        [ "$rc" -ne 1 ] && break
        [ "$room_announced" -eq 0 ] &&
            echo "heavy: holding off — ${free}MB free, load $load (wants ${FREE_FLOOR_MB}MB and $LOAD_CEILING)" >&2
        room_announced=1
        sleep 5
    done

    lock_announced=0
    while :; do
        if mkdir "$LOCK" 2>/dev/null; then
            echo "$WHO" > "$LOCK/who"
            echo "$$" > "$LOCK/pid"
            trap 'release; exit 130' INT TERM
            trap release EXIT
            break
        fi
        holder=$(cat "$LOCK/who" 2>/dev/null || echo "someone")
        holder_pid=$(cat "$LOCK/pid" 2>/dev/null || true)
        # A lock whose holder process is gone is stale, whatever its age.
        if [ -n "$holder_pid" ] && ! kill -0 "$holder_pid" 2>/dev/null; then
            echo "heavy: breaking a stale lock held by $holder (pid $holder_pid is gone)" >&2
            rm -rf "$LOCK"
            continue
        fi
        [ "$lock_announced" -eq 0 ] && echo "heavy: waiting for $holder to finish" >&2
        lock_announced=1
        sleep 3
    done

    room_fits
    if [ "$?" -eq 1 ]; then
        echo "heavy: ${free}MB free, load $load right after taking the lock — giving it back" >&2
        trap - INT TERM EXIT
        rm -rf "$LOCK"
        continue
    fi
    break
done

echo "heavy: $WHO starts (${free}MB free, load $load)" >&2
# Job control puts the child in its own process group, so the watchdog can
# stop the whole tree (browsers, workers), not only the direct child.
set -m
"$@" &
child=$!
set +m

strikes=0
ticks=0
while kill -0 "$child" 2>/dev/null; do
    sleep 1
    ticks=$((ticks + 1))
    [ "$((ticks % 15))" -eq 0 ] || continue
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
