#!/bin/sh
# The machine's budget for heavy runs on IznoServer.
#
# USE. Wrap anything that starts browsers, builds, or a parallel test run:
#
#   sh scripts/heavy.sh [--class browser|rule|test|build] "<who>" <command...>
#   sh scripts/heavy.sh --held      # prints the runs admitted, or « free » (exit 1)
#   sh scripts/heavy.sh --budget    # prints the capacity, the reserves and what is left
#   sh scripts/heavy.sh --plex-decision <suspended|-> <latest|-> < sessions.xml
#                                   # the Plex loop's decision, for the tests
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
# PLEX IS FOLLOWED ON ITS OWN SIGNAL, NOT A CALIBRATED SHARE (2026-10-01).
# Nobody has the time to measure what a transcode costs under rising load;
# Plex says itself whether it keeps up. Each `<TranscodeSession>` of
# `/status/sessions` carries a `speed` (1 is real time) and `throttled="1"`
# when Plex is ahead and brakes itself. No session holds nothing, a direct
# play 0.3 core, a transcode 1 core at its start; then, while a transcode that
# is not braking runs under PLEX_HOLD_SPEED, no new run is admitted, and under
# PLEX_SUSPEND_SPEED the most recent run this script admitted is stopped
# (SIGSTOP) until the speed is back above PLEX_HOLD_SPEED, then continued
# (SIGCONT). One run is stopped at a time. Each run's own watcher decides and
# acts only on its own run: nothing this script did not launch is touched.
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
# Every line also goes to a persistent log, `~/Library/Logs/heavy.log`
# (`HEAVY_LOG`), dated and signed with the script's pid, so an audit reads what
# was admitted, refused, stopped and killed after the caller's terminal is gone
# (B-702); past HEAVY_LOG_MAX_BYTES it is moved to `heavy.log.1`.
#
# THE RUN IS OWNED WHOLE (B-700). A descendant that leaves the run's process
# group — a double fork plus `setsid`, the way Playwright detaches its browsers
# and the way CPU burners re-parent to 1 — never hears a signal sent to the
# group. The command runs with a tag in its environment that every descendant
# inherits (`HEAVY_RUN_<pid>=<second asked>`); the watcher records, every
# GUARD_SECONDS, every process of the group, of the tree or carrying the tag,
# with its start time; when the run ends, is interrupted or is stopped, the
# group and every recorded process still alive (same pid, same start time:
# never a pid reused by someone else) are stopped, terminated, then killed.
#
# WHAT WAS ADMITTED IS WATCHED (B-701). An admission is one look; the incident
# of 2026-10-05 was a `browser` run that started eight browsers and eight CPU
# burners after it was admitted. Every GUARD_SECONDS the watcher counts the
# run's browsers (a browser process whose parent is not one) and its CPU; a run
# beyond its class — more browsers than CLASS_MAX_BROWSERS, or more CPU than
# CPU_LIMIT_PERCENT — for GUARD_STRIKES looks in a row is stopped (SIGSTOP),
# logged, then killed whole.
#
# THE PLEX TOKEN reaches curl on its standard input, never on a command line,
# in a file or in a line printed: it opens the operator's Plex account.

HOME_DIR=${HEAVY_HOME:-/private/tmp/tm-heavy}
QUEUE="$HOME_DIR/queue"
RUNNING="$HOME_DIR/running"
SUSPENDED="$HOME_DIR/suspended"
ADMIT="$HOME_DIR/admit"

