# ensign — visual indicator for CLOSED issues

- **Ticket**: #82 — "Indicateurs visuel issues close"
- **Track**: lite (skiff) · **Codename**: `ensign` · **Bump**: minor (new backward-compatible UI signal)
- **One-liner**: surface each card's GitHub open/closed state on the KanbanMateUI **Board** and
  **Monitoring** views, so a CLOSED issue is visually marked.

## Problem & approach (already determined — no open design question)

The card data model carries **no** open/closed state today. The board snapshot rides a single
`board_items` GraphQL query whose Issue fragment reads only `number title body`
(`adapters/github/_queries.py:81`); `Ticket` (`core/domain.py:61-80`) has no state field. A separate
per-issue `issue_state` query exists (`_queries.py:165-189`, returns `"OPEN"`/`"CLOSED"`) but is used
only by the dependency gate — not per-card.

**Approach** (grounded, zero extra GraphQL cost — rides the existing board query, no N+1): add
`state` to the board-items Issue fragment, thread an `is_closed: bool` field down the parse chain
into `Ticket`, expose it on both serving endpoints, and render a closed badge in the two SPA panels.
`is_closed` is `True` iff the content is an Issue with `state == "CLOSED"` (uppercase is GitHub's
`IssueState` contract, confirmed at `_queries.py:179-180`); draft/PR content → `False`.

## Complete touchpoint set (verified against source)

### Backend — plumbing chain (import order, downward-only; `core` stays I/O-free)

1. `adapters/github/_queries.py:81` — board_items Issue fragment
   `... on Issue { number title body }` → `... on Issue { number title body state }`.
2. `adapters/github/_parsers.py:118-140` `_content_fields` — currently returns
   `(issue_number, title, body)`; extend to `(issue_number, title, body, is_closed)` with
   `is_closed = is_issue and content.get("state") == "CLOSED"`. Update signature + docstring
   (`-> tuple[int | None, str, str, bool]`).
3. `adapters/github/_parsers.py:143-175` `parse_board_items` — unpack the 4th value at line 164 and
   pass `is_closed=...` into the `RawItem(...)` constructor (lines 165-174).
4. `adapters/github/types.py:16-42` `RawItem` — add `is_closed: bool = False` (+ Attributes docstring).
5. `core/domain.py:61-80` `Ticket` — add `is_closed: bool = False` (+ Attributes docstring).
6. `adapters/github/client.py:206-223` `_to_ticket` — add `is_closed=raw.is_closed` to the
   `Ticket(...)` call.

### Backend — serving endpoints (both consumers from triage/brainstorm)

7. `http/board_routes.py:258-285` `board_state` — extend the identity tuple at line 263 from
   `(t.issue_number, t.title, _body_excerpt(t.body))` to add `t.is_closed`; unpack at line 275; add
   `"is_closed": is_closed` to the card dict (lines 276-285). Missing-identity default (forge JOIN
   degraded) → `False`.
8. `app/monitor.py:40-98` `build_board` — `tickets` param tuple
   `(number, title, column_key)` → `(number, title, column_key, is_closed)`; update signature
   (`Sequence[tuple[int, str, str, bool]]`) + docstring; unpack `for num, title, col, is_closed in
   tickets` (line 73); add `"is_closed": is_closed` to `ticket_payload` (lines 86-93).
9. `http/monitor_routes.py:151-153` — build the tuple as
   `(t.issue_number, t.title, t.column_key, t.is_closed)`.

### Frontend (SPA) — render the indicator

10. `web/src/panels/BoardPanel.jsx` `RichCardFace` (990-1075) — the single shared card face (desktop
    line 642 + mobile line 815). When `card.is_closed`, render a small closed badge near the
    `#{card.issue_number}` span and mute the title. Reuse the already-imported `Badge` (used at
    line 698) + a lucide icon (icons already imported, e.g. `MonitorCheck` at line 1056); use the new
    i18n label.
11. `web/src/panels/MonitoringPanel.jsx` — two ticket render spots: the mobile chip grid (~681-720)
    and the desktop list rows (~789-851, where `tk.number`/`tk.title`/`tk.agent_state` render). When
    `tk.is_closed`, show a closed badge in the list row and mark the chip. `Badge` is already imported
    (line 23).

### i18n

12. `web/src/i18n/en.yaml` `board:` block (after `untitled:`, line 555) — add `closed: Closed` (+ a
    tooltip key, e.g. `closed_hint: This issue is closed`). Mirror the same keys in
    `web/src/i18n/fr.yaml` (`closed: Clôturé`, `closed_hint: Cette issue est clôturée`). If
    Monitoring needs its own key, add under the existing `monitoring:` block; otherwise reuse
    `board.closed`.

## Plan (checklist)

- [ ] **B1 — plumb backend** (touchpoints 1-6): add `state` to the query, derive `is_closed` in
  `_content_fields`, thread through `parse_board_items` → `RawItem` → `Ticket` → `_to_ticket`.
- [ ] **B2 — serving endpoints** (7-9): expose `is_closed` on `/api/board/state` cards and the
  monitoring board-overview payload (extend the `build_board` tuple + its caller).
- [ ] **F1 — Board panel** (10): closed badge + muted title in `RichCardFace`.
- [ ] **F2 — Monitoring panel** (11): closed badge in list rows + chip grid.
- [ ] **F3 — i18n** (12): `closed` / `closed_hint` in `en.yaml` + `fr.yaml`.
- [ ] **T — tests** (mirror `tests/<layer>/`):
  - `tests/adapters/github/test_pagination.py` — extend the `_board_item` helper (lines 75-81) to
    accept `state`; assert the parsed `RawItem.is_closed` is `True` for a `state:"CLOSED"` Issue and
    `False` for an open Issue and for a draft (real values, not None/None).
  - `tests/app/test_monitor.py` — `build_board` with a closed ticket tuple → its `ticket_payload`
    entry carries `is_closed: True` (and `False` for an open one).
  - `tests/http/test_board_routes.py` — `/api/board/state` card JSON includes `is_closed`.
- [ ] **Gate**: `make check` (ruff + mypy + tests + module-size); `npm run build` in `web/` for the
  SPA bundle; bump VERSION/`pyproject.toml`/`__init__.py`/plugin manifest (minor).

## Out of scope / non-goals

- No new GraphQL round-trip (no per-issue `issue_state` N+1 — rides the board query).
- No new third-party dependency.
- No filtering/hiding of closed cards — purely a visual indicator.
- No change to move/transition/daemon logic; `is_closed` is read-only display data.
