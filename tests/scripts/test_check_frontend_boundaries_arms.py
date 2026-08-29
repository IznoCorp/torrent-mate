"""Every arm of the frontend-boundary guard is exercised by a test, or is counted.

B-041. The entry read « the newest guard is the only one of its family with
nothing to re-run », and that had STOPPED BEING TRUE: the test file beside this
one has existed since #484 and carries 42 tests. What was still true is the part
the entry actually faulted — those 42 tests are ALL about the addressing arm, its
own docstring says so, and the guard carries eleven. **Eight were named by no
test at all**, measured on 2026-08-29.

WHY A META-ASSERTION AND NOT JUST MORE TESTS. Both. The assertion is what stops
the next arm arriving uncovered — a guard grows an arm per wave here, and every
one of them was written by someone who had just proved it by hand and moved on.
The ratchet may only go DOWN: it is a CEILING on how many arms nobody exercises,
which is the opposite shape from a floor set at the current value, because
adding an arm without a test raises the count and is refused.

WHAT THIS FILE DOES NOT PROVE. That an arm is exercised is not that it is
exercised WELL: each mutation below breaks the one thing its arm exists to
refuse, and a second blind spot in the same arm would pass. The addressing arm's
own history is the warning — three adversarial reviews found three further blind
spots in a reader that already had tests.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-frontend-boundaries.py"
DESIGN_SRC = ROOT / "frontend" / "maquette" / "design" / "src"
TESTS = Path(__file__).resolve().parent

# HOW MANY ARMS MAY GO UNEXERCISED. A CEILING, lowered by this wave from 8 to 3
# and never raised: an arm added without a test pushes the count up and is
# refused. It is not a floor set at the current value — that shape is
# pre-satisfied and can never fall (B-075) — it is the burn-down's remaining
# balance, and the three names are written out so nobody has to guess which.
UNEXERCISED_CEILING = 3
KNOWN_UNEXERCISED = {
    # Needs five features importing one module to trip; building that tree is a
    # fixture in itself and belongs with whoever next touches the arm.
    "arm_fan_in",
    # Its subject is `lib/addresses.ts`'s declared members against what routes
    # use, and the addressing tests already rewrite that file for other reasons.
    "arm_reference_slice",
    # One address per route file; the addressing suite rewrites route files
    # constantly and a mutation here would collide with those fixtures.
    "arm_one_address",
}


def load():
    """Imports the guard, despite its hyphenated filename."""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_frontend_boundaries", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


def arms():
    """Returns every arm callable the entry point can reach."""
    return sorted(name for name in dir(guard) if name.startswith("arm_"))


def copy_tree(tmp_path: Path) -> Path:
    """Copies the real maquette sources so a mutation measures the real corpus.

    THE DEPTH IS MIRRORED, not flattened. Two modules import
    `../../../fixture-projections.json` and one imports
    `../../../contract/openapi.json`; copied to `tmp/src` those paths climb out
    of the scratch tree, `arm_cycles` reports three unresolved imports, and the
    GREEN case fails — so every mutation below would have been measured against
    a red baseline and proved nothing. Copied to `tmp/design/src` they land in
    `tmp/`, where the two files are created beside it.
    """
    root = tmp_path / "design" / "src"
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DESIGN_SRC, root)
    (tmp_path / "fixture-projections.json").write_text("{}", encoding="utf-8")
    (tmp_path / "contract").mkdir(exist_ok=True)
    (tmp_path / "contract" / "openapi.json").write_text("{}", encoding="utf-8")
    return root


def test_every_arm_is_exercised_by_some_test():
    """The count of unexercised arms is a ceiling, and it is printed."""
    named = "\n".join(path.read_text(encoding="utf-8") for path in TESTS.glob("test_check_frontend_boundaries*.py"))
    unexercised = [arm for arm in arms() if arm not in named]
    assert len(arms()) >= 8, (
        f"only {len(arms())} arm(s) found — the guard carries eleven, and a "
        "reader that finds none reports the same word as one that found them all"
    )
    assert len(unexercised) <= UNEXERCISED_CEILING, (
        f"{len(unexercised)} arm(s) are named by no test — {sorted(unexercised)} "
        f"— against a ceiling of {UNEXERCISED_CEILING}. An arm nobody exercises "
        "is a refusal nobody has seen refuse."
    )
    assert set(unexercised) <= KNOWN_UNEXERCISED, (
        f"a NEW arm is unexercised: {sorted(set(unexercised) - KNOWN_UNEXERCISED)}. "
        "The ceiling counts, and this names — a count alone would let a fresh "
        "arm take a retired one's place in silence."
    )


def test_the_tree_as_it_stands_passes_every_arm(tmp_path):
    """The green case, so a mutation's red means the mutation."""
    root = copy_tree(tmp_path)
    for arm in ("arm_cycles", "arm_layering", "arm_typing", "arm_duplicate_import", "arm_mocks"):
        assert getattr(guard, arm)(root) == 0, (
            f"{arm} refuses the unmutated tree, so nothing below measures the mutation"
        )


