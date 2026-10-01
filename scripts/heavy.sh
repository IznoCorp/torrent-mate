#!/bin/sh
# The machine's budget for heavy runs on IznoServer.
#
# USE. Wrap anything that starts browsers, builds, or a parallel test run:
#
#   sh scripts/heavy.sh [--class browser|rule|test|build] "<who>" <command...>
#   sh scripts/heavy.sh --held      # prints the runs admitted, or « free » (exit 1)
#   sh scripts/heavy.sh --budget    # prints the capacity, the reserves and what is left
#
# A BUDGET, NOT A LOCK (2026-10-01). One lock and a load ceiling of 6 ran one
# heavy run at a time whatever the machine had left, and still let a run start
# over a Plex transcode. The machine has CAPACITY_CORES; the services that
# serve someone hold a reserve only while they serve; each class declares what
# it costs; several runs coexist while the sum fits. A run is admitted when
#
#   capacity − reserves − the admitted runs' costs ≥ its cost   (declared)
#   the idle cores measured by `top` ≥ its cost                 (measured)
#   the memory pressure is normal, the free memory above the class's floor,
#   and the one-minute load under capacity − its cost
#
# and, for the classes that use the served copy (`browser`, `rule`), when no
# other such run is admitted: there is one served copy per machine.
#
# A run that drops the machine under HARD_FLOOR_MB for 45 s is stopped: only
# what this script started is ever touched. `HEAVY_HOME` moves the script's
# directory; every signal can be fixed by a variable, for the tests.
#
# WAITERS ARE SERVED IN THE ORDER THEY ASKED (B-472). Each one writes a ticket
# in `queue/`, named by the second it asked and its pid, and only the oldest
# ticket whose process is alive may be admitted.
#
# EVERY LINE IS TIMED, and the start says how long the run waited (B-495).
#
# THE PLEX TOKEN reaches curl on its standard input, never on a command line,
# in a file or in a line printed: it opens the operator's Plex account.

HOME_DIR=${HEAVY_HOME:-/private/tmp/tm-heavy}
QUEUE="$HOME_DIR/queue"
RUNNING="$HOME_DIR/running"
ADMIT="$HOME_DIR/admit"

CAPACITY_CORES=${HEAVY_CAPACITY_CORES:-8}
MACOS_RESERVE_CORES=1
# CALIBRATION PENDING: the operator and the auditor measure a transcoded film
# under rising load at this lot's end, and their figure replaces this one.
PLEX_TRANSCODE_CORES=2
PLEX_DIRECT_CORES=0.3
PARSEC_SESSION_CORES=1
QBIT_DOWNLOAD_CORES=0.5
# qBittorrent downloads when more than this comes in per second.
QBIT_DOWNLOAD_BYTES_PER_SECOND=1048576
# A Parsec session encodes the screen: VideoToolbox's encoder above this % CPU.
PARSEC_ENCODER_PERCENT=1
PLEX_URL=${HEAVY_PLEX_URL:-http://127.0.0.1:32400/status/sessions}

export LC_ALL=C

say() {
    echo "heavy: $(date '+%H:%M:%S') $*" >&2
}

add() {
    awk -v a="$1" -v b="$2" 'BEGIN { printf "%g", a + b }'
}

multiply() {
    awk -v a="$1" -v b="$2" 'BEGIN { printf "%g", a * b }'
}

at_least() {
    awk -v have="$1" -v want="$2" 'BEGIN { print (have >= want) ? 1 : 0 }'
}

# --- What the services that serve someone hold -------------------------------

# Sets plex_cores and plex_said. Plex not running holds nothing; a Plex that
# answers something unreadable is held at one transcode, the safe guess.
plex_reserve() {
    token=$(defaults read com.plexapp.plexmediaserver PlexOnlineToken 2>/dev/null || true)
    status=$(printf 'X-Plex-Token: %s\nAccept: application/xml\n' "$token" |
        curl -s --connect-timeout 2 --max-time 5 -H @- "$PLEX_URL" 2>/dev/null)
    reached=$?
    token=""
    if [ "$reached" -eq 7 ]; then
        plex_cores=0
        plex_said="0 (not running)"
        return
    fi
    case "$status" in
        *"<MediaContainer"*) ;;
        *)
            plex_cores=$PLEX_TRANSCODE_CORES
            plex_said="$plex_cores (unreadable: held as one transcode)"
            return
            ;;
    esac
    sessions=$(printf '%s' "$status" | grep -o '<Player ' | wc -l | tr -d ' ')
    transcoded=$(printf '%s' "$status" | grep -o '<TranscodeSession [^>]*videoDecision="transcode"' | wc -l | tr -d ' ')
    direct=$((sessions - transcoded))
    [ "$direct" -lt 0 ] && direct=0
    plex_cores=$(add "$(multiply "$transcoded" "$PLEX_TRANSCODE_CORES")" "$(multiply "$direct" "$PLEX_DIRECT_CORES")")
    plex_said="$plex_cores ($transcoded transcoded, $direct direct)"
}

