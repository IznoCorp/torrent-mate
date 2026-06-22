"""Pure redeploy-target validator (bosun §8, decision D4).

Maps the operator-chosen target to the audited deploy script + the clone it runs in. The HTTP layer
NEVER takes a client-supplied script path — only the fixed ``prod``/``staging`` enum (DESIGN §8).
"""

from __future__ import annotations

# (script_relpath, clone_dir) per target. clone_dir is expanded by the app layer (it is ``~``-based,
# i.e. environment I/O, so it is NOT a core constant — passed in by the caller).
REDEPLOY_TARGETS: frozenset[str] = frozenset({"prod", "staging"})


def script_for_target(target: str) -> str | None:
    """Return the deploy script relpath for ``target``, or ``None`` if the target is unknown.

    Args:
        target: The operator-chosen redeploy target — one of ``REDEPLOY_TARGETS``
            (``"prod"`` / ``"staging"``).

    Returns:
        The repo-relative deploy script path for a known target, else ``None`` (caller → HTTP 422).
    """
    return {"prod": "scripts/deploy.sh", "staging": "scripts/deploy-staging.sh"}.get(target)
