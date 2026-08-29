"""Holds on the invariant-10 arm: what it reads, and what it refuses to read.

Every hold here corresponds to a defect the arm actually shipped with. The arm
went through review counting module specifiers as identifiers, blind to the
seven page aliases, blanking code that followed a `//` inside a string, and
summing its corpus floor across three directories so a ceiling of ZERO could be
satisfied by reading nothing. None of those was visible in its output — each
one made the arm report a smaller number, and a smaller number passes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_arm():
    """Imports the arm by path, the way `make check` invokes it.

    Returns:
        The module object.
    """
    spec = importlib.util.spec_from_file_location("check_frame_domain", ROOT / "scripts" / "check-frame-domain.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_frame_domain"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="arm")
def arm_fixture():
    """Provides the loaded arm.

    Returns:
        The module object.
    """
    return load_arm()


def test_the_vocabulary_carries_the_page_aliases(arm):
    """The frame writes `acq`, never `acquisition` — both halves must be there.

    Args:
        arm: The loaded module.
    """
    words = set(arm.domain_vocabulary())
    assert {"acquisition", "arrivals", "settings"} <= words, "feature names"
    assert {"acq", "arr", "cfg", "maint", "sys"} <= words, (
        "the page aliases are the half the frame actually writes; without them "
        "app/page-host.tsx's table of pages is invisible to this arm"
    )


def test_the_aliases_are_derived_and_not_a_list(arm):
    """An alias enters by being declared in the address model, not by being typed here.

    Args:
        arm: The loaded module.
    """
    source = arm.ADDRESS_MODEL.read_text(encoding="utf-8")
    declared = set(arm.PAGE_ALIAS.findall(source))
    assert declared, "the address model declares page ids"
    assert declared <= set(arm.domain_vocabulary())


def test_a_slash_inside_a_string_is_not_a_comment(arm):
    """`${scheme}//${host}` must not blank the rest of its line.

    Args:
        arm: The loaded module.
    """
    source = "const url = `${scheme}//${host}`; const settingsPage = 1;"
    assert "settingsPage" in arm.strip_comments(source)


def test_a_block_opener_inside_a_string_is_not_a_comment(arm):
    """A `"/*"` literal must not swallow the file to the next `*/`.

    Args:
        arm: The loaded module.
    """
    # THE CLOSER MUST EXIST FURTHER DOWN, or the regex version matched nothing
    # and this hold passed against the very defect it names. That is the shape
    # the register counts: a mutation that does not bite is a hold that is not
    # one. Here the `*/` of an ordinary comment closes the string's `/*`, and
    # everything between them was eaten.
    source = 'const opener = "/*";\nconst settingsPage = 1;\n/* an ordinary comment */\n'
    assert "settingsPage" in arm.strip_comments(source)


def test_real_comments_are_still_removed(arm):
    """The repair must not have turned the stripper off.

    Args:
        arm: The loaded module.
    """
    stripped = arm.strip_comments("// settingsPage\n/* arrivalsPage */\nconst a = 1;")
    assert "settingsPage" not in stripped
    assert "arrivalsPage" not in stripped
    assert "const a = 1;" in stripped


def test_a_module_specifier_is_not_an_identifier(arm):
    """A path names a directory; it is not a name the code chose.

    Args:
        arm: The loaded module.
    """
    words = arm.words_of('import { useUiState } from "../lib/store-access";')
    assert "lib" not in words, (
        "both of ui/'s hits were import paths naming the frame's own lib/ directory, under a ceiling of ZERO"
    )
    assert "state" in words, "the imported NAMES are still read"


def test_an_ordinary_string_is_still_read(arm):
    """Blanking specifiers must not blank every string in the file.

    Args:
        arm: The loaded module.
    """
    assert "settings" in arm.words_of('const page = "settingsPage";')


def test_the_corpus_floor_is_per_directory(arm):
    """A sum let ui/ be read as nothing while app/ carried the total.

    Args:
        arm: The loaded module.
    """
    assert isinstance(arm.IDENTIFIER_FLOOR, dict)
    assert set(arm.IDENTIFIER_FLOOR) == set(arm.FRAME)
    for directory in arm.FRAME:
        _, _, seen = arm.count_directory(directory, arm.domain_vocabulary())
        assert seen >= arm.IDENTIFIER_FLOOR[directory], (
            f"{directory}/ read {seen} identifier words, under its own floor"
        )


def test_only_what_the_invariant_names_is_exempt(arm):
    """An exemption added because a file carried words is the move exemptions prevent.

    Args:
        arm: The loaded module.
    """
    assert set(arm.EXEMPT) == {"lib/addresses.ts"}


def test_the_arm_passes_over_the_repository(arm):
    """The recorded ceilings hold against the tree as it stands.

    Args:
        arm: The loaded module.
    """
    assert arm.main() == 0