parsec_active() {
    if [ -n "${HEAVY_PARSEC:-}" ]; then
        [ "$HEAVY_PARSEC" = 1 ]
        return
    fi
    encoder=$(ps -Ao pcpu,comm | awk '/VTEncoderXPCService$/ { print $1; exit }')
    [ -n "$encoder" ] && [ "$(at_least "$encoder" "$PARSEC_ENCODER_PERCENT")" = 1 ] && return 0
    parsecd=$(pgrep -f /Applications/Parsec.app/Contents/MacOS/parsecd 2>/dev/null | head -1)
    [ -n "$parsecd" ] && lsof -nP -a -p "$parsecd" -i UDP 2>/dev/null | grep -q -- '->'
}

qbit_downloading() {
    if [ -n "${HEAVY_QBIT:-}" ]; then
        [ "$HEAVY_QBIT" = 1 ]
        return
    fi
    qbit=$(pgrep -f /Applications/qBittorrent.app/Contents/MacOS/qbittorrent 2>/dev/null | head -1)
    [ -n "$qbit" ] || return 1
    incoming=$(nettop -P -L 2 -s 1 -d -x -J bytes_in -p "$qbit" 2>/dev/null |
        awk -F, 'NF > 1 && $2 ~ /^[0-9]+$/ { last = $2 } END { print last + 0 }')
    [ "$(at_least "$incoming" "$QBIT_DOWNLOAD_BYTES_PER_SECOND")" = 1 ]
}

# Sets reserved_cores and reserves_said.
reserves() {
    plex_reserve
    parsec_cores=0
    parsec_active && parsec_cores=$PARSEC_SESSION_CORES
    qbit_cores=0
    qbit_downloading && qbit_cores=$QBIT_DOWNLOAD_CORES
    reserved_cores=$(add "$(add "$MACOS_RESERVE_CORES" "$plex_cores")" "$(add "$parsec_cores" "$qbit_cores")")
    reserves_said="macOS $MACOS_RESERVE_CORES, plex $plex_said, parsec $parsec_cores, qbittorrent $qbit_cores"
}

# --- What the admitted runs hold ---------------------------------------------

# Sets admitted_cores and served_copy_holder; removes the entries of runs gone.
admitted() {
    admitted_cores=0
    served_copy_holder=""
    for entry in "$RUNNING"/*; do
        [ -f "$entry" ] || continue
        if ! kill -0 "${entry##*/}" 2>/dev/null; then
            rm -f "$entry"
            continue
        fi
        admitted_cores=$(add "$admitted_cores" "$(sed -n 3p "$entry")")
        case "$(sed -n 2p "$entry")" in
            browser|rule) served_copy_holder=$(sed -n 1p "$entry") ;;
        esac
    done
    # A run under the previous script, from a checkout older than the budget,
    # holds its lock directory instead: it counts as a browser run, until no
    # checkout runs that script.
    legacy="$HOME_DIR/holder"
    if [ -d "$legacy" ] && kill -0 "$(cat "$legacy/pid" 2>/dev/null || echo 0)" 2>/dev/null; then
        admitted_cores=$(add "$admitted_cores" 1.5)
        served_copy_holder=$(cat "$legacy/who" 2>/dev/null || echo "an older heavy.sh")
    fi
}

# --- What the machine measures -----------------------------------------------

