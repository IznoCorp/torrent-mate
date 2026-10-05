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
  ``openssl speed``, and ``--cpu N``-style load flags (save docker/podman's limits);
- busy loops with an empty body: ``while true; do :; done`` and its shell,
  Python and JavaScript spellings;
- a harness host (``server.py --serve``, ``http.server``) started on the harness
  port while one already listens there (``LOAD_HOOK_HARNESS_PORT``, 8899).

A generator only MENTIONED in a quoted argument (a commit message, a search
pattern, an ``echo``) passes; the body of ``sh -c '…'`` and ``eval '…'`` is read
as a command. This hook catches the deliberate case; ``scripts/heavy.sh``'s
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
_CPU_FLAG = re.compile(r"(?:^|\s)--cpu(?:s|-load|-method)?[= ]+\d+")
_CONTAINER = re.compile(r"\b(?:docker|podman)\b")

# Rules read on the raw command: an interpreter's busy loop sits inside quotes.
_BUSY_LOOPS = (
    re.compile(r"\b(?:while\s+(?:true|:|\[\s*1\s*\])|until\s+false)\s*;\s*do\s+(?::|true)?\s*;?\s*done\b"),
    re.compile(r"\bwhile\s+(?:True|1)\s*:\s*pass\b"),
    re.compile(r"(?:\bwhile\s*\(\s*(?:true|1)\s*\)|\bfor\s*\(\s*;\s*;\s*\))\s*\{\s*\}"),
)

_INNER = re.compile(r"""(?:\b(?:ba|z|da)?sh\s+-c|\beval)\s+(?:'([^']*)'|"([^"]*)")""")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_SERVE = re.compile(r"(?:server\.py\s+--serve|http\.server|--serve)\s+(\d+)\b")

_ALTERNATIVE = (
    "The operator's rule: never deliberate real load on IznoServer — no parallel runs to "
    "« reproduce under load », no CPU burners. Reproduce a slowness with Playwright's emulated "
    "CPU throttling (CDP `Emulation.setCPUThrottlingRate`) in ONE run, or in CI. "
    "scripts/heavy.sh's watcher and scripts/machine_guard.py kill a run that saturates the "
    "machine. See CLAUDE.md « The machine »."
)


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
    for text in commands_in(command):
        for name, pattern in _COMMAND_RULES:
            if pattern.search(text):
                return name
        if _CPU_FLAG.search(text) and not _CONTAINER.search(text):
            return "a `--cpu N` load flag"
    if any(pattern.search(command) for pattern in _BUSY_LOOPS):
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
    rule = load_rule(command)
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
