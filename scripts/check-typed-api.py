#!/usr/bin/env python3
"""Forbid dict[str, Any] in public api/ surface and direct HttpTransport construction.

Rule (DESIGN S13.3 — refined):
  - Files starting with ``_`` (private modules like ``_base.py``, ``_factory.py``)
    are skipped entirely.
  - Within public files (e.g. ``tmdb.py``), the script only flags ``dict[str, Any]``
    when it appears in the signature of a **public** function or method (one whose
    name does NOT start with ``_``). Private helpers (``_parse_*``, ``_assert_*``)
    and local variable annotations are allowed — they are implementation details,
    not API surface.
  - ``HttpTransport(...)`` calls outside transport internals must construct via a
    TransportPolicy keyword (``provider_name=...`` positional/kwarg-without-policy
    is forbidden — must pass a built TransportPolicy instance).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent / "personalscraper" / "api"
DICT_PATTERN = re.compile(r"dict\[\s*str\s*,\s*Any\s*\]")
PUBLIC_DEF_PATTERN = re.compile(r"^\s*(?:async\s+)?def\s+(?!_)([A-Za-z][A-Za-z0-9_]*)\s*\(")
TRANSPORT_PATTERN = re.compile(r"HttpTransport\(\s*.*provider_name\s*=")


def _signature_lines(source: str) -> set[int]:
    """Return the 1-based line numbers that belong to a public function signature.

    A public def starts at a line matching ``def <name>(`` (where ``<name>`` does
    not start with ``_``); the signature continues until the line containing
    ``):`` or ``) ->`` followed by ``:`` is found.
    """
    lines = source.splitlines()
    flagged: set[int] = set()
    in_sig = False
    for idx, raw in enumerate(lines, 1):
        if not in_sig:
            if PUBLIC_DEF_PATTERN.match(raw):
                in_sig = True
                flagged.add(idx)
                if re.search(r"\)\s*(?:->[^:]*)?:\s*(#.*)?$", raw):
                    in_sig = False
        else:
            flagged.add(idx)
            if re.search(r"\)\s*(?:->[^:]*)?:\s*(#.*)?$", raw):
                in_sig = False
    return flagged


violations: list[str] = []
for py in ROOT.rglob("*.py"):
    if py.name.startswith("_") or py.parent.name.startswith("_"):
        continue
    source = py.read_text()
    sig_lines = _signature_lines(source)
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if DICT_PATTERN.search(line) and i in sig_lines:
            violations.append(f"{py}:{i}: dict[str, Any] in public signature — {line.strip()}")
        if TRANSPORT_PATTERN.search(line):
            violations.append(f"{py}:{i}: HttpTransport constructed without TransportPolicy — {line.strip()}")

if violations:
    print("api/ guardrail violations:", file=sys.stderr)
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    sys.exit(1)
