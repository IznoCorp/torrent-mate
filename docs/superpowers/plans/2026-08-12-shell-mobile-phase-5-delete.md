# Shell Mobile — Phase 5: Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator remove a medium they no longer want — files, metadata, library rows, Plex entry — showing first, always, exactly what would go.

**Architecture:** One endpoint with two modes. `dry_run=true` computes and returns the full inventory of what deletion would touch, and changes nothing. `dry_run=false` performs it and writes a destructive-journal entry. **The dry run stays mandatory until the operator validates that it tells the truth**; removing that requirement later is an explicit act, not a cleanup. Three entry points reach it — the media sheet, a swipe in the list, and selection mode in the grid — and all three go through the same confirmation.

**Tech Stack:** FastAPI + Pydantic, SQLite, the Plex API client, React 19, vitest, pytest, the phase-0 parity guards.

## Global Constraints

- **The prototype is the source.** `frontend/maquette/refonte.html` is the design reference (§15 of `docs/reference/product-intent.md`).
- **CSS is extracted, never retyped.** Run `python scripts/extract-maquette-css.py`.
- **Dry-run first, and it is mandatory.** The endpoint refuses `dry_run=false` unless the caller passes the inventory token returned by the dry run: a real deletion must be preceded by a shown inventory, in the same session, for the same media.
- **Destruction is confirmed, never reversible by accident.** No mutation happens before confirmation, and the confirmation names what will go.
- **The deletion asks what it means for the follow** — stop it, or keep it, because the operator may be deleting to re-acquire a better version. No permanent exclusion list.
- **Every mutating endpoint is staging-guarded** (`require_not_staging`) and typed. Run `make openapi`, commit the regenerated files.
- **Write/destructive maintenance actions hold `pipeline.lock` for their runner's whole lifetime.**
- **Never fabricate a medium to prove a deletion.** A real deletion is validated on a medium the operator names, after a genuine `sqlite3 .backup` of `library.db` — a file copy of a WAL database is not a backup.
- **Probe emulation:** 390 × 844, DPR 2, `isMobile`, `hasTouch`. Never bind a local server to 8710 or 8711.
- **Search safety:** every `rg` carries `--type` or `-g`. **Network safety:** every `curl` carries `--connect-timeout 10 --max-time 30`.
- **Gates:** `make lint`, `make test`, `make check-frontend`.
- **Comments in English**, no session/phase/date references. Interface copy stays French.
- **Commits:** Conventional Commits, scope `(shell-mobile)`. No AI attribution. **Version bump on every PR.**

---

## File Structure

| File                                                   | Responsibility                                                                                              |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `personalscraper/maintenance/deletion.py`              | **Create.** The inventory computation and the deletion itself. Pure enough to test without touching a disk. |
| `personalscraper/web/models/deletion.py`               | **Create.** `DeletionInventory`, `DeletionRequest`, `DeletionResult`.                                       |
| `personalscraper/web/routes/maintenance.py`            | **Modify.** `POST /api/maintenance/media/{id}/delete`.                                                      |
| `tests/maintenance/test_deletion_inventory.py`         | **Create.** Inventory tests against a temporary tree.                                                       |
| `tests/web/test_delete_route.py`                       | **Create.** Route tests: dry-run mandatory, staging guard, journal entry.                                   |
| `frontend/src/components/mediatheque/DeleteDialog.tsx` | **Create.** The confirmation, showing the inventory.                                                        |
| `frontend/src/components/mediatheque/SelectionBar.tsx` | **Create.** The grid's selection mode.                                                                      |

**Read before starting:** §5.3 of the spec, `docs/reference/maintenance.md` (the destructive journal and the pipeline lock), and the prototype states `lib-suppression`, `lib-suppression-multiple`, `lib-selection`.

---

### Task 1: The inventory — what would go

**Files:**

- Create: `personalscraper/maintenance/deletion.py`
- Create: `tests/maintenance/test_deletion_inventory.py`

**Interfaces:**

- Produces: `inventory(media_id: int, *, db, root: Path) -> DeletionInventory` with `files: list[Path]`, `bytes: int`, `library_rows: dict[str, int]`, `plex_entry: str | None`, `follow: FollowLink | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/maintenance/test_deletion_inventory.py`:

