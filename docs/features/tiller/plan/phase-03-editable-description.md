# Phase 3 — Editable description (marker-safe)

## Gate

**Phase 1 must be COMPLETE (or sub-phase 3.1 can run independently as it is pure core).**

Required artifacts from Phase 1:

- `src/kanbanmate/http/monitor_routes.py` has the side-effect import of `agent_terminal`.
- `make check` green on the Phase 1 commit.

Sub-phase 3.1 (`core/body_regions.py`) has **no dependency on any prior phase** — it is pure and
can be committed on an empty branch. Sub-phases 3.2–3.4 require the existing monitoring endpoints
(present since helm PR2, not tiller-specific).

## Overview

Add `core/body_regions.py` (pure split/merge helpers), a `PATCH /api/monitor/ticket/{number}/body`
endpoint that applies the marker-safe merge, remove/redirect the raw `_execute_ticket_edit` intent
path, and add an Edit mode to the MonitoringPanel ticket detail using RichPromptEditor. Four
commits — one per sub-phase.

---

## Sub-phase 3.1 — core/body_regions.py (pure)

**Commit:** `feat(tiller): add core/body_regions — split/merge body with protected regions`

**Files touched:**

- Create: `src/kanbanmate/core/body_regions.py`
- Create: `tests/core/test_body_regions.py`

**What to implement in `src/kanbanmate/core/body_regions.py`:**

```python
"""Pure body-region split/merge for marker-safe ticket description edits (tiller §6.1).

Reuses the delimiters and regexes from :mod:`kanbanmate.core.body_edit` (STATUS_BEGIN/END,
_MARKER_LINE, PRESERVED_MARKERS) to parse an issue body into disjoint protected regions +
operator-editable freeform prose. The merge re-assembles them so protected content is
NEVER altered by an operator edit — only the freeform prose changes.

Pure functional core — imports only :mod:`re` and :mod:`dataclasses`; no I/O (DESIGN §3.2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from kanbanmate.core.body_edit import (
    PRESERVED_MARKERS,
    STATUS_BEGIN,
    STATUS_END,
    _MARKER_LINE,
    _STATUS_BLOCK,
)

# Heading that marks the start of the brainstorm section (appended by the brainstorm agent).
_BRAINSTORM_HEADING = "## Brainstorm"
# Match the brainstorm section: the heading + everything after it (greedy to end of string).
_BRAINSTORM_SECTION = re.compile(
    r"^## Brainstorm\b.*",
    re.MULTILINE | re.DOTALL,
)


@dataclass
class BodyRegions:
    """The decomposed regions of an issue body.

    Attributes:
        status_block: The full ``<!-- kanban:status:begin -->…end -->`` block, or ``None``.
        markers: Mapping of marker key → full ``**key**: value`` line for each PRESERVED_MARKERS key
            found in the body.
        brainstorm: The ``## Brainstorm`` section (heading + body), or ``None`` when absent.
        freeform: The operator-editable prose (everything not in the above regions).
    """

    status_block: str | None = None
    markers: dict[str, str] = field(default_factory=dict)
    brainstorm: str | None = None
    freeform: str = ""


def split_body_regions(body: str) -> BodyRegions:
    """Split *body* into protected regions + freeform prose.

    Protected regions (extracted verbatim, in order of priority):
    1. The status block (``STATUS_BEGIN``…``STATUS_END``).
    2. Each ``**key**: value`` marker line for keys in ``PRESERVED_MARKERS``.
    3. The ``## Brainstorm`` section (heading + all text after it).

    Everything else is ``freeform`` — the prose the operator may freely edit.

    The split is ORDER-PRESERVING and DISJOINT: no byte appears in more than one
    region, so ``merge_body_regions(split_body_regions(body), new_freeform=…)``
    never double-counts or drops content.

    Args:
        body: The raw GitHub issue body string.

    Returns:
        A :class:`BodyRegions` with the parsed regions.
    """
    regions = BodyRegions()
    work = body

    # 1. Extract status block (HTML comment delimiters — invisible in rendered body).
    m = _STATUS_BLOCK.search(work)
    if m:
        regions.status_block = m.group(0)
        work = work[: m.start()] + work[m.end() :]

    # 2. Extract brainstorm section (everything from ## Brainstorm to end-of-string).
    m = _BRAINSTORM_SECTION.search(work)
    if m:
        regions.brainstorm = m.group(0).rstrip()
        work = work[: m.start()].rstrip()

    # 3. Extract preserved marker lines one by one (in place).
    for key in PRESERVED_MARKERS:
        # Build a per-key pattern anchored at line start.
        pat = re.compile(rf"^\*\*{re.escape(key)}\*\*:[^\n]*$", re.MULTILINE)
        mm = pat.search(work)
        if mm:
            regions.markers[key] = mm.group(0)
            # Remove the matched line plus any surrounding blank lines it created.
            start = mm.start()
            end = mm.end()
            work = (work[:start].rstrip("\n") + "\n" + work[end:].lstrip("\n")).strip("\n")

    # 4. What remains is freeform prose.
    regions.freeform = work.strip()
    return regions


def merge_body_regions(regions: BodyRegions, *, new_freeform: str) -> str:
    """Re-assemble *regions* with *new_freeform* replacing the previous freeform prose.

    Assembly order (matches the canonical body layout):
    1. Status block at the very top (always-visible header).
    2. New freeform prose (the operator's edit).
    3. Preserved marker lines (one per line, blank-line separated block).
    4. Brainstorm section.

    *new_freeform* is de-fanged: any literal ``STATUS_BEGIN``/``STATUS_END`` delimiter is
    stripped so an operator cannot embed a fake status block that confuses the region parser
    on the next read.

    Args:
        regions: The :class:`BodyRegions` from :func:`split_body_regions`.
        new_freeform: The operator's edited prose (replaces ``regions.freeform``).

    Returns:
        The reassembled issue body string.
    """
    # De-fang: strip delimiter literals from the operator-supplied freeform.
    safe_freeform = new_freeform.replace(STATUS_BEGIN, "").replace(STATUS_END, "").strip()

    parts: list[str] = []
    if regions.status_block:
        parts.append(regions.status_block)
    if safe_freeform:
        parts.append(safe_freeform)
    if regions.markers:
        parts.append("\n".join(regions.markers[k] for k in PRESERVED_MARKERS
                               if k in regions.markers))
    if regions.brainstorm:
        parts.append(regions.brainstorm)

    return "\n\n".join(p for p in parts if p)
```

