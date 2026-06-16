"""Health single-select field find-or-create + set helpers (health-field).

Extracted from :mod:`kanbanmate.adapters.github.client` (the client was at 918 LOC,
under the 1000-LOC hard ceiling but tight — mirrors the earlier ``_transport`` /
``_rest`` extractions). These are free functions taking the client's injected
GraphQL transport callable so :class:`~kanbanmate.adapters.github.client.GithubClient`
can delegate with two thin wrapper methods, keeping the field/option machinery out of
the already-large client module.

The "Health" field is the per-card custom single-select the daemon maintains so the
operator's own vocabulary (``INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE``) shows
as native chips on each card (GitHub's fixed status-update pill enum cannot carry the
operator's words — see :mod:`kanbanmate.core.health`). The helpers MIRROR the existing
Status-field machinery (:meth:`GithubClient.ensure_columns` /
:meth:`GithubClient._resolve_status_field`): they reuse the ``status_option_map`` read
(it returns EVERY single-select field, not just Status) and the
``update_status_field_options`` REPLACE (a generic single-select option REPLACE despite
the name) — only the field CREATE is a new mutation.

Layering: ``adapters`` may import ``core`` + ``ports`` (DESIGN §3.2). This module imports
the ``core`` Health vocabulary + the adapter peers (``_queries`` / ``_parsers`` / the
``HealthField`` value object); it speaks to GitHub only through the injected transport,
which carries the client's mandatory connect+read timeouts.
"""

from __future__ import annotations

from typing import Any

from kanbanmate.adapters.github import _parsers, _queries
from kanbanmate.adapters.github.types import HealthField
from kanbanmate.core.health import HEALTH_OPTION_COLORS, HEALTH_OPTIONS_ORDER
from kanbanmate.core.status_update import STATUS_VALUES

# The field name the daemon maintains. Single source of truth so the read filter
# (``parse_health_field``) and the create mutation use the identical string.
HEALTH_FIELD_NAME = "Health"

# A type alias mirroring the client's GraphQLTransport (a callable taking a payload
# dict and returning the decoded response). Kept local so this module does not depend
# on the client's internal type aliases (no import cycle).
GraphQLCallable = Any


def _option_specs() -> list[dict[str, Any]]:
    """Build the full ordered option-create specs (name + colour + empty description).

    Returns:
        One ``{"name": ..., "color": ..., "description": ""}`` mapping per Health value,
        in :data:`~kanbanmate.core.health.HEALTH_OPTIONS_ORDER` (the chip order).
    """
    return [
        {"name": name, "color": HEALTH_OPTION_COLORS[name], "description": ""}
        for name in HEALTH_OPTIONS_ORDER
    ]


def ensure_health_field(graphql: GraphQLCallable, project_id: str) -> HealthField:
    """Find-or-create the "Health" single-select field; reconcile drifted options.

    Mirrors :meth:`kanbanmate.adapters.github.client.GithubClient.ensure_columns`:

    * read every single-select field via the EXISTING ``status_option_map`` query and
      look for "Health" (:func:`~kanbanmate.adapters.github._parsers.parse_health_field`);
    * ABSENT → create it once (``createProjectV2Field`` SINGLE_SELECT with the 5 options
      + colours) and parse the new ids;
    * PRESENT with all 5 options → return it unchanged (no mutation);
    * PRESENT but drifted (missing options) → REPLACE the option set via
      ``update_status_field_options`` (a generic single-select REPLACE), PRESERVING the
      ids of existing options so cards keep their chip value.

    The caller (the client) caches the result so it costs one read per process.

    Args:
        graphql: The client's injected GraphQL transport (carries the mandatory
            connect+read timeouts).
        project_id: The ``ProjectV2`` node id whose Health field to ensure.

    Returns:
        The resolved/created :class:`~kanbanmate.adapters.github.types.HealthField`.
    """
    data = graphql(_queries.status_option_map(project_id))
    existing = _parsers.parse_health_field(data)
    if existing is None:
        created = graphql(
            _queries.create_project_field_single_select(
                project_id, HEALTH_FIELD_NAME, _option_specs()
            )
        )
        return _parsers.parse_created_single_select_field(created)
    # Present + every required option already there → idempotent no-op.
    if set(existing.options) >= STATUS_VALUES:
        return existing
    # Present but drifted: REPLACE the option set, PRESERVING existing option ids so the
    # cards already holding a Health value keep their chip (the same preserve-by-id
    # discipline ``ensure_columns`` uses for the Status field).
    merged: list[dict[str, Any]] = []
    for name in HEALTH_OPTIONS_ORDER:
        opt: dict[str, Any] = {
            "name": name,
            "color": HEALTH_OPTION_COLORS[name],
            "description": "",
        }
        if name in existing.options:
            opt["id"] = existing.options[name]  # preserve → cards keep their value
        merged.append(opt)
    updated = graphql(_queries.update_status_field_options(existing.field_id, merged))
    options = _parsers.parse_updated_field_options(updated) or existing.options
    return HealthField(field_id=existing.field_id, options=options)
