"""Regression tests for .env.example completeness.

Ensures every ``os.environ`` / ``os.getenv`` key referenced in the codebase
is declared in ``.env.example``, and that the three keys added in §12.2
(tech-debt phase 12) are present.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHECK_SCRIPT = _REPO_ROOT / "scripts" / "check_env_keys.py"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"

# §12.2 keys — must be present in .env.example forever.
_KEYS_12_2: tuple[str, ...] = (
    "OMDB_API_KEY",
    "OMDB_DAILY_LIMIT",
    "LIBRARY_ANALYZER_MAX_WORKERS",
)


def _parse_env_keys(path: Path) -> set[str]:
    """Extract declared keys from .env.example (active + commented-out defaults)."""
    import re

    decl_re = re.compile(r"^#?\s*([A-Z][A-Z0-9_]*)=.*")
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = decl_re.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def test_env_example_completeness() -> None:
    """The check script must report zero missing keys."""
    result = subprocess.run(
        [sys.executable, str(_CHECK_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"check_env_keys.py exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "0 missing keys" in result.stdout, f"Expected '0 missing keys' in output, got:\n{result.stdout}"


def test_section_12_2_keys_present() -> None:
    """Sanity guard: the three §12.2 keys must be declared in .env.example."""
    declared = _parse_env_keys(_ENV_EXAMPLE)
    for key in _KEYS_12_2:
        assert key in declared, f"§12.2 key {key!r} is missing from {_ENV_EXAMPLE} — was it accidentally deleted?"
