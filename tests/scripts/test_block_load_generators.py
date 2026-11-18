"""The PreToolUse hook that refuses deliberate load on IznoServer (B-704).

The 2026-10-05 incident ran `( yes > /dev/null & )` burners « to reproduce under
load ». Each test drives `.claude/hooks/block_load_generators.py` as Claude Code
does — a subprocess, the payload on stdin — and runs nothing it inspects. The
harness-host check is pointed at a port this test opens itself
(`LOAD_HOOK_HARNESS_PORT`), never at 8899.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "block_load_generators.py"
SETTINGS = ROOT / ".claude" / "settings.json"


def decide(command: str, port: int | None = None) -> dict[str, object]:
    """Runs the hook on a Bash command.

    Args:
        command: The command Claude would run.
        port: The harness host's port for this run, when the test opened one.

    Returns:
        The hook's JSON answer.
    """
    environment = dict(os.environ)
    if port is not None:
        environment["LOAD_HOOK_HARNESS_PORT"] = str(port)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        env=environment,
    )
    answer: dict[str, object] = json.loads(result.stdout)
    return answer


@pytest.mark.parametrize(
    "command",
    [
        "( yes > /dev/null & )",
        "for i in 1 2 3 4; do (yes > /dev/null &); done",
        "yes >/dev/null",
        "nohup yes > /dev/null 2>&1 &",
        "yes | cat > /dev/null",
        "sh -c 'yes > /dev/null &'",
        "stress --cpu 8 --timeout 60",
        "stress-ng --cpu 0 --timeout 60s",
        "/opt/homebrew/bin/stress-ng --matrix 4",
        "while true; do :; done",
        "while :; do :; done &",
        "bash -c 'while true; do true; done' &",
        "until false; do :; done",
        "python3 -c 'while True: pass' &",
        "node -e 'while(true){}' &",
        "sysbench cpu --threads=8 run",
        "openssl speed -multi 8",
        "some-burner --cpu-load 100 --cpu-method matrixprod",
        'python3 -c "while 1: pass" &',
        "bash <<'EOF'\nyes > /dev/null\nEOF",
        "cat <<EOF\n$(yes > /dev/null)\nEOF",
    ],
)
def test_a_deliberate_load_generator_is_refused(command: str) -> None:
    """B-704: CPU burners and load generators are refused, the alternative named."""
    answer = decide(command)

    assert answer.get("decision") == "block", answer
    reason = str(answer.get("reason"))
    assert "setCPUThrottlingRate" in reason, reason
    assert "never deliberate real load" in reason, reason


@pytest.mark.parametrize(
    "command",
    [
        "yes | head -n 3",
        "yes | npx some-installer",
        "git commit -m 'fix: survive stress in the queue'",
        "echo 'never run yes > /dev/null here'",
        "rg -n -g '*.py' 'stress-ng' scripts",
        "while true; do sleep 5; curl -s --max-time 2 localhost; done",
        "sh scripts/heavy.sh --class test me pytest -n 2",
        "pytest tests/scripts/test_block_load_generators.py",
        "cat > body.md <<'EOF'\nrefuses `yes >` burners and `stress-ng`\nEOF",
        'gh pr create --body-file - <<"EOF"\nwhile true; do :; done is refused\nEOF',
        # A tool's worker count is no load generator.
        "pytest --cpu 4 tests/scripts",
        "make test --cpus 2",
        # A busy loop only named in a quoted string: a commit message, an echo.
        "git commit -m 'fix(hook): refuse while true; do :; done'",
        'echo "a busy loop: while True: pass"',
        "git commit -F - <<'EOF'\nfix(hook): refuse node -e 'while(true){}'\nEOF",
    ],
)
def test_an_ordinary_command_passes(command: str) -> None:
    """A command that only mentions a generator, or uses `yes` to answer prompts, passes."""
    assert decide(command) == {"continue": True}


@pytest.fixture
def listening_port() -> Iterator[int]:
    """A port this test listens on, standing for a harness host already up.

    Yields:
        The port.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        yield int(server.getsockname()[1])
    finally:
        server.close()


def test_a_second_harness_host_is_refused_while_one_listens(listening_port: int) -> None:
    """B-704: the incident started another harness server on 8899 while one listened."""
    command = f"python3 webui/harness/server.py --serve {listening_port} /tmp/served &"

    answer = decide(command, port=listening_port)

    assert answer.get("decision") == "block", answer
    assert "already listens" in str(answer.get("reason")), answer


def test_a_harness_host_may_start_when_none_listens(listening_port: int) -> None:
    """The first harness host is not refused."""
    free = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    free.bind(("127.0.0.1", 0))
    port = int(free.getsockname()[1])
    free.close()

    assert decide(f"python3 webui/harness/server.py --serve {port} /tmp/served &", port=port) == {"continue": True}


def test_the_hook_is_wired_in_the_bash_dispatch() -> None:
    """B-704: the hook runs on every Bash command, through the dispatcher."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["PreToolUse"]
        if group["matcher"] == "Bash"
        for hook in group["hooks"]
    ]

    assert any('"$D/block_load_generators.py"' in command for command in commands), commands