```python
"""What a deletion would touch, computed before anything is touched.

The inventory is the whole guarantee of this feature: an operator who has seen
what will go can decide; one who has not is gambling.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_the_inventory_lists_every_file(tmp_path: Path, seeded_media) -> None:
    """Every file under the media directory is listed, not merely counted."""
    result = inventory(seeded_media.id, db=seeded_media.db, root=tmp_path)
    assert len(result.files) == 4
    assert all(isinstance(p, Path) for p in result.files)


def test_the_inventory_touches_nothing(tmp_path: Path, seeded_media) -> None:
    """Computing what would go must not make any of it go."""
    before = sorted(p.name for p in tmp_path.rglob("*"))
    inventory(seeded_media.id, db=seeded_media.db, root=tmp_path)
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_the_inventory_names_the_library_rows(tmp_path: Path, seeded_media) -> None:
    """Rows are named by table, so the operator sees the scope and not a number."""
    result = inventory(seeded_media.id, db=seeded_media.db, root=tmp_path)
    assert result.library_rows["media_file"] == 4
    assert result.library_rows["media_item"] == 1


def test_a_media_absent_from_disk_is_reported_not_assumed(tmp_path: Path, ghost_media) -> None:
    """A row whose files are gone is a real case: say so rather than report zero.

    Reporting « 0 files » reads as « nothing to delete », and the operator then
    cannot tell a clean media from a broken index.
    """
    result = inventory(ghost_media.id, db=ghost_media.db, root=tmp_path)
    assert result.files == []
    assert result.warnings and "introuvable" in result.warnings[0]


def test_the_follow_link_is_reported_when_one_exists(tmp_path: Path, followed_media) -> None:
    """Deleting may mean re-acquiring: the follow's fate is the operator's call."""
    result = inventory(followed_media.id, db=followed_media.db, root=tmp_path)
    assert result.follow is not None
    assert result.follow.title == followed_media.title
```

- [ ] **Step 2: Run it to verify it fails, then write the inventory**

Run: `pytest tests/maintenance/test_deletion_inventory.py -v` → FAIL.

Create `personalscraper/maintenance/deletion.py` with the inventory function and its dataclasses. It reads; it never writes.

Run again: PASS — 5 passed.

- [ ] **Step 3: Commit**

```bash
git add personalscraper/maintenance/deletion.py tests/maintenance/test_deletion_inventory.py
git commit -m "feat(shell-mobile): compute what a deletion would touch, before touching it

The inventory is the whole guarantee: an operator who has seen what will go can
decide; one who has not is gambling.

A media whose files are gone is reported as such rather than as « 0 files » —
zero reads as « nothing to delete », and that hides the difference between a
clean media and a broken index."
```

---

### Task 2: The endpoint, with the dry run made mandatory

**Files:**

- Create: `personalscraper/web/models/deletion.py`
- Modify: `personalscraper/web/routes/maintenance.py`
- Create: `tests/web/test_delete_route.py`

**Interfaces:**

