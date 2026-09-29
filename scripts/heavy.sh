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
# It waits until the machine has room to spare, THEN waits for whoever holds
# the lock, re-reads room once the lock is its own (the reading may have moved
# meanwhile) and gives the lock straight back if it no longer fits, runs the
# command under a watchdog, and releases the lock whatever happens. The lock is
# held only by a run that is running or about to — never by one still waiting
# for room (auditor's order 71: a holder used to take the lock BEFORE waiting
# for room, so a run stuck on load held it for everyone behind it, including a
# run whose own class already fit). Once running, it also YIELDS TO PLEX
# (auditor's order 88): a run that starts clean can still starve a transcode
# minutes later, so the watchdog pauses (SIGSTOP) the whole wrapped tree for as
# long as Plex is transcoding under load, and resumes it (SIGCONT) rather than
# killing it — see PLEX_LOAD_CEILING below. `HEAVY_LOCK` moves the lock, which
# is what `tests/scripts/test_heavy.py` uses to exercise every path here
# without touching the machine's real lock.
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

# Plex is this machine's production service; a heavy run outranks nothing here
# except waiting for it (auditor's order 88, 2026-09-29 22:27: the operator's
# transcode starved at 0 % while a harness suite with no TM_HARNESS_JOBS took
# every core). Unlike the memory floor above, which STOPS the run for good, a
# run caught behind Plex is only PAUSED — SIGSTOP costs it nothing but time,
# and a run killed mid-suite has to start over.
#
# WHAT THIS DOES NOT READ: a Plex DIRECT-PLAY stream runs no transcoder at all
# (the client decodes its own file), so a heavy run shares the machine with one
# untouched — this guard only ever fires on a stream Plex itself had to
# transcode, which is the CPU-bound case a parallel run can actually starve.
PLEX_LOAD_CEILING=${HEAVY_PLEX_LOAD_CEILING:-12}
PLEX_LOAD_RESUME=${HEAVY_PLEX_LOAD_RESUME:-8}

# A SHORT run (class `rule` or `test`) does not wait behind a LONG one (class
# `browser`) — it pauses the browser holder's tree for the length of its own
# run instead (auditor's order 90 — the operator asked for the fan-out to be
# watched and the speed controlled). Capped: past this many seconds the holder
# is resumed anyway and the short run keeps going unprotected, exactly as it
# would have without this — a rule or a build is never LEFT stopping
# something else for good.
PREEMPT_CAP_SECONDS=${HEAVY_PREEMPT_CAP_SECONDS:-600}
# Overridable so a test can point this at a name nothing real ever answers to —
# the real Plex Transcoder can be genuinely running on the machine a test runs
# on, and a fixture sharing its exact name would be read as the real thing.
PLEX_PROCESS_PATTERN=${HEAVY_PLEX_PROCESS_PATTERN:-"Plex Transcoder"}

# True while a transcode is actually running — never while Plex merely sits
# idle. `pgrep -f` reads the full command line, which is how a plain `ps` on
# this host already spots it (the binary's own path names it).
plex_is_transcoding() {
    command -v pgrep > /dev/null 2>&1 || return 1
    pgrep -f "$PLEX_PROCESS_PATTERN" > /dev/null 2>&1
}

# Every pid reachable from $1 by descent, $1 included — a plain process-group
# signal misses a browser a driver launched detached (its own new group), and
# that is exactly the tree a suspend/resume pair here is answerable for. Used
# by the Plex guard AND by short-run preemption (order 90) — both pause a
# whole wrapped tree, never a lone pid.
heavy_process_tree() {
    queue="$1"
    seen=""
    while [ -n "$queue" ]; do
        pid=$(printf '%s\n' "$queue" | head -n1)
        queue=$(printf '%s\n' "$queue" | sed 1d)
        case " $seen " in
            *" $pid "*) continue ;;
        esac
        seen="$seen $pid"
        kids=$(pgrep -P "$pid" 2>/dev/null || true)
        [ -n "$kids" ] && queue="$queue
$kids"
    done
    printf '%s\n' $seen
}

