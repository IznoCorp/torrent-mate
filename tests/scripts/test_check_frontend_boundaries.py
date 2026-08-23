"""Tests for the addressing arm of the frontend-boundary guard.

The arm refuses a page identity travelling in the query (`?page=`), a dial
promoted into the path, and a screen the model does not declare. An adversarial
review mutation-proved two blind spots: an inline `validateSearch` with no
named `SearchParams` type escaped the declared-type reader entirely, and a
deleted `lib/addresses.ts` reported « 0 dial(s), 0 page(s) » and clean. A
reader that stays green over a tree it cannot read is the failure the guard's
own cycle arm names — so absence is a violation and the inline shape is read.

The arm also holds the two PAGE tables against each other — `PAGE_PATHS` and
the engine's `PAGES_OF()` — because a page in one and not the other is an
address leading nowhere or a surface nobody can link to, and both cases are
invisible until someone types the address.

Each mutation case copies the real maquette tree into a scratch directory,
mutates the copy, and runs the arm over it: the cases measure the arm over the
corpus it really reads, and the green case proves it still reads the repository.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-frontend-boundaries.py"
DESIGN_SRC = Path(__file__).resolve().parents[2] / "frontend" / "maquette" / "design" / "src"


def load():
    """Imports the guard, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_frontend_boundaries", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


def copy_design_src(tmp_path: Path) -> Path:
    """Copy the real maquette tree into a scratch root a case may mutate.

    Args:
        tmp_path: The pytest scratch directory for this test.

    Returns:
        The copy's root, ready to be handed to the arm.
    """
    root = tmp_path / "src"
    shutil.copytree(DESIGN_SRC, root, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    return root


class TestAddressingArm:
    """The six mutation cases, then the real tree, unmodified, reading clean."""

    def test_a_deleted_address_model_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse a missing `lib/addresses.ts` — a tree the arm cannot read must not read clean."""
        root = copy_design_src(tmp_path)
        (root / "lib" / "addresses.ts").unlink()
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations >= 1
        assert "address model is missing" in captured.err
        # The summary line is still printed — the arm reports what it read.
        assert "addressing:" in captured.out

    def test_b_an_inline_validate_search_reading_page_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse the inline shape — `validateSearch: (raw) => ({ page: … })` with no named type."""
        root = copy_design_src(tmp_path)
        (root / "routes" / "add.tsx").write_text(
            'import { createRoute } from "@tanstack/react-router";\n'
            'import { rootRoute } from "../app/root-route";\n'
            "\n"
            "export const addRoute = createRoute({\n"
            "  getParentRoute: () => rootRoute,\n"
            '  path: "/add",\n'
            '  validateSearch: (raw) => ({ page: String(raw.page ?? "") }),\n'
            "  component: () => null,\n"
            "});\n",
            encoding="utf-8",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_c_a_dial_promoted_into_the_path_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse the shape D1 forbids — `/media/lens/inc` puts the `lens` dial in the PATH."""
        root = copy_design_src(tmp_path)
        (root / "routes" / "add.tsx").write_text(
            'import { createRoute } from "@tanstack/react-router";\n'
            'import { rootRoute } from "../app/root-route";\n'
            "\n"
            "export const addRoute = createRoute({\n"
            "  getParentRoute: () => rootRoute,\n"
            '  path: "/media/lens/inc",\n'
            "  validateSearch: (raw) => ({}),\n"
            "  component: () => null,\n"
            "});\n",
            encoding="utf-8",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations >= 1
        assert any("puts the dial « lens » in the PATH" in line for line in captured.err.splitlines())

    def test_d_a_named_search_params_type_declaring_page_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse the named shape — `type SearchParams = { page?: string }` puts a page in the query."""
        root = copy_design_src(tmp_path)
        (root / "routes" / "add.tsx").write_text(
            'import { createRoute } from "@tanstack/react-router";\n'
            'import { rootRoute } from "../app/root-route";\n'
            "\n"
            "type SearchParams = { page?: string };\n"
            "\n"
            "export const addRoute = createRoute({\n"
            "  getParentRoute: () => rootRoute,\n"
            '  path: "/add",\n'
            "  validateSearch: (raw) => ({}),\n"
            "  component: () => null,\n"
            "});\n",
            encoding="utf-8",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("declares « page » as a search parameter" in line for line in captured.err.splitlines())

    def test_e_a_page_the_engine_does_not_draw_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse an address for a page `PAGES_OF()` never draws — a link leading nowhere."""
        root = copy_design_src(tmp_path)
        model = root / "lib" / "addresses.ts"
        model.write_text(
            model.read_text(encoding="utf-8").replace(
                '  acq: "/acquisition",',
                '  acq: "/acquisition",\n  ghost: "/ghost",',
            ),
            encoding="utf-8",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations >= 1
        assert any("« ghost »" in line and "PAGES_OF() does not draw" in line for line in captured.err.splitlines())

    def test_f_a_page_with_no_address_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse a page the engine draws and the model gives no address — nobody can link to it."""
        root = copy_design_src(tmp_path)
        engine = root / "engine" / "legacy.js"
        engine.write_text(
            engine.read_text(encoding="utf-8").replace(
                '      id: "acq",',
                '      id: "phantom",\n      l: "Phantom",\n    },\n    {\n      id: "acq",',
                1,
            ),
            encoding="utf-8",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations >= 1
        assert any("« phantom »" in line and "no address" in line for line in captured.err.splitlines())

    def test_the_real_tree_reads_clean(self, capsys) -> None:
        """The unmodified repository reports zero violations — the arm still reads the tree it guards."""
        violations = guard.arm_addressing(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 0
        assert "0 violation(s)" in captured.out
