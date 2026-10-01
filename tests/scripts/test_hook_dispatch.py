"""The hook dispatcher: one Python process per hook event, every guard still biting.

WHAT IT PAID FOR. Each hook in `.claude/settings.json` was its own `python3` through
the pyenv shim — about 25 processes per hook, six hooks per Bash command. The
dispatcher runs them in one process; what these tests hold is that nothing a hook
used to decide is lost on the way: the order, the skip of an absent file, a JSON
block handed back verbatim, an exit-2 block turned into the dispatcher's exit 2,
and the settings wiring every matcher through it.

Every test drives `dispatch.py` as Claude Code does — a subprocess, the payload on
stdin — against throwaway hook scripts written in `tmp_path`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = ROOT / ".claude" / "hooks" / "dispatch.py"
SETTINGS = ROOT / ".claude" / "settings.json"

PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "true"}})


def write_hook(directory: Path, name: str, body: str) -> Path:
    """Write a throwaway hook script.

    Args:
        directory: Where to write it.
        name: Its file name.
        body: Its Python source.

    Returns:
        The script's path.
    """
    path = directory / name
    path.write_text(body)
    return path


def run_dispatcher(*hooks: Path | str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the dispatcher on the hooks, the payload on stdin.

    Args:
        hooks: The hook scripts, in order.
        cwd: The working directory of the run.

    Returns:
        The finished process.
    """
    return subprocess.run(
        [sys.executable, str(DISPATCHER), *map(str, hooks)],
        input=PAYLOAD,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=60,
    )


def recorder(log: Path, label: str) -> str:
    """Return the source of a hook that appends its label and its payload's tool to a log.

    Args:
        log: The shared log file.
        label: What this hook writes.

    Returns:
        The hook's source.
    """
    return (
        "import json, sys\n"
        f"tool = json.load(sys.stdin)['tool_name']\n"
        f"open({str(log)!r}, 'a').write({label!r} + ':' + tool + '\\n')\n"
        "print(json.dumps({'continue': True}))\n"
    )


def test_hooks_run_in_the_given_order_each_with_the_full_payload(tmp_path: Path) -> None:
    """Every hook reads the whole payload on its own stdin, in command-line order."""
    log = tmp_path / "log"
    first = write_hook(tmp_path, "first.py", recorder(log, "first"))
    second = write_hook(tmp_path, "second.py", recorder(log, "second"))
    result = run_dispatcher(second, first, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert log.read_text() == "second:Bash\nfirst:Bash\n"
    assert result.stdout == ""


def test_an_absent_hook_is_skipped(tmp_path: Path) -> None:
    """A hook file that does not exist is skipped, the others still run."""
    log = tmp_path / "log"
    present = write_hook(tmp_path, "present.py", recorder(log, "present"))
    result = run_dispatcher(tmp_path / "absent.py", present, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert log.read_text() == "present:Bash\n"


def test_a_json_block_is_handed_back_verbatim_and_later_hooks_still_run(tmp_path: Path) -> None:
    """A `decision: block` on stdout comes back as the dispatcher's stdout, exit 0."""
    log = tmp_path / "log"
    decision = {"decision": "block", "reason": "BLOCKED: no timeout"}
    blocker = write_hook(tmp_path, "blocker.py", f"import json\nprint(json.dumps({decision!r}))\n")
    after = write_hook(tmp_path, "after.py", recorder(log, "after"))
    result = run_dispatcher(blocker, after, cwd=tmp_path)
    assert result.returncode == 0
    assert json.loads(result.stdout) == decision
    assert log.read_text() == "after:Bash\n"


def test_an_exit_two_block_becomes_the_dispatchers_exit_two(tmp_path: Path) -> None:
    """A hook's exit 2 with its reason on stderr is the dispatcher's exit 2 and stderr."""
    blocker = write_hook(
        tmp_path,
        "blocker.py",
        "import sys\nprint('BLOCKED: attribution', file=sys.stderr)\nsys.exit(2)\n",
    )
    passer = write_hook(tmp_path, "passer.py", "import json\nprint(json.dumps({'continue': True}))\n")
    result = run_dispatcher(passer, blocker, cwd=tmp_path)
    assert result.returncode == 2
    assert "BLOCKED: attribution" in result.stderr


def test_a_failing_hook_fails_open(tmp_path: Path) -> None:
    """A hook that raises or exits 1 does not block, and its trace is on stderr."""
    raiser = write_hook(tmp_path, "raiser.py", "raise RuntimeError('boom')\n")
    one = write_hook(tmp_path, "one.py", "import sys\nprint('REJECT: something')\nsys.exit(1)\n")
    result = run_dispatcher(raiser, one, cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""
    assert "boom" in result.stderr
    assert "REJECT: something" in result.stderr


def test_settings_route_every_tool_pattern_through_one_dispatcher_without_the_shim_pinned() -> None:
    """Each tool pattern holds ONE command: the dispatcher, under the overridable interpreter."""
    settings = json.loads(SETTINGS.read_text())
    for event, groups in settings["hooks"].items():
        for group in groups:
            assert len(group["hooks"]) == 1, (event, group["matcher"])
            command = group["hooks"][0]["command"]
            assert '"${CLAUDE_HOOK_PYTHON:-python3}"' in command, command
            assert 'D="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks"' in command, command
            assert '"$D/dispatch.py"' in command, command
            assert "versions/" not in command, command
            assert "|| true" not in command, command  # it swallowed every exit-2 block
