#!/usr/bin/env python3
"""Project filter in front of the global auto-format hook.

This repository's Markdown, JSON and YAML are not prettier-shaped: BUGS.md and the
register are parsed by scripts, openapi.json and the harness baselines are generated
with their own shape, and a reflow buries a wave's real change. Those extensions are
left untouched; every other edited file goes to the global formatter unchanged.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SKIPPED = {".md", ".json", ".json5", ".yaml", ".yml"}
GLOBAL_HOOK = Path.home() / ".claude" / "hooks" / "auto_format.py"


def main() -> None:
    raw = sys.stdin.read()
    try:
        file_path = json.loads(raw).get("tool_input", {}).get("file_path", "")
    except (json.JSONDecodeError, AttributeError):
        file_path = ""
    if file_path and Path(file_path).suffix.lower() in SKIPPED:
        return
    if not GLOBAL_HOOK.exists():
        return
    subprocess.run([sys.executable, str(GLOBAL_HOOK)], input=raw, text=True, check=False)


if __name__ == "__main__":
    main()
