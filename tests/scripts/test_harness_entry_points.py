"""A harness rule can be IMPORTED, and pointed at a build (B-325).

WHAT IT PAID FOR. `common.PROTOTYPE` was a module constant hard-coded to
`http://127.0.0.1:8899/` with no override, and every rule ended in a bare
`asyncio.run(main())` — so a rule could not be imported without running, and a
reader wanting to measure its OWN build had to rebind a constant from a wrapper
outside the tree. The independent reader of #567 had to build that wrapper; the
instruction « run it against your head port » could not be followed as written.

AND THE REBINDING WAS WORSE THAN THE OBSTACLE. `served_copy`'s stamp (B-256)
answers « is the prototype I am finishing on the prototype I started on? » about
the directory it was told to read, so a rule pointed at another port was
certified against a copy it never opened. The two variables move together now,
and a run that moves one and leaves the other is refused.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "frontend" / "maquette" / "harness"

# Three rules of different shapes: one `asyncio.run(main())`, one `main()`, and
# the one module that runs TWO rules with a definition between them.
SAMPLED_RULES = ("machine", "identity", "pop")

# The rules that still carry the host's address as a LITERAL rather than reading
# `common.PROTOTYPE`, measured on 2026-09-12. They predate the constant and
# rewriting them would change rules this wave is not allowed to touch, so the
# number is FROZEN instead: the override does not reach them, and the count of
# what it does not reach may not grow.
RULES_WITH_A_LITERAL_HOST = 31

# The module-level call every rule opens with, so `from common import …`
# resolves. It is not an invocation and must never move behind the guard: a
# first version of the rewriting tool moved it in forty-one files at once.
IMPORT_PLUMBING = "sys.path.insert"

# How many modules carry it today. Frozen so a tool that DELETED the plumbing,
# rather than moving it, cannot leave the order hold below with nothing to read.
MODULES_CARRYING_THE_PLUMBING = 62

FAKE_PLAYWRIGHT = """
import sys, types
class Refuses(types.ModuleType):
    def __getattr__(self, name):
        def refuse(*arguments, **keywords):
            raise AssertionError("THE RULE RAN ON IMPORT: it called " + name)
        return refuse
