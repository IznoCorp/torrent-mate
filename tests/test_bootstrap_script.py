"""Guard: bootstrap-pm2.sh must be fail-fast and reference the allowlisted app names (bosun §10)."""

from __future__ import annotations
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_sh_has_strict_mode_and_app_names() -> None:
    text = (_ROOT / "scripts" / "bootstrap-pm2.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "kanban-km" in text
    assert "kanban-km-serve" in text
    assert "kanban-km-config" in text
    assert "pm2 save" in text
