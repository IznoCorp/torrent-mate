"""Advisory ``kanban doctor`` check for the per-card Health single-select field (health-field nit).

Lifted out of :mod:`kanbanmate.cli.doctor` for LOC-ceiling headroom (doctor.py sat near the
1000-LOC hard ceiling). The check is ADVISORY — it NEVER fails the doctor run (the Health chips are
observability, not a launch gate, per :mod:`kanbanmate.app.health_reporter`): it returns ``ok=True``
always, surfacing a ``WARNING:`` detail when the field is missing options. When no project is
registered (or resolution fails) it is an advisory PASS-skip, exactly like the board-reachable check.

Mirrors :func:`kanbanmate.cli.doctor._resolve_board_probe`: the resolver reads ``projects.json`` and
returns a deferred thunk that ensures/reads the Health field at call time, so a missing token /
unreachable API surfaces as a WARN (advisory) rather than a crash.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from kanbanmate.core.status_update import STATUS_VALUES

# A doctor check result: ``(name, ok, detail)`` — identical to ``cli.doctor.CheckResult`` (kept as a
# local alias so this module does not import from ``cli.doctor`` and risk a cycle).
HealthCheckResult = tuple[str, bool, str]

# A deferred Health-field check: returns the resolved option-name set (its presence/absence vs
# STATUS_VALUES drives the advisory verdict). Raises on a network/API error (turned into a WARN).
HealthFieldCheck = Callable[[], set[str]]


def _check_health_field(health_check: HealthFieldCheck | None = None) -> HealthCheckResult:
    """Advisory: verify the per-card Health field is provisioned with the 5 named options.

    ADVISORY — always ``ok=True`` (the Health chips are observability, never a launch gate):

    * ``health_check is None`` → advisory PASS-skip (no project registered).
    * the resolved option set equals :data:`~kanbanmate.core.status_update.STATUS_VALUES` →
      advisory PASS.
    * the resolved set is missing one or more of the 5 names → advisory ``WARNING:`` (the daemon
      will reconcile it on the next Health tick, but flag it so the operator knows the chips are
      incomplete right now).
    * the resolver raises (missing token / unreachable API) → advisory ``WARNING:`` (never a FAIL).

    Args:
        health_check: A zero-arg callable returning the field's option-name set, or ``None`` to skip.

    Returns:
        A ``(name, ok, detail)`` tuple; ``ok`` is ALWAYS ``True`` (advisory).
    """
    if health_check is None:
        return ("health field", True, "skipped — no project registered (advisory)")
    try:
        options = health_check()
    except Exception as exc:  # noqa: BLE001 — advisory: a probe failure WARNs, never FAILs doctor.
        return ("health field", True, f"WARNING: could not read the Health field ({exc})")
    missing = STATUS_VALUES - options
    if missing:
        return (
            "health field",
            True,
            f"WARNING: Health field missing option(s): {', '.join(sorted(missing))} "
            "(the daemon reconciles it on the next Health tick)",
        )
    return ("health field", True, f"Health field provisioned with all {len(STATUS_VALUES)} options")


def _resolve_health_check(root: Path) -> HealthFieldCheck | None:
    """Build a LIVE Health-field probe for the first registered project (advisory).

    Mirrors :func:`kanbanmate.cli.doctor._resolve_board_probe`: reads ``<root>/projects.json``,
    resolves the FIRST project's ``project_id`` + token, and returns a deferred thunk that ensures
    the Health field and returns its option-name set. ``None`` when no project is registered (or
    resolution fails) so :func:`_check_health_field` keeps its advisory skip.

    FAIL-SOFT at resolve time (registry/token/import errors yield ``None``); the network round-trip
    is deferred to call time, where :func:`_check_health_field` turns an error into a WARN.

    Args:
        root: The kanban runtime root holding ``projects.json``.

    Returns:
        A zero-arg ``() -> option_names`` Health-field probe, or ``None`` when none is registered.
    """
    try:
        from kanbanmate.adapters.github.client import GithubClient
        from kanbanmate.adapters.github.token import load_token
        from kanbanmate.cli.init import _load_registry, _projects_path

        registry = _load_registry(_projects_path(root))
        if not registry:
            return None
        first_entry = next(iter(registry.values()))
        project_id = first_entry.project_id
        if not project_id:
            return None
        client = GithubClient(load_token(), project_id=project_id, repo=first_entry.repo)
    except Exception:  # noqa: BLE001 — resolution is best-effort; never crash doctor.
        return None

    def _probe() -> set[str]:
        """Ensure the Health field and return its option-name set (the advisory check input)."""
        field = client.ensure_health_field(project_id)
        return set(field.options)

    return _probe
