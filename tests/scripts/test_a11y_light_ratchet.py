"""Holds on the light-theme ratchet: its bound must move with its subject.

The ratchet read `counts.total` and nothing else, so editing that one integer
to 99999 raised the ceiling by 165 834 without touching a single recorded
finding — and no gate anywhere compared the summary to the list it summarises.
A ratchet whose bound can be moved without moving its subject is a tolerance
wearing a ratchet's name, which is precisely what `a11y-debt.json` refuses to
be and what this file was written to be instead.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAQUETTE = ROOT / "frontend" / "maquette"


@pytest.fixture(name="audit")
def audit_fixture():
    """Imports `a11y.py`, which reaches its siblings by path.

    Returns:
        The module object.
    """
    sys.path.insert(0, str(MAQUETTE))
    try:
        spec = importlib.util.spec_from_file_location("a11y", MAQUETTE / "a11y.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["a11y"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(MAQUETTE))


def test_the_ceiling_is_the_recorded_findings(audit):
    """The bound is a sum over the list, not a number written beside it.

    Args:
        audit: The loaded module.
    """
    recorded = json.loads(audit.LIGHT_DEBT_FILE.read_text(encoding="utf-8"))
    listed = sum(len(finding["targets"]) for findings in recorded["states"].values() for finding in findings)
    assert audit.light_ceiling() == listed


def test_editing_only_the_summary_is_refused(audit, tmp_path, monkeypatch):
    """99999 in `counts.total` must not become the ceiling.

    Args:
        audit: The loaded module.
        tmp_path: pytest's per-test directory.
        monkeypatch: pytest's patcher.
    """
    recorded = json.loads(audit.LIGHT_DEBT_FILE.read_text(encoding="utf-8"))
    recorded["counts"]["total"] = 99999
    forged = tmp_path / "a11y-light-debt.json"
    forged.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(audit, "LIGHT_DEBT_FILE", forged)
    with pytest.raises(RuntimeError, match="99999"):
        audit.light_ceiling()


def test_an_absent_file_is_not_a_ceiling_of_zero(audit, tmp_path, monkeypatch):
    """None is refused by the caller; zero and infinity would both be wrong.

    Args:
        audit: The loaded module.
        tmp_path: pytest's per-test directory.
        monkeypatch: pytest's patcher.
    """
    monkeypatch.setattr(audit, "LIGHT_DEBT_FILE", tmp_path / "absent.json")
    assert audit.light_ceiling() is None
