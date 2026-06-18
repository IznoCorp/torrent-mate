# Phase 1 — Core: profiles relocation + config model

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `core/profiles.py` (relocating `PROFILES` from adapters) and
`core/config_model.py` (the `PipelineDraft` data model + `from_loaded` classmethod that rebuilds
an editable draft from the raw YAML files).

**Architecture:** Pure `core` layer (no I/O, no adapters import). `profiles.py` is a one-liner
tuple that the validator and adapters both import from. `config_model.py` re-parses the raw YAML
string with `yaml.safe_load` to recover row order and wildcard shape that the frozen `TransitionConfig`
discards, then calls the existing loaders as a validation oracle only.

**Tech Stack:** Python 3.12 stdlib (`dataclasses`, `yaml`). No new runtime deps. The existing
`core.transitions.load_transitions` and `core.columns.load_columns` are used as read-only oracles.

## Global Constraints

- `core/` imports ONLY stdlib + `yaml` + sibling `core` modules — the layering guard
  (`tests/test_layering.py`) walks the full AST and will fail if any `adapters`/`app`/`cli`/`daemon`
  import appears anywhere, including function-local imports.
- All new modules/classes/functions must have Google-style docstrings (`Args:`/`Returns:`/`Raises:`).
- Inline comments explain the **why** (not the what), in English.
- Module size: hard ceiling 1000 LOC (`make check` enforces this).
- Tests live in `tests/core/` — never in a flat `tests/` root.
- Conventional Commits for every commit; no AI attribution, no version prefix.

---

## Task 1.1 — `core/profiles.py`: relocate PROFILES

**Files:**
- Create: `src/kanbanmate/core/profiles.py`
- Modify: `src/kanbanmate/adapters/perms.py` (line 337 — replace definition with import)
- Create: `tests/core/test_profiles.py`

**Interfaces:**
- Produces: `PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check")` in `kanbanmate.core.profiles`
- `adapters/perms.py` re-exports `PROFILES` from `core.profiles` so existing call sites
  (`perms.PROFILES`) continue to work unchanged.

- [ ] **Step 1.1.1: Write the failing test**

```python
# tests/core/test_profiles.py
"""Tests for :mod:`kanbanmate.core.profiles`.

Verifies that the canonical PROFILES tuple contains the expected four names and
that it stays in parity with the per-profile allow-list in adapters.perms.
"""

from __future__ import annotations

from kanbanmate.core.profiles import PROFILES


def test_profiles_contains_expected_names() -> None:
    """PROFILES must contain the four documented workflow stages (no more, no less)."""
    assert set(PROFILES) == {"docs", "prepare", "dev", "check"}


def test_profiles_is_tuple() -> None:
    """PROFILES must be a tuple (immutable, hashable)."""
    assert isinstance(PROFILES, tuple)
```

- [ ] **Step 1.1.2: Run test to verify it fails**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_profiles.py -v
```

Expected: `ImportError: cannot import name 'PROFILES' from 'kanbanmate.core.profiles'`
(module does not exist yet)

- [ ] **Step 1.1.3: Create `core/profiles.py`**

```python
# src/kanbanmate/core/profiles.py
"""Canonical permission-profile name set (DESIGN §13).

This module holds the single source of truth for the four supported profile
names. It lives in ``core`` (pure: no I/O) so the validator (``core/config_validate.py``)
can import it directly without violating the downward-only layering rule.
``adapters/perms.py`` imports from here and re-exports ``PROFILES`` so all
existing callers of ``perms.PROFILES`` are unaffected.
"""

from __future__ import annotations

# The four per-stage workflow profiles.  The PoC ``merge`` profile is
# deliberately absent — merge is human-only, not a launched-agent concern.
PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check")
```

- [ ] **Step 1.1.4: Edit `adapters/perms.py`** — replace the inline `PROFILES` definition at line 337 with an import + re-export

Find in `src/kanbanmate/adapters/perms.py` around line 335-337:
```python
# All supported profile names (DESIGN §10) — the four per-stage profiles. The PoC's ``merge``
# profile is deliberately absent (merge = human-only).
PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check")
```
Replace with:
```python
# Re-exported from ``core.profiles`` (DESIGN §13 layering fix): the validator
# lives in core and cannot import adapters, so the canonical name-set must sit
# in core. Existing callers of ``perms.PROFILES`` are unaffected.
from kanbanmate.core.profiles import PROFILES as PROFILES  # noqa: PLC0414
```

- [ ] **Step 1.1.5: Run tests to verify they pass**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_profiles.py tests/test_perms.py tests/test_layering.py -v
```

Expected: all PASS. The layering test must also pass — the re-export is a `core → adapters` direction (the import lives in `adapters/perms.py`, not in `core`), which is legal.

- [ ] **Step 1.1.6: Add parity test (perms._PROFILE_ALLOW vs core.profiles.PROFILES)**

Append to `tests/core/test_profiles.py`:

```python
def test_profiles_parity_with_perms_allow_list() -> None:
    """core.profiles.PROFILES must be in exact parity with adapters.perms._PROFILE_ALLOW.

    This test is the drift guard: if a new profile is added to perms but not to
    the canonical tuple (or vice versa), the validator (V4) and the allow-list
    (perms) will disagree. The test imports _PROFILE_ALLOW directly from the
    adapters layer — that direction (test → adapters) is legal from the test suite.
    """
    from kanbanmate.adapters.perms import _PROFILE_ALLOW  # noqa: PLC2701

    assert set(PROFILES) == set(_PROFILE_ALLOW.keys()), (
        "core.profiles.PROFILES and adapters.perms._PROFILE_ALLOW are out of sync; "
        "update both when adding a new profile"
    )
```