**Tests** (`tests/core/test_body_regions.py`):

```python
"""Adversarial tests for core/body_regions — split/merge round-trips and region safety.

Style mirrors tests/core/test_body_edit.py: class-per-concern, adversarial cases.
"""
from __future__ import annotations

from kanbanmate.core.body_edit import STATUS_BEGIN, STATUS_END
from kanbanmate.core.body_regions import BodyRegions, merge_body_regions, split_body_regions


_STATUS_BLOCK = f"{STATUS_BEGIN}\n**KanbanMate status** — Design · running\n{STATUS_END}"
_MARKERS = "**roadmap**: A1\n**codename**: tiller\n**design**: docs/features/tiller/DESIGN.md"
_BRAINSTORM = "## Brainstorm\n\nNeeds interactive terminal."
_FREEFORM = "Operator description of the feature.\n\nWith paragraphs."


def _full_body() -> str:
    return f"{_STATUS_BLOCK}\n\n{_FREEFORM}\n\n{_MARKERS}\n\n{_BRAINSTORM}"


class TestSplitRoundTrip:
    """merge(split(body), freeform=split(body).freeform) == body (up to whitespace)."""

    def test_round_trip_full_body(self) -> None:
        body = _full_body()
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform=regions.freeform)
        # All key content must survive (exact whitespace may differ by reassembly).
        assert "**KanbanMate status**" in merged
        assert "**roadmap**: A1" in merged
        assert "**codename**: tiller" in merged
        assert "## Brainstorm" in merged
        assert _FREEFORM.strip() in merged

    def test_round_trip_empty_body(self) -> None:
        regions = split_body_regions("")
        merged = merge_body_regions(regions, new_freeform="")
        assert merged == ""

    def test_round_trip_markers_only(self) -> None:
        body = "**roadmap**: B2\n**codename**: test"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform=regions.freeform)
        assert "**roadmap**: B2" in merged
        assert "**codename**: test" in merged


class TestDisjointness:
    """Editing freeform must not alter protected regions."""

    def test_marker_preserved_when_freeform_changed(self) -> None:
        body = f"{_FREEFORM}\n\n{_MARKERS}"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform="Completely new description.")
        assert "**roadmap**: A1" in merged
        assert "**codename**: tiller" in merged
        assert "Completely new description." in merged
        assert _FREEFORM not in merged  # old freeform replaced

    def test_status_block_preserved_when_freeform_changed(self) -> None:
        body = f"{_STATUS_BLOCK}\n\n{_FREEFORM}"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform="New prose.")
        assert STATUS_BEGIN in merged
        assert STATUS_END in merged
        assert "New prose." in merged

    def test_brainstorm_preserved_when_freeform_changed(self) -> None:
        body = f"{_FREEFORM}\n\n{_BRAINSTORM}"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform="Replaced.")
        assert "## Brainstorm" in merged
        assert "Needs interactive terminal." in merged


class TestDefang:
    """STATUS_BEGIN/END literals in freeform are stripped before merge."""

    def test_defang_status_begin_in_freeform(self) -> None:
        evil_freeform = f"Legit prose {STATUS_BEGIN} injected"
        regions = BodyRegions(freeform=evil_freeform)
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        # The literal delimiter must not appear inside freeform prose.
        assert merged.count(STATUS_BEGIN) == 0

    def test_defang_status_end_in_freeform(self) -> None:
        evil_freeform = f"Legit prose {STATUS_END} injected"
        regions = BodyRegions(freeform=evil_freeform)
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        assert merged.count(STATUS_END) == 0


class TestMissingSections:
    """Absent sections produce no gaps or errors."""

    def test_no_status_block(self) -> None:
        body = f"{_FREEFORM}\n\n**roadmap**: X"
        regions = split_body_regions(body)
        assert regions.status_block is None
        merged = merge_body_regions(regions, new_freeform="Updated.")
        assert STATUS_BEGIN not in merged

    def test_no_brainstorm(self) -> None:
        body = f"{_FREEFORM}\n\n**roadmap**: X"
        regions = split_body_regions(body)
        assert regions.brainstorm is None

    def test_no_markers(self) -> None:
        body = _FREEFORM
        regions = split_body_regions(body)
        assert regions.markers == {}
        merged = merge_body_regions(regions, new_freeform="OK")
        assert "**" not in merged
```

