"""Validator and move-resolution simulator for the pipeline draft (DESIGN §6–§7).

:func:`validate` converts the loaders' launch-time ``ValueError`` s into
structured save-time ``Finding`` objects, plus 10 semantic checks the loaders
never emit (V1–V10).  :func:`resolve` simulates the whitelist-resolution step
of the daemon's ``decide()`` path for a given ``(from, to)`` move — PR-1 scoped
to whitelist resolution only (DESIGN §6).

Layering: ``core`` only — no I/O, no adapters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import yaml

from kanbanmate.core.columns import load_columns
from kanbanmate.core.config_model import PipelineDraft, TransitionDef
from kanbanmate.core.config_serialize import render_pipeline
from kanbanmate.core.placeholders import _TOKEN
from kanbanmate.core.profiles import PROFILES
from kanbanmate.core.transitions import _ALLOWED_PERMISSION_MODES, load_transitions


@dataclass
class Finding:
    """A single validator finding with a field locus (DESIGN §7).

    Attributes:
        field: Dot-path to the offending field, e.g. ``"transitions[3].permission_mode"``.
        message: Human-readable explanation of the issue.
        severity: ``"error"`` (blocks save) or ``"warning"`` (advisory only).
        locus: Short locus label for grouping, e.g. ``"transitions[3]"``.
    """

    field: str
    message: str
    severity: Literal["error", "warning"]
    locus: str


@dataclass
class ValidationResult:
    """Result of :func:`validate` (DESIGN §7).

    Attributes:
        findings: All findings produced by the validator (errors + warnings).
        ok: ``True`` iff no ``"error"``-severity finding exists.  Warnings do
            not block save (DESIGN §11).
    """

    findings: list[Finding]
    ok: bool


@dataclass
class ResolvedTransition:
    """Result of :func:`resolve` (DESIGN §6).

    Attributes:
        matched: Whether a whitelisted transition was found.
        transition: The matched :class:`~kanbanmate.core.config_model.TransitionDef`,
            or ``None`` when unmatched.
        tier: Precedence tier — ``"explicit"``, ``"wild_from"``, ``"wild_to"``,
            or ``"none"``.
        engine_handled: ``"teardown"`` when the destination is a reactive
            column (Cancel); ``"reset"`` when leaving a reactive column to the
            reset target (``Cancel → Backlog``); ``""`` otherwise.  These moves
            are intercepted by ``decide()`` before the whitelist in the real
            engine (``core/decide.py:212-237``); PR 1 labels them rather than
            simulating the full ``decide()`` verdict.
        would_launch: ``True`` when the matched transition has a prompt (an
            agent fires for this move).
    """

    matched: bool
    transition: TransitionDef | None
    tier: str  # "explicit" | "wild_from" | "wild_to" | "none"
    engine_handled: str  # "" | "teardown" | "reset"
    would_launch: bool


# The 12 dispatch context keys built in app/launch_context.py:86-112.
# Core may not import app, so the set is reproduced here verbatim.
_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "code",
        "title",
        "branch",
        "ticket_body",
        "script_output",
        "issue_body",
        "comments",
        "codename",
        "design_path",
        "plan_paths",
        "base_clone",
        "dev_repo_path",
    }
)

# The reset target: a card leaving a reactive column goes here (core/decide.py:63).
_DEFAULT_RESET_TARGET = "Backlog"

# Valid column_class values — mirrors ColumnClass member values (core/domain.py:34-35).
# A draft column_class outside this set silently demotes to "inert" on render/load
# (the serializer emits no `action` key and load_columns accepts it), losing the
# reactive teardown semantics with no daemon crash — so V9 flags it at save time.
_VALID_COLUMN_CLASSES: frozenset[str] = frozenset({"reactive", "inert"})


def _check_v1_placeholders(t: TransitionDef, idx: int, findings: list[Finding]) -> None:
    """V1: every {{token}} in a prompt must resolve against the 12 dispatch context keys."""
    if t.prompt is None:
        return
    for m in _TOKEN.finditer(t.prompt):
        key = m.group(1).split(".")[0]  # top-level segment only
        if key not in _CONTEXT_KEYS:
            findings.append(
                Finding(
                    field=f"transitions[{idx}].prompt",
                    message=(
                        f"Unknown placeholder {{{{{key}}}}} — not in dispatch "
                        f"context keys ({sorted(_CONTEXT_KEYS)})"
                    ),
                    severity="error",
                    locus=f"transitions[{idx}]",
                )
            )


def _check_v2_slash_commands(t: TransitionDef, idx: int, findings: list[Finding]) -> None:
    """V2: /implement:* tokens must be preserved (not mangled by an edit)."""
    if t.prompt is None:
        return
    # If the prompt contains what looks like a mangled implement command
    # (e.g. "implement:brainstorm" without a leading slash), flag it.
    # Pattern: any word immediately followed by ":brainstorm", ":plan", etc.
    # that LACKS the leading slash.
    _SLASH_CMDS = (
        "brainstorm",
        "plan",
        "create-branch",
        "phase",
        "pr-review",
        "feature",
        "prepare-feature",
    )
    for cmd in _SLASH_CMDS:
        # Match "implement<sep><cmd>" without a preceding "/" (mangled form):
        # the round-trip may strip just the leading slash ("implement:brainstorm")
        # or also mangle the ":" into whitespace ("implement brainstorm"). Both
        # are the signature of a slash command that lost its leading "/".
        if re.search(rf"(?<![/\w])implement[\s:]+{re.escape(cmd)}\b", t.prompt):
            findings.append(
                Finding(
                    field=f"transitions[{idx}].prompt",
                    message=(
                        f"Slash command '/implement:{cmd}' appears mangled "
                        "(missing leading '/'); verify the prompt"
                    ),
                    severity="error",
                    locus=f"transitions[{idx}]",
                )
            )


def _check_v3_permission_mode(t: TransitionDef, idx: int, findings: list[Finding]) -> None:
    """V3: permission_mode must be in the allowed set; bypass* is banned."""
    mode = t.permission_mode
    if not mode:
        return  # empty string → loader will default it; not a validator concern
    if mode not in _ALLOWED_PERMISSION_MODES:
        findings.append(
            Finding(
                field=f"transitions[{idx}].permission_mode",
                message=(
                    f"permission_mode {mode!r} is not allowed. "
                    f"Allowed: {sorted(_ALLOWED_PERMISSION_MODES)}. "
                    "bypassPermissions is NEVER allowed."
                ),
                severity="error",
                locus=f"transitions[{idx}]",
            )
        )


def _check_v4_profile(t: TransitionDef, idx: int, findings: list[Finding]) -> None:
    """V4: profile must be one of the workflow profiles (docs/prepare/dev/check/merge) or empty."""
    profile = t.profile
    if not profile:
        return  # empty = no-op / script-only transition; allowed
    if profile not in PROFILES:
        findings.append(
            Finding(
                field=f"transitions[{idx}].profile",
                message=(
                    f"profile {profile!r} is not a valid workflow profile. "
                    f"Allowed: {list(PROFILES)}"
                ),
                severity="error",
                locus=f"transitions[{idx}]",
            )
        )


def _extract_col_targets(value: str) -> list[str]:
    """Return concrete column key targets from an advance/on_fail directive string.

    Parses 'auto:<col>' (advance) and 'move:<col>' (on_fail) to extract the
    column key.  Returns an empty list for 'stop', '', 'rollback' (no column).
    """
    if value.startswith("auto:"):
        return [value[5:]]
    if value.startswith("move:"):
        return [value[5:]]
    return []


def _col_keys(value: str | list[str]) -> list[str]:
    """Normalise a from_col/to_col (``str`` | ``"*"`` | ``list[str]``) to concrete keys.

    Drops the ``"*"`` wildcard (it matches any column, so it is never an
    existence target). A scalar becomes a one-element list; a list is returned
    element-wise. This is the single seam the validators use so the
    ``str | list[str]`` authoring shape (DESIGN §4.1) is handled in one place.
    """
    vals = value if isinstance(value, list) else [value]
    return [v for v in vals if v and v != "*"]


def _check_v5_column_targets(
    t: TransitionDef, idx: int, col_keys: frozenset[str], findings: list[Finding]
) -> None:
    """V5: every non-wildcard from/to, advance:auto:<col>, on_fail:move:<col> must name a real column."""

    def _check_key(key: str, field_name: str) -> None:
        if key and key not in col_keys:
            findings.append(
                Finding(
                    field=f"transitions[{idx}].{field_name}",
                    message=f"Column key {key!r} does not exist in the column list",
                    severity="error",
                    locus=f"transitions[{idx}]",
                )
            )

    # Check every concrete from_col / to_col key (the wildcard and lists are
    # normalised by _col_keys; each list member is checked individually).
    for k in _col_keys(t.from_col):
        _check_key(k, "from_col")
    for k in _col_keys(t.to_col):
        _check_key(k, "to_col")

    # Check advance:auto:<col> and on_fail:move:<col> targets.
    for col in _extract_col_targets(t.advance):
        _check_key(col, "advance")
    for col in _extract_col_targets(t.on_fail):
        _check_key(col, "on_fail")


def _check_v6_wildcard_shadow(transitions: list[TransitionDef], findings: list[Finding]) -> None:
    """V6: warn when a wildcard row makes a later explicit row unreachable-by-intent.

    Specifically: a (*, to) wild_to entry that appears BEFORE an explicit (from, to)
    makes the explicit row unreachable (the wildcard wins per precedence at
    core/transitions.py:202-211). This is a WARNING — it may be intentional.
    """
    # Collect (*, to) wild_to entries and their positions. A wildcard is always
    # a scalar "*"; list-valued from/to (authoring sugar) is never a wildcard.
    wild_to_seen: dict[str, int] = {}  # to_col → earliest index
    for idx, t in enumerate(transitions):
        if t.from_col == "*" and isinstance(t.to_col, str) and t.to_col != "*":
            if t.to_col not in wild_to_seen:
                wild_to_seen[t.to_col] = idx

    # Look for explicit (from, to) rows that come AFTER the wild_to for the same
    # to_col. Restrict to plain scalar explicit edges — list-valued rows are
    # authoring sugar covered by the oracle pass + V5, not by this shadow heuristic.
    for idx, t in enumerate(transitions):
        if (
            isinstance(t.from_col, str)
            and t.from_col != "*"
            and isinstance(t.to_col, str)
            and t.to_col != "*"
        ):
            wild_idx = wild_to_seen.get(t.to_col)
            if wild_idx is not None and wild_idx < idx:
                findings.append(
                    Finding(
                        field=f"transitions[{idx}]",
                        message=(
                            f"Explicit ({t.from_col!r} → {t.to_col!r}) at index {idx} is shadowed "
                            f"by wildcard (* → {t.to_col!r}) at index {wild_idx} "
                            "(wildcard-precedence: explicit wins, but the wildcard appeared first — "
                            "verify authoring intent)"
                        ),
                        severity="warning",
                        locus=f"transitions[{idx}]",
                    )
                )


def _check_v7_launch_target_invariant(draft: PipelineDraft, findings: list[Finding]) -> None:
    """V7: no prompt-bearing transition may resolve into a reactive column, nor into 'Merge' UNLESS
    it carries the 'merge' profile (the sanctioned autonomous merge stage, DESIGN §15)."""
    reactive_keys = frozenset(
        c.key for c in draft.definition.columns if c.column_class == "reactive"
    )
    for idx, t in enumerate(draft.definition.transitions):
        if t.prompt is None:
            continue
        # Concrete to_col targets (the wildcard and lists are normalised by
        # _col_keys — a prompt-bearing row into any of these keys is checked).
        for col in _col_keys(t.to_col):
            if col in reactive_keys:
                findings.append(
                    Finding(
                        field=f"transitions[{idx}].to_col",
                        message=(
                            f"A prompt-bearing transition resolves into reactive column {col!r}. "
                            "Reactive columns are handled mechanically by the engine (teardown/reset); "
                            "a prompt would re-fire the agent."
                        ),
                        severity="error",
                        locus=f"transitions[{idx}]",
                    )
                )
            if col == "Merge" and t.profile != "merge":
                findings.append(
                    Finding(
                        field=f"transitions[{idx}].to_col",
                        message=(
                            "A prompt-bearing transition targets 'Merge' WITHOUT the 'merge' profile. "
                            "Merge is human-only EXCEPT the sanctioned autonomous merge stage "
                            "(profile 'merge', DESIGN §15 / V7) — no OTHER agent may be launched into "
                            "Merge."
                        ),
                        severity="error",
                        locus=f"transitions[{idx}]",
                    )
                )


def _check_v8_defaults_coherence(
    draft: PipelineDraft,
    columns_yaml: str | None,
    findings: list[Finding],
) -> None:
    """V8: warn if an uncommented columns.yml defaults: block disagrees with transitions.yml.

    The authoritative defaults are in transitions.yml (DESIGN §10 / app/wiring.py:229-230).
    A hand-uncommented columns.yml defaults: block that disagrees is dead config that the
    daemon silently ignores, trapping the operator.
    """
    if not columns_yaml:
        return
    from kanbanmate.core.columns import load_board_defaults  # noqa: PLC0415

    # CRITICAL: load_board_defaults() NEVER returns None — an ABSENT defaults:
    # block yields BoardDefaults() (3/10) exactly like a present block that
    # spells out 3/10 (core/columns.py:217-235). The shipped columns.yml ships
    # the block COMMENTED OUT (assets/columns.yml.tmpl:26-28), so the raw
    # document has no top-level "defaults" key. V8 fires ONLY when an
    # uncommented block is actually present — detect presence on the RAW
    # document, never on the loader's defaulted return (else raising the
    # transitions cap with columns.yml's block still commented would emit a
    # false-positive warning).
    # Fail-soft: validate() must return a ValidationResult, never let a raw YAMLError escape (the
    # rest of this validator converts loader errors into Findings — V8 must hold the same contract).
    # A malformed columns_yaml surfaces as a warning Finding and skips the comparison; the operator
    # still gets a save-time signal rather than an uncaught exception out of the daemon/HTTP boundary.
    try:
        raw_cols: Any = yaml.safe_load(columns_yaml)
    except yaml.YAMLError as exc:
        findings.append(
            Finding(
                field="columns.defaults",
                message=(
                    f"columns.yml is not parseable YAML ({exc}); skipping the V8 defaults-coherence "
                    "check. Fix columns.yml so its defaults block can be compared to transitions.yml."
                ),
                severity="warning",
                locus="columns.defaults",
            )
        )
        return
    if not isinstance(raw_cols, dict) or not isinstance(raw_cols.get("defaults"), dict):
        return  # No uncommented columns.yml defaults: block — nothing to compare.

    board_defaults = load_board_defaults(columns_yaml)

    t_cap = draft.definition.defaults.concurrency_cap
    t_rate = draft.definition.defaults.move_rate_limit_per_hour
    c_cap = board_defaults.concurrency_cap
    c_rate = board_defaults.move_rate_limit_per_hour

    if c_cap != t_cap:
        findings.append(
            Finding(
                field="columns.defaults.concurrency_cap",
                message=(
                    f"columns.yml defaults.concurrency_cap={c_cap} disagrees with "
                    f"transitions.yml defaults.concurrency_cap={t_cap}. "
                    "The daemon reads transitions.yml (authoritative); the columns.yml value is dead config."
                ),
                severity="warning",
                locus="columns.defaults",
            )
        )
    if c_rate != t_rate:
        findings.append(
            Finding(
                field="columns.defaults.move_rate_limit_per_hour",
                message=(
                    f"columns.yml defaults.move_rate_limit_per_hour={c_rate} disagrees with "
                    f"transitions.yml defaults.move_rate_limit_per_hour={t_rate}. "
                    "The daemon reads transitions.yml (authoritative); the columns.yml value is dead config."
                ),
                severity="warning",
                locus="columns.defaults",
            )
        )


def _check_v9_column_classes(draft: PipelineDraft, findings: list[Finding]) -> None:
    """V9: every column_class must be 'reactive' or 'inert'.

    A typo (e.g. ``"reactve"``) is silently treated as inert by the serializer
    and loader (no daemon crash), so the oracle pass never catches it. Flagging
    it here surfaces the silent loss of reactive semantics at save time.
    """
    for cidx, c in enumerate(draft.definition.columns):
        if c.column_class not in _VALID_COLUMN_CLASSES:
            findings.append(
                Finding(
                    field=f"columns[{cidx}].column_class",
                    message=(
                        f"column_class {c.column_class!r} is invalid; "
                        f"must be one of {sorted(_VALID_COLUMN_CLASSES)}"
                    ),
                    severity="error",
                    locus=f"columns[{cidx}]",
                )
            )


def _check_v10_defaults_sanity(draft: PipelineDraft, findings: list[Finding]) -> None:
    """V10: the board defaults must be positive.

    The loaders coerce any int (``core/transitions.py:292-293``), so a
    non-positive ``concurrency_cap`` (stalls every launch) or
    ``move_rate_limit_per_hour`` (blocks every bot move) is dead config the
    oracle accepts. The published JSON Schema declares ``minimum: 1`` for both
    (``http/config_api.py``); V10 enforces the same bound at save time.
    """
    d = draft.definition.defaults
    if d.concurrency_cap < 1:
        findings.append(
            Finding(
                field="defaults.concurrency_cap",
                message=f"concurrency_cap must be >= 1, got {d.concurrency_cap}",
                severity="error",
                locus="defaults",
            )
        )
    if d.move_rate_limit_per_hour < 1:
        findings.append(
            Finding(
                field="defaults.move_rate_limit_per_hour",
                message=f"move_rate_limit_per_hour must be >= 1, got {d.move_rate_limit_per_hour}",
                severity="error",
                locus="defaults",
            )
        )


def _check_v11_nonempty_board(draft: PipelineDraft, findings: list[Finding]) -> None:
    """V11: a saved pipeline must define at least one column AND at least one transition.

    An empty board (no columns / no transitions) trips none of V1-V10 and the loaders accept it
    (``load_transitions('transitions: []')`` / ``load_columns('columns: []')`` both succeed), so
    without this guard a ``POST /api/config`` with an empty or fully-defaulted draft would validate
    clean and the write path would WIPE the live pipeline (data-loss). A real pipeline always has
    both, so an empty board is an error.
    """
    if not draft.definition.columns:
        findings.append(
            Finding(
                field="definition.columns",
                message="The pipeline must define at least one column "
                "(an empty board would wipe the config).",
                severity="error",
                locus="definition",
            )
        )
    if not draft.definition.transitions:
        findings.append(
            Finding(
                field="definition.transitions",
                message="The pipeline must define at least one transition "
                "(an empty board would wipe the config).",
                severity="error",
                locus="definition",
            )
        )


def validate(draft: PipelineDraft, *, columns_yaml: str | None = None) -> ValidationResult:
    """Validate a :class:`~kanbanmate.core.config_model.PipelineDraft`.

    Runs two tiers (DESIGN §7):

    1. **Oracle pass** — render the draft and feed both YAML documents through
       the real loaders (``load_transitions`` + ``load_columns``). Any
       ``ValueError`` becomes a ``Finding(severity='error')``. This guarantees
       helm can never save a config the daemon would crash on.
    2. **Semantic checks V1–V10** — field-located checks the loaders never emit
       (placeholder resolution, slash-command preservation, permission_mode
       whitelist, profile whitelist, column-target existence,
       wildcard-precedence shadow, launch-target invariant, defaults
       coherence, column-class membership, defaults sanity).

    Args:
        draft: The pipeline draft to validate.
        columns_yaml: The raw ``columns.yml`` string, required for V8 (defaults
            coherence).  When ``None``, V8 is skipped.

    Returns:
        A :class:`ValidationResult` with all findings.  ``ok`` is ``True``
        iff no ``error``-severity finding exists.
    """
    findings: list[Finding] = []

    # §7.1 — Per-row semantic checks V1–V6 run FIRST, independent of the oracle.
    # These are field-located checks the loaders never emit, and they stay valid
    # even when the rendered YAML is structurally rejected (e.g. a banned
    # permission_mode is both an oracle reject AND a V3 finding — the caller wants
    # the field-located V3 finding, not only the opaque oracle error). Running
    # them before the oracle's early-return is what lets V3 surface on a draft
    # the oracle also rejects.
    col_keys = frozenset(c.key for c in draft.definition.columns)
    for idx, t in enumerate(draft.definition.transitions):
        _check_v1_placeholders(t, idx, findings)
        _check_v2_slash_commands(t, idx, findings)
        _check_v3_permission_mode(t, idx, findings)
        _check_v4_profile(t, idx, findings)
        _check_v5_column_targets(t, idx, col_keys, findings)
        # Structural: an empty from/to key is a degenerate row the loaders
        # silently accept (it can never match a real board column → dead row),
        # so the oracle alone would miss it. Flag it as a field-located error.
        for side, value in (("from_col", t.from_col), ("to_col", t.to_col)):
            if isinstance(value, str) and value == "":
                findings.append(
                    Finding(
                        field=f"transitions[{idx}].{side}",
                        message=f"transitions[{idx}].{side} is empty; a column key is required",
                        severity="error",
                        locus=f"transitions[{idx}]",
                    )
                )

    _check_v6_wildcard_shadow(draft.definition.transitions, findings)

    # V9/V10/V11 operate on the draft directly (render-independent), so run them
    # alongside V1–V6 — they must surface even when the oracle rejects the render.
    _check_v9_column_classes(draft, findings)
    _check_v10_defaults_sanity(draft, findings)
    _check_v11_nonempty_board(draft, findings)

    # §7.0 — Oracle pass: render and feed through the real loaders.
    try:
        rendered = render_pipeline(draft)
        load_transitions(rendered.transitions)
        load_columns(rendered.columns)
    except ValueError as exc:
        findings.append(
            Finding(
                field="draft",
                message=f"Loader oracle rejected the rendered config: {exc}",
                severity="error",
                locus="draft",
            )
        )
        # When the oracle fails, the rendered YAML is invalid; checks that depend
        # on a successful render (V7's launch-target invariant, V8's defaults
        # coherence) would produce spurious findings, so skip them — the V1–V6
        # field-located findings above are still reported.
        return ValidationResult(findings=findings, ok=False)

    # §7.2 — Render-dependent semantic checks (only after a clean oracle pass).
    _check_v7_launch_target_invariant(draft, findings)
    _check_v8_defaults_coherence(draft, columns_yaml, findings)

    ok = not any(f.severity == "error" for f in findings)
    return ValidationResult(findings=findings, ok=ok)


def resolve(draft: PipelineDraft, from_col: str, to_col: str) -> ResolvedTransition:
    """Simulate whitelist resolution for a ``(from_col, to_col)`` move (DESIGN §6).

    Mirrors ``TransitionConfig.get`` precedence (``core/transitions.py:183-211``)
    by rendering the draft → ``load_transitions`` → calling ``.get()``.  This is the
    single source of truth for whitelist precedence — no re-implementation.

    Also computes ``engine_handled`` from the column classes in the draft:
    - ``"teardown"`` when ``to_col`` is a reactive column (the engine's
      ``decide()`` intercepts before the whitelist; ``core/decide.py:212-237``).
    - ``"reset"`` when ``from_col`` is reactive and ``to_col == "Backlog"``
      (the engine's reset-target return path; ``core/decide.py:63``).
    - ``""`` otherwise.

    PR-1 scope: whitelist resolution only.  The full ``decide()`` verdict set
    (LAUNCH / ROLLBACK / TEARDOWN / RESET) is mirrored end-to-end in PR 3.

    Args:
        draft: The editable pipeline draft.
        from_col: The source column key.
        to_col: The destination column key.

    Returns:
        A :class:`ResolvedTransition` describing the whitelist verdict.
    """
    # Render and load to get a TransitionConfig (single source of truth for
    # precedence — core/transitions.py:183-211).
    rendered = render_pipeline(draft)
    tc = load_transitions(rendered.transitions)

    matched_transition = tc.get(from_col, to_col)

    # Determine the precedence tier by querying which lookup table matched.
    # Mirrors the order in TransitionConfig.get (transitions.py:202-211):
    # explicit > wild_from > wild_to.
    tier = "none"
    if matched_transition is not None:
        if tc._explicit and (from_col, to_col) in (tc._explicit or {}):  # noqa: SLF001
            tier = "explicit"
        elif tc._wild_from and from_col in (tc._wild_from or {}):  # noqa: SLF001
            tier = "wild_from"
        elif tc._wild_to and to_col in (tc._wild_to or {}):  # noqa: SLF001
            tier = "wild_to"

    # Determine engine_handled from column classes.
    reactive_keys = frozenset(
        c.key for c in draft.definition.columns if c.column_class == "reactive"
    )
    engine_handled = ""
    if to_col in reactive_keys:
        engine_handled = "teardown"
    elif from_col in reactive_keys and to_col == _DEFAULT_RESET_TARGET:
        engine_handled = "reset"

    # Convert matched Transition to TransitionDef for the caller.
    transition_def: TransitionDef | None = None
    if matched_transition is not None:
        transition_def = TransitionDef(
            from_col=matched_transition.from_col,
            to_col=matched_transition.to_col,
            profile=matched_transition.profile,
            prompt=matched_transition.prompt,
            script=matched_transition.script,
            advance=matched_transition.advance,
            on_fail=matched_transition.on_fail,
            permission_mode=matched_transition.permission_mode,
        )

    return ResolvedTransition(
        matched=matched_transition is not None,
        transition=transition_def,
        tier=tier,
        engine_handled=engine_handled,
        would_launch=matched_transition is not None and matched_transition.prompt is not None,
    )
