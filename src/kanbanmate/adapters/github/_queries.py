"""Pure GraphQL request/mutation BUILDERS (ported from the PoC). No I/O.

Each builder returns a ``{"query": ..., "variables": ...}`` payload ready for the
client's GraphQL transport. Mutations operate on stable node ids and single-select
OPTION IDs (never column names), per DESIGN §3.3. The shapes are exercised in tests
against fixtures via the parsers.
"""

from __future__ import annotations

from typing import Any


def cheap_probe(project_id: str) -> dict[str, Any]:
    """Build the cheap change-detection probe (DESIGN §3.1).

    Reads every item's ``updatedAt`` (first page, up to 100). The client hashes the
    sorted timestamps into an opaque token, so any move/edit/add/remove on the board
    flips the token and triggers a full snapshot — at a fraction of a snapshot's
    rate-limit cost (``updatedAt`` only, no status/content fields).

    GitHub's ``ProjectV2ItemOrderField`` accepts only ``POSITION`` (NOT ``UPDATED_AT``),
    so the probe cannot order by recency server-side; it hashes the whole first page
    instead. Boards larger than 100 items are not fully covered by the probe (the
    snapshot still paginates to the full board on the ticks that run) — acceptable for
    the v1 single-board scale; a paginated/always-snapshot fallback is a ROADMAP item.

    Args:
        project_id: The ``ProjectV2`` node id of the board to probe.

    Returns:
        A GraphQL payload reading up to 100 items' ``updatedAt`` timestamps.
    """
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100) {
            nodes { updatedAt }
          }
        }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id}}


def board_items(project_id: str, after: str | None = None) -> dict[str, Any]:
    """Build the full board-items read query for a snapshot (one page).

    Reads every project item with the fields needed to construct a
    :class:`kanbanmate.core.domain.Ticket`: the item id, its Status single-select
    value (the column), its ``updatedAt``, and — for Issue content — the issue
    number, title, and body (the body feeds the dependency gate's ``Depends on
    #N`` parsing, DESIGN §9; draft/PR content has no number nor body).

    ``after`` is threaded by the client's pagination loop so boards with more
    than 100 items return a complete snapshot.

    Args:
        project_id: The ``ProjectV2`` node id of the board to read.
        after: Optional ``endCursor`` for the next page.

    Returns:
        A GraphQL payload reading one page of the board's items.
    """
    query = """
    query($projectId: ID!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              updatedAt
              fieldValueByName(name: "Status") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
              content {
                __typename
                ... on Issue { number title body }
                ... on DraftIssue { title }
              }
            }
          }
        }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id, "after": after}}


def status_option_map(project_id: str) -> dict[str, Any]:
    """Fetch the Status single-select field's id + options (name -> option id).

    Args:
        project_id: The ``ProjectV2`` node id whose Status field is read.

    Returns:
        A GraphQL payload reading the project's single-select fields and options.
    """
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
        }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id}}


def issue_context(owner: str, name: str, number: int) -> dict[str, Any]:
    """Build the ``issue_context`` query for an issue's body, comments, and first linked issue.

    Ported VERBATIM-IN-SPIRIT from the PoC ``_queries.py:289-319`` (the GraphQL string
    is the contract). Fetches the issue body, up to 50 comment bodies, and the body of
    the FIRST cross-referenced/linked Issue found in the timeline via
    ``timelineItems(itemTypes: [CROSS_REFERENCED_EVENT])``. The launch-prompt enrichment
    pipeline consumed this to fill ``{{ticket_body}}`` / ``{{issue_body}}`` /
    ``{{comments}}`` — a separate restoration.

    Args:
        owner: Repository owner login.
        name: Repository name.
        number: The issue number.

    Returns:
        A GraphQL payload reading the issue's body, up to 50 comment bodies, and the
        first cross-referenced Issue body.
    """
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) {
          body
          comments(first: 50) {
            nodes { body createdAt }
          }
          timelineItems(first: 20, itemTypes: [CROSS_REFERENCED_EVENT]) {
            nodes {
              ... on CrossReferencedEvent {
                source {
                  ... on Issue { body }
                }
              }
            }
          }
        }
      }
    }
    """
    return {"query": query, "variables": {"owner": owner, "name": name, "number": number}}


