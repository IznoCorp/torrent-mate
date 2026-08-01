"""Config sync engine — additive deep-merge from config.example to canonical.

Never modifies or removes existing keys.  Reports every addition made.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import json5

from personalscraper.logger import get_logger

log = get_logger("conf.sync")


def _deep_merge_additive(
    example_dict: dict[str, Any],
    target_dict: dict[str, Any],
    *,
    prefix: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Deep-merge *example_dict* into *target_dict* additively.

    For every key in *example_dict*:
    - If the key is absent from *target_dict*, add it (with example value).
    - If both values are dicts, recurse.
    - Otherwise, keep the target value (never overwrite).

    Args:
        example_dict: Source dict (from config.example).
        target_dict: Destination dict (the canonical config).
        prefix: Dot-separated key path for reporting (e.g. ``"paths"``).

    Returns:
        ``(merged_dict, additions)`` where *merged_dict* is the result and
        *additions* is a list of human-readable descriptions.
    """
    result = dict(target_dict)  # shallow copy — recursive calls re-copy
    additions: list[str] = []

    for key, example_val in example_dict.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if key not in result:
            result[key] = example_val
            additions.append(f"add key: {full_key}")
        elif isinstance(example_val, dict) and isinstance(result[key], dict):
            merged_sub, sub_additions = _deep_merge_additive(example_val, result[key], prefix=full_key)
            result[key] = merged_sub
            additions.extend(sub_additions)
        # else: target value exists and is not a dict-to-dict — preserve as-is

    return result, additions


def _files_to_sync(example: Path, target: Path) -> list[tuple[Path, Path, str]]:
    """Enumerate files to sync from *example* to *target*.

    Args:
        example: Source config.example directory.
        target: Destination canonical config directory.

    Returns:
        List of ``(example_path, target_path, action)`` tuples where
        *action* is ``"copy"`` (file missing from target) or ``"merge"``
        (file exists in both — JSON5 deep-merge needed).
    """
    pairs: list[tuple[Path, Path, str]] = []
    for ex_file in sorted(example.iterdir()):
        if not ex_file.is_file():
            continue
        if ex_file.suffix not in (".json5", ".json"):
            continue
        target_file = target / ex_file.name
        if target_file.exists():
            pairs.append((ex_file, target_file, "merge"))
        else:
            pairs.append((ex_file, target_file, "copy"))
    return pairs


def sync_config_dir(
    example: Path,
    target: Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Sync config.example into the canonical config directory.

    Additive only: copies missing files, merges missing keys into existing
    files.  Never modifies or removes an existing key/value.

    Args:
        example: Path to ``config.example/``.
        target: Path to the canonical config directory.
        dry_run: If ``True``, report would-be additions without writing.

    Returns:
        List of human-readable descriptions of every addition.
        Empty if the target is already fully in sync.

    Raises:
        FileNotFoundError: If *example* is not a directory.
    """
    if not example.is_dir():
        raise FileNotFoundError(f"Example directory not found: {example}")

    target.mkdir(parents=True, exist_ok=True)
    pairs = _files_to_sync(example, target)
    all_additions: list[str] = []

    for ex_path, tgt_path, action in pairs:
        if action == "copy":
            msg = f"copy new file: {tgt_path.name}"
            all_additions.append(msg)
            if not dry_run:
                tgt_path.write_text(ex_path.read_text(), encoding="utf-8")
        elif action == "merge":
            ex_data = json5.loads(ex_path.read_text(encoding="utf-8"))
            tgt_data = json5.loads(tgt_path.read_text(encoding="utf-8"))
            merged, additions = _deep_merge_additive(ex_data, tgt_data)
            if additions:
                for a in additions:
                    all_additions.append(f"{tgt_path.name}: {a}")
                if not dry_run:
                    tgt_path.write_text(json5.dumps(merged, indent=2), encoding="utf-8")
            # else: no new keys to add — skip write (preserves comments in
            # untouched sections, but a rewritten file loses hand-written
            # comments in the merged sections — documented in DESIGN §3.3).

    return all_additions
