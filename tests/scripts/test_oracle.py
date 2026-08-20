"""Tests for the recorded oracle's pure parts.

The oracle's measuring half needs a browser and is proved by mutation in the
wave's ACCEPTANCE. What is tested here is everything that can be wrong WITHOUT
a browser — and every case below is a way this instrument could go green while
measuring something other than what it claims.

The recipe is the subject of most of them. It was recovered from history rather
than rebuilt (`docs/features/maquette-l01/DESIGN.md`), so the risk is not that
someone writes it wrong: it is that someone removes a key, or restores the one
key that was deliberately left empty.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "frontend" / "maquette" / "oracle.py"
RECIPE_FILE = ROOT / "frontend" / "maquette" / "regions.json"


def load():
    """Imports the oracle module by path.

    Returns:
        The imported module.
    """
    spec = importlib.util.spec_from_file_location("maquette_oracle", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recipe_has_the_six_recovered_keys():
    """The recovered recipe keeps every key, and gains none by accident."""
    probe = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))["probe"]
    assert {key for key in probe if not key.startswith("$")} == {
        "viewport",
        "assertBeforeMeasuring",
        "computedStyleSubset",
        "knownAbsent",
        "neutralise",
        "allowlist",
    }


def test_computed_style_subset_is_the_recovered_seventeen_plus_two():
    """Nineteen: the recovered seventeen, plus the two L01 measured a hole for.

    `opacity` and `visibility` were added because `#scrim` opening changes
    NEITHER the other seventeen NOR its bounding rectangle — the overlay could
    stop appearing altogether and this instrument would stay green.
    """
    probe = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))["probe"]
    assert len(probe["computedStyleSubset"]) == 19
    assert len(set(probe["computedStyleSubset"])) == 19
    assert {"opacity", "visibility"} <= set(probe["computedStyleSubset"])


def test_allowlist_starts_empty():
    """The one key that changed on recovery, and it must stay changed.

    Its single historical entry declared a MAQUETTE-VS-APP divergence, and this
    oracle compares the maquette to itself at two commits. An entry restored
    here would excuse a divergence for a comparison the instrument never makes —
    which is how an allowlist stops being a list of exceptions and starts being
    a list of things nobody looks at.
    """
    probe = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))["probe"]
    assert probe["allowlist"] == []


def test_every_known_absent_entry_carries_a_reason():
    """An excuse with no reason is an excuse nobody can review."""
    probe = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))["probe"]
    for entry in probe["knownAbsent"]:
        assert entry["cause"].strip(), entry


def test_every_neutralise_entry_carries_a_justification():
    """Removing a node before measuring changes the document; say why."""
    probe = json.loads(RECIPE_FILE.read_text(encoding="utf-8"))["probe"]
    for entry in probe["neutralise"]:
        assert entry["justification"].strip(), entry


def test_load_recipe_refuses_a_record_with_no_probe(tmp_path, monkeypatch):
    """Measuring without the recipe answers a different question, confidently.

    A viewport that is not 390 wide, a computed subset that is not the
    seventeen — the figures would still print. So the absence of the block is a
    hard stop, not a default.
    """
    module = load()
    empty = tmp_path / "regions.json"
    empty.write_text(json.dumps({"$comment": "no probe here"}), encoding="utf-8")
    monkeypatch.setattr(module, "RECIPE_FILE", empty)
    with pytest.raises(SystemExit) as raised:
        module.load_recipe()
    assert "probe" in str(raised.value)


def test_context_options_come_from_the_recipe_not_from_constants():
    """The viewport is READ, so editing the recipe moves the measurement."""
    module = load()
    options = module.context_options(
        {
            "viewport": {"width": 411, "height": 731, "deviceScaleFactor": 3, "isMobile": True, "hasTouch": True},
        }
    )
    assert options["viewport"] == {"width": 411, "height": 731}
    assert options["device_scale_factor"] == 3
    assert options["is_mobile"] is True
    assert options["has_touch"] is True


def test_appearance_is_pinned_dark():
    """A headless browser's colour-scheme preference is an accident.

    The document's « système » mode follows that preference, so an oracle that
    inherits it measures a different document on a different machine.
    """
    module = load()
    options = module.context_options(
        {
            "viewport": {"width": 390, "height": 844, "deviceScaleFactor": 2, "isMobile": True, "hasTouch": True},
        }
    )
    assert options["color_scheme"] == "dark"


def test_rect_precision_is_declared_and_keeps_half_pixels():
    """Sub-pixel layout at DPR 2 produces legitimate halves; noise sits below."""
    module = load()
    assert module.RECT_PRECISION == 1


def test_it_reads_the_harness_host_never_the_design_host():
    """`serve.py` answers 401 without a session.

    Pointed at it, this would measure the sign-in screen and report every state
    as identical — a green run over nothing, which is the failure this whole
    instrument exists to make impossible.
    """
    module = load()
    assert module.PROTOTYPE == "http://127.0.0.1:8899/wrapped.html"
    assert "8712" not in module.PROTOTYPE
