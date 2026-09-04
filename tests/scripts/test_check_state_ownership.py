"""Holds on the `ENGINE_OWNED` exemption: what makes it live, and what kills it.

An exemption is a hole cut in a guard by hand, so the only thing that keeps it
honest is the fact it claims. This one claims that the dying engine still
imports the module — and the first version of that read asked whether the
module's path appeared ANYWHERE in the engine's text. A comment naming the path
answered yes, and `engine/legacy.js` is full of comments naming feature paths,
so the exemption would have outlived the import that justifies it inside the one
file whose whole purpose is to shrink. Every hold below is that defect, or the
shape of the answer it must give now.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_arm():
    """Imports the guard by path, the way `make check` invokes it.

    Returns:
        The module object.
    """
    spec = importlib.util.spec_from_file_location(
        "check_state_ownership", ROOT / "scripts" / "check-state-ownership.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_state_ownership"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="arm")
def arm_fixture():
    """Provides the loaded guard.

    Returns:
        The module object.
    """
    return load_arm()


def write_engine(root: Path, body: str) -> None:
    """Writes a stand-in engine holding `body`.

    Args:
        root: The fake `design/src`.
        body: The engine's text.
    """
    (root / "engine").mkdir(parents=True, exist_ok=True)
    (root / "engine" / "legacy.js").write_text(body, encoding="utf-8")


def test_a_real_import_makes_the_exemption_live(arm, tmp_path):
    """The fact the exemption claims, in the form that makes it true."""
    write_engine(tmp_path, 'import { feed } from "../features/acquisition/discover-feed";\n')
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is True


def test_a_commented_out_import_does_not(arm, tmp_path):
    """THE DEFECT. A dead import is exactly as dead as a deleted one."""
    write_engine(tmp_path, '// import { feed } from "../features/acquisition/discover-feed";\n')
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is False


def test_a_block_comment_does_not_either(arm, tmp_path):
    """The same, through the other comment syntax."""
    write_engine(tmp_path, '/* import { feed } from "../features/acquisition/discover-feed"; */\n')
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is False


def test_prose_naming_the_path_does_not_either(arm, tmp_path):
    """The shape the engine actually holds: a comment that mentions a feature path."""
    write_engine(tmp_path, "// the reserve lives in ../features/acquisition/discover-feed now\n")
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is False


def test_a_side_effect_import_counts(arm, tmp_path):
    """`import "spec";` reaches for the module as surely as a named one."""
    write_engine(tmp_path, 'import "../features/acquisition/discover-feed";\n')
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is True


@pytest.mark.parametrize("specifier", [
    "../features/acquisition/discover-feed",
    "../features/acquisition/discover-feed.js",
    "../features/acquisition/discover-feed.ts",
    "../features/acquisition/discover-feed/index",
])
def test_every_spelling_of_one_file_counts(arm, tmp_path, specifier):
    """A resolver fills in the extension and the folder index; all four name it."""
    write_engine(tmp_path, f'import {{ feed }} from "{specifier}";\n')
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is True


def test_a_longer_path_ending_in_the_same_name_does_not(arm, tmp_path):
    """A different module whose specifier merely ends the same way is not it."""
    write_engine(tmp_path, 'import { feed } from "../features/other/discover-feed";\n')
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is False


def test_no_engine_no_exemption(arm, tmp_path):
    """The day `legacy.js` goes, every entry stops being honoured."""
    assert arm.engine_imports(tmp_path, "features/acquisition/discover-feed.ts") is False


def test_the_arm_refuses_a_dead_exemption(arm, tmp_path, monkeypatch, capsys):
    """The whole point: a stale exemption is a VIOLATION, not a quiet skip.

    The tree holds the exempt file and an engine whose import of it is commented
    out — the mutation a wave would commit without noticing.
    """
    for bucket in arm.COMPONENT_BUCKETS:
        (tmp_path / bucket).mkdir(parents=True, exist_ok=True)
    exempt = "features/acquisition/discover-feed.ts"
    (tmp_path / exempt).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / exempt).write_text("export const feed = [];\n", encoding="utf-8")
    write_engine(tmp_path, '// import { feed } from "../features/acquisition/discover-feed";\n')
    (tmp_path / "engine" / "states.js").write_text("", encoding="utf-8")
    monkeypatch.setattr(arm, "ENGINE_OWNED", {exempt: "a reason nobody can check"})

    violations = arm.arm_server_state(tmp_path)

    assert violations >= 1
    printed = capsys.readouterr().out
    assert "1 stale" in printed


def test_the_arm_is_clean_while_the_import_is_real(arm, tmp_path, monkeypatch, capsys):
    """The control: the same tree with the import alive reports nothing stale."""
    for bucket in arm.COMPONENT_BUCKETS:
        (tmp_path / bucket).mkdir(parents=True, exist_ok=True)
    exempt = "features/acquisition/discover-feed.ts"
    (tmp_path / exempt).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / exempt).write_text("export const feed = [];\n", encoding="utf-8")
    write_engine(tmp_path, 'import { feed } from "../features/acquisition/discover-feed";\n')
    (tmp_path / "engine" / "states.js").write_text("", encoding="utf-8")
    monkeypatch.setattr(arm, "ENGINE_OWNED", {exempt: "a reason the engine's import backs"})

    violations = arm.arm_server_state(tmp_path)

    assert violations == 0
    assert "0 stale" in capsys.readouterr().out