- Produces: `POST /api/maintenance/media/{id}/delete` with body `{dry_run: bool, inventory_token: str | None, follow_action: "stop" | "keep" | null}` → `DeletionResult`.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_delete_route.py`:

```python
"""Deleting a medium: shown first, confirmed always, journalled once."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_a_dry_run_returns_the_inventory_and_changes_nothing(client, seeded_media) -> None:
    response = client.post(
        f"/api/maintenance/media/{seeded_media.id}/delete", json={"dry_run": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["inventory"]["files"]
    assert body["inventory_token"]
    assert seeded_media.path.exists()


def test_a_real_deletion_without_a_prior_dry_run_is_refused(client, seeded_media) -> None:
    """A real deletion must be preceded by a shown inventory, or it is a gamble."""
    response = client.post(
        f"/api/maintenance/media/{seeded_media.id}/delete",
        json={"dry_run": False, "inventory_token": None},
    )
    assert response.status_code == 400
    assert "dry" in response.json()["detail"].lower()
    assert seeded_media.path.exists()


def test_a_stale_token_is_refused(client, seeded_media) -> None:
    """A token for another media, or from another session, proves nothing."""
    response = client.post(
        f"/api/maintenance/media/{seeded_media.id}/delete",
        json={"dry_run": False, "inventory_token": "not-a-real-token"},
    )
    assert response.status_code == 400
    assert seeded_media.path.exists()


def test_the_route_is_staging_guarded(staging_client, seeded_media) -> None:
    response = staging_client.post(
        f"/api/maintenance/media/{seeded_media.id}/delete", json={"dry_run": True}
    )
    assert response.status_code == 403


def test_a_real_deletion_is_journalled(client, seeded_media) -> None:
    """A destruction with no trace is a destruction nobody can account for."""
    token = client.post(
        f"/api/maintenance/media/{seeded_media.id}/delete", json={"dry_run": True}
    ).json()["inventory_token"]
    client.post(
        f"/api/maintenance/media/{seeded_media.id}/delete",
        json={"dry_run": False, "inventory_token": token, "follow_action": "keep"},
    )
    log = client.get("/api/maintenance/destructive-log").json()
    assert any(entry["media_id"] == seeded_media.id for entry in log["entries"])


def test_the_follow_action_is_honoured(client, followed_media) -> None:
    """Deleting may mean re-acquiring: keeping the follow must actually keep it."""
    token = client.post(
        f"/api/maintenance/media/{followed_media.id}/delete", json={"dry_run": True}
    ).json()["inventory_token"]
    client.post(
        f"/api/maintenance/media/{followed_media.id}/delete",
        json={"dry_run": False, "inventory_token": token, "follow_action": "keep"},
    )
    follows = client.get("/api/acquisition/follows").json()
    assert any(f["title"] == followed_media.title for f in follows["items"])
```

- [ ] **Step 2: Run it to verify it fails, then write the route**

Run: `pytest tests/web/test_delete_route.py -v` → FAIL.

Write the models and the route. The route holds `pipeline.lock` for the whole deletion, writes the destructive-journal entry, and honours `follow_action`.

Run again: PASS — 6 passed.

- [ ] **Step 3: Regenerate the contract and run the backend gates**

Run: `make openapi && make lint && make test`
Expected: all pass. Commit the regenerated files.

- [ ] **Step 4: Commit**

```bash
git add personalscraper/web tests/web/test_delete_route.py openapi.json frontend/src/api/schema.d.ts
git commit -m "feat(shell-mobile): deleting a medium, shown first and journalled once

A real deletion is refused unless it carries the token of a dry run for the same
media: a deletion nobody was shown is a gamble, and the token is what makes
« shown first » a property of the endpoint rather than a habit of the interface.

The follow's fate is the operator's call, because deleting often means
re-acquiring a better version. The route holds the pipeline lock for its whole
lifetime and writes a destructive-journal entry: a destruction with no trace is
a destruction nobody can account for."
```

---

### Task 3: The confirmation, and the three ways in

**Files:**

- Create: `frontend/src/components/mediatheque/DeleteDialog.tsx` + test
- Create: `frontend/src/components/mediatheque/SelectionBar.tsx` + test
- Modify: `frontend/src/pages/MediathequePage.tsx`, `frontend/src/pages/MediaSheetPage.tsx`

**Interfaces:**

- Produces: `<DeleteDialog inventory={…} onConfirm={(followAction) => …} onCancel={fn} />`; `<SelectionBar count={n} onDelete={fn} onCancel={fn} />`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/mediatheque/DeleteDialog.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { DeleteDialog } from "./DeleteDialog";

const INVENTORY = {
  files: ["/disk/Silo/S01E01.mkv", "/disk/Silo/S01E02.mkv"],
  bytes: 8_000_000_000,
  library_rows: { media_item: 1, media_file: 2 },
  plex_entry: "Silo",
  follow: { id: 3, title: "Silo" },
  warnings: [],
} as never;

test("the dialog shows what would go before asking", () => {
  render(
    <DeleteDialog
      inventory={INVENTORY}
      onConfirm={() => {}}
      onCancel={() => {}}
    />,
  );
  expect(screen.getByText(/2 fichiers/i)).toBeInTheDocument();
  expect(screen.getByText(/8/)).toBeInTheDocument();
  expect(screen.getByText(/plex/i)).toBeInTheDocument();
});

test("nothing is deleted before confirmation", () => {
  const onConfirm = vi.fn();
  render(
    <DeleteDialog
      inventory={INVENTORY}
      onConfirm={onConfirm}
      onCancel={() => {}}
    />,
  );
  expect(onConfirm).not.toHaveBeenCalled();
});

test("the follow's fate is asked, not assumed", () => {
  // Deleting often means re-acquiring a better version: assuming the follow
  // should stop silently cancels the very reason for the deletion.
  const onConfirm = vi.fn();
  render(
    <DeleteDialog
      inventory={INVENTORY}
      onConfirm={onConfirm}
      onCancel={() => {}}
    />,
  );
  fireEvent.click(screen.getByRole("radio", { name: /garder le suivi/i }));
  fireEvent.click(screen.getByRole("button", { name: /supprimer/i }));
  expect(onConfirm).toHaveBeenCalledWith("keep");
});

test("a warning from the inventory is shown, not swallowed", () => {
  render(
    <DeleteDialog
      inventory={
        {
          ...INVENTORY,
          warnings: ["Dossier introuvable sur le disque."],
        } as never
      }
      onConfirm={() => {}}
      onCancel={() => {}}
    />,
  );
  expect(screen.getByText(/introuvable/i)).toBeInTheDocument();
});

test("cancel is reachable and is the calm option", () => {
  const onCancel = vi.fn();
  render(
    <DeleteDialog
      inventory={INVENTORY}
      onConfirm={() => {}}
      onCancel={onCancel}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /annuler/i }));
  expect(onCancel).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run it to verify it fails, then write the dialog**

Run: `cd frontend && npx vitest run src/components/mediatheque/DeleteDialog.test.tsx` → FAIL, then write it and re-run → PASS — 5 passed.

- [ ] **Step 3: Write the selection mode**

Create `SelectionBar.tsx`. **It replaces the tab bar** while a selection is active rather than stacking above it: stacked, it covered « Supprimer » and cost 57 px of height on a phone. « Annuler » is the mode's exit and is always present.

Selection must work in **both** layouts — grid and list. It once existed on tiles only, so « Sélectionner » switched on in list mode with nothing selectable, and a mode one can enter and do nothing in is worse than no mode.

- [ ] **Step 4: Wire the three entry points**

- the media sheet's « Supprimer de la médiathèque »,
- a swipe on a list row,
- selection mode in the grid, reached by long-press or by « Sélectionner ».

All three open the same dialog, after the same dry run. A simple tap still opens the sheet: the most frequent path is never sacrificed to a rare action.

- [ ] **Step 5: Run the frontend gates**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src && npx vitest run`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(shell-mobile): deleting is shown, asked, and reachable three ways

The dialog shows the inventory before asking, and asks what the deletion means
for the follow rather than assuming: deleting often means re-acquiring a better
version, and stopping the follow silently cancels the very reason for it.

The selection bar REPLACES the tab bar rather than stacking above it — stacked,
it covered « Supprimer » and cost 57 px on a phone. Selection works in both
layouts: it once existed on tiles only, so the mode could be entered in list view
with nothing selectable, which is worse than no mode."
```

---

### Task 4: Phase gate — and the one thing that cannot be validated before production

- [ ] **Step 1: Run every gate**

Run: `make lint && make test && make check-frontend && python scripts/parity-probe.py --app-url http://127.0.0.1:4173`
Expected: all pass.

- [ ] **Step 2: Exercise the dry run on staging, against the real library**

On staging, open a real medium and run the dry run. Check the inventory names the real files, the real byte count, the real Plex entry, and the follow if there is one.
**Stop there.** Staging writes to the real disks and the real databases: a real deletion from staging is a real deletion.

- [ ] **Step 3: Record the protocol for the first real deletion**

Add to `IMPLEMENTATION.md`:

```markdown
## The first real deletion — protocol

Not validatable before production, and named rather than hidden.

1. The operator names the medium.
2. `sqlite3 .data/library.db ".backup /tmp/library-before-delete.db"` — a file
   copy of a WAL database is not a backup.
3. Dry run first; the inventory is read aloud and confirmed.
4. Real deletion, with the token from that dry run.
5. The destructive-journal entry is the evidence; check it names the same files.

Fabricating a medium to prove the path is forbidden: a proof on a media nobody
owns proves nothing about the media the operator owns.
```

- [ ] **Step 4: Update the tracker, bump the version, commit**

```bash
git add IMPLEMENTATION.md pyproject.toml
git commit -m "chore(shell-mobile): phase 5 gate — deleting is possible, and shown first

The dry run is validated on staging against the real library. The first REAL
deletion happens after the production merge, on a medium the operator names,
after a genuine sqlite3 .backup — and the protocol is written down rather than
improvised on the day."
```

---

## Self-Review

**1. Spec coverage.** B8 (the deletion asks what it means for the follow) → Task 2's last test and Task 3's third. B9 (dry run mandatory until validated) → Task 2's second and third tests, which make it a property of the endpoint rather than a habit of the interface. B10 (reachable from the poster grid without degrading it) → Task 3 Steps 3 and 4. §5.3's inventory → Task 1. Open item 1 (Plex deletion route unverified) → Task 1's inventory reports the Plex entry; whether the removal call exists is verified in Task 2 and is the one thing this plan cannot assert in advance. Open item 2 (real deletion not validatable before production) → Task 4 Step 3.

**2. Placeholder scan.** No TBD. Task 3 Steps 3 and 4 describe composition and wiring; the rules those steps must respect are stated exactly, and the components' props are fixed above.

**3. Type consistency.** `DeletionInventory` (`files`, `bytes`, `library_rows`, `plex_entry`, `follow`, `warnings`) is defined in Task 1 and consumed by `DeleteDialog` in Task 3 with those exact keys. `follow_action` takes `"stop" | "keep"` in both the route body and `onConfirm`.

**One risk named, and it is the largest in the mission:** `api/plex.py` only refreshes. Whether a route exists on this Plex server to remove an entry is unknown until Task 2 verifies it. If none does, the inventory must say that the Plex entry will **survive** the deletion rather than silently omitting it — a dialog that lists what will go must not quietly leave out what will stay.
