# skiff — manual Track override (label + KanbanMateUI editing) Implementation Plan

> Addendum to the skiff fast-track feature. Adds a NATIVE, GitHub-editable manual override for the
> processing lane (`track:*` label) and makes it readable + editable in KanbanMateUI on the issue
> detail panel AND the monitoring row. Lanes vocabulary stays the closed `{full, lite, express}`;
> absence of any `track:*` label = `auto` (the triage classifies).

**Goal:** Let the operator force a ticket's lane via a `track:full|lite|express` GitHub label — set in
GitHub directly OR from KanbanMateUI (detail + monitoring) over the GitHub API.

**Global constraints:** PYTHONPATH=src for tests (worktree editable install points elsewhere); fail-soft
HTTP (HTTPException with status); CSRF/auth handled by existing middleware; network calls inherit the
client's mandatory connect+read timeouts; closed lane vocabulary `TRACK_VALUES` (from
`core.transitions_defaults`); Google docstrings; no daemon-snapshot bloat.

---

### Task 13: GitHub client — read/write the track label

**Files:**
- Modify: `src/kanbanmate/adapters/github/types.py` (IssueRef carries labels)
- Modify: `src/kanbanmate/adapters/github/client.py` (`fetch_issue` parses labels; `set_issue_track_label`; `board_item_tracks`)
- Modify: `src/kanbanmate/adapters/github/_queries.py` (add/remove label GraphQL mutations + a projectItems-with-labels query)
- Test: `tests/adapters/test_github_client.py` (or the repo's client test module — match location)

**Interfaces produced:**
- `IssueRef.labels: tuple[str, ...]` (label NAMES; default `()`).
- `GithubClient.set_issue_track_label(issue_number: int, track_value: str | None) -> None` — idempotent: validates `track_value in TRACK_VALUES` (else raises `ValueError`) or `None`; ensures `track:{value}` exists (`ensure_labels`); removes any existing `track:*` label != the target; adds the target (or, for `None`, removes all `track:*`). Uses the GraphQL `addLabelsToLabelable`/`removeLabelsFromLabelable` mutations on `IssueRef.node_id`.
- `GithubClient.board_item_tracks() -> dict[int, str]` — `{issue_number: track_value}` for items that carry a `track:*` label (one GraphQL projectItems query that returns each item's content issue number + labels; items with no `track:*` are omitted). UI-only read; does NOT touch the daemon snapshot.

- [ ] **Step 1: Failing tests**

```python
# tests/adapters/test_github_client.py  (match the repo's client-test fixture style)
def test_fetch_issue_parses_labels(fake_client_with_rest):
    # REST GET /issues/{n} returns labels: [{name: "track:express"}, {name: "bug"}]
    ref = fake_client_with_rest.fetch_issue(7)
    assert "track:express" in ref.labels and "bug" in ref.labels

def test_set_issue_track_label_replaces_existing_track(fake_client_graphql):
    # issue currently has track:full; setting express removes track:full, adds track:express
    fake_client_graphql.set_issue_track_label(7, "express")
    assert fake_client_graphql.removed == ["track:full"]
    assert fake_client_graphql.added == ["track:express"]

def test_set_issue_track_label_none_clears_all(fake_client_graphql):
    fake_client_graphql.set_issue_track_label(7, None)
    assert "track:full" in fake_client_graphql.removed and not fake_client_graphql.added

def test_set_issue_track_label_rejects_unknown(fake_client_graphql):
    import pytest
    with pytest.raises(ValueError):
        fake_client_graphql.set_issue_track_label(7, "turbo")
```

- [ ] **Step 2–4: Implement per the scoping recommendations**

- `types.py`: add `labels: tuple[str, ...] = ()` to the frozen `IssueRef`.
- `client.fetch_issue`: after the REST GET, `labels = tuple(str(l["name"]) for l in (data.get("labels") or []))`, pass to `IssueRef`.
- `_queries.py`: `add_labels_to_issue(node_id, label_ids)` (mutation `addLabelsToLabelable`), `remove_labels_from_issue(node_id, label_ids)` (mutation `removeLabelsFromLabelable`), and `project_item_labels(project_id, after)` (query `node(id:$pid){ ... on ProjectV2 { items(first:100, after:$after){ pageInfo{hasNextPage,endCursor} nodes{ content{ ... on Issue { number labels(first:20){nodes{name}} } } } } } }`).
- `client.set_issue_track_label`: validate against `TRACK_VALUES` (import from `core.transitions_defaults`); resolve current labels via `fetch_issue`; `ensure_labels` for the target; map current `track:*` names → ids (the GraphQL labels query returns ids, or reuse `ensure_labels`' name→id for removals — fetch ids via a labels query if needed); remove the stale track ids, add the target id. Fail-soft per the client's `raise_for_errors` convention.
- `client.board_item_tracks`: paginate `project_item_labels`, collect `{number: value}` where a `track:<value>` label is present (strip the `track:` prefix). Inherit timeouts (GraphQL transport).

- [ ] **Step 5: Run + commit** — `PYTHONPATH=src pytest tests/adapters/test_github_client.py -k "track or label" -v && PYTHONPATH=src mypy src tests && ruff check src tests` → `feat(skiff): github client read/write the track:* label`.

---

### Task 14: HTTP — expose + write the track

**Files:**
- Modify: `src/kanbanmate/app/monitor.py` (`build_ticket_detail` adds `track` + `labels`)
- Modify: `src/kanbanmate/http/monitor_routes.py` (`monitor_ticket` passes labels; new `POST …/track`; new `GET …/board/tracks`)
- Test: `tests/http/test_monitor_api.py`

**Interfaces produced:**
- `build_ticket_detail(..., labels=None)` → payload gains `"track": <value|None>` (parsed from a `track:*` label) and `"labels": [names]`.
- `POST /api/monitor/ticket/{number}/track` body `{"track": "full"|"lite"|"express"|null}` → `gh.set_issue_track_label(number, track or None)`; returns `{"ok": true}`. 400 on an invalid value; 502 on GitHub error. Behind the existing CSRF/auth middleware.
- `GET /api/monitor/board/tracks?project=` → `{"tracks": {number: value}}` via `gh.board_item_tracks()`.

- [ ] **Steps:** Mirror the existing PATCH `…/ticket/{number}/body` (validation + `_monitor_github(entry)` wiring + JSONResponse) for the POST, and the GET `…/ticket/{number}` for the new GET. Validate `track in TRACK_VALUES or track in (None, "")`. Tests: a fake gh spy asserts `set_issue_track_label` called with the right args; the detail GET returns `track`; the board/tracks GET returns the map. Mirror `test_launch_endpoint`/`test_patch_ticket_body` fixtures (auth disabled, `app.state.monitor_github` injected). Run `PYTHONPATH=src pytest tests/http/test_monitor_api.py -v && mypy + ruff`. Commit: `feat(skiff): /track endpoint + track in the ticket detail/board payloads`.

---

### Task 15: KanbanMateUI — Track selector (detail + monitoring row)

**Files:**
- Modify: `web/src/api.js` (`setTicketTrack`, `getBoardTracks`)
- Modify: the monitoring panel (`web/src/panels/…` — the one rendering the issue rows + the detail right-panel) + reuse the DS `Select`
- Modify: `web/src/i18n/*` if the app localizes labels
- Test: a frontend test if the repo has them (else manual — note it)

**Interfaces consumed:** `POST /api/monitor/ticket/{n}/track`, `GET /api/monitor/board/tracks`, the detail payload's `track`.

- [ ] **Steps:** Add `setTicketTrack(number, track, project)` (POST, CSRF header via the existing fetch wrapper) + `getBoardTracks(project)` (GET) to `api.js`, mirroring `moveTicket`. Add a `Track` `<Select>` (options: `Auto` (empty), `Full`, `Lite`, `Express`) — (a) in the issue **detail** panel after the status/move section, bound to a `doTrack()` handler (optimistic + refetch `monitorTicket`); (b) on each monitoring **row**, compact, wrapped in a `div` with `onClick stopPropagation` so it doesn't trigger row-select; its current value comes from a `boardTracks` map fetched alongside the board poll. Disable while a write is in flight; show a small status message like the move handler. Run `npm run build` (or the web test) to confirm it compiles. Commit: `feat(skiff): KanbanMateUI Track selector on issue detail + monitoring row`.

---

### Task 16 (inline, controller): triage robustness + label seeding

- Tweak `_TRIAGE_PROMPT` (`transitions_defaults.py`): if MULTIPLE `track:*` labels are present (shouldn't happen — the UI/`set_issue_track_label` enforce single-select), treat as ambiguous → `full`. (One clause; the existing single-label honour stays.)
- The three `track:full|lite|express` labels are auto-created on first use by `set_issue_track_label` (`ensure_labels`); optionally seed them with distinct colours at `kanban seed`/init (cosmetic — defer if not trivial).
