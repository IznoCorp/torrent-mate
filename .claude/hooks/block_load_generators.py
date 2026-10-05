#!/usr/bin/env python3
"""Block deliberate CPU load on IznoServer, and a second harness host on 8899 (B-704).

On 2026-10-05 a run « reproducing a flake under load » started eight
`( yes > /dev/null & )` burners beside eight parallel browsers and a harness
server on 8899; the load reached 84 on 8 cores until the operator had it killed:
« ça doit plus jamais se reproduire ! ». The operator's rule: never deliberate
real load on this machine. A slowness is reproduced with Playwright's emulated
CPU throttling (CDP ``Emulation.setCPUThrottlingRate``) in one run, or in CI.

Refused:

- ``yes`` written to a file or ``/dev/null`` (``yes >``, ``yes | … > /dev/null``);
  ``yes | cmd`` answering prompts passes;
- ``stress``, ``stress-ng``, ``cpuburn``, ``burnP6``, ``sysbench cpu``,
  ``openssl speed``, and a generator's ``--cpu-load`` / ``--cpu-method`` flags
  (a bare ``--cpu N`` is a tool's worker count: ``pytest --cpu 4`` passes);
- busy loops with an empty body: ``while true; do :; done`` and its shell spellings,
  and the Python and JavaScript ones an interpreter's ``-c`` / ``-e`` runs;
- a harness host (``server.py --serve``, ``http.server``) started on the harness
  port while one already listens there (``LOAD_HOOK_HARNESS_PORT``, 8899).

A generator only MENTIONED in a quoted argument (a commit message, a search
pattern, an ``echo``) or in the body of a heredoc whose delimiter is quoted
(``<<'EOF'``, text no shell expands) passes — unless that heredoc feeds a shell
or an interpreter; the body of ``sh -c '…'`` and ``eval '…'`` is read as a
command, and the program of ``python -c '…'`` / ``node -e '…'`` is read for a
busy loop. This hook catches the deliberate case; ``scripts/heavy.sh``'s
watcher and ``scripts/machine_guard.py`` catch what slips past it.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys

HARNESS_PORT = 8899

# Where a command word may start, and the wrappers that may stand before it.
_START = (
    r"(?:^|[\n;&|(`{]|\$\(|\bthen\b|\bdo\b|\belse\b)\s*"
    r"(?:(?:nohup|exec|command|time|nice(?:\s+-n\s*-?\d+)?|timeout\s+\S+|env(?:\s+\w+=\S*)*)\s+)*"
    r"(?:\S*/)?"
)

# Rules read on the command with its quoted strings removed.
_COMMAND_RULES = (
    ("a `yes` burner written to a file", re.compile(_START + r"yes\b[^;&|\n]*>")),
    ("a `yes` burner piped into /dev/null", re.compile(_START + r"yes\b[^;&\n]*\|[^;&\n]*/dev/null")),
    (
        "a load generator",
        re.compile(_START + r"(?:stress-ng|stress|cpuburn|burnP6|sysbench\s+cpu|openssl\s+speed)\b"),
    ),
)
# A load generator's own flags; a bare `--cpu N` / `--cpus N` is a tool's worker
# count (`pytest --cpu 4`, docker's limit), not a load.
_CPU_FLAG = re.compile(r"(?:^|\s)--cpu-(?:load|method)\b")

# Read on the command with its quoted strings removed, and in the program an
# interpreter's `-c` / `-e` runs: there an interpreter's busy loop sits in quotes.
_BUSY_LOOPS = (
    re.compile(r"\b(?:while\s+(?:true|:|\[\s*1\s*\])|until\s+false)\s*;\s*do\s+(?::|true)?\s*;?\s*done\b"),
    re.compile(r"\bwhile\s+(?:True|1)\s*:\s*pass\b"),
    re.compile(r"(?:\bwhile\s*\(\s*(?:true|1)\s*\)|\bfor\s*\(\s*;\s*;\s*\))\s*\{\s*\}"),
)

_INNER = re.compile(r"""(?:\b(?:ba|z|da)?sh\s+-c|\beval)\s+(?:'([^']*)'|"([^"]*)")""")
_PROGRAM = re.compile(r"""\b(?:python[\d.]*|node|perl|ruby)\s+(?:-\S+\s+)*?-[ce]\s+(?:'([^']*)'|"([^"]*)")""")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
# A heredoc whose delimiter is quoted: its body is literal text, never expanded.
_LITERAL_HEREDOC = re.compile(
    r"""(?P<head>[^\n]*?)<<-?\s*(['"])(?P<tag>\w+)\2(?P<rest>[^\n]*)\n.*?\n\s*(?P=tag)(?=\n|$)""", re.S
)
_INTERPRETER = re.compile(r"(?:^|[\s;&|(/])(?:(?:ba|z|da)?sh|python[\d.]*|node|perl|ruby|osascript|eval|xargs)\b")
_SERVE = re.compile(r"(?:server\.py\s+--serve|http\.server|--serve)\s+(\d+)\b")

