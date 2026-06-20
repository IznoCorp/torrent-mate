"""Mutable, JSON-serializable draft model for the pipeline config (DESIGN §4–§5).

The two YAML files that configure the engine (``transitions.yml`` + ``columns.yml``)
are parsed by frozen, lookup-optimised core loaders that discard row order and
wildcard shape. This module provides an EDITABLE intermediate representation:
plain dataclasses that survive a JSON round-trip and can be rendered back to
valid YAML via :mod:`~kanbanmate.core.config_serialize`.

The draft is created by :meth:`PipelineDraft.from_loaded`, which re-parses the
raw YAML strings with ``yaml.safe_load`` to recover the ordered ``transitions:``
rows (the only way to recover authoring shape), then calls the real loaders as a
validation oracle — if the loaders raise, ``from_loaded`` re-raises rather than
producing an editable draft from invalid input.

Layering: ``core`` only — no I/O, no adapters, no app imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from kanbanmate.core.columns import load_columns
from kanbanmate.core.transitions import load_transitions


@dataclass
class ColumnDef:
    """A single board column in the editable draft.

    Attributes:
        key: Stable machine-readable identifier (e.g. ``"InProgress"``).
        name: Human-readable GitHub Projects v2 label (e.g. ``"In Progress"``).
        column_class: The plain string ``"reactive"`` or ``"inert"`` — mirrors
            :attr:`~kanbanmate.core.domain.ColumnClass` values
            (``core/domain.py:34-35``) but kept as a string so the draft is
            JSON-friendly and free of enum imports.
    """

    key: str
    name: str
    column_class: str  # "reactive" | "inert"


@dataclass
class TransitionDef:
    """A single whitelist row in the editable draft.

    Mirrors :class:`~kanbanmate.core.transitions.Transition`
    (``core/transitions.py:50-101``) so a round-trip through the serializer
    produces semantically identical loader output. The one widening: the
    EDITABLE draft is the PRE-expansion authoring shape, so ``from_col`` /
    ``to_col`` are ``str | list[str]`` — a YAML list authors several edges that
    share one action (the loader's ``_expand_side`` cartesian product,
    ``core/transitions.py:47-51``; e.g. the shipped early-skip row
    ``from: [Backlog, Brainstorming, Spec, Plan, ReadyToDev]`` →
    ``to: Done``). The frozen runtime ``Transition.from_col`` is a single
    post-expansion ``str``; the draft preserves the list so render is exact and
    list-expansion is NOT re-collapsed at load (§5). A plain ``list[str]`` is
    natively JSON-serialisable — no encoding sentinel is used.

    Attributes:
        from_col: Source column key, ``"*"`` wildcard, or a ``list[str]`` of
            keys (authoring sugar for several edges sharing one action).
        to_col: Destination column key, ``"*"`` wildcard, or a ``list[str]``.
        profile: Permission profile name (``"docs"`` / ``"prepare"`` / ``"dev"`` /
            ``"check"``).  Empty string means no profile is set.
        prompt: Launch prompt template with ``{{placeholder}}`` tokens, or
            ``None`` for no-op / script-only transitions.
        script: Mechanical script path, or ``None``.
        advance: Post-action advance directive: ``"stop"`` or
            ``"auto:<column>"``.
        on_fail: Failure routing: ``""`` (default), ``"move:<column>"``, or
            ``"rollback"``.
        permission_mode: ``claude --permission-mode`` value for the session.
    """

    from_col: str | list[str]
    to_col: str | list[str]
    profile: str = ""
    prompt: str | None = None
    script: str | None = None
    advance: str = "stop"
    on_fail: str = ""
    permission_mode: str = "auto"


@dataclass
class Defaults:
    """Board-wide pipeline defaults from the ``transitions.yml`` ``defaults:`` block.

    The ``transitions.yml`` ``defaults:`` block is the authoritative source
    (DESIGN §10 / ``app/wiring.py:229-230``). The ``columns.yml`` block is a
    documented fallback only and ships commented out.

    Attributes:
        concurrency_cap: Maximum concurrent agent sessions across the whole
            project. Default 3 (``core/transitions_defaults.py:644``).
        move_rate_limit_per_hour: Per-item AUTO/bot move rate limit per hour.
            Default 10 (``core/transitions_defaults.py:645``).
    """

    concurrency_cap: int
    move_rate_limit_per_hour: int


@dataclass
class Binding:
    """GitHub-specific wiring for the draft (DESIGN §4.2).

    Separating the backend-neutral ``Definition`` from the GitHub ``Binding``
    is the schema evolution that lets PR 3 swap the backend without touching
    the model.

    Attributes:
        project: The ``project:`` header from ``transitions.yml``
            (``TransitionConfig.project``, ``core/transitions.py:166``), an
            ``owner/repo``-style slug.
        option_map: Column key → GitHub Status-option id binding. Lives in
            the runtime registry (``ProjectEntry.option_map``,
            ``cli/init.py:136``), not in ``columns.yml``. In PR 1 this is
            read-only metadata; ``from_loaded`` always returns ``{}`` here
            since ``core`` has no registry access (no I/O). The HTTP layer
            surfaces it from the registry entry.
    """

    project: str
    option_map: dict[str, str] = field(default_factory=dict)


@dataclass
class Definition:
    """The backend-neutral pipeline shape (DESIGN §4.1).

    Attributes:
        columns: Ordered column list mirroring the ``columns.yml`` order.
        transitions: Ordered transition list mirroring the ``transitions.yml``
            rows (row order matters for wildcard-precedence shadow warnings).
        defaults: Board-wide concurrency and rate-limit settings.
    """

    columns: list[ColumnDef]
    transitions: list[TransitionDef]
    defaults: Defaults


@dataclass
class PipelineDraft:
    """Editable, JSON-serializable draft of the full pipeline config (DESIGN §4–§5).

    Attributes:
        definition: Backend-neutral pipeline shape.
        binding: GitHub-specific wiring (read-only in PR 1).
    """

    definition: Definition
    binding: Binding

    @classmethod
    def from_loaded(cls, transitions_yaml: str, columns_yaml: str) -> "PipelineDraft":
        """Rebuild an editable draft from the raw YAML strings.

        Re-parses the raw ``transitions_yaml`` with ``yaml.safe_load`` to
        recover ordered rows and wildcard shape (the frozen
        :class:`~kanbanmate.core.transitions.TransitionConfig` discards both,
        ``core/transitions.py:156-244``).  Calls the real loaders as a
        validation oracle — any ``ValueError`` propagates immediately so the
        caller never receives a draft from input the daemon would crash on.

        ``binding.option_map`` is always ``{}`` here: ``core`` has no registry
        access (no I/O).  The HTTP layer injects the real map from the
        registry entry when surfacing the draft to callers.

        Args:
            transitions_yaml: The raw ``transitions.yml`` content as a string.
            columns_yaml: The raw ``columns.yml`` content as a string.

        Returns:
            An editable :class:`PipelineDraft` reflecting the input files.

        Raises:
            ValueError: If either file fails to parse (invalid YAML) or is
                structurally invalid (propagated from the loader oracle, or a
                non-mapping transitions document).
        """
        # Re-parse the raw transitions YAML FIRST so a malformed, empty, or
        # non-mapping document fails as the documented ValueError. load_transitions
        # itself leaks yaml.YAMLError on bad syntax and AttributeError on a
        # non-dict top level (core/transitions.py:285 does `safe_load(...) or {}`
        # with no guard, unlike load_columns which raises a clean ValueError,
        # core/columns.py:69-72). Guarding here keeps the `Raises: ValueError`
        # contract honest for callers that catch ValueError (e.g. ConfigService.load
        # → the HTTP layer's `except (ValueError, FileNotFoundError)`).
        try:
            raw: Any = yaml.safe_load(transitions_yaml)
        except yaml.YAMLError as exc:
            raise ValueError(f"transitions.yml is not valid YAML: {exc}") from exc
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("transitions.yml must be a top-level mapping")

        # Oracle pass: run the real loaders to catch any defect the raw re-parse
        # might miss.  The return value is discarded — we only care that the
        # loaders do NOT raise (they are the daemon's source of truth).  A
        # malformed columns.yml surfaces as yaml.YAMLError, re-raised as ValueError
        # to honour the contract (load_columns already raises ValueError for a
        # non-mapping document).
        try:
            load_transitions(transitions_yaml)
            load_columns(columns_yaml)
        except yaml.YAMLError as exc:
            raise ValueError(f"config YAML failed to parse: {exc}") from exc

        # Recover ordered rows + the project slug + defaults from the raw dict
        # (the exact structure load_transitions consumed at transitions.py:285-299).
        project: str = raw.get("project", "") or ""
        raw_defaults: dict[str, Any] = raw.get("defaults") or {}
        concurrency_cap: int = int(raw_defaults.get("concurrency_cap", 3))
        move_rate_limit_per_hour: int = int(raw_defaults.get("move_rate_limit_per_hour", 10))

        def _coerce(val: object) -> str | list[str]:
            """Keep a from/to YAML value as the draft's str | list[str]."""
            if isinstance(val, list):
                return [str(v) for v in val]
            return str(val) if val is not None else ""

        transitions: list[TransitionDef] = []
        for row in raw.get("transitions") or []:
            # A row's ``from``/``to`` may be a scalar key, ``"*"``, or a YAML
            # list (authoring sugar — the loader expands lists to a cartesian
            # product of edges, ``core/transitions.py:47-51``). We preserve the
            # AUTHORING shape verbatim: a list stays a ``list[str]`` (natively
            # JSON-serialisable), a scalar stays a ``str``. List-expansion is
            # NOT re-collapsed at load (§5) and is NOT performed here — the
            # serializer re-emits the exact scalar/list, and the loader oracle
            # expands on the next load. (The oracle pass above already proved
            # every row is well-formed.)
            transitions.append(
                TransitionDef(
                    from_col=_coerce(row.get("from", "")),
                    to_col=_coerce(row.get("to", "")),
                    profile=str(row.get("profile") or ""),
                    prompt=row.get("prompt") or None,
                    script=row.get("script") or None,
                    advance=str(row.get("advance") or "stop"),
                    on_fail=str(row.get("on_fail") or ""),
                    permission_mode=str(row.get("permission_mode") or "auto"),
                )
            )

        # Re-parse columns via load_columns (order-preserving dict insertion).
        col_map = load_columns(columns_yaml)
        columns: list[ColumnDef] = [
            ColumnDef(
                key=col.key,
                name=col.name,
                # ColumnClass.REACTIVE.value == "reactive" (core/domain.py:34);
                # store the plain string, not the enum, for JSON-friendliness.
                column_class=col.column_class.value,
            )
            for col in col_map.values()
        ]

        return cls(
            definition=Definition(
                columns=columns,
                transitions=transitions,
                defaults=Defaults(
                    concurrency_cap=concurrency_cap,
                    move_rate_limit_per_hour=move_rate_limit_per_hour,
                ),
            ),
            binding=Binding(project=project, option_map={}),
        )
