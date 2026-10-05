#!/usr/bin/env python3
"""The design host's post-deploy smoke check: every v1 GET it serves, called as the owner.

After each redeploy the check opens an owner session through the dev-only CLI
(``personalscraper accounts open-session --owner``), holds its token in memory only, calls
every ``get`` operation of the contract under ``/api/v1`` and signs out in a ``finally``. The
contract is read, not a hand list, so a new v1 GET is probed the day it ships.

Required parameters are filled by NAME from ``PARAM_SOURCES``, drawn from the first
``readLibraryItems`` item. A required parameter with no source is red
(``unresolvable parameter <name>``), so a new parameter forces its source to be written.

Red is: a status of 500 or more, a 401 anywhere, an empty library, a host that does not
answer, or a CLI that gives no token. Any other 4xx is not red (a poster may be a 404).

Output is ``SMOKE OK <n> GETs`` or one ``SMOKE RED <operationId> <status> <code>`` line per
failure, exit 1 on red. The token is never printed, whatever happens.

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

API_PREFIX: Final = "/api/v1"
SESSION_COOKIE: Final = "tm_v1_session"
LIBRARY_OPERATION: Final = "readLibraryItems"
SIGN_OUT_PATH: Final = "/auth/logout"
DEFAULT_CONTRACT: Final = Path(__file__).resolve().parents[1] / "contract" / "openapi.generated.json"
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
        Red: The CLI failed to start, exited non-zero, or printed nothing.
    """
    try:
        done = subprocess.run(list(cli), capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Red("openSession", 0, "cli.unavailable") from None
    token = done.stdout.strip()
    if done.returncode != 0 or not token:
        raise Red("openSession", done.returncode, "cli.no_token")
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
        except Red as red:
            reds.append(red)
            continue
        except OSError:
            reds.append(Red(operation, 0, "host.unreachable"))
            continue
        called += 1
        problem = body.get("code") if isinstance(body, dict) else None
        code = str(problem) if problem else "-"
        if status >= 500 or status == 401:
            reds.append(Red(operation, status, code))
        elif operation == LIBRARY_OPERATION and status == 200:
            items = body.get("items") if isinstance(body, dict) else None
            if items:
                ids = items[0].get("ids")
            else:
                reds.append(Red(operation, status, "library.empty"))
    return called, reds


def sign_out(base: str, token: str) -> None:
    """Close the session; a failure is left silent, the session expires on its own.

    Args:
        base: The host's base URL.
        token: The session value.
    """
    try:
        call(base, "POST", SIGN_OUT_PATH, token)
    except OSError:
        pass


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
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT, help="the OpenAPI document")
    args = parser.parse_args(argv)

    try:
        token = open_token(cli)
    except Red as red:
        print(red.line())
        return 1
    try:
        called, reds = check(args.base, args.contract, token)
    finally:
        sign_out(args.base, token)
    if reds:
        for red in reds:
            print(re.sub(r"\s+", " ", red.line()).replace(token, "***"))
        return 1
    print(f"SMOKE OK {called} GETs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
