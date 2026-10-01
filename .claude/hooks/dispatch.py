#!/usr/bin/env python3
"""Run a list of hook scripts in ONE Python process, for one hook event and matcher.

WHAT IT PAYS FOR. `.claude/settings.json` used to launch each hook as its own
`python3` through the pyenv shim: about 25 processes and 0.1 s per hook, six hooks
per Bash command. Here the event's payload is read once and every hook listed on the
command line is executed in this process, in the order given, as if it had been run
as a script (`runpy`, `__name__ == "__main__"`, its own stdin, stdout, stderr, argv
and exit code). A hook file that does not exist is skipped, as the former
`test -f … &&` did. The hooks are imported where they live, never copied.

HOW A HOOK BLOCKS, AND WHAT IS KEPT. A PreToolUse hook here blocks in one of two
ways, and the dispatcher hands either on to Claude Code:

- a JSON object on stdout carrying `"decision": "block"` (or `"deny"`, or a
  `hookSpecificOutput.permissionDecision` of `"deny"`) with exit 0 — the first such
  object is printed back verbatim and the dispatcher exits 0;
- exit code 2 with the reason on stderr — the dispatcher exits 2 with every
  blocking hook's reason on stderr. The former commands ended in `|| true`, which
  swallowed this exit code: those hooks (AI attribution, sensitive files, SKILL.md
  frontmatter) were not blocking at all. The `|| true` was there to skip an absent
  file; the dispatcher does that itself, so their exit 2 is honoured again.

Every hook runs even after one has blocked — Claude Code ran them all in parallel,
and the loggers record the attempt. A hook that raises fails open (traceback on
stderr, exit treated as 1, non-blocking), as an uncaught exception under `|| true`
did. Any other stdout a hook prints is forwarded to stderr, where it stays visible
without being parsed as a decision.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import sys
import traceback
from dataclasses import dataclass

BLOCKING_EXIT_CODE = 2


@dataclass(frozen=True)
class HookRun:
    """What one hook did when run against the payload.

    Attributes:
        path: The hook script's path, as given on the command line.
        exit_code: Its exit code (0 when it returned without calling `sys.exit`).
        stdout: What it printed on stdout.
        stderr: What it printed on stderr.
    """

    path: str
    exit_code: int
    stdout: str
    stderr: str


def run_hook(path: str, payload: str) -> HookRun:
    """Execute one hook script in this process, as `python3 path` would have.

    Args:
        path: The hook script to run.
        payload: The event's JSON, handed to the hook on its stdin.

    Returns:
        The hook's exit code and captured output.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    saved_stdin, saved_argv = sys.stdin, sys.argv
    sys.stdin, sys.argv = io.StringIO(payload), [path]
    exit_code = 0
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path(path, run_name="__main__")
            except SystemExit as exit_request:
                exit_code = exit_status(exit_request.code, stderr)
            except Exception:
                traceback.print_exc()
                exit_code = 1
    finally:
        sys.stdin, sys.argv = saved_stdin, saved_argv
    return HookRun(path, exit_code, stdout.getvalue(), stderr.getvalue())


def exit_status(code: object, stderr: io.StringIO) -> int:
    """Translate a `SystemExit` code the way the interpreter does at shutdown.

    Args:
        code: The `SystemExit.code` raised by the hook.
        stderr: The hook's stderr, which receives a non-integer code's text.

    Returns:
        The process exit status the hook would have had.
    """
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=stderr)
    return 1


def blocking_decision(stdout: str) -> dict[str, object] | None:
    """Return the hook's stdout JSON object when it is a blocking decision.

    Args:
        stdout: What the hook printed on stdout.

    Returns:
        The decision object, or None when the output is no blocking decision.
    """
    try:
        decision = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(decision, dict):
        return None
    if decision.get("decision") in ("block", "deny"):
        return decision
    specific = decision.get("hookSpecificOutput")
    if isinstance(specific, dict) and specific.get("permissionDecision") == "deny":
        return decision
    return None


def dispatch(paths: list[str], payload: str) -> tuple[int, str, str]:
    """Run every existing hook in order and combine their verdicts.

    Args:
        paths: The hook scripts, in the order they must run.
        payload: The event's JSON.

    Returns:
        The exit code, stdout and stderr the dispatcher must produce.
    """
    json_block: dict[str, object] | None = None
    exit_blocks: list[str] = []
    messages: list[str] = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        run = run_hook(path, payload)
        decision = blocking_decision(run.stdout)
        if decision is not None:
            json_block = json_block or decision
        elif run.stdout.strip() and not is_plain_continue(run.stdout):
            messages.append(run.stdout)
        if run.exit_code == BLOCKING_EXIT_CODE:
            exit_blocks.append(run.stderr)
        elif run.stderr:
            messages.append(run.stderr)
    if exit_blocks:
        # On exit 2 Claude Code reads stderr only: a JSON decision's reason joins it there.
        if json_block is not None:
            exit_blocks.append(str(json_block.get("reason", "")))
        return BLOCKING_EXIT_CODE, "", "".join(text if text.endswith("\n") else text + "\n" for text in exit_blocks)
    stdout = json.dumps(json_block) if json_block is not None else ""
    return 0, stdout, "".join(messages)


def is_plain_continue(stdout: str) -> bool:
    """Say whether a hook's stdout is only the no-op `{"continue": true}`.

    Args:
        stdout: What the hook printed on stdout.

    Returns:
        True when it carries nothing but `continue: true`.
    """
    try:
        return json.loads(stdout) == {"continue": True}
    except ValueError:
        return False


def main() -> int:
    """Read the payload, dispatch it to the hooks named in argv, emit the verdict.

    Returns:
        The dispatcher's exit code: 2 when a hook blocked by exit code, else 0.
    """
    try:
        payload = sys.stdin.read()
        exit_code, stdout, stderr = dispatch(sys.argv[1:], payload)
    except Exception:
        # The dispatcher itself fails open, as the hooks it replaces did under `|| true`.
        traceback.print_exc()
        return 0
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, end="", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