Run: `pytest tests/core/test_body_regions.py -v` → ≥ 11 PASS, 0 FAIL.

---

## Sub-phase 3.2 — PATCH /api/monitor/ticket/{number}/body

**Commit:** `feat(tiller): add PATCH /api/monitor/ticket/{number}/body endpoint`

**Files touched:**

- Modify: `src/kanbanmate/http/monitor_routes.py` — add the PATCH route.
- Modify: `tests/http/test_monitor_api.py` — add body-patch tests.

**What to add to `monitor_routes.py`** (after the existing ticket-detail GET, before the
side-effect import at the bottom):

```python
from pydantic import BaseModel  # already imported transitively via FastAPI; add if missing

class _BodyPatchRequest(BaseModel):
    freeform: str

@app.patch("/api/monitor/ticket/{number}/body")
def patch_ticket_body(number: int, req: _BodyPatchRequest, project: str | None = None) -> JSONResponse:
    """Marker-safe rewrite of a ticket's issue body (tiller §6.2).

    Fetches the current body, splits into protected regions + freeform, merges
    with the operator's new freeform, validates coherence, and patches GitHub.
    Protected regions (status block, markers, brainstorm) are NEVER altered.

    Args:
        number: The GitHub issue number.
        req: ``{"freeform": "<edited prose>"}`` — 1 MiB cap enforced by FastAPI.
        project: The Project v2 node id selector (optional; auto-resolved for N=1).

    Returns:
        ``{"ok": true}`` on success.

    Raises:
        HTTPException: 400 on roadmap/title incoherence; 404 issue not found; 502 GitHub error.
    """
    from kanbanmate.core.body_edit import validate_roadmap_matches_title  # noqa: PLC0415
    from kanbanmate.core.body_regions import merge_body_regions, split_body_regions  # noqa: PLC0415

    entry = _resolve_entry(project)
    gh = _monitor_github(entry)

    try:
        issue_ref = gh.fetch_issue(number)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Issue #{number} not found: {exc}") from exc

    current_body = issue_ref.body or ""
    title = issue_ref.title or ""

    regions = split_body_regions(current_body)
    merged = merge_body_regions(regions, new_freeform=req.freeform)

    coherence_error = validate_roadmap_matches_title(merged, title)
    if coherence_error:
        raise HTTPException(status_code=400, detail=coherence_error)

    try:
        gh.update_issue_body(issue_ref.node_id, merged)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub update failed: {exc}") from exc

    return JSONResponse(content={"ok": True})
```

