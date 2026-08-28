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

    It reads the host's ROOT, not `wrapped.html`. A page sits at a real path
    since L05, and `/wrapped.html` matches no route: pointed there the router
    would render its not-found page and all 2 739 measurements would describe
    that instead of the prototype. The harness host folds every unresolved
    address onto the document, so the root is the address to read.
    """
    module = load()
    assert module.PROTOTYPE == "http://127.0.0.1:8899/"
    assert "wrapped.html" not in module.PROTOTYPE
    assert "8712" not in module.PROTOTYPE


def test_allowlist_entry_without_a_reason_is_refused():
    """A reason or nothing.

    An allowlist is how an oracle is disarmed one entry at a time — friction
    cause 5, which kills instruments within weeks. An excuse nobody wrote down
    is an excuse nobody can review, so the empty one is a hard stop rather than
    a warning.
    """
    module = load()
    with pytest.raises(SystemExit) as raised:
        module.allowed(
            {
                "allowlist": [
                    {"region": "shell/scrim", "property": "opacity", "justification": ""},
                ]
            }
        )
    assert "justification" in str(raised.value)


def test_allowlist_entry_with_a_reason_excuses_exactly_one_pair():
    """And nothing beyond it — not the region, not the property elsewhere."""
    module = load()
    pairs = module.allowed(
        {
            "allowlist": [
                {"region": "shell/scrim", "property": "opacity", "justification": "measured, and written down"},
            ]
        }
    )
    assert pairs == {("shell/scrim", "opacity")}


def _measure(**style):
    """Builds a measurement with a fixed rectangle and the given style."""
    return {"matches": 1, "rect": {"x": 0, "y": 0, "width": 10, "height": 10}, "style": style}


def test_compare_names_the_property_and_both_sides():
    """The report is what a reviewer reads; a bare « differs » is useless."""
    module = load()
    findings = module.compare(
        {"lib-list": {"library/body": _measure(**{"font-size": "12px"})}},
        {"lib-list": {"library/body": _measure(**{"font-size": "13px"})}},
        set(),
    )
    assert len(findings) == 1
    state, region, what = findings[0]
    assert (state, region) == ("lib-list", "library/body")
    assert "font-size" in what and "12px" in what and "13px" in what


def test_compare_honours_the_allowlist_for_that_pair_only():
    """An excuse is scoped to one region AND one property."""
    module = load()
    reference = {"s": {"r": _measure(**{"opacity": "1", "color": "red"})}}
    fresh = {"s": {"r": _measure(**{"opacity": "0", "color": "blue"})}}
    findings = module.compare(reference, fresh, {("r", "opacity")})
    assert len(findings) == 1
    assert "color" in findings[0][2]


def test_compare_reports_a_region_appearing_or_vanishing():
    """Absence is data. A region that stops resolving is a divergence."""
    module = load()
    findings = module.compare({"s": {"r": _measure(**{"opacity": "1"})}}, {"s": {"r": None}}, set())
    assert len(findings) == 1
    assert "present" in findings[0][2]


def test_compare_says_nothing_when_nothing_moved():
    """The common path, and the one a noisy oracle loses first."""
    module = load()
    reading = {"s": {"r": _measure(**{"opacity": "1"})}}
    assert module.compare(reading, json.loads(json.dumps(reading)), set()) == []


def test_the_reference_is_sorted_so_a_diff_is_readable():
    """Friction cause 4: an unsorted reference buries one change under hundreds.

    Insertion order is stable within a run and unstable across a refactor, so
    the sort is explicit rather than inherited from the dict.
    """
    module = load()
    text = module.render_reference(
        {"zulu": {"b/x": None, "a/x": None}, "alpha": {"b/x": None}}, {"a/x": {}, "b/x": {}}, ["alpha", "zulu"]
    )
    document = json.loads(text)
    assert list(document["measurements"]) == ["alpha", "zulu"]
    assert list(document["measurements"]["zulu"]) == ["a/x", "b/x"]
    assert text.endswith("\n")


def test_the_reference_records_the_commit_it_was_taken_at():
    """« Known-good » with no SHA means nothing."""
    module = load()
    document = json.loads(module.render_reference({}, {}, []))
    assert document["baseCommit"]
    assert document["counts"] == {"states": 0, "regions": 0}


def test_the_reference_records_the_platform_it_was_taken_on():
    """A measurement is not portable, and the reference has to say so.

    Learned from a red pipeline: the same unmodified tree reports a height of
    1477 on a GitHub Linux runner where it records 1474.1 on the machine that
    took the reference. Three pixels of font metrics, and not a change to
    anything — but compared across platforms it is a wall of divergences that
    are all false, which is how an oracle gets muted within a week.
    """
    module = load()
    document = json.loads(module.render_reference({}, {}, []))
    assert document["platform"] == module.fingerprint()
    assert "/" in document["platform"]


def test_the_committed_reference_carries_a_platform():
    """The stored file, not just a freshly rendered one."""
    reference = json.loads((ROOT / "frontend" / "maquette" / "oracle-reference.json").read_text(encoding="utf-8"))
    assert reference["platform"]
    # The pin follows the corpus on purpose. How many states exist is counted by execution
    # elsewhere (`window.__states()`); what this assertion pins is the COMMITTED reference's
    # own bookkeeping, so a reference recorded on a different corpus cannot pass. It moves
    # only when a state is added deliberately — 83 since the `mediasheet-no-poster` state
    # (7ba93b07), and 84 since `settings-field-schedule`, the state for the NINTH kind of
    # settings field. That kind existed nowhere before L09: the interface guessed a cron
    # from the shape of its value, and the six cron settings rendered as raw cron with no
    # state showing one for anybody to look at.
    #
    # 87 SINCE L10, and the three are `relay-reconnecting`, `relay-lost` and `relay-refused`:
    # what the interface says about its own connection. Until that lot the header carried
    # « Connecté » as a LITERAL, beside a green dot, with no connection anywhere in the
    # prototype (B-155) — §8 of the constitution inverted, since a permanent claim of liveness
    # is worse than silence. The reference GREW rather than moved: 3 states added, 0 removed,
    # and not one of the 84 existing measurements changed.
    assert reference["counts"] == {"states": 87, "regions": 33}