_ALTERNATIVE = (
    "The operator's rule: never deliberate real load on IznoServer — no parallel runs to "
    "« reproduce under load », no CPU burners. Reproduce a slowness with Playwright's emulated "
    "CPU throttling (CDP `Emulation.setCPUThrottlingRate`) in ONE run, or in CI. "
    "scripts/heavy.sh's watcher and scripts/machine_guard.py kill a run that saturates the "
    "machine. See CLAUDE.md « The machine »."
)


def without_literal_text(command: str) -> str:
    """The command with the bodies of its quoted-delimiter heredocs removed, save those a program runs.

    Args:
        command: The Bash command.

    Returns:
        The command, each such heredoc reduced to its first line.
    """

    def keep_or_drop(heredoc: re.Match[str]) -> str:
        """A heredoc fed to a shell or an interpreter stays; any other loses its body."""
        if _INTERPRETER.search(heredoc.group("head")):
            return heredoc.group(0)
        return heredoc.group("head") + heredoc.group("rest")

    return _LITERAL_HEREDOC.sub(keep_or_drop, command)


def commands_in(command: str) -> list[str]:
    """The command and the bodies of its ``sh -c`` / ``eval`` strings, quotes removed.

    Args:
        command: The Bash command.

    Returns:
        The texts read as commands.
    """
    texts = [command]
    texts += [single or double for single, double in _INNER.findall(command)]
    return [_QUOTED.sub("", text) for text in texts]


def load_rule(command: str) -> str | None:
    """The deliberate-load rule a command breaks.

    Args:
        command: The Bash command.

    Returns:
        The rule's name, or None when the command breaks none.
    """
    texts = commands_in(command)
    for text in texts:
        for name, pattern in _COMMAND_RULES:
            if pattern.search(text):
                return name
        if _CPU_FLAG.search(text):
            return "a `--cpu-load`-style load flag"
    programs = [single or double for single, double in _PROGRAM.findall(command)]
    if any(pattern.search(text) for text in texts + programs for pattern in _BUSY_LOOPS):
        return "a busy loop"
    return None


def listening(port: int) -> bool:
    """Whether something accepts connections on a loopback port.

    Args:
        port: The port.

    Returns:
        True when a connection is accepted.
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def second_host(command: str, port: int) -> bool:
    """Whether a command starts a harness host on a port where one already listens.

    Args:
        command: The Bash command.
        port: The harness host's port.

    Returns:
        True when it does.
    """
    asked = {int(found) for found in _SERVE.findall(command)}
    return port in asked and listening(port)


def main() -> None:
    """Block a deliberate load generator or a second harness host."""
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"continue": True}))
        return

    if input_data.get("tool_name") != "Bash":
        print(json.dumps({"continue": True}))
        return

    command: str = input_data.get("tool_input", {}).get("command", "")
    rule = load_rule(without_literal_text(command))
    if rule is not None:
        print(json.dumps({"decision": "block", "reason": f"BLOCKED: {rule}. {_ALTERNATIVE}"}))
        return

    port = int(os.environ.get("LOAD_HOOK_HARNESS_PORT", HARNESS_PORT))
    if second_host(command, port):
        reason = (
            f"BLOCKED: a harness host already listens on {port}; a second one races it for the "
            "socket. webui/harness/run.sh reuses or replaces the host itself. " + _ALTERNATIVE
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return

    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