idle_cores() {
    if [ -n "${HEAVY_IDLE_CORES:-}" ]; then
        echo "$HEAVY_IDLE_CORES"
        return
    fi
    top -l 2 -n 0 -s 1 2>/dev/null | awk -v cores="$CAPACITY_CORES" '
        /CPU usage/ { for (i = 1; i <= NF; i++) if ($i == "idle") idle = $(i - 1) }
        END { sub(/%/, "", idle); if (idle != "") printf "%g", idle * cores / 100 }'
}

# normal, warn or critical: the kernel's level, the one `memory_pressure` reports.
pressure() {
    if [ -n "${HEAVY_PRESSURE:-}" ]; then
        echo "$HEAVY_PRESSURE"
        return
    fi
    case "$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null)" in
        1) echo normal ;;
        2) echo warn ;;
        4) echo critical ;;
        *) echo normal ;;
    esac
}

# Reclaimable memory: free + inactive + speculative pages. Wired and
# compressed memory are not coming back, so they never count as room.
free_megabytes() {
    if [ -n "${HEAVY_FREE_MB:-}" ]; then
        echo "$HEAVY_FREE_MB"
        return
    fi
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
    if [ -n "${HEAVY_LOAD:-}" ]; then
        echo "$HEAVY_LOAD"
        return
    fi
    uptime | sed 's/.*load averages*: *//' | awk '{ print $1 }' | tr ',' '.' | sed 's/\.$//'
}