def test_cycles_refuses_an_import_cycle(tmp_path):
    """A cycle makes every other dependency rule unenforceable."""
    root = copy_tree(tmp_path)
    (root / "lib" / "cycle-one.ts").write_text(
        'import { two } from "./cycle-two";\nexport const one = () => two;\n', encoding="utf-8"
    )
    (root / "lib" / "cycle-two.ts").write_text(
        'import { one } from "./cycle-one";\nexport const two = () => one;\n', encoding="utf-8"
    )
    assert guard.arm_cycles(root) > 0, (
        "a cycle makes every other dependency rule unenforceable, because the cycle IS the violation (invariant 8)"
    )


def test_layering_refuses_ui_importing_a_feature(tmp_path):
    """`ui/` is a vocabulary, and a vocabulary names no subject."""
    root = copy_tree(tmp_path)
    target = root / "ui" / "layer-probe.tsx"
    target.write_text(
        'import { AddFooter } from "../features/acquisition/add-footer";\nexport const probe = AddFooter;\n',
        encoding="utf-8",
    )
    assert guard.arm_layering(root) > 0, (
        "`ui/` never imports a feature — invariant 7, and it is what keeps the vocabulary a vocabulary"
    )


def test_typing_refuses_an_escape_hatch(tmp_path):
    """The `any` ratchet has been held from zero since L04."""
    root = copy_tree(tmp_path)
    (root / "lib" / "typing-probe.ts").write_text("export const loose = (value: any) => value;\n", encoding="utf-8")
    assert guard.arm_typing(root) > 0, "no `any`, no `ts-ignore` — a ratchet held from zero since L04"


def test_duplicate_import_refuses_one_module_imported_twice(tmp_path):
    """Two imports of one module is a conflict resolved by keeping both halves."""
    root = copy_tree(tmp_path)
    (root / "lib" / "duplicate-probe.ts").write_text(
        'import { first } from "./addresses";\n'
        'import { second } from "./addresses";\n'
        "export const both = [first, second];\n",
        encoding="utf-8",
    )
    assert guard.arm_duplicate_import(root) > 0, (
        "two import statements for one module is a merge conflict resolved by keeping both halves"
    )


def test_mocks_refuses_a_value_import_outside_app(tmp_path):
    """Only `app/` may import `mocks/`: a module reading a SEED is a fixture that outlives its own removal."""
    root = copy_tree(tmp_path)
    (root / "lib" / "mocks-probe.ts").write_text(
        'import { seeds } from "../mocks";\nexport const leak = seeds;\n', encoding="utf-8"
    )
    assert guard.arm_mocks(root) > 0, (
        "only `app/` may import `mocks/`: a module reading a SEED is a fixture that survives its own removal"
    )


@pytest.mark.parametrize("arm", sorted(KNOWN_UNEXERCISED))
def test_the_named_debt_is_still_real(arm):
    """A retired name may not sit in the ceiling's list for ever."""
    assert hasattr(guard, arm), (
        f"{arm} no longer exists — remove it from KNOWN_UNEXERCISED and lower "
        "the ceiling, or the debt list is protecting nothing"
    )
