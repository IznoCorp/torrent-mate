#!/usr/bin/env python3
"""Project filter in front of the global auto-format hook.

This repository's Markdown, JSON and YAML are not prettier-shaped: BUGS.md and the
register are parsed by scripts, openapi.json and the harness baselines are generated
with their own shape, and a reflow buries a wave's real change. Those extensions are
left untouched.

AND NEITHER IS ANYTHING GIT DOES NOT TRACK (B-387). The formatter rewrote a `.py`
a review reader had written under the untracked `.review/` directory of its own
worktree: an instrument rewritten by a hook is an instrument its author did not
write. A path that is git-ignored, that git does not track, or that lies outside
any repository at all is left alone and the skip is said on stderr — a hook that
declines silently is indistinguishable from a hook that did nothing.

The consequence is deliberate: a file that has never been `git add`-ed is not
formatted either. The repository's own gate (`ruff format --check` in `make lint`
and in CI) is what says so, and it says so about a file somebody chose to track.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SKIPPED = {".md", ".json", ".json5", ".yaml", ".yml"}
GLOBAL_HOOK = Path.home() / ".claude" / "hooks" / "auto_format.py"

# Git hands a hook GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE in the environment,
# and they override `-C`: a probe run with them set answers about the repository
# the outer command was aimed at, not about the file in hand. `scripts/pre-push`
# pays for the same leak, from the other direction.
_LEAKED_GIT_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")


def run_git(directory: Path, *arguments: str) -> int:
    """Run a git query from a directory and return its exit code.

    Args:
        directory: The directory to run git in — the file's own, so the answer
            comes from the repository the file actually lives in.
        arguments: The git arguments, after `-C <directory>`.

    Returns:
        Git's exit code, or 128 when git could not run at all.
    """
    environment = {key: value for key, value in os.environ.items() if key not in _LEAKED_GIT_VARIABLES}
    try:
        return subprocess.run(
            ["git", "-C", str(directory), *arguments],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            check=False,
        ).returncode
    except OSError:
        return 128


def reason_to_skip(file_path: str) -> str:
    """Say why this path must not be handed to the formatter, or an empty string.

    Args:
        file_path: The path the tool reported editing.

    Returns:
        The reason, ready to print, or `""` when the file may be formatted.
    """
    if not file_path:
        return "the tool reported no file path"
    path = Path(file_path)
    if path.suffix.lower() in SKIPPED:
        return f"{path.suffix} files are not prettier-shaped in this repository"
    directory = path.parent
    if not directory.is_dir():
        return "its directory does not exist"
    if run_git(directory, "check-ignore", "-q", "--", str(path)) == 0:
        return "git ignores it"
    if run_git(directory, "ls-files", "--error-unmatch", "--", str(path)) != 0:
        return "git does not track it"
    return ""


def main() -> None:
    """Read the tool's payload and forward it to the global formatter, or decline."""
    raw = sys.stdin.read()
    try:
        file_path = json.loads(raw).get("tool_input", {}).get("file_path", "")
    except (json.JSONDecodeError, AttributeError):
        file_path = ""
    skip = reason_to_skip(file_path)
    if skip:
        print(f"auto_format_project: leaving {file_path or '(no path)'} alone — {skip}", file=sys.stderr)
        return
    if not GLOBAL_HOOK.exists():
        return
    subprocess.run([sys.executable, str(GLOBAL_HOOK)], input=raw, text=True, check=False)


if __name__ == "__main__":
    main()
