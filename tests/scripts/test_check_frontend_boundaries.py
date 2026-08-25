"""Tests for the addressing arm of the frontend-boundary guard.

The arm refuses a page identity travelling in the query (`?page=`), a dial
promoted into the path, a screen the model does not declare, and a screen put
under a page the model does not carry. An adversarial
review mutation-proved two blind spots: an inline `validateSearch` with no
named `SearchParams` type escaped the declared-type reader entirely, and a
deleted `lib/addresses.ts` reported « 0 dial(s), 0 page(s) » and clean. A
reader that stays green over a tree it cannot read is the failure the guard's
own cycle arm names — so absence is a violation and the inline shape is read.

The arm also holds the two PAGE tables against each other — `PAGE_PATHS` and
the engine's `PAGES_OF()` — because a page in one and not the other is an
address leading nowhere or a surface nobody can link to, and both cases are
invisible until someone types the address.

A second review then mutation-proved the inline reader itself: it closed ONE
shape and three equivalents still read clean — a method shorthand, a reference
to a helper, a return type not called `*SearchParams`, and a returned literal
whose page key is not the first one. A page declared in `PAGE_PATHS` with no
route file was green too. So the reader is bounded to its own member, a
reference is resolved (and a reference resolving to nothing is a violation,
never silence), and the summary says how many bodies it actually read — a
number nobody prints is a number nobody can hold against the tree.

A third review then mutation-proved the reader's TEXT: it scanned comments and string
literals as if they were code, so a legitimate `// validateSearch: …` note failed the
build, while an inline return type, a call, a destructured parameter and two `raw`
spellings all read clean and were counted as bodies read. So the route text is stripped
of its comments and its string literals before the member scan, the declared type and the
body are told apart, and a key is read only where an object-literal key can sit.

Each mutation case copies the real maquette tree into a scratch directory,
mutates the copy, and runs the arm over it: the cases measure the arm over the
corpus it really reads, and the green case proves it still reads the repository.
A rewritten route keeps `path: "/add"` so the screen cross-check stays quiet and
the violation count measures the case alone.
"""

from __future__ import annotations

import importlib.util
import re
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


def write_add_route(root: Path, member: str, prelude: str = "") -> None:
    """Rewrite the `/add` route around one `validateSearch` member.

    The path stays `/add` so the screen cross-check stays quiet and the case's
    own shape is the only thing the violation count measures.

    Args:
        root: The scratch tree's root.
        member: The `validateSearch` member, written as it sits in the route.
        prelude: What the case declares above the route — a helper, a type.
    """
    (root / "routes" / "add.tsx").write_text(
        'import { createRoute } from "@tanstack/react-router";\n'
        'import { rootRoute } from "../app/root-route";\n'
        "\n" + prelude + "export const addRoute = createRoute({\n"
        "  getParentRoute: () => rootRoute,\n"
        '  path: "/add",\n' + member + "  component: () => null,\n"
        "});\n",
        encoding="utf-8",
    )