**Add to `tests/http/test_monitor_api.py`:**

```python
class _FakeIssueRef:
    def __init__(self, body, title="[A1] My ticket", node_id="NODE_1"):
        self.body = body
        self.title = title
        self.node_id = node_id

class _FakeGithub:
    def __init__(self, body="**roadmap**: A1\n\nSome freeform.", title="[A1] My ticket"):
        self._ref = _FakeIssueRef(body=body, title=title)
        self.updated_body = None
    def fetch_issue(self, number):
        return self._ref
    def update_issue_body(self, node_id, body):
        self.updated_body = body


def test_body_patch_happy_path(tmp_path) -> None:
    import kanbanmate.http.config_api as api_mod
    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    gh = _FakeGithub()
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"freeform": "Updated operator description."},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert gh.updated_body is not None
    assert "Updated operator description." in gh.updated_body
    assert "**roadmap**: A1" in gh.updated_body  # marker preserved


def test_body_patch_400_on_roadmap_title_incoherence(tmp_path) -> None:
    import kanbanmate.http.config_api as api_mod
    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    # Body has roadmap B2 but title has [A1] — incoherent
    gh = _FakeGithub(body="**roadmap**: B2\n\nDesc.", title="[A1] My ticket")
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"freeform": "New prose."},
        )
    assert resp.status_code == 400
    assert "roadmap" in resp.json()["detail"]


def test_body_patch_422_bad_shape(tmp_path) -> None:
    import kanbanmate.http.config_api as api_mod
    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    api_mod.app.state.monitor_github = _FakeGithub()
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"wrong_field": "oops"},
        )
    assert resp.status_code == 422


def test_body_patch_preserves_status_block(tmp_path) -> None:
    from kanbanmate.core.body_edit import STATUS_BEGIN, STATUS_END
    import kanbanmate.http.config_api as api_mod
    api_mod.app.state.kanban_root = _single_project_root(tmp_path)
    api_mod.app.state.auth = None
    status = f"{STATUS_BEGIN}\n**KanbanMate status** — Design · running\n{STATUS_END}"
    gh = _FakeGithub(body=f"{status}\n\n**roadmap**: A1\n\nOld prose.", title="[A1] T")
    api_mod.app.state.monitor_github = gh
    with TestClient(api_mod.app) as client:
        resp = client.patch(
            "/api/monitor/ticket/1/body?project=PVT_x",
            json={"freeform": "New prose."},
        )
    assert resp.status_code == 200
    assert STATUS_BEGIN in gh.updated_body
    assert STATUS_END in gh.updated_body
    assert "**roadmap**: A1" in gh.updated_body
```

Run: `pytest tests/http/test_monitor_api.py -v` → all existing tests PASS + 4 new PASS.

---

## Sub-phase 3.3 — Remove/secure raw intents ticket-edit path

**Commit:** `refactor(tiller): route ticket_edit intent through marker-safe body_regions merge`

**Files touched:**

- Modify: `src/kanbanmate/app/intents.py` — update `_execute_ticket_edit` to use
  `split_body_regions` / `merge_body_regions` instead of replacing the full body verbatim.
- Modify: `tests/app/test_intents.py` (if existing ticket_edit tests need updating).

**What to change in `_execute_ticket_edit`** (around line 421 in `intents.py`):

Replace the raw `seeder.update_issue_body(node_id, body)` with a marker-safe merge:

```python
    # Fetch the current body so we can apply a marker-safe merge (tiller §6.2 D4).
    try:
        issue_ref = seeder.fetch_issue(intent.issue)
        current_body = issue_ref.body or ""
    except Exception:
        current_body = ""  # fail-soft: if we can't fetch, treat as empty (first write)

    from kanbanmate.core.body_regions import merge_body_regions, split_body_regions  # noqa: PLC0415
    regions = split_body_regions(current_body)
    merged = merge_body_regions(regions, new_freeform=body)

    seeder.update_issue_body(node_id, merged)
```

This preserves markers and the status block even when the intent caller supplies only freeform
prose. The intent's `args["body"]` is now treated as the new freeform, not a full replacement.

Run existing intent tests:

```bash
pytest tests/app/test_intents.py -v
```

Expected: all previously-passing tests still PASS (the merge is a no-op when the body has no
protected regions, so existing tests with plain bodies are unaffected).

