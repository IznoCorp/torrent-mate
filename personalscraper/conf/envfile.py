"""Shared .env file operations — upsert and catalog parsing.

Provides atomic, comment-preserving upsert of KEY=value pairs into a
``.env`` file, and a catalog parser that reads ``.env.example`` to
enumerate known keys without ever touching the real ``.env``.
"""

from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path

from personalscraper.io_utils import atomic_write_text

#: Characters forbidden in .env values because they act as line separators in
#: ``str.splitlines()`` (which is Python's default when re-parsing a text file).
#: A value containing any of these could inject a fake ``KEY=value`` line on a
#: later upsert.  This set covers every character *c* where
#: ``("x" + c + "y").splitlines()`` has ``len != 1``.
FORBIDDEN_CONTROL_CHARS: frozenset[str] = frozenset(
    {
        "\n",
        "\r",
        "\x0b",
        "\x0c",
        "\x1c",
        "\x1d",
        "\x1e",
        "\x85",
        " ",
        " ",
    }
)


def write_env_keys(keys: dict[str, str], env_path: Path) -> None:
    """Atomically upsert KEY=value pairs into a .env file.

    Existing lines whose key matches one in *keys* are replaced in place;
    every other line (comments, blanks, unrelated keys) is preserved.
    Keys not already present are appended.  The write is atomic and
    crash-durable via :func:`personalscraper.io_utils.atomic_write_text`
    (temp file + fsync + rename + parent-dir fsync), then chmod-ed back to
    ``0o600`` because the shared writer creates its temp world-readable and
    a ``.env`` holds secrets.  Secret values are never logged by this
    function.

    Args:
        keys: Mapping of KEY → value to upsert.
        env_path: Path to the .env file (created if absent).
    """
    # Defense in depth: reject control characters that could inject new
    # KEY=value lines when the value is written verbatim.
    for _key, _val in keys.items():
        if any(c in _val for c in FORBIDDEN_CONTROL_CHARS):
            raise ValueError(f"Value for {_key!r} contains control characters")

    existing_lines: list[str] = []
    if env_path.exists():
        # Use "\n" (not splitlines) so that characters like \x0b, \x1c, …
        # that splitlines treats as separators do NOT inject fake lines.
        text = env_path.read_text(encoding="utf-8")
        existing_lines = text.split("\n")
        # .split("\n") on "a\nb\n" yields ["a", "b", ""] — one more
        # trailing empty than splitlines().  Drop it so the join below
        # doesn't inject an extra blank line.
        if existing_lines and existing_lines[-1] == "":
            existing_lines.pop()

    seen: set[str] = set()
    out_lines: list[str] = []
    for line in existing_lines:
        stripped = line.lstrip()
        key = stripped.split("=", 1)[0] if ("=" in stripped and not stripped.startswith("#")) else None
        if key is not None and key in keys:
            out_lines.append(f"{key}={keys[key]}")
            seen.add(key)
        else:
            out_lines.append(line)
    for key, value in keys.items():
        if key not in seen:
            out_lines.append(f"{key}={value}")

    content = "\n".join(out_lines) + "\n"

    try:
        atomic_write_text(env_path, content)
        # The shared writer creates its temp at 0o644; a .env holds secrets
        # and must stay owner-only, matching the previous mkstemp(0o600) write.
        os.chmod(env_path, 0o600)
    except BaseException:
        # atomic_write_text leaves its "<name>.tmp" behind only if the write
        # itself fails; drop it so a failed write leaves no orphan temp file.
        with contextlib.suppress(OSError):
            os.unlink(env_path.with_suffix(env_path.suffix + ".tmp"))
        raise


def read_env_catalog(env_example_path: Path) -> dict[str, str]:
    """Parse .env.example into {KEY: description} catalog.

    A catalog entry is any line matching ``^[A-Z][A-Z0-9_]*=``.  Its
    description is the concatenation of the contiguous ``#`` comment lines
    immediately above it (with the leading ``# `` stripped), excluding
    section-rule lines that start with ``# ──``.  A blank line breaks the
    comment run.  Keys with no preceding comment get ``""``.

    Args:
        env_example_path: Path to the ``.env.example`` file.

    Returns:
        Mapping of KEY → description for every key declared in the file.
    """
    catalog: dict[str, str] = {}
    comment_lines: list[str] = []

    for line in env_example_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped:
            comment_lines = []
            continue

        if stripped.startswith("#"):
            content = stripped[1:].lstrip()
            # Section-rule lines (──) reset the comment accumulator;
            # they describe the following keys but are not descriptions themselves.
            if content.startswith("──"):
                comment_lines = []
                continue
            comment_lines.append(content)
            continue

        match = re.match(r"^([A-Z][A-Z0-9_]*)=.*", stripped)
        if match:
            key = match.group(1)
            catalog[key] = " ".join(comment_lines)
            comment_lines = []

    return catalog