def issue_state(owner: str, name: str, number: int) -> dict[str, Any]:
    """Build the ``issue_state`` query for an issue's open/closed state.

    Ported VERBATIM-IN-SPIRIT from the PoC ``_queries.py:123-132`` (the GraphQL
    string is the contract). Reads only ``state`` (and ``number`` for fidelity)
    — the phase-17 #13 dependency-gate fallback uses this to resolve off-board
    ``Depends on #N`` references (a closed issue satisfies a dependency).

    Args:
        owner: Repository owner login.
        name: Repository name.
        number: The issue number whose state to read.

    Returns:
        A GraphQL payload reading the issue's ``state`` (``"OPEN"`` or
        ``"CLOSED"``) and its ``number``.
    """
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) { number state }
      }
    }
    """
    return {"query": query, "variables": {"owner": owner, "name": name, "number": number}}


def move_item(
    project_id: str, item_id: str, status_field_id: str, option_id: str
) -> dict[str, Any]:
    """Set the Status single-select value of an item to ``option_id`` (not a name).

    Args:
        project_id: The ``ProjectV2`` node id owning the item.
        item_id: The ``ProjectV2Item`` node id to move.
        status_field_id: The Status single-select field node id.
        option_id: The destination column's single-select option id.

    Returns:
        A GraphQL ``updateProjectV2ItemFieldValue`` mutation payload.
    """
    # The mutation returns the item's RESULTING Status name so a caller can verify the remote state
    # read-your-write (no second query, no eventual-consistency lag) — used by the board-mirror's
    # verified-move path.
    query = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: { singleSelectOptionId: $optionId }
      }) {
        projectV2Item {
          id
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
        }
      }
    }
    """
    return {
        "query": query,
        "variables": {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": status_field_id,
            "optionId": option_id,
        },
    }


