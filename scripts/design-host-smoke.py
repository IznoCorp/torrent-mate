#!/usr/bin/env python3
"""The design host's post-deploy smoke check: every v1 GET it serves, called as the owner.

After each redeploy the check opens an owner session through the dev-only CLI
(``personalscraper accounts open-session --owner``), holds its token in memory only, calls
every ``get`` operation of the contract under ``/api/v1`` and signs out in a ``finally``. The
contract is read, not a hand list, so a new v1 GET is probed the day it ships.

Required parameters are filled by NAME from ``PARAM_SOURCES``, drawn from the first
``readLibraryItems`` item. A required parameter with no source is red
(``unresolvable parameter <name>``), so a new parameter forces its source to be written.

Red is: any status of 400 or more, bar the pairs in ``ALLOWED_STATUSES`` (a title with no
poster is a 404), an empty library, a host that does not answer (the round stops at the first
such GET), an unexpected failure (``internal.<ExceptionName>``), or a CLI that gives no token
(``cli.no_token.<exit code>``, its last stderr line going to stderr).

Output is ``SMOKE OK <n> GETs`` or one ``SMOKE RED <operationId> <status> <code>`` line per
failure, exit 1 on red, a failure of the smoke itself included. The token is never printed,
whatever happens.

Usage:
    python scripts/design-host-smoke.py --base http://127.0.0.1:8713 [--contract contract/openapi.generated.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from _repo_paths import SERVED_CONTRACT

API_PREFIX: Final = "/api/v1"
SESSION_COOKIE: Final = "tm_v1_session"
LIBRARY_OPERATION: Final = "readLibraryItems"
SIGN_OUT_PATH: Final = "/auth/logout"
# The only ``(operationId, status)`` pairs at 400 or more that are not red.
ALLOWED_STATUSES: Final = frozenset({("readMediaPoster", 404)})
CLI_COMMAND: Final = (sys.executable, "-m", "personalscraper", "accounts", "open-session", "--owner")
TIMEOUT_SECONDS: Final = 30

# Each required parameter name maps to how it is read from the first library item's ``ids``
# (a provider name and its id). A new required parameter name needs its source written here.
PARAM_SOURCES: Final[Mapping[str, Callable[[Mapping[str, Any]], str]]] = {
    "provider": lambda ids: next(iter(ids)),
    "providerId": lambda ids: str(next(iter(ids.values()))),
}


class Red(Exception):
    """One failure, worded as the three fields of a ``SMOKE RED`` line."""

    def __init__(self, operation: str, status: int, code: str) -> None:
        """Keep the fields.

        Args:
            operation: The operation id.
            status: The HTTP status, 0 when none was answered.
            code: The problem's code, or a short reason.
        """
        super().__init__(f"{operation} {status} {code}")
        self.operation = operation
        self.status = status
        self.code = code

    def line(self) -> str:
        """Word the failure.

        Returns:
            The ``SMOKE RED`` line.
        """
        return f"SMOKE RED {self.operation} {self.status} {self.code}"


def open_token(cli: Sequence[str]) -> str:
    """Run the CLI as a child process and keep its token in memory.

    Args:
        cli: The command that prints a session token alone on stdout.

    Returns:
        The token.

    Raises:
        Red: The CLI failed to start, exited non-zero, or printed nothing. In the last two cases
            its last stderr line has been written to stderr.
    """
    try:
        done = subprocess.run(list(cli), capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Red("openSession", 0, "cli.unavailable") from None
    token = done.stdout.strip()
    if done.returncode != 0 or not token:
        reason = done.stderr.strip().splitlines()[-1:]
        if reason:
            print(reason[0], file=sys.stderr)
        raise Red("openSession", done.returncode, f"cli.no_token.{done.returncode}")
    return token


def call(base: str, method: str, path: str, token: str) -> tuple[int, Any]:
    """Send one request as the session and read the answer.

    Args:
        base: The host's base URL.
        method: The HTTP method.
        path: The path under ``/api/v1``, query included.
        token: The session value.

    Returns:
        The status and the decoded JSON body (``None`` when it is not JSON).

    Raises:
        OSError: The host did not answer.
    """
    request = urllib.request.Request(
        f"{base.rstrip('/')}{API_PREFIX}{path}",
        method=method,
        data=b"" if method == "POST" else None,
        headers={"Cookie": f"{SESSION_COOKIE}={token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - the base is an operator argument
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, None


def get_operations(contract: Path) -> list[tuple[str, str, list[str]]]:
    """List the contract's GETs, the library listing first (it holds the parameters' sample).

    Args:
        contract: The OpenAPI document.

    Returns:
        ``(operation id, path template, required parameter names)`` per GET.
    """
    paths = json.loads(contract.read_text())["paths"]
    found = []
    for template, item in paths.items():
        operation = item.get("get")
        if operation is None:
            continue
        required = [p["name"] for p in operation.get("parameters", []) if p.get("required")]
        found.append((operation.get("operationId", template), template, required))
    return sorted(found, key=lambda op: op[0] != LIBRARY_OPERATION)


def fill(template: str, names: Sequence[str], ids: Mapping[str, Any] | None, operation: str) -> str:
    """Fill a GET's required parameters from the sample, path ones in place and query ones appended.

    Args:
        template: The path template.
        names: The required parameter names.
        ids: The first library item's ``ids``, or ``None`` when there is none.
        operation: The operation id, for the failure.

    Returns:
        The path with its query.

    Raises:
        Red: A required parameter has no source, or the sample is missing.
    """
    values: dict[str, str] = {}
    for name in names:
        source = PARAM_SOURCES.get(name)
        if source is None:
            raise Red(operation, 0, f"unresolvable parameter {name}")
        if not ids:
            raise Red(operation, 0, f"no sample for parameter {name}")
        values[name] = source(ids)
    path = template
    query = {}
    for name, value in values.items():
        if "{" + name + "}" in path:
            path = path.replace("{" + name + "}", urllib.parse.quote(value, safe=""))
        else:
            query[name] = value
    return f"{path}?{urllib.parse.urlencode(query)}" if query else path


def check(base: str, contract: Path, token: str) -> tuple[int, list[Red]]:
    """Call every GET of the contract and collect the failures.

    Args:
        base: The host's base URL.
        contract: The OpenAPI document.
        token: The session value.

    Returns:
        How many GETs were called, and the failures.
    """
    reds: list[Red] = []
    called = 0
    ids: Mapping[str, Any] | None = None
    for operation, template, names in get_operations(contract):
        try:
            path = fill(template, names, ids, operation)
            status, body = call(base, "GET", path, token)
            called += 1
            problem = body.get("code") if isinstance(body, dict) else None
            code = str(problem) if problem else "-"
            if operation == LIBRARY_OPERATION:
                if status != 200:
                    raise Red(operation, status, code)
                items = body.get("items") if isinstance(body, dict) else None
                if not items:
                    raise Red(operation, status, "library.empty")
                ids = items[0].get("ids")
            elif status >= 400 and (operation, status) not in ALLOWED_STATUSES:
                raise Red(operation, status, code)
        except Red as red:
            reds.append(red)
        except OSError:
            reds.append(Red(operation, 0, "host.unreachable"))
            break
        except Exception as exc:  # noqa: BLE001 - any failure must be named, or the watcher stays mute
            reds.append(Red(operation, 0, f"internal.{type(exc).__name__}"))
    return called, reds


def sign_out(base: str, token: str) -> None:
    """Close the session; any failure is left silent, the session expires on its own.

    Args:
        base: The host's base URL.
        token: The session value.
    """
    try:
        call(base, "POST", SIGN_OUT_PATH, token)
    except Exception:  # noqa: BLE001, S110 - the verdict stands, whatever the sign-out does
        pass


def _verdict(base: str, contract: Path, cli: Sequence[str]) -> int:
    """Open the session, check, sign out and print the verdict.

    Args:
        base: The host's base URL.
        contract: The OpenAPI document.
        cli: The command that opens the owner's session.

    Returns:
        0 when green, 1 on any red.
    """
    try:
        token = open_token(cli)
    except Red as red:
        print(red.line())
        return 1
    try:
        called, reds = check(base, contract, token)
    finally:
        sign_out(base, token)
    if reds:
        for red in reds:
            print(re.sub(r"\s+", " ", red.line()).replace(token, "***"))
        return 1
    print(f"SMOKE OK {called} GETs")
    return 0


def main(argv: Sequence[str] | None = None, cli: Sequence[str] = CLI_COMMAND) -> int:
    """Run the smoke and print its verdict.

    Args:
        argv: The arguments (``--base``, ``--contract``); the process's when ``None``.
        cli: The command that opens the owner's session (a seam for the tests).

    Returns:
        0 when green, 1 on any red.
    """
    parser = argparse.ArgumentParser(description="Call every v1 GET of the design host as the owner.")
    parser.add_argument("--base", required=True, help="the host's base URL, e.g. http://127.0.0.1:8713")
    parser.add_argument("--contract", type=Path, default=SERVED_CONTRACT, help="the OpenAPI document")
    args = parser.parse_args(argv)

    try:
        return _verdict(args.base, args.contract, cli)
    except Exception as exc:  # noqa: BLE001 - last resort: the watcher greps for ``SMOKE RED``
        print(f"SMOKE RED - 0 internal.{type(exc).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
