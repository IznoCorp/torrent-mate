#!/usr/bin/env python3
"""Forbid dict[str, Any] in public api/ surface and direct HttpTransport construction."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent / "personalscraper" / "api"
DICT_PATTERN = re.compile(r"dict\[\s*str\s*,\s*Any\s*\]")
TRANSPORT_PATTERN = re.compile(r"HttpTransport\(\s*.*provider_name\s*=")

violations: list[str] = []
for py in ROOT.rglob("*.py"):
    if py.name.startswith("_") or py.parent.name.startswith("_"):
        continue
    for i, line in enumerate(py.read_text().splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if DICT_PATTERN.search(line):
            violations.append(f"{py}:{i}: dict[str, Any] — {line.strip()}")
        if TRANSPORT_PATTERN.search(line):
            violations.append(f"{py}:{i}: HttpTransport constructed without TransportPolicy — {line.strip()}")

if violations:
    print("api/ guardrail violations:", file=sys.stderr)
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    sys.exit(1)