def create_project_field_single_select(
    project_id: str, name: str, options: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build the ``createProjectV2Field`` mutation for a NEW single-select field (health-field).

    Creates a per-card single-select FIELD (used for the custom "Health" field so the
    operator's vocabulary shows as native chips). Each option carries a ``name`` +
    ``color`` (one of GitHub's fixed palette tokens GRAY / BLUE / GREEN / YELLOW /
    ORANGE / RED / PINK / PURPLE) + a ``description`` — the same
    ``ProjectV2SingleSelectFieldOptionInput`` shape :func:`update_status_field_options`
    builds. The response returns the new field id + its option ids so the caller can
    persist them and set per-card values without a re-read.

    Args:
        project_id: The ``ProjectV2`` node id to create the field on.
        name: The field name (``"Health"`` for the health-field feature).
        options: The single-select options to create, each a
            ``{"name": ..., "color": ..., "description": ...}`` mapping.

    Returns:
        A GraphQL ``createProjectV2Field`` mutation payload whose response carries
        ``projectV2Field { id name options { id name } }``.
    """
    query = """
    mutation($projectId: ID!, $name: String!,
             $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
      createProjectV2Field(input: {
        projectId: $projectId
        dataType: SINGLE_SELECT
        name: $name
        singleSelectOptions: $options
      }) {
        projectV2Field {
          ... on ProjectV2SingleSelectField { id name options { id name } }
        }
      }
    }
    """
    return {
        "query": query,
        "variables": {"projectId": project_id, "name": name, "options": options},
    }


# NOTE (#14): the GraphQL comment path (``issue_node_id`` builder + ``add_comment`` mutation) was
# DELETED here. The PoC posted a comment via two GraphQL calls; NEW posts via a single REST POST
# (:meth:`kanbanmate.adapters.github.client.GithubClient.comment`), so these builders were dead
# code. Do NOT reintroduce a GraphQL comment builder — the REST path is the contract.


# ---------------------------------------------------------------------------
# Project status-update builders (the rolling dashboard, phase-24 §24.2).
# These maintain ONE rolling status update in the Project's "Status updates"
# section — created once, then refreshed by id on change (never per tick).
# ---------------------------------------------------------------------------


def create_status_update(project_id: str, body: str, status: str) -> dict[str, Any]:
    """Build the ``createProjectV2StatusUpdate`` mutation (the first post).

    Creates a fresh status update under the project's "Status updates" section
    and returns the new node id so the daemon can persist it and ``update`` (not
    re-create) on subsequent on-change refreshes (phase-24 §24.2).

    Args:
        project_id: The ``ProjectV2`` node id whose status update to create.
        body: The markdown status-update body (the rendered dashboard).
        status: A ``ProjectV2StatusUpdateStatus`` enum value (``INACTIVE`` /
            ``ON_TRACK`` / ``AT_RISK`` / ``OFF_TRACK`` / ``COMPLETE``).

    Returns:
        A GraphQL ``createProjectV2StatusUpdate`` mutation payload whose response
        carries ``statusUpdate { id }`` (the new node id).
    """
    query = """
    mutation($projectId: ID!, $body: String, $status: ProjectV2StatusUpdateStatus) {
      createProjectV2StatusUpdate(input: {
        projectId: $projectId
        body: $body
        status: $status
      }) {
        statusUpdate { id }
      }
    }
    """
    return {
        "query": query,
        "variables": {"projectId": project_id, "body": body, "status": status},
    }


def update_status_update(status_update_id: str, body: str, status: str) -> dict[str, Any]:
    """Build the ``updateProjectV2StatusUpdate`` mutation (an on-change refresh).

    Refreshes the EXISTING rolling status update in place (by its node id) rather
    than creating a new one, so the project shows a single rolling pill that the
    daemon updates only when the body or status enum changes (phase-24 §24.2).

    Args:
        status_update_id: The ``ProjectV2StatusUpdate`` node id to refresh (the id
            :func:`create_status_update`'s response returned).
        body: The new markdown status-update body.
        status: A ``ProjectV2StatusUpdateStatus`` enum value (``INACTIVE`` /
            ``ON_TRACK`` / ``AT_RISK`` / ``OFF_TRACK`` / ``COMPLETE``).

    Returns:
        A GraphQL ``updateProjectV2StatusUpdate`` mutation payload whose response
        carries ``statusUpdate { id }``.
    """
    query = """
    mutation($statusUpdateId: ID!, $body: String, $status: ProjectV2StatusUpdateStatus) {
      updateProjectV2StatusUpdate(input: {
        statusUpdateId: $statusUpdateId
        body: $body
        status: $status
      }) {
        statusUpdate { id }
      }
    }
    """
    return {
        "query": query,
        "variables": {"statusUpdateId": status_update_id, "body": body, "status": status},
    }


def delete_status_update(status_update_id: str) -> dict[str, Any]:
    """Build the ``deleteProjectV2StatusUpdate`` mutation (orphan cleanup, phase-36).

    Deletes a status update by its node id. The reporter's self-heal path (an
    ``update`` of a stale id failing → a fresh ``create``) leaves the OLD update
    lingering in the project's "Status updates" section (observed live: 3 stacked
    pills). After a successful re-create, the reporter best-effort deletes the
    stale id via this mutation so the project keeps a SINGLE rolling pill; a
    delete failure is logged and swallowed (the lingering update is cosmetic, not
    a launch blocker).

    Args:
        status_update_id: The orphaned ``ProjectV2StatusUpdate`` node id to delete.

    Returns:
        A GraphQL ``deleteProjectV2StatusUpdate`` mutation payload whose response
        carries the ``deletedStatusUpdateId``.

    Note:
        The payload's selection MUST be ``deletedStatusUpdateId`` — the
        ``DeleteProjectV2StatusUpdatePayload`` type has NO ``statusUpdate`` field
        (selecting it makes GitHub reject the whole mutation), so the previous
        ``statusUpdate { id }`` selection silently failed EVERY delete, leaving
        orphaned status updates stacked on the board (observed live: 52 stacked).
    """
    query = """
    mutation($statusUpdateId: ID!) {
      deleteProjectV2StatusUpdate(input: {
        statusUpdateId: $statusUpdateId
      }) {
        deletedStatusUpdateId
      }
    }
    """
    return {
        "query": query,
        "variables": {"statusUpdateId": status_update_id},
    }


# ---------------------------------------------------------------------------
# Seeder builders (consumed by ``kanban init`` / ``kanban seed``, DESIGN §4.3).
# These bootstrap the board once per repo; they are NOT on the daemon hot path.
# ---------------------------------------------------------------------------


def org_id(org: str) -> dict[str, Any]:
    """Fetch an organization's global node id (owner_id for ``createProjectV2``).

    Args:
        org: The organization login.

    Returns:
        A GraphQL payload reading the organization's node id.
    """
    query = """
    query($org: String!) {
      organization(login: $org) { id }
    }
    """
    return {"query": query, "variables": {"org": org}}


def find_org_project(org: str) -> dict[str, Any]:
    """List an organization's Projects v2 (id/title/number) to find one by title.

    Args:
        org: The organization login whose projects to list.

    Returns:
        A GraphQL payload reading the org's first 100 Projects v2.
    """
    query = """
    query($org: String!) {
      organization(login: $org) {
        projectsV2(first: 100) { nodes { id title number } }
      }
    }
    """
    return {"query": query, "variables": {"org": org}}


def create_project(owner_id: str, title: str) -> dict[str, Any]:
    """Create a new Projects v2 board owned by ``owner_id`` (the org node id).

    Args:
        owner_id: The organization node id that will own the project.
        title: The project title.

    Returns:
        A GraphQL ``createProjectV2`` mutation payload.
    """
    query = """
    mutation($ownerId: ID!, $title: String!) {
      createProjectV2(input: { ownerId: $ownerId, title: $title }) {
        projectV2 { id title number }
      }
    }
    """
    return {"query": query, "variables": {"ownerId": owner_id, "title": title}}


def project_short_description(project_id: str) -> dict[str, Any]:
    """Read a project's current ``shortDescription`` (the idempotency probe).

    ``kanban init`` sets a default project description ONLY when the field is
    empty (phase-33); this reads the current value so the setter can skip a
    project whose description an operator already filled in.

    Args:
        project_id: The ``ProjectV2`` node id whose short description to read.

    Returns:
        A GraphQL payload reading ``node(id) { ... on ProjectV2 { shortDescription } }``.
    """
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 { shortDescription }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id}}


def update_project_description(project_id: str, short_description: str) -> dict[str, Any]:
    """Build the ``updateProjectV2`` mutation that sets a project's ``shortDescription``.

    Used by ``kanban init`` to give a fresh board a default one-line description
    (phase-33). The seam reuses the standard ``updateProjectV2`` mutation already
    used for other project-level edits; only the ``shortDescription`` input is set.

    Args:
        project_id: The ``ProjectV2`` node id whose short description to set.
        short_description: The one-line description to write.

    Returns:
        A GraphQL ``updateProjectV2`` mutation payload whose response echoes the
        project's ``id`` + ``shortDescription``.
    """
    query = """
    mutation($projectId: ID!, $shortDescription: String!) {
      updateProjectV2(input: {
        projectId: $projectId
        shortDescription: $shortDescription
      }) {
        projectV2 { id shortDescription }
      }
    }
    """
    return {
        "query": query,
        "variables": {"projectId": project_id, "shortDescription": short_description},
    }


def project_item_statuses(project_id: str, after: str | None = None) -> dict[str, Any]:
    """Page through a project's items, reading each item's Status name.

    Used to count cards per column BEFORE dropping a residual column
    (orphan-safety): an option that still holds cards must never be removed by
    the option-set REPLACE in :func:`update_status_field_options`.

    Args:
        project_id: The ``ProjectV2`` node id whose items to read.
        after: Optional ``endCursor`` for the next page.

    Returns:
        A GraphQL payload reading one page of the project's item Status names.
    """
    query = """
    query($projectId: ID!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $after) {
            pageInfo { hasNextPage endCursor }
            nodes {
              fieldValueByName(name: "Status") {
                ... on ProjectV2ItemFieldSingleSelectValue { name }
              }
            }
          }
        }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id, "after": after}}


