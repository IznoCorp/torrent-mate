# Phase 4 — UI finishes

## Gate

**Phase 3 COMPLETE is recommended for a clean branch**, but sub-phases 4.1–4.4 have no backend
dependency and can run after Phase 1. Sub-phase 4.5 (`/api/health` version) requires only a
one-line change to `config_api.py` — independent of Phases 2–3.

Required at minimum:

- `make check` green on the Phase 3 (or Phase 1) commit.
- `npm --prefix web run build` exit 0.

## Overview

Five frontend (+ one backend) sub-phases: collapsible columns in BoardPanel with
default-empty-collapse logic, collapsible status groups in MonitoringPanel, shadcn Card migration
with polished drag, markdown-rendered timeline with progress/comment separation, and a
deployed-version indicator in the sidebar backed by `/api/health` returning `{status, version}`.

---

## Sub-phase 4.1 — Collapsible columns (BoardPanel)

**Commit:** `feat(tiller): collapsible board columns with default-empty-collapse + localStorage`

**Files touched:**

- Create: `web/src/lib/collapse.js`
- Modify: `web/src/panels/BoardPanel.jsx`

**Create `web/src/lib/collapse.js`:**

```js
/**
 * Shared localStorage helper for collapsible UI state (tiller §7.1).
 *
 * Stores `{ explicit: boolean, collapsed: boolean }` per key.
 * - `explicit: false` means "collapsed by default because it was empty" — auto-expands
 *   when tickets arrive.
 * - `explicit: true` means the operator chose to collapse it — stays collapsed even
 *   when tickets arrive.
 */

/**
 * @param {string} key - localStorage key
 * @param {{ explicit: boolean, collapsed: boolean }} value
 */
export function setCollapseState(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {}
}

/**
 * @param {string} key - localStorage key
 * @returns {{ explicit: boolean, collapsed: boolean } | null}
 */
export function getCollapseState(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

/**
 * Compute whether a column should be collapsed, applying the default-empty rule.
 *
 * Rules:
 * 1. If the operator has explicitly set a state (`explicit: true`), honour it.
 * 2. If the column has 0 tickets and no stored state, collapse by default.
 * 3. If the column now has tickets and the stored state is `explicit: false`, auto-expand.
 *
 * @param {string} key - localStorage key for this column
 * @param {number} ticketCount - current number of tickets in the column
 * @returns {boolean} - true if the column should be shown collapsed
 */
export function resolveCollapsed(key, ticketCount) {
  const stored = getCollapseState(key);
  if (stored === null) {
    // No stored state: collapse iff empty (default-empty rule).
    return ticketCount === 0;
  }
  if (stored.explicit) {
    // Operator explicitly chose — honour that choice regardless of ticket count.
    return stored.collapsed;
  }
  // Default-empty: auto-expand when tickets arrive, collapse when empty.
  return ticketCount === 0;
}
```

**Modify `web/src/panels/BoardPanel.jsx`:**

Import the helper at the top:

```jsx
import {
  getCollapseState,
  resolveCollapsed,
  setCollapseState,
} from "../lib/collapse.js";
```

Add column-collapse state. Each column key maps to its current collapsed state (computed via
`resolveCollapsed`). The collapse state is initialised from localStorage + ticket counts on first
render, then updated on toggle:

```jsx
// collapseMap: { [colKey]: boolean } — derived from localStorage + ticket counts.
const [collapseMap, setCollapseMap] = React.useState({});

// Initialise / sync collapse state whenever board data changes.
React.useEffect(() => {
  if (!data) return;
  const next = {};
  for (const col of data.columns) {
    const lsKey = `km:board:collapsed:${project}:${col.key}`;
    const count = (data.cards || []).filter(
      (c) => c.column_key === col.key,
    ).length;
    next[col.key] = resolveCollapsed(lsKey, count);
  }
  setCollapseMap(next);
}, [data, project]);

const toggleColumn = (colKey, ticketCount) => {
  const lsKey = `km:board:collapsed:${project}:${colKey}`;
  const current = collapseMap[colKey] ?? false;
  const next = !current;
  // Mark as explicit when the operator actively toggles.
  setCollapseState(lsKey, { explicit: true, collapsed: next });
  setCollapseMap((m) => ({ ...m, [colKey]: next }));
};
```

In the column render: add an expand/collapse button on the column header. When
`collapseMap[col.key]` is true, render only the column header strip (with ticket count) and hide
the card list:

```jsx
{
  data.columns.map((col) => {
    const cards = (data.cards || []).filter((c) => c.column_key === col.key);
    const collapsed = collapseMap[col.key] ?? cards.length === 0;
    return (
      <div
        key={col.key}
        className={collapsed ? "km-col km-col--collapsed" : "km-col"}
      >
        <div
          className="km-col-header"
          style={{ cursor: "pointer", userSelect: "none" }}
          onClick={() => toggleColumn(col.key, cards.length)}
        >
          <span>{col.name}</span>
          <Badge>{cards.length}</Badge>
          <span style={{ marginLeft: 4 }}>{collapsed ? "▶" : "▼"}</span>
        </div>
        {!collapsed && (
          <div className="km-col-cards">{/* existing card render */}</div>
        )}
      </div>
    );
  });
}
```

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Sub-phase 4.2 — Collapsible status groups (MonitoringPanel)

