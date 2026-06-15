"""Pure probe parsers for ``kanban doctor`` (core layer — zero I/O).

These functions turn an already-decoded GitHub API body (or a raw JSON string,
for back-compat) into a boolean signal the ``doctor`` command renders. They are
**pure** — no network, no filesystem — so they live in ``core/`` and the
layering guard sees no I/O import. The REST call that produces the body lives in
the GitHub adapter (:meth:`~kanbanmate.adapters.github.client.GithubClient.branch_protection_on`);
the CLI does the wiring (:mod:`kanbanmate.cli.doctor`).

Ported from the PoC ``cli/probes.py:59-79`` (``parse_branch_protection_on``),
adapted to NEW's JSON-decoding client: the PoC parsed a raw ``gh api`` STRING,
whereas the NEW adapter passes an already-decoded ``dict``. The string path is
kept for back-compat (``json.loads`` it when a ``str`` arrives).
"""

from __future__ import annotations

import json
from collections.abc import Mapping

# The fields a ``branches/{b}/protection`` body carries when protection is ON. The
# presence of ANY of these marks the branch as protected (PoC probes.py:59-79).
_PROTECTION_FIELDS = (
    "required_status_checks",
    "enforce_admins",
    "required_pull_request_reviews",
)


def parse_branch_protection_on(payload: object) -> bool:
    """Return ``True`` iff a branch-protection body indicates protection is ON.

    Ported from the PoC ``cli/probes.py:59-79``. The ``GET .../branches/{b}/protection``
    endpoint 404s with a ``message``-only body when protection is OFF; a protected
    branch returns an object carrying ``required_status_checks`` /
    ``enforce_admins`` / ``required_pull_request_reviews``. We treat the presence
    of any protection field as protected, and a message-only body (the 404 "Branch
    not protected") as not protected.

    This function is PURE — it performs no I/O (it lives in ``core/`` so the
    layering guard sees no I/O import). The REST round-trip that produces *payload*
    lives in the GitHub adapter.

    Args:
        payload: An already-decoded ``Mapping``/``dict`` (the NEW adapter path), or
            a raw JSON ``str`` (back-compat with the PoC's ``gh api`` output). A
            ``str`` is ``json.loads``-decoded first; invalid JSON yields ``False``.

    Returns:
        ``True`` when the body carries any protection field; ``False`` for a
        message-only body, an empty/other dict, a non-dict, or invalid JSON.
    """
    data: object = payload
    # Back-compat: a raw ``gh api`` STRING is decoded first (the PoC input shape).
    # Invalid JSON is treated as "not protected" rather than raising — doctor's
    # branch check is advisory and must never crash on a malformed body.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            return False

    if not isinstance(data, Mapping):
        return False

    # A message-only body (the 404 "Branch not protected") carries a ``message``
    # key WITHOUT any protection field → not protected.
    if "message" in data and not any(field in data for field in _PROTECTION_FIELDS):
        return False

    return any(field in data for field in _PROTECTION_FIELDS)
