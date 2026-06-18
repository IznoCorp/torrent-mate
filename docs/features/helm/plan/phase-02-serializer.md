# Phase 2 — Serializer (render_pipeline)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `core/config_serialize.py` with `RenderedPipeline` and `render_pipeline(draft)`,
which converts a `PipelineDraft` into valid `transitions.yml` and `columns.yml` YAML strings that
the existing loaders accept.

**Architecture:** Pure `core` layer. The serializer mirrors the shape of the shipped renderer
`render_transitions_yaml` (`core/transitions_defaults.py:648-684`) — same `yaml.safe_dump` kwargs,
same 3-line permission_mode comment header. The round-trip test (`load(render(from_loaded(X))) ==semantic== load(X)`)
is the hard gate for this phase.

**Tech Stack:** `yaml` (PyYAML, already a dependency). No new deps.

## Global Constraints

- `core/` imports ONLY stdlib + `yaml` + sibling `core` modules.
- Google-style docstrings on all new modules/classes/functions.
- Module size hard ceiling: 1000 LOC.
- Tests live in `tests/core/`.

---

## Task 2.1 — `core/config_serialize.py` + round-trip tests

**Files:**
- Create: `src/kanbanmate/core/config_serialize.py`
- Create: `tests/core/test_config_serialize.py`

**Interfaces:**
- Consumes: `PipelineDraft` from `core.config_model` (Phase 1)
- Produces:
  - `RenderedPipeline(transitions: str, columns: str)` dataclass
  - `render_pipeline(draft: PipelineDraft) -> RenderedPipeline`
- Consumed by: Phase 3 (validator oracle pass), Phase 4 (config service `.render()`), Phase 5 (HTTP `/api/config/render` endpoint)

**Key design decisions:**
- `transitions.yml` output: `yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)` — same kwargs as `core/transitions_defaults.py:678`.
- The 3-line permission_mode comment header (`core/transitions_defaults.py:679-683`) is prepended verbatim.
- Multiline prompts serialize as block scalars automatically (PyYAML emits these for `\n`-bearing strings).
- `doc` shape: `{project: ..., defaults: {concurrency_cap: ..., move_rate_limit_per_hour: ...}, transitions: [...]}` — same top-level shape `load_transitions` consumes (`core/transitions.py:285-299`).
- Each transition row: emit only non-empty/non-default fields; `prompt: None` → key omitted; `advance: "stop"` → key can be omitted (the loader defaults to `"stop"`); `on_fail: ""` → key omitted.
- `from_col` / `to_col` are the authoring shape (`str | list[str]`) — emitted directly; PyYAML renders a `list[str]` as a block list, reproducing the multi-source row exactly.
- `columns.yml` output: `{columns: [{key, name[, action: teardown]}]}` — `column_class == "reactive"` emits `action: teardown`; `"inert"` emits no `action` key (inverse of `core/columns._resolve_class`, `core/columns.py:42-45`).

- [ ] **Step 2.1.1: Write the failing round-trip tests**

```python
# tests/core/test_config_serialize.py
"""Round-trip tests for :mod:`kanbanmate.core.config_serialize`.

The hard invariant: load_transitions(render_pipeline(from_loaded(X)).transitions)
is SEMANTICALLY equal to load_transitions(X) — compare .get() over every real
(from, to) edge and launch_target_columns(). Likewise for columns.
"""

from __future__ import annotations

import importlib.resources

from kanbanmate.core.config_model import PipelineDraft
from kanbanmate.core.config_serialize import RenderedPipeline, render_pipeline
from kanbanmate.core.transitions import load_transitions
from kanbanmate.core.columns import load_columns
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
    assert len(col_map) == 14


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
```