**Commit:** `feat(tiller): collapsible monitoring status groups with default-empty-collapse`

**Files touched:**

- Modify: `web/src/panels/MonitoringPanel.jsx`

Import the helper (if not already imported):

```jsx
import { resolveCollapsed, setCollapseState } from "../lib/collapse.js";
```

The monitoring panel groups agents by status (running / waiting / blocked). Add
`statusCollapse` state and apply the same default-empty-collapse logic:

```jsx
const [statusCollapse, setStatusCollapse] = React.useState({});

const STATUS_GROUPS = ["running", "waiting", "blocked"];

// Sync collapse state when agents change.
React.useEffect(() => {
  const next = {};
  for (const status of STATUS_GROUPS) {
    const lsKey = `bridge.monitor.collapsed.${project}.${status}`;
    const count = agents.filter((a) => a.state === status).length;
    next[status] = resolveCollapsed(lsKey, count);
  }
  setStatusCollapse(next);
}, [agents, project]);

const toggleStatus = (status, count) => {
  const lsKey = `bridge.monitor.collapsed.${project}.${status}`;
  const next = !(statusCollapse[status] ?? false);
  setCollapseState(lsKey, { explicit: true, collapsed: next });
  setStatusCollapse((m) => ({ ...m, [status]: next }));
};
```

In the agent-list render, wrap each group with the collapse toggle:

```jsx
{
  STATUS_GROUPS.map((status) => {
    const group = agents.filter((a) => a.state === status);
    const collapsed = statusCollapse[status] ?? group.length === 0;
    return (
      <div key={status}>
        <div
          onClick={() => toggleStatus(status, group.length)}
          style={{
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Badge tone={STATE_TONE[status]}>{status}</Badge>
          <span>({group.length})</span>
          <span>{collapsed ? "▶" : "▼"}</span>
        </div>
        {!collapsed &&
          group.map((a) => (
            /* existing agent row render */
            <div key={a.issue_number}>…</div>
          ))}
      </div>
    );
  });
}
```

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Sub-phase 4.3 — shadcn Card migration + drag polish

**Commit:** `feat(tiller): shadcn card style + polished drag effect in BoardPanel`

**Files touched:**

- Modify: `web/src/panels/BoardPanel.jsx`

**What to change:**

The project uses CSS variables (`var(--border)`, `var(--shadow-md)`, etc.) from its design system.
There is no shadcn package installed; "shadcn Card" here means applying the design-system card
token set: a `1px solid var(--border)` border, `var(--card)` background, `var(--radius)` corner
radius, and `var(--shadow-sm)` base shadow.

Replace the existing `BoardStyles` inline `<style>` block with the updated version:

```jsx
function BoardStyles() {
  return (
    <style>{`
      .km-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow-sm);
        padding: 10px 12px;
        cursor: grab;
        transition: transform .12s ease, box-shadow .15s ease, opacity .12s ease, border-color .12s ease;
      }
      .km-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
        border-color: var(--ring);
      }
      .km-card.km-dragging {
        opacity: .35;
        transform: scale(.96);
        box-shadow: var(--shadow-lg);
        border-color: var(--primary);
      }
      .km-card.km-grab { cursor: grab; }
      .km-card.km-grab:active { cursor: grabbing; }
      .km-dropline {
        height: 3px;
        border-radius: 2px;
        background: var(--primary);
        margin: 2px 4px;
        transition: opacity .1s ease;
      }
      .km-colstrip { transition: background .12s ease, border-color .12s ease; }
      .km-colstrip:hover { background: var(--muted); }
    `}</style>
  );
}
```

No change to drag/drop event handlers or move logic — visual only.

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Sub-phase 4.4 — Markdown timeline

**Commit:** `feat(tiller): markdown-rendered timeline with progress/comment separation`

**Files touched:**

- Modify: `web/src/panels/MonitoringPanel.jsx`

**What to change:**

The ticket detail `comments` array from `GET /api/monitor/ticket/{number}` contains timeline
entries. Render each with `marked` and visually distinguish "progress events" (daemon stage
comments that match the `**KanbanMate status**` pattern or start with the status-block pattern)
from operator comments.

Import `marked` at the top of `MonitoringPanel.jsx` (already a dependency):

```jsx
import { marked } from "marked";
```

Replace the existing flat comment list with:

```jsx
function TimelineEntry({ comment }) {
  // Progress events: daemon-authored comments containing the KanbanMate status header pattern.
  const isProgress =
    comment.body &&
    (comment.body.includes("**KanbanMate status**") ||
      comment.body.includes("<!-- kanban:status:begin -->"));
  const html = { __html: marked.parse(comment.body || "", { breaks: true }) };
  return (
    <div
      style={{
        padding: "8px 12px",
        borderRadius: 6,
        borderLeft: isProgress
          ? "3px solid var(--primary)"
          : "3px solid var(--border)",
        background: isProgress ? "var(--muted)" : "var(--card)",
        fontSize: 13,
      }}
    >
      {isProgress && (
        <div
          style={{
            fontSize: 11,
            color: "var(--muted-foreground)",
            marginBottom: 4,
          }}
        >
          ⚙ progress
        </div>
      )}
      {/* eslint-disable-next-line react/no-danger */}
      <div dangerouslySetInnerHTML={html} />
      {comment.created_at && (
        <div
          style={{
            fontSize: 11,
            color: "var(--muted-foreground)",
            marginTop: 4,
          }}
        >
          {new Date(comment.created_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}
```

Replace the existing comment list render in ticket detail with:

```jsx
{
  detail?.comments?.length > 0 && (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        marginTop: 12,
      }}
    >
      {detail.comments.map((c, i) => (
        <TimelineEntry key={c.id ?? i} comment={c} />
      ))}
    </div>
  );
}
```

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Sub-phase 4.5 — /api/health version + sidebar footer

**Commit:** `feat(tiller): surface kanbanmate.__version__ on /api/health + sidebar version footer`

**Files touched:**

- Modify: `src/kanbanmate/http/config_api.py` — update the `health()` route.
- Modify: `web/src/api.js` — add `fetchHealth()`.
- Modify: `web/src/components/AppShell.jsx` — fetch version at boot, render in sidebar footer.
- Modify: `web/src/components/SidebarNav.jsx` — add version footer prop.
- Modify: `tests/http/test_config_api.py` — add test for version field.

**Backend — update `health()` in `config_api.py`** (currently returns `{"status": "ok"}`):

```python
@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe — now also surfaces the deployed package version (tiller §7.4).

    Returns:
        ``{"status": "ok", "version": "<kanbanmate.__version__>"}``.
    """
    import kanbanmate  # noqa: PLC0415
    return {"status": "ok", "version": kanbanmate.__version__}
```

**Add to `web/src/api.js`** (after `logout`):

```js
export const fetchHealth = () => call("GET", "/api/health");
```

**Modify `web/src/components/AppShell.jsx`** — fetch health once at boot, pass version down:

Add state at the top of `AppShell`:

```jsx
const [version, setVersion] = React.useState(null);
React.useEffect(() => {
  import("../api.js").then(({ fetchHealth }) =>
    fetchHealth()
      .then((d) => setVersion(d.version))
      .catch(() => {}),
  );
}, []);
```

Pass `version` to `SidebarNav`:

```jsx
const nav = (
  <SidebarNav
    active={active}
    onNav={onNav}
    projects={projects}
    selected={selected}
    onSelect={onSelect}
    repo={repo}
    errorCount={errorCount}
    version={version}
  />
);
```

In the mobile drawer, also render the version chip in the drawer footer:

```jsx
{
  version && (
    <div
      style={{
        padding: "8px 16px",
        fontSize: 11,
        color: "var(--muted-foreground)",
      }}
    >
      v{version}
    </div>
  );
}
```

**Modify `web/src/components/SidebarNav.jsx`** — accept and render `version` prop:

Add `version = null` to the default props of the exported `SidebarNav` component (or add it to
the function signature). At the bottom of the sidebar nav render (after the nav items), add:

```jsx
{
  version && (
    <div
      style={{
        marginTop: "auto",
        padding: "12px 16px",
        fontSize: 11,
        color: "var(--muted-foreground)",
        borderTop: "1px solid var(--border)",
      }}
    >
      v{version}
    </div>
  );
}
```

**Add backend test** in `tests/http/test_config_api.py`:

```python
def test_health_includes_version() -> None:
    import kanbanmate
    import kanbanmate.http.config_api as api_mod
    from fastapi.testclient import TestClient
    api_mod.app.state.auth = None
    with TestClient(api_mod.app) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == kanbanmate.__version__
    assert data["version"]  # not empty
```

Run:

```bash
pytest tests/http/test_config_api.py::test_health_includes_version -v
```

Expected: PASS.

Verify frontend build + version in bundle:

```bash
npm --prefix web run build 2>&1 | tail -3
```

---

## Definition of Done

- [ ] `pytest tests/http/test_config_api.py::test_health_includes_version -v` → PASS.
- [ ] `make check` → zero lint/mypy errors, all tests green.
- [ ] `npm --prefix web run build` → exit 0.
- [ ] `web/src/lib/collapse.js` exists with `setCollapseState`, `getCollapseState`,
      `resolveCollapsed`.
- [ ] `BoardPanel.jsx` uses `resolveCollapsed` and persists explicit collapse choices.
- [ ] `MonitoringPanel.jsx` renders markdown timeline and collapsible status groups.
- [ ] `AppShell.jsx` / `SidebarNav.jsx` render `v{version}` in the sidebar footer (desktop +
      mobile drawer).
