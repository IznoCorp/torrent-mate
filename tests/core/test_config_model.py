"""Tests for :mod:`kanbanmate.core.config_model`.

Uses the shipped config (render_transitions_yaml + columns.yml.tmpl) to assert
that from_loaded produces a structurally-correct PipelineDraft.
"""

from __future__ import annotations

import importlib.resources

import pytest

from kanbanmate.core.config_model import (
    PipelineDraft,
    TransitionDef,
)
from kanbanmate.core.transitions_defaults import render_transitions_yaml


def _columns_yaml() -> str:
    """Return the shipped columns.yml.tmpl content as a string."""
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    return ref.read_text(encoding="utf-8")


def _transitions_yaml() -> str:
    return render_transitions_yaml("owner/repo")


def test_from_loaded_column_count() -> None:
    """The shipped board has 14 columns (DESIGN §9) — Ready to merge added before Merge."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    assert len(draft.definition.columns) == 14


def test_from_loaded_cancel_is_reactive() -> None:
    """Cancel is the only reactive column (DESIGN §9)."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    reactive = [c for c in draft.definition.columns if c.column_class == "reactive"]
    assert len(reactive) == 1
    assert reactive[0].key == "Cancel"


def test_from_loaded_column_class_strings() -> None:
    """column_class must be the plain string 'reactive' or 'inert' (never an enum)."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    for col in draft.definition.columns:
        assert col.column_class in ("reactive", "inert"), (
            f"column {col.key!r} has unexpected column_class {col.column_class!r}"
        )


def test_from_loaded_known_keys() -> None:
    """Real column keys (InProgress, PRCI) must appear in the draft."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    keys = {c.key for c in draft.definition.columns}
    assert "InProgress" in keys
    assert "PRCI" in keys


def test_from_loaded_transitions_non_empty() -> None:
    """The shipped transitions.yml produces a non-empty transition list."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    assert len(draft.definition.transitions) > 0


def test_from_loaded_binding_project() -> None:
    """The binding.project field captures the project slug from the YAML header."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    assert draft.binding.project == "owner/repo"


def test_from_loaded_binding_option_map_default_empty() -> None:
    """option_map defaults to {} in PR 1 (no registry access in core)."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    assert draft.binding.option_map == {}


def test_from_loaded_defaults() -> None:
    """Defaults come from the transitions.yml defaults: block."""
    draft = PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())
    assert draft.definition.defaults.concurrency_cap == 3
    assert draft.definition.defaults.move_rate_limit_per_hour == 10


def test_from_loaded_rejects_invalid_transitions_yaml() -> None:
    """from_loaded must raise ValueError when the transitions YAML is malformed."""
    # A transitions row missing its 'to' key is rejected fail-closed by the
    # loader oracle (load_transitions: "entry missing 'from' or 'to'",
    # core/transitions.py:301-302). The empty-string 'from'/'to' shape the plan
    # first suggested is NOT rejected — _expand_side accepts a bare '' as a
    # 1-element side (core/transitions.py:127-128) — so a missing key is used
    # instead to exercise the same propagation path.
    bad_yaml = "project: x\ntransitions:\n  - from: A\n"
    with pytest.raises(ValueError):
        PipelineDraft.from_loaded(bad_yaml, _columns_yaml())


def test_from_loaded_empty_transitions_no_attribute_error() -> None:
    """An empty transitions.yml must not crash with AttributeError.

    yaml.safe_load("") is None; without the `is None` guard, raw.get(...) would
    raise AttributeError — a non-ValueError that callers catching ValueError
    (ConfigService.load, the HTTP layer) would not handle, surfacing an opaque
    500. The loader treats an empty document as a valid empty config, so
    from_loaded yields a graceful empty-transitions draft instead.
    """
    draft = PipelineDraft.from_loaded("", _columns_yaml())
    assert draft.definition.transitions == []
    # Columns still load from the valid columns.yml.
    assert len(draft.definition.columns) == 14


def test_from_loaded_malformed_yaml_raises_value_error() -> None:
    """Syntactically broken YAML must surface as ValueError (not yaml.YAMLError)."""
    # Unbalanced bracket → yaml.scanner/parser error; the documented contract is
    # ValueError, so from_loaded must wrap it.
    malformed = "project: x\ntransitions: [unterminated\n"
    with pytest.raises(ValueError):
        PipelineDraft.from_loaded(malformed, _columns_yaml())


def test_from_loaded_non_mapping_transitions_raises_value_error() -> None:
    """A transitions.yml whose top level is a list/scalar must raise ValueError."""
    # A top-level list parses fine but is not a mapping; without the isinstance
    # guard load_transitions would raise AttributeError on data.get(...).
    with pytest.raises(ValueError):
        PipelineDraft.from_loaded("- a\n- b\n", _columns_yaml())


def test_transition_def_defaults() -> None:
    """TransitionDef carries the same defaults as core.transitions.Transition."""
    t = TransitionDef(from_col="Backlog", to_col="InProgress")
    assert t.profile == ""
    assert t.prompt is None
    assert t.script is None
    assert t.advance == "stop"
    assert t.on_fail == ""
    assert t.permission_mode == "auto"