- [ ] **Step 2.1.2: Run tests to verify they fail**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_serialize.py -v
```

Expected: `ImportError: cannot import name 'render_pipeline' from 'kanbanmate.core.config_serialize'`

- [ ] **Step 2.1.3: Create `core/config_serialize.py`**

```python
# src/kanbanmate/core/config_serialize.py
"""Serializer: render a PipelineDraft back to transitions.yml + columns.yml (DESIGN §8).

``render_pipeline(draft)`` is the inverse of ``PipelineDraft.from_loaded``:
it takes the editable draft and emits two YAML strings that the existing core
loaders (``load_transitions``, ``load_columns``) accept without modification.

The output shape mirrors the shipped renderer
(``core/transitions_defaults.render_transitions_yaml``, ``core/transitions_defaults.py:648-684``):
same ``yaml.safe_dump`` kwargs (``sort_keys=False``, ``allow_unicode=True``,
``width=120``) and the same 3-line permission_mode comment header prepended
verbatim.  Comments inside rows and key ordering within a row are NOT preserved
— helm owns the file after ``kanban init`` and the rendered file carries only
the 3-line header.

Layering: ``core`` only — no I/O, no adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from kanbanmate.core.config_model import PipelineDraft


# The 3-line permission_mode header prepended verbatim to transitions.yml output.
# Must match core/transitions_defaults.py:679-683 exactly (the daemon parses it as a
# comment, but operators and PR-2 SPA may display it).
_TRANSITIONS_HEADER = (
    "# permission_mode (per launch transition): claude --permission-mode for the session.\n"
    "# Configurable per transition; default 'auto' (headless-safe; STILL enforces deny).\n"
    "# Allowed: default | acceptEdits | auto | dontAsk | plan. bypassPermissions is NOT allowed.\n"
)


@dataclass
class RenderedPipeline:
    """Output of :func:`render_pipeline` — both YAML documents as strings.

    Attributes:
        transitions: The rendered ``transitions.yml`` content.
        columns: The rendered ``columns.yml`` content.
    """

    transitions: str
    columns: str


def _transition_row(t: "kanbanmate.core.config_model.TransitionDef") -> dict[str, Any]:  # type: ignore[name-defined]
    """Convert a TransitionDef into a YAML-serialisable dict row.

    Omits keys whose value is falsy / default to match the shape ``load_transitions``
    accepts and to keep the rendered file clean (no ``advance: stop`` noise on
    every no-op row).  The loader defaults ``advance`` to ``"stop"`` when the key is
    absent (``core/transitions.py:307``), so omitting it is safe.

    Args:
        t: The transition to serialise.

    Returns:
        A dict suitable for ``yaml.safe_dump``.
    """
    # ``from_col`` / ``to_col`` are already the authoring shape (``str``,
    # ``"*"``, or ``list[str]``) — yaml.safe_dump emits a scalar or a block
    # list directly, reproducing the source exactly. No decoding needed.
    row: dict[str, Any] = {
        "from": t.from_col,
        "to": t.to_col,
    }
    # Emit only non-empty optional fields so the rendered YAML stays compact.
    if t.profile:
        row["profile"] = t.profile
    if t.prompt is not None:
        row["prompt"] = t.prompt
    if t.script is not None:
        row["script"] = t.script
    # Omit "stop" (the loader default) to reduce noise; keep explicit values.
    if t.advance and t.advance != "stop":
        row["advance"] = t.advance
    if t.on_fail:
        row["on_fail"] = t.on_fail
    # Omit "auto" (the loader default) to reduce noise; keep explicit values.
    if t.permission_mode and t.permission_mode != "auto":
        row["permission_mode"] = t.permission_mode
    return row


def render_pipeline(draft: PipelineDraft) -> RenderedPipeline:
    """Render a :class:`~kanbanmate.core.config_model.PipelineDraft` to YAML strings.

    Produces a ``transitions.yml`` and a ``columns.yml`` document that the
    existing core loaders accept without modification.  The round-trip contract:
    ``load_transitions(render_pipeline(from_loaded(X)).transitions)`` is
    semantically equal to ``load_transitions(X)`` — every ``(from, to)`` edge
    resolves to the same :class:`~kanbanmate.core.transitions.Transition`.

    Args:
        draft: The editable pipeline draft to serialise.

    Returns:
        A :class:`RenderedPipeline` containing the ``transitions.yml`` and
        ``columns.yml`` YAML strings.
    """
    # Build the transitions document dict — same top-level shape as
    # load_transitions expects (core/transitions.py:285-299).
    transitions_doc: dict[str, Any] = {
        "project": draft.binding.project,
        "defaults": {
            "concurrency_cap": draft.definition.defaults.concurrency_cap,
            "move_rate_limit_per_hour": draft.definition.defaults.move_rate_limit_per_hour,
        },
        "transitions": [_transition_row(t) for t in draft.definition.transitions],
    }
    transitions_body = yaml.safe_dump(
        transitions_doc,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    transitions_yaml = _TRANSITIONS_HEADER + transitions_body

    # Build the columns document dict — inverse of load_columns/core.columns._resolve_class
    # (core/columns.py:42-45): "reactive" → action: teardown; "inert" → no action key.
    columns_list: list[dict[str, Any]] = []
    for col in draft.definition.columns:
        entry: dict[str, Any] = {"key": col.key, "name": col.name}
        if col.column_class == "reactive":
            entry["action"] = "teardown"
        columns_list.append(entry)
    columns_doc: dict[str, Any] = {"columns": columns_list}
    columns_yaml = yaml.safe_dump(
        columns_doc,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )

    return RenderedPipeline(transitions=transitions_yaml, columns=columns_yaml)
```

Fix the type hint in `_transition_row` — replace the forward reference with the correct import:

```python
from kanbanmate.core.config_model import PipelineDraft, TransitionDef
```

And update `_transition_row(t: TransitionDef)` signature accordingly.

- [ ] **Step 2.1.4: Run round-trip tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_serialize.py -v
```

Expected: all PASS. If `test_round_trip_every_real_edge` fails, check that the multi-source Done edge (`["Backlog","Brainstorming","Spec","Plan","Planned","ReadyToDev"]` → `"Done"`) is stored as a `list[str]` on `from_col` and re-emitted by PyYAML as a block list (the loader then re-expands it to the same per-edge `.get()` results).

- [ ] **Step 2.1.5: Run layering guard + full test suite**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/test_layering.py tests/core/ -v
```

Expected: all PASS.

- [ ] **Step 2.1.6: Phase gate**

```bash
cd /Users/izno/dev/worktrees/ticket-5
make lint
make test
make check
python -c "import kanbanmate"
```

Expected: all clean.

- [ ] **Step 2.1.7: Commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add src/kanbanmate/core/config_serialize.py tests/core/test_config_serialize.py
git commit -m "feat(helm): core/config_serialize.py — render_pipeline round-trip serializer"
```