class TestAddressingArm:
    """The mutation cases, then the real tree, unmodified, reading clean."""

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

    def test_g_a_method_shorthand_is_read(self, tmp_path, capsys) -> None:
        """Refuse the shorthand — `validateSearch(raw) { … }` carries no colon to anchor on."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch(raw: Record<string, unknown>) {\n    return { page: String(raw.page ?? "") };\n  },\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_h_a_helper_reference_is_resolved(self, tmp_path, capsys) -> None:
        """Refuse the reference — `validateSearch: readSearch` names a body in the same file."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: readSearch,\n",
            prelude="function readSearch(raw: Record<string, unknown>) {\n"
            '  return { page: String(raw.page ?? "") };\n'
            "}\n"
            "\n",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_i_a_reference_resolving_to_nothing_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse silence — a body the reader cannot reach must not be read as an empty one."""
        root = copy_design_src(tmp_path)
        write_add_route(root, "  validateSearch: readSearch,\n")
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("cannot read" in line and "readSearch" in line for line in captured.err.splitlines())

    def test_j_a_return_type_under_another_name_is_read(self, tmp_path, capsys) -> None:
        """Refuse a page in the declared return type, whatever that type is called."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: (s: Record<string, unknown>): AddQuery => {\n"
            "    const out: AddQuery = {};\n"
            "    return out;\n"
            "  },\n",
            prelude="type AddQuery = { page?: string };\n\n",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("« page »" in line for line in captured.err.splitlines())

    def test_k_a_page_key_that_is_not_the_first_is_read(self, tmp_path, capsys) -> None:
        """Refuse a page key anywhere in the returned literal, not only in first position."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: (raw) => ({ tab: String(raw.tab ?? ""), page: "acq" }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert any("« page »" in line for line in captured.err.splitlines())

    def test_l_a_page_path_no_route_serves_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse an address the table promises and no route file answers."""
        root = copy_design_src(tmp_path)
        (root / "routes" / "account.tsx").unlink()
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        offender = [line for line in captured.err.splitlines() if "« profile »" in line]
        assert offender and "/account" in offender[0]
        assert "SCREEN_PARENTS" not in captured.err

    def test_m_the_summary_counts_the_bodies_it_read(self, capsys) -> None:
        """The summary says how many validateSearch bodies were read — one per route declaring it."""
        guard.arm_addressing(DESIGN_SRC)
        captured = capsys.readouterr()
        declaring = [
            route
            for route in sorted((DESIGN_SRC / "routes").glob("*.tsx"))
            if re.search(r"validateSearch\s*[:(]", route.read_text(encoding="utf-8"))
        ]
        assert declaring, "the routes declare no validateSearch — the count would prove nothing"
        assert f"{len(declaring)} validateSearch" in captured.out

    def test_n_a_literal_below_the_member_is_not_its_body(self, tmp_path, capsys) -> None:
        """A resolved reference is read, and an unrelated literal below it invents no violation."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: readSearch,\n",
            prelude='function readSearch(raw: Record<string, unknown>) {\n  return { q: String(raw.q ?? "") };\n}\n\n',
        )
        with (root / "routes" / "add.tsx").open("a", encoding="utf-8") as handle:
            handle.write('\nconst HOME_QUERY = { page: "acq" };\nexport const home = () => HOME_QUERY;\n')
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 0, captured.err

    def test_o_a_shape_the_reader_cannot_follow_says_so(self, tmp_path, capsys) -> None:
        """A member the reader cannot follow is named as unread, never read out of a later block."""
        root = copy_design_src(tmp_path)
        write_add_route(root, "  validateSearch: (raw) => buildSearch(raw),\n")
        with (root / "routes" / "add.tsx").open("a", encoding="utf-8") as handle:
            handle.write('\nconst HOME_QUERY = { page: "acq" };\nexport const home = () => HOME_QUERY;\n')
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1
        assert "cannot read" in captured.err
        assert "« page »" not in captured.err

    def test_p_an_inline_return_type_is_not_the_body(self, tmp_path, capsys) -> None:
        """Refuse a page behind an inline return type — its brace must not be read as the body."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: (raw: Record<string, unknown>): { page?: string } =>"
            ' ({ page: String(raw.page ?? "") }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_q_a_call_is_not_a_reference(self, tmp_path, capsys) -> None:
        """A CALL names no body this reader can follow — and the factory's body is not counted."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: reader("page"),\n',
            prelude="function reader(key: string) {\n"
            '  return (raw: Record<string, unknown>) => ({ [key]: String(raw[key] ?? "") });\n'
            "}\n"
            "\n",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "cannot read" in captured.err
        assert "3 validateSearch body(ies) read" in captured.out

    def test_r_a_destructured_parameter_is_read(self, tmp_path, capsys) -> None:
        """Refuse a page pulled out of the parameter list — `({ page, ...rest }) => …`."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: ({ page, ...rest }: Record<string, unknown>) => ({ ...rest, p: String(page ?? "") }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_s_a_single_quoted_index_is_read(self, tmp_path, capsys) -> None:
        """Refuse `raw['page']` — a quote is a spelling, not an escape from the guard."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: (raw: Record<string, unknown>) => ({ q: String(raw['page'] ?? \"\") }),\n",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_t_an_optional_chain_is_read(self, tmp_path, capsys) -> None:
        """Refuse `raw?.page` — an optional chain reads the same query as a plain one."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: (raw: Record<string, unknown>) => ({ q: String(raw?.page ?? "") }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_t2_an_optional_chained_index_is_read(self, tmp_path, capsys) -> None:
        """Refuse `raw?.["page"]` — the two spellings of a read are one read."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: (raw: Record<string, unknown>) => ({ q: String(raw?.["page"] ?? "") }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_t3_a_quoted_literal_key_is_read(self, tmp_path, capsys) -> None:
        """Refuse `({ "page": … })` — a key in quotes is the key it spells."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: (raw: Record<string, unknown>) => ({ "page": String(raw.q ?? "") }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_t4_a_quoted_destructured_key_is_read(self, tmp_path, capsys) -> None:
        """Refuse `({ "page": name }) => …` — quoting the bound key does not hide it."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: ({ "page": asked }: Record<string, unknown>) => ({ q: String(asked ?? "") }),\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« page »" in line and "inline" in line for line in captured.err.splitlines())

    def test_u_a_comment_is_not_a_member(self, tmp_path, capsys) -> None:
        """A note, a block comment and a string naming `validateSearch` are text, not members."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: (raw: Record<string, unknown>) => ({ q: String(raw.q ?? "") }),\n',
            prelude="// validateSearch: the raw query is never trusted here.\n"
            "/* validateSearch (raw) names nothing outside this note. */\n"
            'const NOTE = "validateSearch: x";\n'
            "export const note = () => NOTE;\n"
            "\n",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 0, captured.err
        assert "4 validateSearch body(ies) read" in captured.out

    def test_v_a_type_annotation_is_not_an_object_key(self, tmp_path, capsys) -> None:
        """A declaration's type and a ternary's operands sit where no object key can — read neither."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: (raw: Record<string, unknown>): AddSearchParams => {\n"
            "    const read: AddSearchParams = {};\n"
            '    const cfg: string = "";\n'
            "    const pick = raw.x ? acq : sys;\n"
            '    if (typeof raw.q === "string" && raw.q) read.q = raw.q;\n'
            "    return read;\n"
            "  },\n",
            prelude='type AddSearchParams = { q?: string };\nconst acq = "a";\nconst sys = "s";\n\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 0, captured.err

    def test_w_the_summary_falls_when_a_body_goes_unread(self, tmp_path, capsys) -> None:
        """The bodies-read count MOVES: an unreadable member reports one fewer than the routes declare."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            '  validateSearch: reader("page"),\n',
            prelude="function reader(key: string) {\n"
            '  return (raw: Record<string, unknown>) => ({ [key]: String(raw[key] ?? "") });\n'
            "}\n"
            "\n",
        )
        declaring = [
            route
            for route in sorted((root / "routes").glob("*.tsx"))
            if re.search(r"validateSearch\s*[:(]", route.read_text(encoding="utf-8"))
        ]
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert f"{len(declaring) - 1} validateSearch body(ies) read" in captured.out

    def test_x_a_declared_name_is_not_a_name_declared_nowhere(self, tmp_path, capsys) -> None:
        """A name this file DOES declare, in a shape the reader does not follow, is named as such."""
        root = copy_design_src(tmp_path)
        write_add_route(
            root,
            "  validateSearch: readSearch,\n",
            prelude='const readSearch = async (raw: Record<string, unknown>) => ({ page: "x" });\n\n',
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "does not follow" in captured.err
        assert "declares nowhere" not in captured.err

    def test_y_a_name_absent_from_the_file_declares_nowhere(self, tmp_path, capsys) -> None:
        """The « declares nowhere » sentence is reserved for a name the file never declares."""
        root = copy_design_src(tmp_path)
        write_add_route(root, "  validateSearch: readSearch,\n")
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "declares nowhere" in captured.err

    def test_z_a_screen_parent_that_is_no_page_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse a screen belonging to a page the table does not carry — it would close onto nothing."""
        root = copy_design_src(tmp_path)
        model = root / "lib" / "addresses.ts"
        model.write_text(
            model.read_text(encoding="utf-8").replace(
                '"/media/$provider/$id": "lib"', '"/media/$provider/$id": "nowhere"'
            ),
            encoding="utf-8",
        )
        violations = guard.arm_addressing(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert any("« nowhere »" in line and "/media/$provider/$id" in line for line in captured.err.splitlines())

    def test_the_real_tree_reads_clean(self, capsys) -> None:
        """The unmodified repository reports zero violations — the arm still reads the tree it guards."""
        violations = guard.arm_addressing(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 0
        assert "0 violation(s)" in captured.out


class TestTreeArmNestedCopy:
    """B-065 — a tree copied under its own path, read by nothing, drifting."""

    def test_a_nested_copy_of_the_tree_is_a_violation(self, tmp_path, capsys) -> None:
        """Refuse a source file under a directory bearing an ancestor's name."""
        root = copy_design_src(tmp_path)
        nested = tmp_path / "frontend" / "maquette" / "src" / "lib"
        nested.mkdir(parents=True)
        (nested / "engine-queue.ts").write_text("export const x = 1;\n", encoding="utf-8")
        violations = guard.arm_tree(root)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "« src/ » again" in captured.err

    def test_the_repetition_is_read_from_ABOVE_the_corpus(self) -> None:
        """The copy's own path repeats nothing — only the enclosing tree's name does.

        The first version of this hold looked for a segment repeated INSIDE the
        relative path and reported the real defect clean:
        `design/frontend/maquette/design/src/lib/x.ts` spells five distinct
        segments once you are standing in `design/`. What repeats is the name of
        the directory you are standing in.
        """
        relative = "frontend/maquette/design/src/lib/engine-queue.ts"
        # Nothing repeats INSIDE the path: five distinct segments. Told neither
        # the ancestors nor the corpus's name, the hold has nothing to see —
        # which is verbatim what the first version of it reported.
        assert guard.echoed_ancestor(relative, set(), "unrelated") is None
        # Told what it is standing in, it sees the copy at once.
        assert guard.echoed_ancestor(relative, {"design"}, "unrelated") == "design"
        assert guard.echoed_ancestor(relative, set(), "src") == "src"
        # And the corpus's own name, one level below where it belongs — while
        # the level where it BELONGS reads clean.
        assert guard.echoed_ancestor("src/src/lib/x.ts", set(), "src") == "src"
        assert guard.echoed_ancestor("src/lib/x.ts", set(), "src") is None

    def test_the_bundler_s_own_directories_are_not_read(self, tmp_path, capsys) -> None:
        """`node_modules/` and `dist/` repeat names by the hundred and are skipped."""
        root = copy_design_src(tmp_path)
        buried = tmp_path / "node_modules" / "any" / "src" / "src" / "deep"
        buried.mkdir(parents=True)
        (buried / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
        violations = guard.arm_tree(root)
        captured = capsys.readouterr()
        assert violations == 0, captured.err

    def test_the_real_tree_reads_clean(self, capsys) -> None:
        """The repository carries no nested copy — the eleven files are gone."""
        violations = guard.arm_tree(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 0, captured.err
        assert "0 under a repeated directory" in captured.out


class TestSizeArmReadsTheLabel:
    """B-073 — the grandfathered list guaranteed its membership, never its promise."""

    def test_a_label_leading_with_a_landed_lot_is_a_violation(self, monkeypatch, capsys) -> None:
        """Refuse an entry promising a lot the plan already marks `LANDED`."""
        monkeypatch.setitem(guard.GRANDFATHERED, "engine/legacy.js", "L07 — long since been and gone")
        violations = guard.arm_size(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "leads with L07, already `LANDED`" in captured.err

    def test_a_lot_that_has_not_landed_is_accepted(self, monkeypatch, capsys) -> None:
        """`L13` is `NOT STARTED`, so the promise still stands."""
        monkeypatch.setitem(guard.GRANDFATHERED, "engine/legacy.js", "L13 — the engine dies by subtraction")
        violations = guard.arm_size(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 0, captured.err

    def test_a_label_naming_no_lot_is_a_violation(self, monkeypatch, capsys) -> None:
        """A label nobody can act on is the state B-073 found the list in."""
        monkeypatch.setitem(guard.GRANDFATHERED, "engine/legacy.js", "big, and someone will look")
        violations = guard.arm_size(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "leads with no lot" in captured.err

    def test_a_plan_that_cannot_be_read_is_a_violation_not_a_pass(self, monkeypatch, capsys) -> None:
        """No status read means the hold cannot be checked — never that nothing landed."""
        monkeypatch.setattr(guard, "PLAN", Path("does/not/exist.md"))
        violations = guard.arm_size(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "no lot status could be read" in captured.err

    def test_the_real_list_reads_clean(self, capsys) -> None:
        """Every entry leads with a lot that still owes the reduction."""
        violations = guard.arm_size(DESIGN_SRC)
        captured = capsys.readouterr()
        assert violations == 0, captured.err