CAPACITY_CORES=${HEAVY_CAPACITY_CORES:-8}
MACOS_RESERVE_CORES=1
# What a transcode holds at its start; its speed says the rest.
PLEX_TRANSCODE_START_CORES=1
PLEX_DIRECT_CORES=0.3
# Under this speed a transcode holds new runs; a stopped run resumes only
# above it.
PLEX_HOLD_SPEED=1.5
# Under this speed a transcode stops the most recent run of this script's.
PLEX_SUSPEND_SPEED=1.1
PARSEC_SESSION_CORES=1
QBIT_DOWNLOAD_CORES=0.5
# qBittorrent downloads when more than this comes in per second.
QBIT_DOWNLOAD_BYTES_PER_SECOND=1048576
# A Parsec session encodes the screen: VideoToolbox's encoder above this % CPU.
PARSEC_ENCODER_PERCENT=1
PLEX_URL=${HEAVY_PLEX_URL:-http://127.0.0.1:32400/status/sessions}

# How often a run's watcher looks at the memory and at Plex, in seconds.
WATCH_SECONDS=${HEAVY_WATCH_SECONDS:-15}
# How often it records the run's processes and weighs them against the class,
# and how many looks in a row beyond the class stop the run: 30 s.
GUARD_SECONDS=${HEAVY_GUARD_SECONDS:-3}
GUARD_STRIKES=${HEAVY_GUARD_STRIKES:-10}
# A run may burn this many times its declared cost, never more than the
# machine's capacity less two cores.
CPU_COST_FACTOR=4
CPU_HEADROOM_CORES=2

LOG_FILE=${HEAVY_LOG:-$HOME/Library/Logs/heavy.log}
LOG_MAX_BYTES=${HEAVY_LOG_MAX_BYTES:-1048576}

export LC_ALL=C

# The persistent log's line; the file is rotated once past its size. A log
# that cannot be written never stops a run.
log_line() {
    mkdir -p "${LOG_FILE%/*}" 2>/dev/null
    if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE" | tr -d ' ')" -ge "$LOG_MAX_BYTES" ]; then
        mv -f "$LOG_FILE" "$LOG_FILE.1" 2>/dev/null
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') heavy[$$] $*" >> "$LOG_FILE" 2>/dev/null
}

say() {
    echo "heavy: $(date '+%H:%M:%S') $*" >&2
    log_line "$*"
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

# Sets plex_cores, plex_said and plex_status (the answer, for the speed loop).
# Plex not running holds nothing; a Plex that answers something unreadable is
# held at one transcode, the safe guess.
plex_reserve() {
    token=$(defaults read com.plexapp.plexmediaserver PlexOnlineToken 2>/dev/null || true)
    status=$(printf 'X-Plex-Token: %s\nAccept: application/xml\n' "$token" |
        curl -s --connect-timeout 2 --max-time 5 -H @- "$PLEX_URL" 2>/dev/null)
    reached=$?
    token=""
    plex_status=$status
    if [ "$reached" -eq 7 ]; then
        plex_cores=0
        plex_said="0 (not running)"
        return
    fi
    case "$status" in
        *"<MediaContainer"*) ;;
        *)
            plex_cores=$PLEX_TRANSCODE_START_CORES
            plex_said="$plex_cores (unreadable: held as one transcode)"
            return
            ;;
    esac
    sessions=$(printf '%s' "$status" | grep -o '<Player ' | wc -l | tr -d ' ')
    transcoded=$(printf '%s' "$status" | grep -o '<TranscodeSession [^>]*videoDecision="transcode"' | wc -l | tr -d ' ')
    direct=$((sessions - transcoded))
    [ "$direct" -lt 0 ] && direct=0
    plex_cores=$(add "$(multiply "$transcoded" "$PLEX_TRANSCODE_START_CORES")" "$(multiply "$direct" "$PLEX_DIRECT_CORES")")
    plex_said="$plex_cores ($transcoded transcoded, $direct direct)"
}

# The slowest speed among the transcodes that must keep up, read from a
# `/status/sessions` answer on stdin; nothing when there is none. A transcode
# braking itself (throttled) is ahead, a finished one (complete) needs nothing,
# one with no speed yet has not said.
plex_slowest() {
    awk '
        function attribute(element, name) {
            if (match(element, "[ \t]" name "=\"[^\"]*\""))
                return substr(element, RSTART + length(name) + 3, RLENGTH - length(name) - 4)
            return ""
        }
        { answer = answer $0 " " }
        END {
            count = split(answer, elements, "<")
            for (i = 1; i <= count; i++) {
                if (elements[i] !~ /^TranscodeSession[ \t\/>]/) continue
                if (attribute(elements[i], "throttled") == "1") continue
                if (attribute(elements[i], "complete") == "1") continue
                speed = attribute(elements[i], "speed")
                if (speed == "") continue
                if (slowest == "" || speed + 0 < slowest + 0) slowest = speed
            }
            if (slowest != "") printf "%g\n", slowest
        }'
}

