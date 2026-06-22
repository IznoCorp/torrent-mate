"""Guard: deploy scripts must fail-fast (set -euo pipefail) with pip BEFORE restart (bosun §8/ACC-06)."""

from __future__ import annotations
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_deploy_sh_has_strict_mode_and_pip_before_restart() -> None:
    text = (_ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    pip_idx = text.index("pip install -e .")
    restart_idx = text.index("pm2 restart")
    assert pip_idx < restart_idx, "pip install must precede pm2 restart (no half-deployed serve)"


def test_deploy_staging_sh_has_strict_mode() -> None:
    text = (_ROOT / "scripts" / "deploy-staging.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "kanban-staging-config" in text
