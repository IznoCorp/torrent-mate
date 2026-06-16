"""Tests for the advisory ingress + multi-project doctor checks (ingress-multiproject §8 / §9).

Both checks are ADVISORY — always ``ok=True`` (ingress is config, not a launch gate). Covers the
webhook-secret presence/perms WARNINGs and the registry summary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from kanbanmate.cli.doctor_ingress import check_registry_summary, check_webhook_secret


def _register(root: Path, pid: str, *, repo: str = "o/r", ingress: str = "webhook") -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "projects.json"
    reg = json.loads(path.read_text()) if path.exists() else {}
    reg[pid] = {
        "repo": repo,
        "clone": "/c",
        "project_id": pid,
        "status_field_node_id": "F",
        "ingress": ingress,
    }
    path.write_text(json.dumps(reg), encoding="utf-8")


def test_webhook_secret_skip_when_all_polling(tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A", ingress="polling")
    name, ok, detail = check_webhook_secret(tmp_path)
    assert ok is True
    assert "skipped" in detail


def test_webhook_secret_missing_warns(tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A", ingress="webhook")
    name, ok, detail = check_webhook_secret(tmp_path)
    assert ok is True  # advisory — never FAIL
    assert "WARNING" in detail and "missing" in detail


def test_webhook_secret_present_0600_passes(tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A", ingress="webhook")
    secret = tmp_path / "webhook_secret"
    secret.write_text("s")
    os.chmod(secret, 0o600)
    name, ok, detail = check_webhook_secret(tmp_path)
    assert ok is True
    assert "present (0600)" in detail


def test_webhook_secret_placeholder_warns(tmp_path: Path) -> None:
    """#3: a present-but-placeholder (comment-only) secret WARNs (serve would refuse to start)."""
    from kanbanmate.cli.init import _WEBHOOK_SECRET_PLACEHOLDER

    _register(tmp_path, "PVT_A", ingress="webhook")
    secret = tmp_path / "webhook_secret"
    secret.write_text(_WEBHOOK_SECRET_PLACEHOLDER, encoding="utf-8")
    os.chmod(secret, 0o600)
    name, ok, detail = check_webhook_secret(tmp_path)
    assert ok is True  # advisory — never FAIL
    assert "WARNING" in detail and "placeholder" in detail


def test_webhook_secret_loose_perms_warns(tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A", ingress="webhook")
    secret = tmp_path / "webhook_secret"
    secret.write_text("s")
    os.chmod(secret, 0o644)  # group/other readable
    name, ok, detail = check_webhook_secret(tmp_path)
    assert ok is True
    assert "WARNING" in detail and "0600" in detail


def test_registry_summary_lists_ingress_modes(tmp_path: Path) -> None:
    _register(tmp_path, "PVT_A", repo="o/r1", ingress="polling")
    _register(tmp_path, "PVT_B", repo="o/r2", ingress="webhook")
    name, ok, detail = check_registry_summary(tmp_path)
    assert ok is True
    assert "2 enabled project(s)" in detail
    assert "o/r1=polling" in detail and "o/r2=webhook" in detail


def test_registry_summary_skip_when_empty(tmp_path: Path) -> None:
    name, ok, detail = check_registry_summary(tmp_path)
    assert ok is True
    assert "skipped" in detail