# THE PLEX LOOP'S DECISION, pure: a `/status/sessions` answer on stdin, the run
# already stopped ($1) and the most recent run still running ($2), "" or "-"
# for none. Prints admit, hold, suspend <run> or resume <run>.
plex_decision() {
    stopped=${1#-}
    latest=${2#-}
    slowest=$(plex_slowest)
    if [ -n "$stopped" ]; then
        if [ -z "$slowest" ] || [ "$(at_least "$PLEX_HOLD_SPEED" "$slowest")" = 0 ]; then
            echo "resume $stopped"
        else
            echo hold
        fi
    elif [ -z "$slowest" ] || [ "$(at_least "$slowest" "$PLEX_HOLD_SPEED")" = 1 ]; then
        echo admit
    elif [ -n "$latest" ] && [ "$(at_least "$slowest" "$PLEX_SUSPEND_SPEED")" = 0 ]; then
        echo "suspend $latest"
    else
        echo hold
    fi
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

# Its loop variables are not `entry` nor `marker`: those name this run's own.
# Sets admitted_cores, served_copy_holder, stopped_run (the run the Plex loop
# stopped) and latest_run (the most recent admitted run still running);
# removes the entries of runs gone.
admitted() {
    admitted_cores=0
    served_copy_holder=""
    stopped_run=""
    latest_run=""
    latest_since=-1
    for stop in "$SUSPENDED"/*; do
        [ -f "$stop" ] || continue
        if kill -0 "${stop##*/}" 2>/dev/null; then
            stopped_run=${stop##*/}
        else
            rm -f "$stop"
        fi
    done
    for other in "$RUNNING"/*; do
        [ -f "$other" ] || continue
        if ! kill -0 "${other##*/}" 2>/dev/null; then
            rm -f "$other"
            continue
        fi
        admitted_cores=$(add "$admitted_cores" "$(sed -n 3p "$other")")
        since=$(sed -n 4p "$other")
        if [ "${other##*/}" != "$stopped_run" ] && [ "${since:-0}" -ge "$latest_since" ]; then
            latest_since=${since:-0}
            latest_run=${other##*/}
        fi
        case "$(sed -n 2p "$other")" in
            browser|rule) served_copy_holder=$(sed -n 1p "$other") ;;
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

if [ "${1:-}" = "--plex-decision" ]; then
    plex_decision "${2:-}" "${3:-}"
    exit 0
fi

if [ "${1:-}" = "--held" ]; then
    admitted
    found=1
    for other in "$RUNNING"/*; do
        [ -f "$other" ] || continue
        echo "$(sed -n 1p "$other") ($(sed -n 2p "$other"), $(sed -n 3p "$other") cores)"
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
    echo "plex: slowest transcode $(printf '%s' "$plex_status" | plex_slowest | grep . || echo none), $(printf '%s' "$plex_status" | plex_decision "$stopped_run" "$latest_run")"
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
# `pytest -n 2` about 2, a build about 3. And the browsers (main executables,
# as `weigh` counts them) a class may hold at once before the watcher stops it:
# 6 for a `browser` or a `rule` run (a harness run's rules side by side, a rule
# may hold Chromium and WebKit), 4 for a `test` run (one per worker, with room),
# 2 for a `build` (a build starts none; two is a margin, not a budget).
case "$RUN_CLASS" in
    browser) CLASS_COST=1.5; CLASS_FLOOR_MB=4096; CLASS_MAX_BROWSERS=6 ;;
    rule)    CLASS_COST=1.5; CLASS_FLOOR_MB=2560; CLASS_MAX_BROWSERS=6 ;;
    test)    CLASS_COST=2;   CLASS_FLOOR_MB=3072; CLASS_MAX_BROWSERS=4 ;;
    build)   CLASS_COST=3;   CLASS_FLOOR_MB=3072; CLASS_MAX_BROWSERS=2 ;;
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
MAX_BROWSERS=${HEAVY_MAX_BROWSERS:-$CLASS_MAX_BROWSERS}
CPU_LIMIT_PERCENT=${HEAVY_CPU_LIMIT_PERCENT:-$(awk -v cost="$COST" -v factor="$CPU_COST_FACTOR" \
    -v capacity="$CAPACITY_CORES" -v headroom="$CPU_HEADROOM_CORES" 'BEGIN {
        limit = cost * factor; if (limit > capacity - headroom) limit = capacity - headroom
        printf "%d", limit * 100 }')}

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
    case "$(printf '%s' "$plex_status" | plex_decision "$stopped_run" "$latest_run")" in
        admit) ;;
        *)
            if [ -n "$stopped_run" ]; then
                refuse plex "a run is stopped for Plex until its transcodes are back above $PLEX_HOLD_SPEED"
            else
                refuse plex "Plex transcodes at $(printf '%s' "$plex_status" | plex_slowest), under $PLEX_HOLD_SPEED"
            fi
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

marker="$SUSPENDED/$$"
tree="$HOME_DIR/tree/$$"
RUN_TAG="HEAVY_RUN_$$=$ASKED"
child=""

# --- The run's processes (B-700, B-701) --------------------------------------

# The machine's process table: pid, parent, group, % CPU, command.
real_table() {
    ps -Ao pid=,ppid=,pgid=,pcpu=,comm= 2>/dev/null
}

# The table the watcher weighs: the machine's, or the tests' fake one. It only
# ever COUNTS; what is signalled is read from the machine's table alone.
weighed_table() {
    if [ -n "${HEAVY_PS_TABLE:-}" ]; then
        cat "$HEAVY_PS_TABLE" 2>/dev/null
        return
    fi
    real_table
}

# The pids whose environment carries this run's tag.
tagged_pids() {
    if [ -r /proc/self/environ ]; then
        for environ in /proc/[0-9]*/environ; do
            if tr '\0' '\n' < "$environ" 2>/dev/null | grep -qx "$RUN_TAG"; then
                tagged=${environ#/proc/}
                echo "${tagged%/environ}"
            fi
        done
    else
        ps -E -ww -Ao pid=,command= 2>/dev/null |
            awk -v tag="$RUN_TAG" '{ for (i = 2; i <= NF; i++) if ($i == tag) { print $1; break } }'
    fi
}

# The rows of a table on stdin that belong to the run: its leader ($1), its
# group, the pids listed in $2, and every descendant of those. Never this
# script nor pid 1, nor a service the run started — a PM2 daemon (`pm2 start`
# from a run hands it the run's tag), Plex, Parsec, qBittorrent — nor anything
# under one: weighed and reaped with the run, it would take the machine's
# services down. The guard (`scripts/machine_guard.py`) knows them alike.
members_of() {
    awk -v root="$1" -v listed="$2" -v me="$$" '
        BEGIN { count = split(listed, pids, " "); for (i = 1; i <= count; i++) wanted[pids[i]] = 1 }
        $1 == me || $1 == 1 { next }
        {
            row[$1] = $0
            parent[$1] = $2
            name = $5
            for (i = 6; i <= NF; i++) name = name " " $i
            if (name ~ /Plex|parsecd|Parsec\.app|qBittorrent|qbittorrent|^PM2 v[0-9.]+: God Daemon/) service[$1] = 1
            if ($1 == root || $3 == root || ($1 in wanted)) member[$1] = 1
        }
        END {
            do {
                grew = 0
                for (pid in parent)
                    if (!(pid in member) && (parent[pid] in member)) { member[pid] = 1; grew = 1 }
            } while (grew)
            for (pid in member) {
                if (!(pid in row)) continue
                # A service, or a descendant of one, is never the run.
                kept = 1
                for (up = pid; up in parent && hops < 64; up = parent[up]) {
                    hops++
                    if (up in service) { kept = 0; break }
                }
                hops = 0
                if (kept) print row[pid]
            }
        }'
}

# The pids recorded so far, on one line.
recorded_pids() {
    cut -d' ' -f1 "$tree" 2>/dev/null | tr '\n' ' '
}

# Records every process of the run not yet recorded, with its start time. The
# descendants are sought under the recorded processes still alive under their
# start time only: a recorded pid now reused by a stranger brings no child in.
record_run() {
    known=$(recorded_pids)
    fresh=$(real_table | members_of "$child" "$(tagged_pids | tr '\n' ' ') $(recorded_alive | tr '\n' ' ')" |
        awk -v known=" $known " 'index(known, " " $1 " ") == 0 { print $1 }' | tr '\n' ',' | sed 's/,$//')
    [ -n "$fresh" ] && ps -o pid=,lstart= -p "$fresh" 2>/dev/null | awk '{ $1 = $1; print }' >> "$tree"
}

# The recorded processes still alive under the start time they were recorded
# with: a pid reused by another process is never one of them.
recorded_alive() {
    pids=$(recorded_pids | tr ' ' ',' | sed 's/,*$//')
    [ -n "$pids" ] || return 0
    ps -o pid=,lstart= -p "$pids" 2>/dev/null | awk '{ $1 = $1; print }' | grep -Fxf "$tree" | cut -d' ' -f1
}

# Signals the run's group and every recorded process still alive.
signal_run() {
    kill "-$1" -"$child" 2>/dev/null
    for pid in $(recorded_alive); do
        [ "$pid" = "$$" ] || kill "-$1" "$pid" 2>/dev/null
    done
}

# Stops, terminates, then kills the whole run; a stopped process keeps a TERM
# pending until it is continued. Says how many processes were still there.
reap_run() {
    [ -n "$child" ] || return 0
    record_run
    survivors=$(recorded_alive | wc -l | tr -d ' ')
    signal_run STOP
    signal_run TERM
    signal_run CONT
    waited=0
    while [ "$waited" -lt 3 ] && [ -n "$(recorded_alive)" ]; do
        sleep 1
        waited=$((waited + 1))
    done
    signal_run KILL
    child=""
    rm -f "$tree"
}

# How many browsers and how much % CPU the run's rows on stdin hold. A browser
# is a browser's MAIN executable whose parent is not one: never a Chrome
# helper (`… Helper (Renderer)`, a `--type=` process) nor a crashpad handler,
# which Chrome starts twice and re-parents to pid 1 with the run's tag.
weigh() {
    awk '
        {
            name = $5
            for (i = 6; i <= NF; i++) name = name " " $i
            parent[$1] = $2
            name = tolower(name)
            executable = name
            sub(/.*\//, "", executable)
            browser[$1] = (name ~ /chrom|firefox|webkit|minibrowser|headless.shell/ &&
                executable !~ /crashpad|helper/ && name !~ / --type=/)
            cpu += $4
        }
        END {
            for (pid in parent) if (browser[pid] && !browser[parent[pid]]) browsers++
            printf "%d %d\n", browsers, cpu
        }'
}

guard_strikes=0
# Records the run's processes and weighs them against its class; a run beyond
# it for GUARD_STRIKES looks in a row is stopped, then killed (exit 75).
watch_run() {
    record_run
    weight=$(weighed_table | members_of "$child" "$(recorded_alive | tr '\n' ' ')" | weigh)
    browsers=${weight% *}
    cpu=${weight#* }
    beyond=""
    if [ "$browsers" -gt "$MAX_BROWSERS" ]; then
        beyond="$browsers browsers, class $RUN_CLASS holds $MAX_BROWSERS at most"
    elif [ "$cpu" -gt "$CPU_LIMIT_PERCENT" ]; then
        beyond="${cpu}% CPU, class $RUN_CLASS burns ${CPU_LIMIT_PERCENT}% at most (declared $COST cores)"
    fi
    if [ -z "$beyond" ]; then
        guard_strikes=0
        return
    fi
    guard_strikes=$((guard_strikes + 1))
    say "$WHO's run is beyond its class — $beyond (look $guard_strikes of $GUARD_STRIKES)"
    [ "$guard_strikes" -ge "$GUARD_STRIKES" ] || return
    signal_run STOP
    say "STOPPED $WHO's run — $beyond"
    held=$(recorded_alive | wc -l | tr -d ' ')
    reap_run
    say "KILLED $WHO's run — $held processes"
    exit 75
}

release() {
    reap_run
    rm -f "$ticket" "$entry" "$marker"
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
        printf '%s\n%s\n%s\n%s\n' "$WHO" "$RUN_CLASS" "$COST" "$(date +%s)" > "$entry"
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
# stop the whole tree (browsers, workers), not only the direct child; the tag
# finds the descendants that leave the group.
mkdir -p "${tree%/*}" 2>/dev/null
: > "$tree"
set -m
env "$RUN_TAG" "$@" &
child=$!
set +m

# The Plex loop, for this run only: every watcher reads the same decision, and
# only the run it names acts, on its own process group.
follow_plex() {
    mkdir -p "$SUSPENDED" 2>/dev/null || return
    plex_reserve
    admitted
    decision=$(printf '%s' "$plex_status" | plex_decision "$stopped_run" "$latest_run")
    case "$decision" in
        "suspend $$")
            : > "$marker"
            kill -STOP -"$child" 2>/dev/null || kill -STOP "$child" 2>/dev/null
            say "suspending $WHO's run — Plex transcodes at $(printf '%s' "$plex_status" | plex_slowest), under $PLEX_SUSPEND_SPEED"
            ;;
        "resume $$")
            kill -CONT -"$child" 2>/dev/null || kill -CONT "$child" 2>/dev/null
            rm -f "$marker"
            say "resuming $WHO's run — Plex keeps up again"
            ;;
    esac
}

strikes=0
ticks=0
while kill -0 "$child" 2>/dev/null; do
    sleep 1
    ticks=$((ticks + 1))
    [ "$((ticks % GUARD_SECONDS))" -eq 0 ] && watch_run
    [ "$((ticks % WATCH_SECONDS))" -eq 0 ] || continue
    follow_plex
    free=$(free_megabytes)
    [ -z "$free" ] && continue
    if [ "$(at_least "$free" "$HARD_FLOOR_MB")" = 0 ]; then
        strikes=$((strikes + 1))
        say "${free}MB free — strike $strikes of $HARD_STRIKES"
        if [ "$strikes" -ge "$HARD_STRIKES" ]; then
            say "STOPPING $WHO's run — the machine is out of room"
            reap_run
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
