"""Check that every env key referenced in the codebase is declared in .env.example.

Scans ``personalscraper/`` for ``os.environ.get("KEY")``, ``os.environ["KEY"]``,
and ``os.getenv("KEY")`` calls with a literal string argument, then verifies
every discovered key appears in ``.env.example``.

Exit 0 and prints "0 missing keys" when all keys are documented.
Exit 1 and prints the missing keys (one per line) otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_SOURCE_DIR = _REPO_ROOT / "personalscraper"

# Env keys that are never expected in .env.example because they are
# runtime-only, CI-injected, or stdlib-defined.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Runtime config path override — not a user-facing credential
        # but a bootstrap hook for dev/testing (conf/loader.py:56).
        "PERSONALSCRAPER_CONFIG",
        # Internal: the web /run route sets this in the spawned run's
        # environment so its run_uid matches the pipeline_run history row.
        # Not user config — never set manually in .env.
        "PERSONALSCRAPER_RUN_UID",
    }
)

# Patterns for literal-string env key lookups.
# Group 1 captures the key name.
_RE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # os.environ.get("KEY")  or  os.environ.get("KEY", default)
    re.compile(r"""os\.environ\.get\(\s*["']([^"']+)["']"""),
    # os.environ["KEY"]
    re.compile(r"""os\.environ\[\s*["']([^"']+)["']\s*\]"""),
    # os.getenv("KEY")  or  os.getenv("KEY", default)
    re.compile(r"""os\.getenv\(\s*["']([^"']+)["']"""),
)

# Matches active KEY=VALUE lines and commented-out defaults (# KEY=VALUE).
# Group 1 captures the key name.
_DECL_RE = re.compile(r"^#?\s*([A-Z][A-Z0-9_]*)=.*")


def parse_env_example(path: Path) -> set[str]:
    """Extract declared env keys from *path* (``.env.example``).

    Counts both active ``KEY=VALUE`` lines and commented-out defaults
    (``# KEY=VALUE``) — the latter document the key even when the code
    already ships a sensible default.  Pure comments without a ``KEY=``
    pattern are ignored.
    """
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _DECL_RE.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def scan_source_keys(root: Path) -> set[str]:
    """Walk *root* recursively and extract every env key referenced as a literal string.

    Covers ``os.environ.get("KEY")``, ``os.environ["KEY"]``, and ``os.getenv("KEY")``.
    """
    keys: set[str] = set()
    for py_file in root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for pat in _RE_PATTERNS:
            for m in pat.finditer(text):
                keys.add(m.group(1))
    return keys


def main() -> int:
    """Run the completeness check; return 0 when all keys are documented."""
    if not _ENV_EXAMPLE.is_file():
        print(f"ERROR: {_ENV_EXAMPLE} not found — run from repo root.", file=sys.stderr)
        return 2

    declared = parse_env_example(_ENV_EXAMPLE)
    code_keys = scan_source_keys(_SOURCE_DIR)
    missing = (code_keys - declared) - _ALLOWLIST

    if not missing:
        print("0 missing keys")
        return 0

    for k in sorted(missing):
        print(k)
    print(f"\n{len(missing)} key(s) missing from {_ENV_EXAMPLE.name}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