# SIGSTOP/SIGCONT rather than TERM/KILL: this is a pause the run resumes from,
# not the hard floor's rescue. The group first (the common case), then every
# descendant found by walking the tree (the one that left it).
heavy_suspend_tree() {
    kill -STOP -"$1" 2>/dev/null || kill -STOP "$1" 2>/dev/null || true
    for pid in $(heavy_process_tree "$1"); do
        kill -STOP "$pid" 2>/dev/null || true
    done
}

heavy_resume_tree() {
    kill -CONT -"$1" 2>/dev/null || kill -CONT "$1" 2>/dev/null || true
    for pid in $(heavy_process_tree "$1"); do
        kill -CONT "$pid" 2>/dev/null || true
    done
}

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
            /Pages speculative/ { speculative = $3 }
            END { gsub(/\./, "", free); gsub(/\./, "", inactive); gsub(/\./, "", speculative);
                  if (size && (free + inactive + speculative) > 0)
                      print int((free + inactive + speculative) * size / 1048576) }'
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

# Sets `free` and `load` for the caller to log, and answers in its exit code:
# 0 room fits, 1 it does not, 2 the machine reports neither figure. Called both
# before the lock is taken and right after, so a reading that moved between the
# two never leaves the lock with a run that no longer fits.
room_fits() {
    free=$(free_megabytes)
    load=$(one_minute_load)
    if [ -z "$free" ] || [ -z "$load" ]; then
        return 2
    fi
    [ "$(at_least "$free" "$FREE_FLOOR_MB")" = 1 ] && [ "$(at_most "$load" "$LOAD_CEILING")" = 1 ]
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

# ── A short run preempts a browser-class holder, never waits behind it ───────
# (auditor's order 90.) `PREEMPT_LOCK` is its OWN mkdir-based lock, a sibling
# of `$LOCK` — never the same directory — so a SECOND short run queues behind
# the FIRST short run's preemption window, and never behind the (possibly very
# long) browser holder itself: THE DEADLOCK THIS AVOIDS. Only a `rule` or
# `test` class run ever reaches this; a `browser` or unclassed run falls
# straight through to the ordinary wait below, and is itself never preempted —
# only ever the one doing the preempting.
if [ "$RUN_CLASS" = "rule" ] || [ "$RUN_CLASS" = "test" ]; then
    PREEMPT_LOCK="${LOCK}-preempt"
    if [ -d "$LOCK" ] && [ "$(cat "$LOCK/class" 2>/dev/null)" = "browser" ]; then
        preempt_announced=0
        while ! mkdir "$PREEMPT_LOCK" 2>/dev/null; do
            # A sub-lock stuck past its own bound is a session that died mid-
            # preemption: age alone breaks it, exactly as the main lock is
            # broken on age when nothing else can tell a dead holder from a
            # slow one — this one has no pid file, so age is all it has.
            if [ -n "$(find "$PREEMPT_LOCK" -maxdepth 0 -mmin +2 2>/dev/null)" ]; then
                rm -rf "$PREEMPT_LOCK"
                continue
            fi
            [ "$preempt_announced" -eq 0 ] &&
                echo "heavy: $WHO queues behind another short run already preempting the browser holder" >&2
            preempt_announced=1
            sleep 1
        done
        trap 'rm -rf "$PREEMPT_LOCK"' EXIT

        # Re-read after taking the sub-lock: the browser holder may have
        # finished while this run waited for it.
        if [ -d "$LOCK" ] && [ "$(cat "$LOCK/class" 2>/dev/null)" = "browser" ]; then
            holder_child=$(cat "$LOCK/child_pid" 2>/dev/null || true)
            if [ -n "$holder_child" ] && kill -0 "$holder_child" 2>/dev/null; then
                holder_name=$(cat "$LOCK/who" 2>/dev/null || echo "the browser holder")
                echo "heavy: $WHO preempts $holder_name (pid $holder_child) — suspending its tree" >&2
                heavy_suspend_tree "$holder_child"
                preempt_started=$(date +%s)
                preempt_resumed=0

                set -m
                "$@" &
                preempt_child=$!
                set +m
                trap 'heavy_resume_tree "$holder_child"; kill -TERM -"$preempt_child" 2>/dev/null || kill -TERM "$preempt_child" 2>/dev/null; rm -rf "$PREEMPT_LOCK"; exit 130' INT TERM

                while kill -0 "$preempt_child" 2>/dev/null; do
                    sleep 1
                    if [ "$preempt_resumed" -eq 0 ] &&
                        [ "$(($(date +%s) - preempt_started))" -ge "$PREEMPT_CAP_SECONDS" ]; then
                        echo "heavy: $WHO past ${PREEMPT_CAP_SECONDS}s — resuming $holder_name early, waits as normal from here" >&2
                        heavy_resume_tree "$holder_child"
                        preempt_resumed=1
                    fi
                done
                wait "$preempt_child"
                preempt_status=$?
                if [ "$preempt_resumed" -eq 0 ]; then
                    echo "heavy: $WHO done — resuming $holder_name" >&2
                    heavy_resume_tree "$holder_child"
                fi
                trap - INT TERM EXIT
                rm -rf "$PREEMPT_LOCK"
                exit "$preempt_status"
            fi
        fi
        trap - EXIT
        rm -rf "$PREEMPT_LOCK"
    fi
fi

# Interrupted while it HOLDS the lock, the wrapper must take DOWN what it
# started, not merely let go: a run stopped by hand that leaves its browsers
# behind is the exact residue the ceiling exists to prevent. `child` is empty
# until the run begins, so the same handler serves both phases. The trap is
# armed only from the moment the lock is actually taken below, and disarmed
# again the moment it is given back on purpose — armed while merely waiting
# (for room or for another holder) it would delete a lock this run does not
# own.
child=""
release() {
    [ -n "$child" ] && { kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null; }
    rm -rf "$LOCK"
}

# ── Wait for room, then take the lock ────────────────────────────────────────
# Room is read BEFORE the lock is taken: a holder who took the lock first and
# only then waited for room kept it for everyone behind it, including a run
# whose own class already fit (auditor's order 71 — docs-l22 held the lock 27
# minutes waiting for load, with a fitting `--class rule` run queued behind
# it). Room can still move between this read and the lock actually landing, so
# it is read once more right after; a lock that no longer fits is given back at
# once and the wait for room starts over. The lock is held only by a run that
# is running or about to, with room read true.
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
    silent_announced=0
    while :; do
        if mkdir "$LOCK" 2>/dev/null; then
            echo "$WHO" > "$LOCK/who"
            # THE PID IS WRITTEN BESIDE THE NAME: this shell lives exactly as
            # long as the run it wraps, so it is the fact the breaker below can
            # ask.
            echo "$$" > "$LOCK/pid"
            # THE CLASS TOO — a short run deciding whether to preempt this
            # holder (auditor's order 90) reads it; a run with no class writes
            # the empty string, which preempts nothing.
            echo "$RUN_CLASS" > "$LOCK/class"
            # Ours now — armed so an interrupt from here on cleans up rather
            # than abandoning it.
            trap 'release; exit 130' INT TERM
            trap release EXIT
            break
        fi
        holder=$(cat "$LOCK/who" 2>/dev/null || echo "someone")
        # A lock older than 45 minutes is BROKEN ONLY WHEN ITS HOLDER IS GONE. Age
        # alone broke the lock of a run that was alive and hung, and the next
        # session rebuilt the served copy under it. A holder alive and silent is
        # held off and said aloud, never broken; a lock with no pid (written before
        # the pid was) is judged by its age, as it always was.
        if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +45 2>/dev/null)" ]; then
            holder_pid=$(cat "$LOCK/pid" 2>/dev/null || true)
            if [ -n "$holder_pid" ] && kill -0 "$holder_pid" 2>/dev/null; then
                if [ "$silent_announced" -eq 0 ]; then
                    since=$(stat -c %Y "$LOCK" 2>/dev/null || stat -f %m "$LOCK")
                    echo "heavy: holding off — $holder (pid $holder_pid) is alive and silent for $(( ($(date +%s) - since) / 60 )) min; the lock is not broken" >&2
                    silent_announced=1
                fi
                sleep 3
                continue
            fi
            echo "heavy: breaking a stale lock held by $holder${holder_pid:+ (pid $holder_pid is gone)}" >&2
            rm -rf "$LOCK"
            continue
        fi
        [ "$lock_announced" -eq 0 ] && echo "heavy: waiting for $holder to finish" >&2
        lock_announced=1
        sleep 3
    done

    # The lock is ours. Trust it only once room is read again — the mkdir above
    # may have landed well after the read that let this run start queuing for
    # it.
    room_fits
    rc=$?
    if [ "$rc" -eq 1 ]; then
        echo "heavy: ${free}MB free, load $load right after taking the lock — giving it back" >&2
        # Disarmed before releasing on purpose: this is not the interrupt or
        # exit the trap exists for, and the lock is about to belong to nobody
        # again — the next holder's is not this run's to remove.
        trap - INT TERM EXIT
        rm -rf "$LOCK"
        continue
    fi
    break
