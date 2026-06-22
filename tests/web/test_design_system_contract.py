"""Guard: every design-system component a panel destructures must be exported by the DS bundle.

A name destructured from the ``window.KanbanMateDesignSystem_*`` global that the bundle does NOT
export resolves to ``undefined`` at render → ``<Name/>`` is React error #130 ("element type is
undefined") → blank page. This is invisible to the JS build (the name is statically *bound* by the
destructure, just ``undefined`` at runtime) AND to code review (it reads as a normal component).
bosun's AdminPanel/WizardPanel destructured a non-existent ``Spinner``, blanking the UI on first
render — this test would have caught it before staging.
"""

from __future__ import annotations

import re
from pathlib import Path

_WEB_SRC = Path(__file__).resolve().parents[2] / "web" / "src"
_DS_BUNDLE = _WEB_SRC / "ds" / "_ds_bundle.js"
_GLOBAL_RE = re.compile(
    r"const\s*\{([^}]*)\}\s*=\s*window\.KanbanMateDesignSystem[A-Za-z0-9_]*", re.S
)
_EXPORT_RE = re.compile(r"__ds_(?:ns|scope)\.([A-Za-z0-9_]+)\s*=")


def _exported_ds_names() -> set[str]:
    """Component names the DS bundle assigns onto the shared global object."""
    return set(_EXPORT_RE.findall(_DS_BUNDLE.read_text(encoding="utf-8")))


def _destructured_ds_names() -> dict[str, list[str]]:
    """Map each DS name destructured from the global to the files that destructure it."""
    out: dict[str, list[str]] = {}
    for path in [*_WEB_SRC.rglob("*.jsx"), *_WEB_SRC.rglob("*.js")]:
        rel = path.relative_to(_WEB_SRC).as_posix()
        if rel.startswith("ds/"):  # the bundle itself is the source of truth, not a consumer
            continue
        for match in _GLOBAL_RE.finditer(path.read_text(encoding="utf-8")):
            for raw in match.group(1).split(","):
                name = raw.strip().split(":")[0].strip()
                if name:
                    out.setdefault(name, []).append(rel)
    return out


def test_every_destructured_ds_component_is_exported() -> None:
    """No consumer may destructure a DS name the bundle does not export (else React #130)."""
    exported = _exported_ds_names()
    assert exported, "could not parse any exported DS names from _ds_bundle.js"
    missing = {n: fs for n, fs in _destructured_ds_names().items() if n not in exported}
    assert not missing, (
        "DS components destructured from window.KanbanMateDesignSystem_* but NOT exported by "
        f"_ds_bundle.js — they render as `undefined` (React #130): {missing}"
    )