api = Refuses("playwright.async_api")
package = types.ModuleType("playwright")
package.async_api = api
sys.modules["playwright"] = package
sys.modules["playwright.async_api"] = api
"""


def import_only(module_name: str, **environment: str) -> subprocess.CompletedProcess[str]:
    """Import a harness module in a fresh process, with playwright made hostile.

    Anything the module does at import time that reaches playwright raises, so
    a rule that still runs itself fails loudly instead of quietly starting a
    browser the test would then have to notice.

    Args:
        module_name: The module to import, by name.
        environment: Extra environment variables for the child.

    Returns:
        The completed process.
    """
    import os

    child = {**os.environ, **environment}
    child.pop("TM_PROTOTYPE_URL", None)
    child.pop("TM_SERVED_COPY", None)
    child.update(environment)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            FAKE_PLAYWRIGHT
            + f"sys.path.insert(0, {str(HARNESS)!r})\n"
            + "import importlib\n"
            + f"importlib.import_module({module_name!r})\n"
            + "print('imported without running')\n",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=child,
    )


@pytest.mark.parametrize("module_name", SAMPLED_RULES)
def test_a_rule_can_be_imported_without_running(module_name: str) -> None:
    """THE DEFECT THIS FILE WAS WRITTEN FOR, driven on three shapes of rule."""
    result = import_only(module_name)

    assert result.returncode == 0, f"{module_name}\n{result.stdout}\n{result.stderr}"
    assert "imported without running" in result.stdout, result.stdout
    assert "THE RULE RAN ON IMPORT" not in result.stderr, result.stderr


def test_every_rule_module_is_guarded_or_defines_no_invocation() -> None:
    """The whole corpus, read with `ast` rather than through the rewriting tool.

    Re-deriving it here is the point: a hold that called the tool's own reader
    would agree with the tool by construction, and the tool is exactly what
    needs an oracle outside itself.
    """
    running_on_import = []
    read = 0
    for path in sorted(HARNESS.glob("*.py")):
        read += 1
        tree = ast.parse(path.read_text(encoding="utf-8"))
        first_definition = next(
            (
                statement.lineno
                for statement in tree.body
                if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            ),
            None,
        )
        for statement in tree.body:
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)):
                continue
            if first_definition is not None and statement.lineno > first_definition:
                running_on_import.append(f"{path.name}:{statement.lineno}")

    assert read >= 100, f"only {read} harness modules read — the corpus has emptied"
    assert running_on_import == [], "these modules still run themselves when imported: " + ", ".join(running_on_import)


def test_the_import_plumbing_still_precedes_what_it_serves() -> None:
    """FORTY-ONE FILES were corrupted this way before the diff was read.

    Every rule opens with `sys.path.insert(0, …)` so that `from common import …`
    resolves. It is a module-level call too, and the first version of the
    rewriting tool moved it to the end of the file — leaving forty-one modules
    unable to import what they depend on, with `ruff` green over all of them.

    THE HOLD IS THE ORDER, not the place, and it was RE-AIMED to be: it first
    asked that no `sys.path` line sit after the guard at all, which `server.py`
    fails legitimately — that module is the HOST as well as a rule, and its
    whole body, plumbing included, lives behind the guard in the right order.
    What must never happen is the plumbing arriving after the import it serves.
    """
    misplaced = []
    carrying = 0
    for path in sorted(HARNESS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # READ AS CODE, never as text: `machine.py` mentions `sys.path` in a
        # comment and `identity.py` writes it inside a string it hands to a
        # child process, and a text search called both of them defects.
        plumbing = [
            statement.lineno
            for statement in tree.body
            if isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and IMPORT_PLUMBING in ast.unparse(statement.value)
        ]
        if not plumbing:
            continue
        carrying += 1
        needs = [
            statement.lineno
            for statement in tree.body
            if isinstance(statement, ast.ImportFrom) and statement.module == "common"
        ]
        if needs and min(needs) < min(plumbing):
            misplaced.append(path.name)

    # A FLOOR AS WELL AS AN ORDER, because the corruption's other shape is
    # DELETION: a tool that removed the plumbing rather than moving it would
    # leave this hold with nothing to read and nothing to say.
    assert carrying >= MODULES_CARRYING_THE_PLUMBING, (
        f"only {carrying} modules carry the import plumbing, down from {MODULES_CARRYING_THE_PLUMBING}"
    )
    assert misplaced == [], "the plumbing comes after the import it serves in: " + ", ".join(misplaced)


def test_the_prototype_reads_an_override_and_the_served_copy_follows_it() -> None:
    """Both variables move together, which is what makes the stamp mean anything."""
    result = import_only(
        "common",
        TM_PROTOTYPE_URL="http://127.0.0.1:9001/",
        TM_SERVED_COPY="/tmp/a-reader-s-own-copy",
    )
    assert result.returncode == 0, result.stderr

    reading = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(HARNESS)!r});"
            " import common, served_copy;"
            " print(common.PROTOTYPE); print(served_copy.SERVED)",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **__import__("os").environ,
            "TM_PROTOTYPE_URL": "http://127.0.0.1:9001/",
            "TM_SERVED_COPY": "/tmp/a-reader-s-own-copy",
        },
    )
    assert reading.returncode == 0, reading.stderr
    assert reading.stdout.splitlines() == [
        "http://127.0.0.1:9001/",
        "/tmp/a-reader-s-own-copy",
    ], reading.stdout


def test_moving_the_url_alone_is_refused_rather_than_certified() -> None:
    """A stamp vouching for a build the run never opened is worse than no stamp.

    This is B-256's subject reached through the door B-325's repair would have
    left open, so the repair refuses instead of honouring half of it.
    """
    result = import_only("common", TM_PROTOTYPE_URL="http://127.0.0.1:9001/")

    assert result.returncode != 0, result.stdout
    assert "TM_SERVED_COPY is not" in result.stderr, result.stderr
    assert "B-325" in result.stderr, result.stderr


def test_the_default_is_unchanged_for_every_run_that_sets_nothing() -> None:
    """THE CONTROL: `run.sh`, the oracle and every brief keep working untouched."""
    reading = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(HARNESS)!r});"
            " import common, served_copy;"
            " print(common.PROTOTYPE); print(served_copy.SERVED)",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert reading.stdout.splitlines() == [
        "http://127.0.0.1:8899/",
        "/tmp/tm-refonte",
    ], reading.stdout


def test_the_rules_the_override_does_not_reach_are_counted_and_frozen() -> None:
    """A ratchet over the residue, because the override is PARTIAL and says so.

    Thirty-one rules carry `http://127.0.0.1:8899` as a literal instead of
    reading `common.PROTOTYPE`, and rewriting them would change rules this wave
    may not touch. What can be held is that the residue does not grow: a rule
    written tomorrow reads the constant.
    """
    literal = [
        path.name
        for path in sorted(HARNESS.glob("*.py"))
        if re.search(r"127\.0\.0\.1:8899", path.read_text(encoding="utf-8"))
    ]

    assert len(literal) <= RULES_WITH_A_LITERAL_HOST, (
        f"{len(literal)} rules carry the host as a literal, up from {RULES_WITH_A_LITERAL_HOST}: " + ", ".join(literal)
    )
