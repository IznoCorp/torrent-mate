#!/usr/bin/env python3
"""The served copy the harness measures: who holds it, and which build it is.

B-256. `run.sh` rebuilds and re-copies `/tmp/tm-refonte/wrapped.html`
unconditionally at every invocation, and until this file existed it did so with
no lock and no stamp. On 2026-08-30 a second session's `make maquette-oracle`
re-copied the prototype while a suite was mid-run, and two rules fell over a
build they were never started against. Both passed when run alone, which is the
harmless direction. **The dangerous one is the other**: a rule can PASS over
the wrong prototype exactly as silently, and nothing in the harness would say
so.

TWO MECHANISMS, BECAUSE NEITHER IS ENOUGH ALONE.

A LOCK PREVENTS. A second builder is refused the copy rather than allowed to
replace it under a reader. `mkdir` is atomic on every filesystem this project
runs on and needs no `flock`, which macOS does not ship. A lock whose holder is
gone is broken with a message naming the holder — a lock that can outlive its
process is a lock that eventually gets deleted by hand, and a lock people delete
by hand protects nothing.

A STAMP DETECTS. The lock covers the builders that take it; it cannot cover a
reader started before the lock existed, a rule launched by hand from an editor,
or a future instrument nobody has written yet. So the copy carries the identity
of the build inside it, and a reader that sees it move between its start and its
end says so instead of reporting a number.

WHAT THE STAMP IS NOT. It is not a freshness check. Nothing here asks whether
the copy is up to date with the sources — `run.sh` rebuilds before every run and
that is what makes it current. This answers one question only: is the prototype
I am finishing on the prototype I started on?
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# The copy the harness serves, and the two files this module owns inside it.
# It is the same path `run.sh` and `server.py --serve` use; it is written here
# rather than imported because this module is the one that may be asked about
# the copy before anything else has run.
SERVED = Path("/tmp/tm-refonte")
STAMP = SERVED / "build-stamp.json"
LOCK = SERVED / ".lock"

# How long a lock may go unrefreshed before its holder is presumed gone AND its
# process is confirmed absent. Both conditions, never either: a suite that runs
# 25 minutes is normal, and an age alone would break the lock underneath it.
STALE_AFTER_SECONDS = 60 * 60

# The one docstring fence this repository writes; `ruff` refuses the other.
FENCE = chr(34) * 3


def _git(*arguments: str) -> str:
    """Runs one read-only git command at the repository root.

    Args:
        *arguments: The git arguments, after `git`.

    Returns:
        The stripped output, or an empty string when git cannot answer — a
        harness that cannot reach git still has a stamp, it simply has one
        that names no commit.
    """
    root = Path(__file__).resolve().parents[3]
    try:
        return subprocess.run(("git", "-C", str(root), *arguments),
                              capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def source_stamp() -> int:
    """Returns the newest mtime among the prototype's sources, in nanoseconds.

    The same definition `serve.py`'s `mtime_sources()` uses, and for the same
    reason: the shell is a DIRECTORY, so a module added tomorrow must not be
    invisible. It is re-derived here rather than imported because importing
    `serve.py` starts a module whose subject is answering HTTP requests, and a
    stamp writer must not depend on a web host being importable.

    Returns:
        The newest modification time in nanoseconds, or 0 when the tree is
        unreachable.
    """
    design = Path(__file__).resolve().parents[1] / "design"
    newest = 0
    for source in (design / "src").rglob("*"):
        if source.is_file():
            newest = max(newest, source.stat().st_mtime_ns)
    for root in (design / "index.html", design / "package.json"):
        if root.is_file():
            newest = max(newest, root.stat().st_mtime_ns)
    return newest


def publish(design: Path | None = None) -> dict:
    """Puts the freshly built prototype in the served copy, and stamps it.

    THE ONE PLACE THE COPY IS ASSEMBLED, and it exists because there were three.
    `run.sh`, `scripts/mutate.sh` and `scripts/harness-hold-counts.py` each had
    their own version, and two of them wrote NEITHER the lock nor the stamp —
    so B-256 stayed open through the two tools most likely to be running beside
    a suite: the mutation tool this project's method mandates, and the very tool
    that records the hold-count baseline.

    They also fell behind in the other direction. `run.sh` learned to copy
    `sw.js` and `build.json` at L11 and the other two did not, so a copy either
    of them made served a worker and a build identity from a PREVIOUS build. A
    build output is a third end, and three copies of an assembly step means
    every new output has to be remembered three times. Now it is one.

    Args:
        design: The design root. Defaults to this file's own tree.

    Returns:
        The stamp written over the copy.

    Raises:
        SystemExit: When the build has produced nothing to publish — an empty
            copy measures nothing and must not be mistaken for a fresh one.
    """
    design = design or (Path(__file__).resolve().parents[1] / "design")
    dist = design / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit(
            f"{dist}/index.html is absent — nothing was built to publish.")
    SERVED.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dist / "index.html", SERVED / "wrapped.html")
    shutil.rmtree(SERVED / "vite", ignore_errors=True)
    if (dist / "vite").is_dir():
        shutil.copytree(dist / "vite", SERVED / "vite", dirs_exist_ok=True)
    # THE WORKER AND THE BUILD'S IDENTITY. Without them the harness host has no
    # `/sw.js` at all: its fallback handler folds any unknown path onto the
    # document, so registration receives an HTML body and refuses it on the MIME
    # type, with nothing said anywhere.
    for name in ("sw.js", "build.json"):
        if (dist / name).is_file():
            shutil.copy2(dist / name, SERVED / name)
    link = SERVED / "assets"
    if link.is_symlink() or link.exists():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.symlink_to(design / "assets", target_is_directory=True)
    return write_stamp()


def write_stamp(token_value: str | None = None) -> dict:
    """Writes the identity of the build now sitting in the served copy.

    Args:
        token_value: The run's own token. Generated when absent — every call
            produces a DIFFERENT one, which is what makes a second builder's
            copy distinguishable from this one even at the same commit and the
            same source stamp. Two consecutive builds of an unchanged tree are
            still two different copies, and a reader that spanned them read
            two files.

    Returns:
        The stamp as written.
    """
    stamp = {
        "commit": _git("rev-parse", "HEAD") or "unknown",
        "dirty": bool(_git("status", "--porcelain")),
        "source_stamp": source_stamp(),
        "token": token_value or f"{os.getpid()}-{time.time_ns()}",
        "written": time.time(),
    }
    SERVED.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n")
    return stamp


def read_stamp() -> dict | None:
    """Reads the served copy's stamp.

    Returns:
        The stamp, or None when the copy carries none — which is what an
        unbuilt copy and a copy built by a `run.sh` older than this file both
        look like. A missing stamp is NEVER a failure here: refusing it is the
        caller's decision, and only one caller can afford to.
    """
    try:
        return json.loads(STAMP.read_text())
    except (OSError, ValueError):
        return None


def token() -> str | None:
    """Returns the served copy's run token, or None when it carries no stamp.

    Returns:
        The token, or None.
    """
    stamp = read_stamp()
    return None if stamp is None else str(stamp.get("token") or "") or None


def assert_unchanged(expected: str | None, where: str) -> None:
    """Refuses to go on when the served copy was replaced under a reader.

    Args:
        expected: The token read when the reader started. None means the
            reader started against a copy with no stamp, and nothing can be
            concluded — say so once and continue, rather than failing every
            rule on a machine whose copy predates this file.
        where: What the reader was doing, printed so the failure names the
            moment rather than the mechanism.

    Raises:
        SystemExit: When the token moved. The message names both tokens: the
            reading is not merely doubtful, it spans two prototypes, and which
            two is the first thing anyone will ask.
    """
    if expected is None:
        return
    seen = token()
    if seen == expected:
        return
    raise SystemExit(
        f"SERVED COPY REPLACED MID-RUN ({where}) — B-256.\n"
        f"  started against: {expected}\n"
        f"  now serving:     {seen or 'no stamp at all'}\n"
        "  This reading spans two builds and means nothing either way.\n"
        "  Another session rebuilt /tmp/tm-refonte. Coordinate first "
        "(docs/reference/frontend-steward.md), then run again."
    )


def _held_by() -> dict | None:
    """Reads who holds the lock.

    Returns:
        `{holder, pid}`, or None when the lock carries no readable holder —
        which happens in the window between `mkdir` and the two writes.
    """
    try:
        return {
            "holder": (LOCK / "holder").read_text().strip(),
            "pid": int((LOCK / "pid").read_text().strip()),
        }
    except (OSError, ValueError):
        return None


def _is_stale(held: dict | None) -> bool:
    """Tells whether a lock's holder is really gone.

    BOTH conditions, never either. An age alone would break the lock under a
    suite that legitimately runs 25 minutes; a missing process alone would
    break it under a holder whose pid was recycled. Age is the cheap filter and
    the signal is the process.

    Args:
        held: What `_held_by` returned, or None for a lock whose holder files
            are missing or unreadable — the window between `mkdir` and the two
            writes, a `SIGKILL` inside it, a full disk. That case had NO exit
            at all: `acquire` refused it, `release` refused to remove it, and
            the staleness path never considered it, so the only way out was the
            `rm -rf` the refusal prints — which is what makes a lock worthless.
            An unreadable lock is broken on AGE alone, because there is no pid
            to ask about.

    Returns:
        True when the lock may be broken.
    """
    try:
        age = time.time() - LOCK.stat().st_mtime
    except OSError:
        return False
    if age < STALE_AFTER_SECONDS:
        return False
    if held is None:
        return True
    try:
        os.kill(held["pid"], 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False


def _release_quietly() -> None:
    """Removes the lock directory, ignoring what is already gone."""
    for name in ("holder", "pid"):
        try:
            (LOCK / name).unlink()
        except OSError:
            pass
    try:
        LOCK.rmdir()
    except OSError:
        pass


def acquire(holder: str, pid: int | None = None) -> None:
    """Takes the served copy, or refuses to build over another session's run.

    Args:
        holder: What is asking for it, printed to whoever is refused.
        pid: The process the lock is held ON BEHALF OF, which is almost never
            this one. `run.sh` acquires through a short-lived `python3` that
            exits a millisecond later; recording ITS pid would make every lock
            look abandoned to the staleness check, so the caller passes the
            process that will actually hold the copy. Defaults to this process
            for a caller that really is the holder.

    Raises:
        SystemExit: When the copy is held by a live process.
    """
    SERVED.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            LOCK.mkdir()
        except FileExistsError:
            held = _held_by()
            if attempt == 0 and _is_stale(held):
                who = ("an unreadable holder" if held is None
                       else f"{held['holder']} (pid {held['pid']}, gone)")
                print(f"Breaking a stale lock left by {who}.", file=sys.stderr)
                _release_quietly()
                continue
            described = "an unreadable lock" if held is None else (
                f"{held['holder']} (pid {held['pid']})")
            raise SystemExit(
                f"The served copy is held by {described}.\n"
                "  Two suites cannot share /tmp/tm-refonte: the second would "
                "rebuild under the first (B-256).\n"
                "  Wait for it, or — if you are certain it is gone — "
                f"rm -rf {LOCK}"
            )
        else:
            (LOCK / "holder").write_text(holder + "\n")
            (LOCK / "pid").write_text(f"{pid or os.getpid()}\n")
            return
    raise SystemExit(f"Could not take {LOCK} after breaking a stale lock.")


def release(pid: int | None = None) -> None:
    """Gives the served copy back — and ONLY when it is ours to give.

    THE CHECK IS THE WHOLE POINT. `run.sh` releases from a trap that fires
    however the script ended, including the path where `acquire` REFUSED it
    because another session was holding the copy. An unconditional release
    there would hand the refused session's lock away to nobody, which is worse
    than having no lock at all: the failure would be silent and would land on
    the session that did everything right.

    Args:
        pid: The process the lock was taken on behalf of. A lock recording a
            different one belongs to somebody else and is left alone.
    """
    held = _held_by()
    # AN UNREADABLE LOCK IS NOT OURS EITHER. `_held_by` answers None for the
    # window between `mkdir` and the two writes, for a truncated `pid`, and for
    # a `.lock` made by hand — and the first version fell THROUGH that case and
    # deleted the lock. `run.sh` releases from a trap that fires on every exit
    # path INCLUDING the refused one, so a session that was correctly turned
    # away would have destroyed the holder's lock on its way out. The victim
    # would have been the session that did everything right.
    if held is None or held["pid"] != (pid or os.getpid()):
        return
    _release_quietly()


def _code_of(path: Path) -> str:
    """Returns a file's lines with its comments removed.

    WHY IT IS NOT OPTIONAL HERE. This rule reads `run.sh` and `common.py` for
    the wiring, and both files DESCRIBE that wiring at length in their comments.
    A rule that searched the raw text would be satisfied by the paragraph
    explaining the mechanism after somebody deleted the mechanism — which is
    the defect L07's compositor guard shipped, counting its own prose.

    Args:
        path: The file to read.

    IT STRIPS DOCSTRINGS TOO, and that is not tidiness. The first version
    dropped `#` comments only, so `common.py`'s hundred-odd lines of docstring
    survived into the "code" — and every hold below is a substring search.
    Deleting `assert_unchanged(STARTED_AGAINST, "opening the prototype")` from
    `open_page` and writing that same sentence into its DOCSTRING left all three
    holds green with the assertion gone. That is the very defect this function's
    header cites, one quoting style further along.

    ONLY THE DOUBLE-QUOTED FENCE, because that is the only one this repository
    writes: `ruff` enforces it, and a stripper that half-understood the other
    would be a stripper nobody could reason about. A single-quoted docstring
    would be a lint error long before it reached here.

    Returns:
        The source with every `#` comment line dropped, every triple-quoted
        block removed, and trailing comments cut at the first `#` that is not
        inside a string.
    """
    kept = []
    inside_docstring = False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if inside_docstring:
            closes = line.find(FENCE)
            if closes >= 0:
                inside_docstring = False
                # WHAT FOLLOWS THE CLOSING FENCE IS CODE. Dropping the whole
                # line loses it — `common.py` has a `"""` that closes and then
                # calls `.replace(...)` twice on the same line, and the first
                # version discarded both calls. A stripper that eats real code
                # makes every negative hold above greener.
                line = line[closes + len(FENCE):]
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                kept.append(line)
            continue
        # THE COMMENT TEST RUNS FIRST. A `#` line containing a fence — `# the
        # fence is """` — would otherwise open a phantom docstring and swallow
        # every line after it until the next fence.
        if stripped.startswith("#"):
            continue
        opened = line.find(FENCE)
        if opened >= 0:
            # A one-line docstring opens and closes on the same line; only an
            # unclosed fence carries into the lines that follow.
            inside_docstring = line.find(FENCE, opened + len(FENCE)) < 0
            line = line[:opened]
            stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        quote = None
        for index, character in enumerate(line):
            if quote:
                if character == quote:
                    quote = None
            elif character in "\"'":
                quote = character
            elif character == "#":
                line = line[:index]
                break
        kept.append(line)
    return "\n".join(kept)


