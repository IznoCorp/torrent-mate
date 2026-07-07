"""Shared .env file operations — upsert and catalog parsing.

Provides atomic, comment-preserving upsert of KEY=value pairs into a
``.env`` file, and a catalog parser that reads ``.env.example`` to
enumerate known keys without ever touching the real ``.env``.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from pathlib import Path


def write_env_keys(keys: dict[str, str], env_path: Path) -> None:
    """Atomically upsert KEY=value pairs into a .env file.

    Existing lines whose key matches one in *keys* are replaced in place;
    every other line (comments, blanks, unrelated keys) is preserved.
    Keys not already present are appended.  The write is atomic via a
    same-directory temp file plus ``os.replace``.  Secret values are never
    logged by this function.

    Args:
        keys: Mapping of KEY → value to upsert.
        env_path: Path to the .env file (created if absent).
    """
    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

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

    fd, tmp_name = tempfile.mkstemp(dir=str(env_path.parent), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_name, env_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
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
