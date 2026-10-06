"""The ``app.db`` migration scripts are numbered 001, 002, … with no gap and no duplicate.

The migrator skips every script numbered at or below the file's ``user_version`` and
tolerates a gap: a script numbered past a gap, or one sharing its number with another,
is silently never applied to a file already past it. So the numbering is checked here,
read as the migrator reads it.
"""

from __future__ import annotations

from personalscraper.app.store.store import _MIGRATIONS_DIR
from personalscraper.core.sqlite._migrate import _migration_version


def test_the_scripts_are_numbered_contiguously_from_one() -> None:
    """Every ``*.sql`` script parses, and the numbers are exactly 1 to their count."""
    scripts = sorted(path.name for path in _MIGRATIONS_DIR.glob("*.sql"))
    assert scripts, "no migration script found"
    numbers = [_migration_version(_MIGRATIONS_DIR / name) for name in scripts]
    assert sorted(numbers) == list(range(1, len(scripts) + 1)), dict(zip(scripts, numbers, strict=True))