done

# A caller that names no TM_HARNESS_JOBS of its own gets one chosen FOR it,
# from what the guard above already knows about Plex (auditor's order 90): 3
# when nothing is transcoding, 2 when the Plex Transcoder is active. An
# explicit value in the environment is never touched — a caller that knows its
# own machine still wins. `run.sh`'s OWN default (used outside heavy.sh) stays
# 2, untouched by this.
if [ -z "${TM_HARNESS_JOBS:-}" ]; then
    if plex_is_transcoding; then
        export TM_HARNESS_JOBS=2
        echo "heavy: TM_HARNESS_JOBS=2 for $WHO (Plex Transcoder active)" >&2
    else
        export TM_HARNESS_JOBS=3
        echo "heavy: TM_HARNESS_JOBS=3 for $WHO (no Plex Transcoder)" >&2
    fi
fi

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
# THE CHILD'S OWN PID, BESIDE THE LOCK'S: `$LOCK/pid` is this wrapper's own
# shell, which lives exactly as long as the run — but a short run preempting a
# browser-class holder (order 90) has to suspend THE WRAPPED COMMAND'S tree,
# not the wrapper waiting on it.
[ -d "$LOCK" ] && echo "$child" > "$LOCK/child_pid" 2>/dev/null

# The watchdog samples memory every 15 s, but it notices the child finishing
# within a second: a wrapper that slept a fixed 15 s before looking would tax
# every quick command with a tail nobody would accept, and the tax is what
# makes a rule get bypassed.
strikes=0
ticks=0
plex_suspended=0
while kill -0 "$child" 2>/dev/null; do
    sleep 1
    ticks=$((ticks + 1))

    # Plex is checked every few seconds — far more often than the memory
    # floor below, because a starved transcoder is heard about in seconds,
    # not minutes.
    if [ "$((ticks % 3))" -eq 0 ]; then
        if [ "$plex_suspended" -eq 0 ]; then
            if plex_is_transcoding; then
                plex_load=$(one_minute_load)
                if [ -n "$plex_load" ] && [ "$(at_least "$plex_load" "$PLEX_LOAD_CEILING")" = 1 ]; then
                    echo "heavy: Plex Transcoder active, load $plex_load >= $PLEX_LOAD_CEILING — suspending $WHO" >&2
                    heavy_suspend_tree "$child"
                    plex_suspended=1
                fi
            fi
        else
            plex_load=$(one_minute_load)
            if ! plex_is_transcoding || { [ -n "$plex_load" ] && [ "$(at_most "$plex_load" "$PLEX_LOAD_RESUME")" = 1 ]; }; then
                echo "heavy: resuming $WHO (Plex Transcoder gone or load $plex_load <= $PLEX_LOAD_RESUME)" >&2
                heavy_resume_tree "$child"
                plex_suspended=0
            fi
        fi
    fi

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