---

## Sub-phase 3.4 — RichPromptEditor edit mode in MonitoringPanel

**Commit:** `feat(tiller): ticket description edit mode in MonitoringPanel (marker-safe)`

**Files touched:**

- Modify: `web/src/panels/MonitoringPanel.jsx`
- Modify: `web/src/api.js` — add `patchTicketBody` helper.

**Add to `web/src/api.js`** (after `monitorTicket`):

```js
export const patchTicketBody = (number, freeform, project) =>
  call(
    "PATCH",
    `/api/monitor/ticket/${encodeURIComponent(number)}/body${q(project)}`,
    { freeform },
  );
```

**Add to `MonitoringPanel.jsx`** (imports):

```jsx
import RichPromptEditor from "../components/RichPromptEditor.jsx";
```

**Add state + logic inside `MonitoringPanel`:**

```jsx
const [editMode, setEditMode] = React.useState(false);
const [editFreeform, setEditFreeform] = React.useState("");
const [saving, setSaving] = React.useState(false);

// Extract freeform from body client-side: strip STATUS block and marker lines.
function extractFreeform(body) {
  if (!body) return "";
  const STATUS_BEGIN = "<!-- kanban:status:begin -->";
  const STATUS_END = "<!-- kanban:status:end -->";
  let text = body;
  // Remove status block
  const sbStart = text.indexOf(STATUS_BEGIN);
  const sbEnd = text.indexOf(STATUS_END);
  if (sbStart !== -1 && sbEnd !== -1) {
    text = text.slice(0, sbStart) + text.slice(sbEnd + STATUS_END.length);
  }
  // Remove **key**: value marker lines
  text = text.replace(/^\*\*\w+\*\*:[^\n]*$/gm, "");
  // Remove ## Brainstorm section
  const bsIdx = text.indexOf("## Brainstorm");
  if (bsIdx !== -1) text = text.slice(0, bsIdx);
  return text.trim();
}

const openEdit = () => {
  setEditFreeform(extractFreeform(detail?.body || ""));
  setEditMode(true);
};

const saveEdit = async () => {
  setSaving(true);
  try {
    await api.patchTicketBody(sel, editFreeform, project);
    setEditMode(false);
    // Refresh detail
    const d = await api.monitorTicket(sel, project);
    setDetail(d);
  } catch (e) {
    setError(e.message);
  } finally {
    setSaving(false);
  }
};
```

**Render in ticket detail section** (after the title/status block, before the timeline):

```jsx
{
  detail && (
    <div>
      {!editMode ? (
        <Button size="sm" variant="outline" onClick={openEdit}>
          {t("body.edit", "Éditer la description")}
        </Button>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <RichPromptEditor
            value={editFreeform}
            onChange={setEditFreeform}
            placeholders={[]}
          />
          <div style={{ display: "flex", gap: 6 }}>
            <Button onClick={saveEdit} disabled={saving}>
              {saving ? "…" : t("body.save", "Enregistrer")}
            </Button>
            <Button variant="outline" onClick={() => setEditMode(false)}>
              {t("body.cancel", "Annuler")}
            </Button>
          </div>
          <details style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
            <summary>
              {t("body.protected_regions", "Régions protégées")}
            </summary>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>
              {detail?.body?.replace(extractFreeform(detail.body), "…") || ""}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
```

Add i18n keys to EN/FR locale files:

```json
"body": {
  "edit": "Edit description",
  "save": "Save",
  "cancel": "Cancel",
  "protected_regions": "Protected regions"
}
```

```json
"body": {
  "edit": "Éditer la description",
  "save": "Enregistrer",
  "cancel": "Annuler",
  "protected_regions": "Régions protégées"
}
```

Verify build:

```bash
npm --prefix web run build 2>&1 | tail -5
```

Expected: exit 0.

---

## Definition of Done

- [ ] `pytest tests/core/test_body_regions.py -v` → ≥ 11 PASS, 0 FAIL.
- [ ] `pytest tests/http/test_monitor_api.py -v` → all tests PASS (including 4 new body-patch tests).
- [ ] `pytest tests/app/test_intents.py -v` → all previously-passing tests still PASS.
- [ ] `npm --prefix web run build` → exit 0.
- [ ] `make check` → zero lint/mypy errors, all tests green.
- [ ] `python -c "from kanbanmate.core.body_regions import split_body_regions, merge_body_regions"` → exit 0.