def update_status_field_options(field_id: str, options: list[dict[str, Any]]) -> dict[str, Any]:
    """Set the FULL single-select option list of a Status field (REPLACE).

    GitHub's ``updateProjectV2Field.singleSelectOptions`` REPLACES the option
    set, so the caller must pass existing + new options. Each option is
    ``{name, color, description}`` plus an optional ``id`` (passing an existing
    option's id preserves it so cards keep their Status — see
    :meth:`kanbanmate.adapters.github.client.GithubClient.ensure_columns`).

    Args:
        field_id: The Status single-select field node id.
        options: The full target option list (existing-with-id + new-without-id).

    Returns:
        A GraphQL ``updateProjectV2Field`` mutation payload.
    """
    query = """
    mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
      updateProjectV2Field(input: { fieldId: $fieldId, singleSelectOptions: $options }) {
        projectV2Field {
          ... on ProjectV2SingleSelectField { id name options { id name } }
        }
      }
    }
    """
    return {"query": query, "variables": {"fieldId": field_id, "options": options}}


def repo_id(owner: str, name: str) -> dict[str, Any]:
    """Fetch a repository node id + its first 100 labels (id+name).

    Args:
        owner: The repository owner login.
        name: The repository name.

    Returns:
        A GraphQL payload reading the repo node id and existing labels.
    """
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        labels(first: 100) { nodes { id name } }
      }
    }
    """
    return {"query": query, "variables": {"owner": owner, "name": name}}


def link_project_to_repo(project_id: str, repository_id: str) -> dict[str, Any]:
    """Build the ``linkProjectV2ToRepository`` mutation (associate a project with a repo).

    Linking makes the org Project v2 appear in the repository's Projects tab and records the
    canonical repo↔project association ``kanban init`` is expected to establish.

    Args:
        project_id: The ``ProjectV2`` node id to link.
        repository_id: The repository node id to link it to (from :func:`repo_id`).

    Returns:
        A GraphQL ``linkProjectV2ToRepository`` mutation payload.
    """
    query = """
    mutation($projectId: ID!, $repositoryId: ID!) {
      linkProjectV2ToRepository(input: {projectId: $projectId, repositoryId: $repositoryId}) {
        repository { id }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id, "repositoryId": repository_id}}