- [ ] **Step 1.1.7: Run full parity test**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_profiles.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 1.1.8: Commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add src/kanbanmate/core/profiles.py src/kanbanmate/adapters/perms.py tests/core/test_profiles.py
git commit -m "feat(helm): relocate PROFILES to core/profiles.py (layering fix §13)"
```

---

## Task 1.2 — `core/config_model.py`: the draft data model

**Files:**
- Create: `src/kanbanmate/core/config_model.py`
- Create: `tests/core/test_config_model.py`

**Interfaces:**
- Produces:
  - `ColumnDef(key: str, name: str, column_class: str)` dataclass
  - `TransitionDef(from_col: str, to_col: str, profile: str = "", prompt: str | None = None, script: str | None = None, advance: str = "stop", on_fail: str = "", permission_mode: str = "auto")` dataclass
  - `Defaults(concurrency_cap: int, move_rate_limit_per_hour: int)` dataclass
  - `Binding(project: str, option_map: dict[str, str])` dataclass
  - `Definition(columns: list[ColumnDef], transitions: list[TransitionDef], defaults: Defaults)` dataclass
  - `PipelineDraft(definition: Definition, binding: Binding)` dataclass with classmethod `from_loaded(transitions_yaml: str, columns_yaml: str) -> PipelineDraft`
- Consumed by: Phase 2 (`config_serialize.py`), Phase 3 (`config_validate.py`), Phase 4 (`config_service.py`)

**Key design decisions to respect:**
- `column_class` is the plain string `"reactive"` or `"inert"` — NOT a `ColumnClass` enum import (keeps the model JSON-friendly and `core`-pure; `ColumnClass.REACTIVE.value == "reactive"`, `core/domain.py:34-35`).
- `from_loaded` re-parses the raw YAML string with `yaml.safe_load` to recover the ordered `transitions:` rows (the frozen `TransitionConfig` discards row order, `core/transitions.py:156-244`). It calls `load_transitions(transitions_yaml)` PURELY as a validation oracle — the return value is discarded; only the absence of a `ValueError` matters.
- `binding.option_map` defaults to `{}` in PR 1 — the HTTP layer surfaces it read-only from the registry; `from_loaded` has no registry access (no I/O in `core`).

- [ ] **Step 1.2.1: Write the failing tests**

```python
# tests/core/test_config_model.py
"""Tests for :mod:`kanbanmate.core.config_model`.

Uses the shipped config (render_transitions_yaml + columns.yml.tmpl) to assert
that from_loaded produces a structurally-correct PipelineDraft.
"""

from __future__ import annotations

import importlib.resources
from dataclasses import fields

import pytest

from kanbanmate.core.config_model import (
    Binding,
    ColumnDef,
    Defaults,
    Definition,
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
    """The shipped board has 14 columns (DESIGN §9)."""
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
    bad_yaml = "project: x\ntransitions:\n  - from: ''\n    to: ''\n"
    with pytest.raises(ValueError):
        PipelineDraft.from_loaded(bad_yaml, _columns_yaml())


def test_transition_def_defaults() -> None:
    """TransitionDef carries the same defaults as core.transitions.Transition."""
    t = TransitionDef(from_col="Backlog", to_col="InProgress")
    assert t.profile == ""
    assert t.prompt is None
    assert t.script is None
    assert t.advance == "stop"
    assert t.on_fail == ""
    assert t.permission_mode == "auto"
```

- [ ] **Step 1.2.2: Run tests to verify they fail**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_model.py -v
```

Expected: `ImportError: cannot import name 'PipelineDraft' from 'kanbanmate.core.config_model'`

- [ ] **Step 1.2.3: Create `core/config_model.py`**

```python
# src/kanbanmate/core/config_model.py
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
    ``from: [Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev]`` →
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
            ValueError: If either file fails to parse or is structurally
                invalid (propagated from the loader oracle).
        """
        # Oracle pass first: run the real loaders to catch any defect the raw
        # re-parse might miss.  The return value is discarded — we only care
        # that the loaders do NOT raise (they are the daemon's source of truth).
        load_transitions(transitions_yaml)
        load_columns(columns_yaml)

        # Re-parse the raw transitions YAML to recover ordered rows + the
        # project slug + defaults.  yaml.safe_load produces a plain dict with
        # the exact structure load_transitions consumed at transitions.py:285-299.
        raw: Any = yaml.safe_load(transitions_yaml)
        project: str = raw.get("project", "") or ""
        raw_defaults: dict[str, Any] = raw.get("defaults") or {}
        concurrency_cap: int = int(raw_defaults.get("concurrency_cap", 3))
        move_rate_limit_per_hour: int = int(
            raw_defaults.get("move_rate_limit_per_hour", 10)
        )

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
            def _coerce(val: object) -> str | list[str]:
                """Keep a from/to YAML value as the draft's str | list[str]."""
                if isinstance(val, list):
                    return [str(v) for v in val]
                return str(val) if val is not None else ""

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
```

- [ ] **Step 1.2.4: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_model.py -v
```

Expected: all PASS. If `test_from_loaded_rejects_invalid_transitions_yaml` fails, check that an empty `from`/`to` string causes `load_transitions` to raise.

- [ ] **Step 1.2.5: Run the layering guard**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/test_layering.py -v
```

Expected: PASS. `config_model.py` imports only `yaml`, `dataclasses`, and sibling `core` modules.

- [ ] **Step 1.2.6: Phase gate**

```bash
cd /Users/izno/dev/worktrees/ticket-5
make lint
make test
make check
python -c "import kanbanmate"
```

Expected: all clean, smoke passes.

- [ ] **Step 1.2.7: Commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add src/kanbanmate/core/config_model.py tests/core/test_config_model.py
git commit -m "feat(helm): core/config_model.py — PipelineDraft + from_loaded"
```
