"""Config sync engine — additive deep-merge from config.example to canonical.

Never modifies or removes existing keys.  Reports every addition made.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import json5

from personalscraper.conf.overlay import ConfigLoadError
from personalscraper.io_utils import atomic_write_text
from personalscraper.logger import get_logger

log = get_logger("conf.sync")


def _write_merge_preserving_mode(path: Path, content: str) -> None:
    """Write *content* to *path* via atomic_write_text, preserving the original mode.

    L11: ``atomic_write_text`` defaults to 0o644.  Stat the file before the
    write and restore its mode afterward so that e.g. a 0o600 config file
    stays 0o600 after a merge update.
    """
    try:
        st_mode = path.stat().st_mode
    except OSError:
        st_mode = None
    atomic_write_text(path, content)
    if st_mode is not None:
        try:
            os.chmod(path, stat.S_IMODE(st_mode))
        except OSError:
            pass


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
    - Otherwise, keep the target value (never overwrite) and report a conflict
      when the types are structurally incompatible (dict vs non-dict).

    Args:
        example_dict: Source dict (from config.example).
        target_dict: Destination dict (the canonical config).
        prefix: Dot-separated key path for reporting (e.g. ``"paths"``).

    Returns:
        ``(merged_dict, report_lines)`` where *merged_dict* is the result and
        *report_lines* is a list of human-readable descriptions.  Addition
        lines are plain strings like ``"add key: <path>"``; conflict lines are
        prefixed ``"conflict (kept target):"``.
    """
    result = dict(target_dict)  # shallow copy — recursive calls re-copy
    report: list[str] = []

    for key, example_val in example_dict.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if key not in result:
            result[key] = example_val
            report.append(f"add key: {full_key}")
        elif isinstance(example_val, dict) and isinstance(result[key], dict):
            merged_sub, sub_report = _deep_merge_additive(example_val, result[key], prefix=full_key)
            result[key] = merged_sub
            report.extend(sub_report)
        else:
            # Key exists in target; only flag when structural types are
            # incompatible (dict vs scalar/list).  Same non-dict types are
            # intentionally silent — the target value is preserved and the
            # example is ignored, which is the normal "user customised" case.
            both_dicts = isinstance(example_val, dict) and isinstance(result[key], dict)
            if not both_dicts and type(example_val) is not type(result[key]):
                report.append(
                    f"conflict (kept target): {full_key} "
                    f"(example={type(example_val).__name__}, target={type(result[key]).__name__})"
                )

    return result, report


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
        List of human-readable descriptions of every addition.  Conflict
        entries (preserved target values with incompatible shapes) are
        prefixed ``"conflict (kept target):"``.  Empty if the target is
        already fully in sync.

    Raises:
        FileNotFoundError: If *example* is not a directory.
        ConfigLoadError: If an example or target file contains malformed
            JSON5 that ``json5`` cannot parse.
    """
    if not example.is_dir():
        raise FileNotFoundError(f"Example directory not found: {example}")

    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
    pairs = _files_to_sync(example, target)
    all_report: list[str] = []
    copied_filenames: set[str] = set()

    for ex_path, tgt_path, action in pairs:
        if action == "copy":
            # Validate the example file parses as valid JSON5 before copying
            # — a malformed example shouldn't silently land in the target.
            try:
                json5.loads(ex_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise ConfigLoadError(f"Malformed JSON5 in example file '{ex_path}': {exc}") from exc
            msg = f"copy new file: {tgt_path.name}"
            all_report.append(msg)
            copied_filenames.add(tgt_path.name)
            if not dry_run:
                atomic_write_text(tgt_path, ex_path.read_text(encoding="utf-8"))
        elif action == "merge":
            try:
                ex_data = json5.loads(ex_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise ConfigLoadError(f"Malformed JSON5 in example file '{ex_path}': {exc}") from exc
            try:
                tgt_data = json5.loads(tgt_path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise ConfigLoadError(f"Malformed JSON5 in target file '{tgt_path}': {exc}") from exc
            merged, report = _deep_merge_additive(ex_data, tgt_data)
            if report:
                for line in report:
                    all_report.append(f"{tgt_path.name}: {line}")
                # M6: only write when the merged dict actually differs from the
                # target — a conflict-only report must NOT rewrite the file
                # (json5.dumps destroys comments, trailing commas, etc.).
                if not dry_run and merged != tgt_data:
                    _write_merge_preserving_mode(tgt_path, json5.dumps(merged, indent=2))

    # ── Overlay registration ──
    # NEW overlay files copied from example must be registered in the target
    # master config.json5 overlays list — otherwise their keys never load.
    if copied_filenames:
        master_name = "config.json5"
        example_master = example / master_name
        target_master = target / master_name
        if example_master.is_file() and target_master.is_file():
            try:
                ex_master_data = json5.loads(example_master.read_text(encoding="utf-8"))
            except ValueError:
                ex_master_data = {}
            try:
                tgt_master_data = json5.loads(target_master.read_text(encoding="utf-8"))
            except ValueError:
                tgt_master_data = {}
            ex_overlays_raw = ex_master_data.get("overlays", [])
            tgt_overlays_raw = tgt_master_data.get("overlays", [])

            # M7/M8: guard against non-list overlays (dict, int, etc.) —
            # ``list()`` on a non-iterable raises TypeError through the CLI.
            if isinstance(tgt_overlays_raw, list) and isinstance(ex_overlays_raw, list):
                ex_overlays: list[str] = list(ex_overlays_raw)
                tgt_overlays: list[str] = list(tgt_overlays_raw)
                tgt_overlay_set = set(tgt_overlays)

                new_overlays: list[str] = []
                for name in ex_overlays:
                    if name in copied_filenames and name not in tgt_overlay_set:
                        new_overlays.append(name)

                # L10: report registration in dry-run too (preview parity).
                if new_overlays:
                    for name in new_overlays:
                        all_report.append(f"register overlay: {name}")
                    if not dry_run:
                        tgt_overlays.extend(new_overlays)
                        tgt_master_data["overlays"] = tgt_overlays
                        atomic_write_text(target_master, json5.dumps(tgt_master_data, indent=2))
            else:
                # M7/M8: non-list overlays — cannot register, report as conflict.
                overlay_names: list[str] = []
                if isinstance(ex_overlays_raw, list):
                    overlay_names = [str(n) for n in ex_overlays_raw]
                new_names = [n for n in overlay_names if n in copied_filenames]
                if new_names:
                    all_report.append(
                        f"conflict (kept target): overlays not a list — cannot register: {', '.join(new_names)}"
                    )

    return all_report
