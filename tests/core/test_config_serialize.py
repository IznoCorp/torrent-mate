"""Round-trip tests for :mod:`kanbanmate.core.config_serialize`.

The hard invariant: load_transitions(render_pipeline(from_loaded(X)).transitions)
is SEMANTICALLY equal to load_transitions(X) — compare .get() over every real
(from, to) edge and launch_target_columns(). Likewise for columns.
"""

from __future__ import annotations

import importlib.resources

from kanbanmate.core.columns import load_columns
from kanbanmate.core.config_model import PipelineDraft
from kanbanmate.core.config_serialize import RenderedPipeline, render_pipeline
from kanbanmate.core.transitions import load_transitions
from kanbanmate.core.transitions_defaults import (
    DEFAULT_TRANSITIONS,
    render_transitions_yaml,
)


def _columns_yaml() -> str:
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    return ref.read_text(encoding="utf-8")


def _transitions_yaml() -> str:
    return render_transitions_yaml("owner/repo")


def _draft() -> PipelineDraft:
    return PipelineDraft.from_loaded(_transitions_yaml(), _columns_yaml())


def test_render_pipeline_returns_rendered_pipeline() -> None:
    """render_pipeline must return a RenderedPipeline with two non-empty strings."""
    result = render_pipeline(_draft())
    assert isinstance(result, RenderedPipeline)
    assert isinstance(result.transitions, str) and result.transitions
    assert isinstance(result.columns, str) and result.columns


def test_render_transitions_parseable() -> None:
    """The rendered transitions.yml must be parseable by load_transitions."""
    rendered = render_pipeline(_draft())
    # Must not raise — if it does, the serializer emits something the daemon crashes on.
    tc = load_transitions(rendered.transitions)
    assert tc.project == "owner/repo"


def test_render_columns_parseable() -> None:
    """The rendered columns.yml must be parseable by load_columns."""
    rendered = render_pipeline(_draft())
    col_map = load_columns(rendered.columns)
    assert len(col_map) == 13


def test_round_trip_every_real_edge() -> None:
    """Every real (from, to) edge from DEFAULT_TRANSITIONS resolves the same way
    before and after a full round-trip through from_loaded → render_pipeline.

    This tests SEMANTIC equality (same Transition object from .get()), not
    byte-level YAML equality (comments/key order are not preserved).
    """
    original_tc = load_transitions(_transitions_yaml())
    rendered = render_pipeline(_draft())
    round_tripped_tc = load_transitions(rendered.transitions)

    # Collect the concrete (from, to) pairs from DEFAULT_TRANSITIONS.
    # List-form entries are expanded into their cartesian product by the loader;
    # we mirror that expansion here so we test real edges, not list objects.
    edges: list[tuple[str, str]] = []
    for row in DEFAULT_TRANSITIONS:
        from_val = row["from"]
        to_val = row["to"]
        froms = from_val if isinstance(from_val, list) else [from_val]
        tos = to_val if isinstance(to_val, list) else [to_val]
        for f in froms:
            for t in tos:
                # Skip wildcard combinations — .get("*", "anything") is not a
                # real edge call; concrete edges only.
                if f != "*" and t != "*":
                    edges.append((f, t))

    assert edges, "No concrete edges found — DEFAULT_TRANSITIONS may have changed"

    for from_col, to_col in edges:
        orig = original_tc.get(from_col, to_col)
        rt = round_tripped_tc.get(from_col, to_col)
        assert (orig is None) == (rt is None), (
            f"Edge ({from_col!r}, {to_col!r}): original matched={orig is not None}, "
            f"round-tripped matched={rt is not None}"
        )
        if orig is not None and rt is not None:
            assert orig.prompt == rt.prompt, f"Edge ({from_col!r}, {to_col!r}): prompt mismatch"
            assert orig.script == rt.script, f"Edge ({from_col!r}, {to_col!r}): script mismatch"
            assert orig.advance == rt.advance, f"Edge ({from_col!r}, {to_col!r}): advance mismatch"
            assert orig.on_fail == rt.on_fail, f"Edge ({from_col!r}, {to_col!r}): on_fail mismatch"
            assert orig.profile == rt.profile, f"Edge ({from_col!r}, {to_col!r}): profile mismatch"
            assert orig.permission_mode == rt.permission_mode, (
                f"Edge ({from_col!r}, {to_col!r}): permission_mode mismatch"
            )


def test_round_trip_launch_target_columns() -> None:
    """launch_target_columns() must be identical after a round-trip."""
    original_tc = load_transitions(_transitions_yaml())
    rendered = render_pipeline(_draft())
    round_tripped_tc = load_transitions(rendered.transitions)
    assert original_tc.launch_target_columns() == round_tripped_tc.launch_target_columns()


def test_round_trip_column_dict_equality() -> None:
    """load_columns output must be equal before and after the round-trip."""
    original_cols = load_columns(_columns_yaml())
    rendered = render_pipeline(_draft())
    round_tripped_cols = load_columns(rendered.columns)

    assert set(original_cols.keys()) == set(round_tripped_cols.keys())
    for key in original_cols:
        orig = original_cols[key]
        rt = round_tripped_cols[key]
        assert orig.key == rt.key, f"Column {key!r}: key mismatch"
        assert orig.name == rt.name, f"Column {key!r}: name mismatch"
        assert orig.column_class == rt.column_class, f"Column {key!r}: column_class mismatch"


def test_render_transitions_has_comment_header() -> None:
    """The rendered transitions.yml must start with the 3-line permission_mode header."""
    rendered = render_pipeline(_draft())
    assert rendered.transitions.startswith("# permission_mode"), (
        "Missing the mandatory 3-line permission_mode comment header "
        "(mirrors core/transitions_defaults.py:679-683)"
    )


def test_render_columns_cancel_has_action_teardown() -> None:
    """Cancel column must serialise as 'action: teardown' in the rendered YAML."""
    rendered = render_pipeline(_draft())
    assert "action: teardown" in rendered.columns


def test_render_columns_inert_no_action_key() -> None:
    """Inert columns must NOT have an 'action:' key in the rendered YAML."""
    import yaml as pyyaml

    rendered = render_pipeline(_draft())
    doc = pyyaml.safe_load(rendered.columns)
    for entry in doc["columns"]:
        if entry["key"] != "Cancel":
            assert "action" not in entry, (
                f"Column {entry['key']!r} is inert but has an 'action' key"
            )