def rules() -> int:
    """R104 — the served copy is held while it is rebuilt, and stamped after.

    THE ARM EXISTS BECAUSE THE TESTS CANNOT SEE THE WIRING.
    `tests/scripts/test_served_copy.py` proves the lock and the stamp BEHAVE;
    it cannot prove that `run.sh` still calls them, and a mechanism nothing
    calls is a mechanism that is not there. That gap is how B-256 existed in the
    first place — every part of the harness worked, and no part of it asked
    whether the copy had moved.

    Returns:
        0 when the wiring holds, 1 otherwise.
    """
    executed = 0
    failures = []
    here = Path(__file__).resolve().parent
    run_sh = _code_of(here / "run.sh")
    common = _code_of(here / "common.py")
    mine = _code_of(here / "served_copy.py")

    def hold(name, condition, detail=""):
        nonlocal executed
        executed += 1
        print(("  PASS" if condition else "  FAIL") + f" {name}"
              + (f" — {detail}" if detail else ""))
        if not condition:
            failures.append(name)

    # THE ORDER IS THE CORRECTNESS. A lock taken after the build has already let
    # the second builder overwrite the copy under a reader.
    acquire_at = run_sh.find('served_copy.py" --acquire')
    build_at = run_sh.find("npm run build")
    publish_at = run_sh.find('served_copy.py" --publish')
    hold("run.sh takes the copy BEFORE it rebuilds it",
         0 <= acquire_at < build_at, f"acquire@{acquire_at} build@{build_at}")
    hold("run.sh publishes the copy AFTER it builds it",
         0 <= build_at < publish_at, f"build@{build_at} publish@{publish_at}")
    # A SIGNAL TRAP THAT DOES NOT EXIT IS NOT A CLEANUP. Bash runs an INT
    # handler and then RESUMES the script, so the first version of this hold
    # certified a string under which Ctrl-C released the lock, deleted the log
    # directory, and carried on running the remaining rules unlocked. The hold
    # reads that each signal trap ends in an `exit`.
    hold("run.sh gives the copy back on every path out",
         "trap cleanup EXIT" in run_sh and "--release" in run_sh)
    hold("and a signal EXITS rather than resuming the run unlocked",
         "trap 'cleanup; exit 130' INT" in run_sh
         and "trap 'cleanup; exit 143' TERM" in run_sh)

    # ONE ASSEMBLY, and this is the hold that keeps it one. Three copies of this
    # step existed; two wrote neither the lock nor the stamp, and one of those
    # is the tool that records the hold-count baseline while the other is the
    # mutation tool this project's method mandates. They also fell behind on
    # WHAT the copy contains: `sw.js` and `build.json` joined it at L11 in
    # `run.sh` alone, so a copy either of them made served a worker from a
    # previous build.
    repository = here.parents[2]
    for tool in ("scripts/mutate.sh", "scripts/harness-hold-counts.py"):
        source = _code_of(repository / tool)
        hold(f"{tool} publishes through the harness rather than copying by hand",
             "served_copy" in source and "wrapped.html" not in source,
             "copies wrapped.html itself" if "wrapped.html" in source
             else "publishes")
        # THE ORDER, not the presence. The name asserts one and the first
        # version asserted the other: swapping the two calls left the hold green
        # while B-256 re-opened through the tool this wave called its worst
        # carrier. It is the same lesson the `run.sh` hold three lines above
        # already applied, and it was applied to one file and not the others.
        acquire_at = source.find("acquire")
        build_at = min([at for at in (source.find("npm run build"),
                                      source.find("npm\", \"run"))
                        if at >= 0] or [-1])
        hold(f"{tool} takes the copy BEFORE it rebuilds it",
             0 <= acquire_at < build_at, f"acquire@{acquire_at} build@{build_at}")
    hold("and the publisher copies the worker and the build's identity",
         '"sw.js", "build.json"' in mine)
    # THE INVARIANT R104 EXISTS FOR, held where it now lives. It used to read
    # `run.sh`'s own `cp` and `--stamp` lines; the assembly moved into
    # `publish()` and the hold moved with the wrong half — so writing the stamp
    # at the TOP of `publish()`, which is the original B-256 defect, passed
    # every hold in this file.
    document_at = mine.find('copy2(dist / "index.html"')
    stamp_at = mine.find("return write_stamp()")
    hold("the publisher stamps the copy AFTER it lands",
         0 <= document_at < stamp_at, f"copy@{document_at} stamp@{stamp_at}")

    # THE COMPARISON ITSELF, and not substrings that survive without it. Two of
    # the three the first version searched for were satisfied by the assignment
    # line alone, and nothing held that `$after` was compared to `$STAMP_TOKEN`,
    # that the operator was `!=`, or that the block ran whichever way the rule
    # went — which is the whole point, because a rule that PASSED over a swapped
    # copy is the case that matters. Wrapping the block in a condition left all
    # three present and the check dead for every rule.
    compared = re.search(
        r'after="\$\(python3 "\$HARNESS_DIR/served_copy\.py" --token\)"\s*\n'
        r'\s*if \[ "\$after" != "\$STAMP_TOKEN" \]; then',
        run_sh)
    hold("run.sh COMPARES the stamp around every rule it launches",
         compared is not None,
         "the read, the comparison and its operator, in one block")
    hold("and a rule that passed over a swapped copy is un-passed",
         compared is not None
         and 'rm -f "$HARNESS_LOGS/$rule.ok"' in run_sh[compared.end():])
    # AND THE TOKEN IS NON-EMPTY BEFORE THE RUN. Empty, `"" != ""` is false for
    # every rule and the wrapper passes seventy-nine times over nothing.
    hold("run.sh refuses to start against a copy with no stamp",
         'if [ -z "$STAMP_TOKEN" ]; then' in run_sh)

    # AND THE READING THAT COVERS A RULE RUN BY HAND, which `run.sh` never sees
    # and which is how a rule is run while it is being written.
    hold("common.py reads the token at import",
         "STARTED_AGAINST = served_copy.token()" in common)
    hold("common.py asserts at the start, in open_page",
         common.find("assert_unchanged(STARTED_AGAINST") > 0
         and "opening the prototype" in common)
    hold("common.py asserts at the end, in Journal.summary",
         common.count("assert_unchanged(STARTED_AGAINST") >= 2)

    # A FILTER THAT CAN RETURN NOTHING MUST HAVE A FLOOR — `run.sh`'s own words,
    # applied in the same commit to `installed.py` and not to this file. Every
    # hold above is a substring search over a stripped corpus, and two of them
    # are NEGATIVE (`"wrapped.html" not in source`): those get GREENER as the
    # stripper loses text, which is the one direction a reader never notices.
    for name, corpus in (("run.sh", run_sh), ("common.py", common),
                         ("served_copy.py", mine)):
        hold(f"the stripped corpus of {name} is not empty",
             len(corpus.splitlines()) >= 80, f"{len(corpus.splitlines())} lines")

    stamp = read_stamp()
    hold("the served copy carries a readable stamp",
         stamp is not None and bool(stamp.get("token")),
         "no copy built yet" if stamp is None else str(stamp.get("token")))

    print()
    print(f"{executed} rules EXECUTED — "
          + ("no violation" if not failures
             else f"{len(failures)} violation(s): {', '.join(failures)}"))
    return 1 if failures else 0


def main() -> int:
    """The command line `run.sh` drives this module through.

    WITH NO ARGUMENT IT IS A RULE, exactly as `server.py` is: the full suite
    launches every `.py` in this directory, so a file here that exits non-zero
    when asked nothing is a rule the suite reports as FAILED forever.

    Returns:
        0, or 1 when a hold falls.
    """
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "--acquire":
        acquire(sys.argv[2] if len(sys.argv) > 2 else "unnamed",
                int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif what == "--release":
        release(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif what == "--publish":
        print(json.dumps(publish(), sort_keys=True))
    elif what == "--stamp":
        print(json.dumps(write_stamp(), sort_keys=True))
    elif what == "--token":
        print(token() or "")
    else:
        print("─" * 62)
        print("served_copy.py — the copy is held while it is rebuilt, "
              "and stamped after")
        print("─" * 62)
        return rules()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