def create_label(repository_id: str, name: str, color: str) -> dict[str, Any]:
    """Create a repository label (``color`` is a 6-hex string, no leading ``#``).

    Args:
        repository_id: The repository node id to create the label on.
        name: The label name.
        color: The 6-hex label colour (no leading ``#``).

    Returns:
        A GraphQL ``createLabel`` mutation payload.
    """
    query = """
    mutation($repositoryId: ID!, $name: String!, $color: String!) {
      createLabel(input: { repositoryId: $repositoryId, name: $name, color: $color }) {
        label { id name }
      }
    }
    """
    return {
        "query": query,
        "variables": {"repositoryId": repository_id, "name": name, "color": color},
    }


def create_issue(repository_id: str, title: str, body: str, label_ids: list[str]) -> dict[str, Any]:
    """Create an Issue with labels; returns the new issue id/number/node.

    Args:
        repository_id: The repository node id to create the issue on.
        title: The issue title.
        body: The issue body (markdown).
        label_ids: The label node ids to attach.

    Returns:
        A GraphQL ``createIssue`` mutation payload.
    """
    query = """
    mutation($repositoryId: ID!, $title: String!, $body: String!, $labelIds: [ID!]) {
      createIssue(input: {
        repositoryId: $repositoryId
        title: $title
        body: $body
        labelIds: $labelIds
      }) {
        issue { id number }
      }
    }
    """
    return {
        "query": query,
        "variables": {
            "repositoryId": repository_id,
            "title": title,
            "body": body,
            "labelIds": label_ids,
        },
    }


def update_issue_body(issue_node_id: str, body: str) -> dict[str, Any]:
    """Update an Issue's body (``seed`` materialises ``Depends on #N``).

    Args:
        issue_node_id: The issue's global node id.
        body: The new markdown body.

    Returns:
        A GraphQL ``updateIssue`` mutation payload.
    """
    query = """
    mutation($id: ID!, $body: String!) {
      updateIssue(input: { id: $id, body: $body }) {
        issue { id number }
      }
    }
    """
    return {"query": query, "variables": {"id": issue_node_id, "body": body}}


def close_issue(issue_node_id: str) -> dict[str, Any]:
    """Close an Issue by its global node id (cockpit PR3 ``ticket_close``).

    The ``CloseIssuePayload`` type DOES carry an ``issue`` field (unlike the status-update delete
    payload), so selecting ``issue { id }`` is valid.

    Args:
        issue_node_id: The issue's global node id to close.

    Returns:
        A GraphQL ``closeIssue`` mutation payload whose response carries ``issue { id }``.
    """
    query = """
    mutation($id: ID!) {
      closeIssue(input: { issueId: $id }) {
        issue { id }
      }
    }
    """
    return {"query": query, "variables": {"id": issue_node_id}}


def add_item_to_project(project_id: str, content_id: str) -> dict[str, Any]:
    """Add an issue (by content node id) to a project; returns the item id.

    Args:
        project_id: The ``ProjectV2`` node id to add the issue to.
        content_id: The issue's global content node id.

    Returns:
        A GraphQL ``addProjectV2ItemById`` mutation payload.
    """
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: { projectId: $projectId, contentId: $contentId }) {
        item { id }
      }
    }
    """
    return {"query": query, "variables": {"projectId": project_id, "contentId": content_id}}
