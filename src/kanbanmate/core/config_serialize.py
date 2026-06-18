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

from kanbanmate.core.config_model import PipelineDraft, TransitionDef


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


def _transition_row(t: TransitionDef) -> dict[str, Any]:
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