if [ "${1:-}" = "--held" ]; then
    admitted
    found=1
    for entry in "$RUNNING"/*; do
        [ -f "$entry" ] || continue
        echo "$(sed -n 1p "$entry") ($(sed -n 2p "$entry"), $(sed -n 3p "$entry") cores)"
        found=0
    done
    [ "$found" -eq 0 ] && exit 0
    echo "free"
    exit 1
fi

if [ "${1:-}" = "--budget" ]; then
    admitted
    reserves
    echo "capacity $CAPACITY_CORES cores"
    echo "reserves: $reserves_said"
    echo "admitted runs: $admitted_cores"
    left=$(add "$CAPACITY_CORES" "-$(add "$reserved_cores" "$admitted_cores")")
    echo "free $left of $CAPACITY_CORES"
    exit 0
fi

RUN_CLASS="browser"
if [ "${1:-}" = "--class" ]; then
    RUN_CLASS=${2:?--class needs a name: browser, rule, test or build}
    shift 2
fi
WHO=${1:?who is asking}
shift

# Each class's cost in cores, measured: a harness run of two rules about 1.5,
# `pytest -n 2` about 2, a build about 3.
case "$RUN_CLASS" in
    browser) CLASS_COST=1.5; CLASS_FLOOR_MB=4096 ;;
    rule)    CLASS_COST=1.5; CLASS_FLOOR_MB=2560 ;;
    test)    CLASS_COST=2;   CLASS_FLOOR_MB=3072 ;;
    build)   CLASS_COST=3;   CLASS_FLOOR_MB=3072 ;;
    *)
        echo "heavy: unknown class '$RUN_CLASS' — say browser, rule, test or build" >&2
        exit 64
        ;;
esac

ASKED=$(date +%s)
COST=${HEAVY_COST:-$CLASS_COST}
FREE_FLOOR_MB=${HEAVY_FREE_FLOOR_MB:-$CLASS_FLOOR_MB}
LOAD_CEILING=${HEAVY_LOAD_CEILING:-$(add "$CAPACITY_CORES" "-$COST")}
HARD_FLOOR_MB=${HEAVY_HARD_FLOOR_MB:-2048}
HARD_STRIKES=3

# 0 when the run fits, 1 when it does not; `refusal` says why and `refused_by`
# names which signal, so a long wait is said once per reason.
room_fits() {
    admitted
    reserves
    left=$(add "$CAPACITY_CORES" "-$(add "$reserved_cores" "$admitted_cores")")
    idle=$(idle_cores)
    level=$(pressure)
    free=$(free_megabytes)
    load=$(one_minute_load)
    refusal=""
    refused_by=""
    refuse() {
        [ -z "$refused_by" ] && { refused_by=$1; refusal=$2; }
    }
    case "$RUN_CLASS" in
        browser|rule)
            [ -n "$served_copy_holder" ] && refuse copy "the served copy is $served_copy_holder's"
            ;;
    esac
    [ "$(at_least "$left" "$COST")" = 0 ] &&
        refuse budget "$left of $CAPACITY_CORES cores free, $RUN_CLASS needs $COST ($reserves_said; admitted $admitted_cores)"
    [ -n "$idle" ] && [ "$(at_least "$idle" "$COST")" = 0 ] &&
        refuse idle "$idle cores idle, $RUN_CLASS needs $COST"
    [ "$level" != normal ] && refuse pressure "memory pressure $level"
    [ -n "$free" ] && [ "$(at_least "$free" "$FREE_FLOOR_MB")" = 0 ] &&
        refuse memory "${free}MB free, wants $FREE_FLOOR_MB"
    [ -n "$load" ] && [ "$(at_least "$LOAD_CEILING" "$load")" = 0 ] &&
        refuse load "load $load, wants $LOAD_CEILING or below"
    [ -z "$refused_by" ]
}

say "wants $COST cores (class $RUN_CLASS), ${FREE_FLOOR_MB}MB free, normal memory pressure"

mkdir -p "$QUEUE" "$RUNNING" 2>/dev/null || true
if [ ! -d "$QUEUE" ] || [ ! -w "$QUEUE" ] || [ ! -d "$RUNNING" ] || [ ! -w "$RUNNING" ]; then
    say "cannot use $HOME_DIR as the budget's home — running unbudgeted"
    exec "$@"
fi

ticket="$QUEUE/$(printf '%012d.%08d' "$ASKED" "$$")"
entry="$RUNNING/$$"
echo "$WHO" > "$ticket"

child=""
release() {
    [ -n "$child" ] && { kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null; }
    rm -f "$ticket" "$entry"
    [ "$(cat "$ADMIT/pid" 2>/dev/null)" = "$$" ] && rm -rf "$ADMIT"
}
trap 'release; exit 130' INT TERM
trap release EXIT

# 0 when this run's ticket is the oldest one whose process is alive; a ticket
# whose process is gone is removed on the way.
my_turn() {
    for waiting in "$QUEUE"/*; do
        [ -f "$waiting" ] || continue
        waiter=$(expr "${waiting##*.}" + 0 2>/dev/null) || waiter=""
        if [ -z "$waiter" ] || ! kill -0 "$waiter" 2>/dev/null; then
            rm -f "$waiting"
            continue
        fi
        [ "$waiting" = "$ticket" ]
        return
    done
    return 0
}

# The admission is decided under a short mutex, so two runs never both count
# the same free cores.
take_admit() {
    while ! mkdir "$ADMIT" 2>/dev/null; do
        holder=$(cat "$ADMIT/pid" 2>/dev/null || true)
        if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
            rm -rf "$ADMIT"
            continue
        fi
        sleep 1
    done
    echo "$$" > "$ADMIT/pid"
}

turn_announced=0
room_said=""
while :; do
    if ! my_turn; then
        [ "$turn_announced" -eq 0 ] && say "waiting behind an older demand in $QUEUE"
        turn_announced=1
        sleep 3
        continue
    fi
    take_admit
    if room_fits; then
        printf '%s\n%s\n%s\n' "$WHO" "$RUN_CLASS" "$COST" > "$entry"
        rm -rf "$ADMIT"
        break
    fi
    rm -rf "$ADMIT"
    # Said when the reason changes, so a long wait stays readable.
    [ "$refused_by" != "$room_said" ] && say "holding off — $refusal"
    room_said=$refused_by
    sleep 5
done

rm -f "$ticket"
say "$WHO starts after $(( $(date +%s) - ASKED )) s waiting ($left of $CAPACITY_CORES cores free before it, ${free}MB free, load $load)"
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
        say "${free}MB free — strike $strikes of $HARD_STRIKES"
        if [ "$strikes" -ge "$HARD_STRIKES" ]; then
            say "STOPPING $WHO's run — the machine is out of room"
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
say "$WHO done (exit $status)"
exit $status
