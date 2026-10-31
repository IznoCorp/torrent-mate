"""``compare-contracts.py --have v1``: the contract against the v1 application, v0's register untouched."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "compare-contracts.py"


def _load() -> ModuleType:
    """Import the script, despite its hyphenated filename.

    Returns:
        The script's module.
    """
    spec = importlib.util.spec_from_file_location("compare_contracts", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # A dataclass resolves its module through sys.modules while the class is built.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


compare = _load()


def _operation(operation_id: str, status: str = "200", names: tuple[str, ...] = ("version",)) -> dict[str, Any]:
    """One operation answering an object with the given property names.

    Args:
        operation_id: Its ``operationId``.
        status: Its success status.
        names: Its answer's property names.

    Returns:
        The operation object.
    """
    schema = {"type": "object", "properties": {name: {"type": "string"} for name in names}}
    return {
        "operationId": operation_id,
        "summary": operation_id,
        "responses": {status: {"description": "ok", "content": {"application/json": {"schema": schema}}}},
    }


def _write(path: Path, document: dict[str, Any]) -> Path:
    """Write one planted document.

    Args:
        path: Where.
        document: The document.

    Returns:
        The path.
    """
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _planted(tmp_path: Path, served: dict[str, Any]) -> tuple[str, dict[str, int]]:
    """Compare a planted contract (``/x`` and ``/y`` under ``/api/v1``) against a planted v1 document.

    Args:
        tmp_path: Where the documents are written.
        served: The planted v1 document's paths.

    Returns:
        The register and its counts.
    """
    contract = {
        "openapi": "3.1.0",
        "servers": [{"url": "/api/v1"}],
        "paths": {"/x": {"get": _operation("readX")}, "/y": {"get": _operation("readY")}},
        "components": {"schemas": {}},
    }
    backend = replace(
        compare.BACKENDS["v1"],
        document=_write(tmp_path / "v1.json", {"openapi": "3.1.0", "paths": served, "components": {}}),
    )
    result: tuple[str, dict[str, int]] = compare.compute(backend, _write(tmp_path / "contract.json", contract))
    return result


def test_v1_reports_the_unserved_operation_and_nothing_for_the_matched_one(tmp_path: Path) -> None:
    """v1's ``/x`` is the contract's ``/x`` under ``/api/v1``: only ``/y`` is missing."""
    register, counts = _planted(tmp_path, {"/x": {"get": _operation("readX")}})

    assert counts == {"missing": 1, "shape": 0, "spelling": 0, "status": 0, "unused": 0}
    assert "| `GET /api/v1/y` | `readY` | readY |" in register
    assert "GET /api/v1/x" not in register


def test_v1_reports_a_served_divergence(tmp_path: Path) -> None:
    """A matched operation answering another status and another name is reported under each kind."""
    served = {"/x": {"get": _operation("readX", status="201", names=("build",))}, "/z": {"get": _operation("readZ")}}

    _, counts = _planted(tmp_path, served)

    assert counts == {"missing": 1, "shape": 1, "spelling": 0, "status": 1, "unused": 1}


def test_v0_register_is_unchanged_on_the_committed_documents() -> None:
    """The default comparison computes, byte for byte, the committed v0 register."""
    register, _ = compare.compute()

    assert register == (_ROOT / "docs" / "reference" / "frontend-backend-demands.md").read_text(encoding="utf-8")


def test_both_modes_end_on_one_summary_line() -> None:
    """``--check`` prints its verdict, then ``compare-contracts: <have> missing=… unused=…``."""
    for have in ("v0", "v1"):
        completed = subprocess.run(
            [sys.executable, str(_SCRIPT), "--check", "--have", have], capture_output=True, text=True, check=False
        )
        last = completed.stdout.strip().splitlines()[-1]

        assert last.startswith(f"compare-contracts: {have} missing=")
        assert [field.split("=")[0] for field in last.split()[2:]] == [
            "missing",
            "shape",
            "spelling",
            "status",
            "unused",
        ]
