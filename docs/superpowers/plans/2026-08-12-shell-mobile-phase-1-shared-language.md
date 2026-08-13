# Shell Mobile — Phase 1: The Shared Language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every future page one vocabulary — one scope class, one set of primitives, one header rule — so that phases 2 to 6 build on shared parts instead of each inventing their own.

**Architecture:** The previous rebuild left a hand-mirrored stylesheet scoped `.mq` and a `PageHeader` that eats a phone's first screenful. This phase renames the scope to `.tm`, supersedes the mirrored stylesheet with the generated one from phase 0, extracts the primitives the prototype proved necessary into `components/ds/`, and takes `PageHeader` off mobile. **Not one shipped pixel may move**: the phase-0 probe reports zero before and after, which is the whole gate.

**Tech Stack:** React 19, TypeScript, Vite 7, vitest + Testing Library, the phase-0 guards (`extract-maquette-css.py`, `check-maquette-classes.py`, `parity-probe.py`).

## Already delivered ahead of this plan

Part of §4.2 landed before phase 0, because the duplication audit that motivated it was already
done (`docs/analysis/2026-08-12-app-component-duplication-audit.md`). Do **not** re-create these;
check them and move on:

| Primitive        | State                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------- |
| `ds/Chip`        | **exists.** Moved out of `acquisition/`, unchanged. Do not rewrite it from the plan below. |
| `ds/Panel`       | **exists.** The bordered surface; `Panel.test.tsx` fails naming any file that writes the string by hand. |
| `ds/MediaRow`    | **exists.** The former `AcquisitionCard`, with `facts: MediaFact[]` in place of `meta: ReactNode`, `journey` in place of `strip`, `action` in place of `footer`. |
| `ds/MediaTile`   | **exists.** The former `ds/MediaCard`, renamed for what it draws.                       |
| `ds/EmptyState`  | **exists since `41f6bec2`** and is now adopted on nine surfaces. The work left is adoption, never creation. |
| `ds/ErrorState`  | **exists**, adopted in 19 files. Nothing to do.                                          |

What this plan still owes: `ViewTabs`, `FilterBar`, `SectionHeader`, `SheetShell`,
`PullToRefresh`, the `.tm` scope rename, and `PageHeader` off mobile.

**`PullToRefresh` carries a trap the maquette has already paid for.** Inside a scrollport the
compositor claims the vertical pan and fires `pointercancel`, so a pointer-only implementation
passes every synthetic test and does nothing under a thumb. Port the prototype's split — the
finger from touch events, everything else from pointer events — and port `harness/doigt.py` with
it. Do not re-derive it.

**`SheetShell` is not a shell.** The prototype's panel takes a descriptor of facts plus ordered
blocks of declared kinds (`note`, `faits`, `actions`, `saisons`); a component that accepts
children is the envelope this mission removed. Port `panneauHTML`, and `harness/panneau.py`
with it.

## Global Constraints

- **The prototype is the source.** `frontend/maquette/refonte.html` is the design reference (§15 of `docs/reference/product-intent.md`). A design change starts there; the code follows. A divergence between the app and the prototype is a defect **in the app**.
- **CSS is extracted, never retyped.** Editing `frontend/src/styles/ps/app-surface.css` by hand is the defect. Re-run `python scripts/extract-maquette-css.py`.
- **Scope class is `.tm`.**
- **Nothing visible changes in this phase.** Every task ends with `python scripts/parity-probe.py --only shell/` at zero, and with the Acquisition page rendering identically.
- **Probe emulation is fixed:** 390 × 844, DPR 2, `isMobile`, `hasTouch`.
- **Never bind a local server to 8710 or 8711.**
- **Search safety:** every `rg` carries `--type` or `-g`.
- **Frontend gates on every commit:** `npx tsc -b --noEmit` (never `tsc --noEmit`, which checks nothing in `frontend/`), `npx eslint src`, `npx vitest run`, `make check-frontend`.
- **Comments in English**, with no reference to a session, a phase number, or a dated decision.
- **Commits:** Conventional Commits, scope `(shell-mobile)`. No AI attribution.
- **Version bump on every PR.**
- **One card, one behaviour, and one panel per medium (R31, R41–R45).** In every list:
  the **poster** opens the media sheet; the **card body** opens the bottom panel; a **gallery
  tile**, being all poster, answers a **long press** for the panel. The **panel carries every
  action** available for that medium, and an inline action on a card is a shortcut to
  something the panel also offers — never the only way in. The panel is **derived** from what
  is true about the medium (followed, incomplete, in the library, to grab, blocked, has a
  sheet), never passed in by the calling screen: that is what makes the panel reached from a
  gallery identical to the one reached from a card. An element states **which** panel it
  addresses (`data-panel="media:<title>"`) and never how to build it; addressing it by list
  index is forbidden. `frontend/maquette/harness/cartes.py` is the executable form of this
  contract — port it, do not re-derive it.
- **One builder per SHAPE, not per screen.** `cardHTML` serves every list, `tileHTML`
  every gallery; a release candidate has its own builder because it is not a medium
  (no sheet, no panel — marked `data-nonmedia`, R46), and the selection row is a mode
  of the list rather than a variant of the card. The card takes a **descriptor of
  facts** — title, kind, sub-line, reason, fraction, chip, caption, fresh, strip. A
  view wanting something outside that list is naming a fact the card does not know
  yet: add the fact, never pass ready-made markup. Props that name an appearance
  (`dense`, `compact`, `showChip`) are the failure mode this avoids.
- **Galleries answer their CONTAINER (R50).** One tile builder for every gallery, one set of
  metrics, and a column ladder driven by a container query on the scrollport — 3 / 4 / 5 / 6
  at 460 / 620 / 820px. A media query reads the viewport and would give a 390px frame the
  column count of the desktop behind it.
- **Same metrics in every list (R47), and a reason that never truncates (R48).** Poster
  38 × 57, padding 9, radius 8, title 13.5, gap 10 — everywhere. Card heights differ only
  because their content does. A surface wanting a bigger picture uses the gallery or deck
  format, which exist for that. Rich text reaches a card as SEGMENTS (plain text plus what
  is emphasised, at its position), never as ready-made markup — see `richText`.


- **Work on `feat/shell-mobile`, never on `main`.** Every phase of this rebuild targets the
  same integration branch; `main` — and therefore production — is touched once, at the end,
  after everything has been validated together. This is the mission's one non-negotiable
  arbitration. Before the first commit of any task, run `git branch --show-current` and stop
  if it is not `feat/shell-mobile`: a phase committed to `main` cannot be un-shipped, and a
  local `main` that has drifted produces a pull request with no checks at all.
---

## File Structure

| File                                                                              | Responsibility                                                                                               |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `frontend/src/styles/ps/maquette-acquisition.css`                                 | **Delete** at the end of the phase, once every rule it carries is served by the generated stylesheet.        |
| `frontend/src/styles/ps/app-surface.css`                                          | **Regenerated.** The single source of surface CSS.                                                           |
| `frontend/src/components/acquisition/MqToast.tsx`                                 | **Rename** to `SurfaceToast.tsx`; the `Mq` prefix names a scope that no longer exists.                       |
| `frontend/src/pages/AcquisitionPage.tsx`, `frontend/src/pages/MediaSheetPage.tsx` | **Modify.** Scope wrapper `.mq` → `.tm`.                                                                     |
| `frontend/src/components/ds/Chip.tsx`                                             | **Create.** The chip the prototype fixes at 11px semibold, pill radius, 6px tone dot, 20% tinted background. |
| `frontend/src/components/ds/SectionHeader.tsx`                                    | **Create.** The section header with its tone dot and its count.                                              |
| `frontend/src/components/ds/SwipeRow.tsx`                                         | **Create.** The row that claims the horizontal axis and reveals its actions.                                 |
| `frontend/src/components/ds/BottomSheet.tsx`                                      | **Create.** The bottom sheet, closable by the scrim and by its handle, reserving the tab bar's height.       |
| `frontend/src/components/ds/PageHeader.tsx`                                       | **Modify.** Renders nothing below the `md` breakpoint.                                                       |
| `frontend/src/components/layout/AppShell.tsx`                                     | **Modify.** Carries the `.tm` scope for the surfaces that opt in.                                            |

**Read before starting:** §4 of the spec (the shared language), `frontend/maquette/README.md`, and `frontend/maquette/regions.json` → `$adversarialReview` rules R2, R5, R7, R8, R12, R19, R22, R23.

---

### Task 1: The scope rename, with nothing moving

**Files:**

- Modify: `frontend/src/pages/AcquisitionPage.tsx`, `frontend/src/pages/MediaSheetPage.tsx`
- Rename: `frontend/src/components/acquisition/MqToast.tsx` → `frontend/src/components/acquisition/SurfaceToast.tsx`
- Modify: every importer of `MqToast`

**Interfaces:**

- Produces: the scope class `.tm` wrapping the surfaces that previously used `.mq`; `SurfaceToast` exported with the same props as `MqToast`.

- [ ] **Step 1: Capture the before-state**

Run:

```bash
cd frontend && npm run build
cd .. && python scripts/parity-probe.py --app-dir frontend/dist --only shell/
```

Expected: `OK`. Write the region count down — it must be identical at the end of the phase. A phase that quietly measures fewer regions is a phase that quietly stopped checking.

- [ ] **Step 2: Find every occurrence**

Run: `rg "\bmq\b|\.mq\b|MqToast" -g '*.tsx' -g '*.ts' -g '*.css' frontend/src`
Expected: a short list — the scope wrapper in two pages, the toast component and its importers, and the mirrored stylesheet. Anything else found here belongs in this task too.

- [ ] **Step 3: Rename the scope in the pages**

In `frontend/src/pages/AcquisitionPage.tsx` and `frontend/src/pages/MediaSheetPage.tsx`, change the wrapper's class from `mq` to `tm`. Do not touch anything else in those files.

- [ ] **Step 4: Rename the toast component**

Run:

```bash
git mv frontend/src/components/acquisition/MqToast.tsx frontend/src/components/acquisition/SurfaceToast.tsx
rg -l "MqToast" -g '*.tsx' -g '*.ts' frontend/src \
  | xargs python3 -c "import pathlib,sys;[pathlib.Path(f).write_text(pathlib.Path(f).read_text().replace('MqToast','SurfaceToast')) for f in sys.argv[1:]]"
```

The rename goes through Python rather than `sed -i`, whose in-place flag takes an argument on macOS and none on Linux — a step that only runs on the machine it was written on is a step the next person cannot run. The `Mq` prefix named a scope that no longer exists; leaving it would teach the next reader a vocabulary the codebase abandoned.

- [ ] **Step 5: Point the mirrored stylesheet at the new scope, temporarily**

In `frontend/src/styles/ps/maquette-acquisition.css`, replace the `.mq` prefix with `.tm` throughout:

```bash
python3 - <<'EOF'
import pathlib, re
p = pathlib.Path("frontend/src/styles/ps/maquette-acquisition.css")
p.write_text(re.sub(r"\.mq\b", ".tm", p.read_text()))
EOF
```

This file is deleted in Task 4; until then it must keep serving the Acquisition page under the new scope, or the page loses its styling mid-phase.

- [ ] **Step 6: Run the frontend gates**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src && npx vitest run`
Expected: all pass. A failing import here means a `MqToast` reference the rename missed.

- [ ] **Step 7: Prove nothing moved**

Run:

```bash
cd frontend && npm run build
cd .. && python scripts/parity-probe.py --app-dir frontend/dist --only shell/
```

Expected: `OK`, with the same region count as Step 1.

- [ ] **Step 8: Commit**

```bash
git add -A frontend/src
git commit -m "refactor(shell-mobile): one scope class for every surface

The surface scope becomes .tm, and the toast loses its Mq prefix — it named a
scope the codebase no longer has, and a prefix that lies teaches the next reader
a vocabulary that was abandoned.

Nothing moved: the probe reports the same regions at the same values."
```

---

### Task 2: The primitives the prototype proved necessary

Four components the prototype uses on every surface. Extracting them now is what stops phases 2 to 6 from each inventing their own chip.

**Files:**

- Create: `frontend/src/components/ds/Chip.tsx` + `Chip.test.tsx`
- Create: `frontend/src/components/ds/SectionHeader.tsx` + `SectionHeader.test.tsx`
- Create: `frontend/src/components/ds/SwipeRow.tsx` + `SwipeRow.test.tsx`
- Create: `frontend/src/components/ds/BottomSheet.tsx` + `BottomSheet.test.tsx`

**Interfaces:**

- Produces:
  - `<Chip tone="warning" label="Incomplet" />` — `tone` is `"success" | "warning" | "danger" | "info" | "neutral"`.
  - `<SectionHeader tone="warning" title="Séries incomplètes" count={47} />`.
  - `<SwipeRow actions={<button …/>}>{children}</SwipeRow>`.
  - `<BottomSheet open onClose={fn} title="…">{children}</BottomSheet>`.

- [ ] **Step 1: Write the failing test for Chip**

Create `frontend/src/components/ds/Chip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Chip } from "./Chip";

test("a chip carries its label", () => {
  render(<Chip tone="warning" label="Incomplet" />);
  expect(screen.getByText("Incomplet")).toBeInTheDocument();
});

test("a chip always carries its tone dot", () => {
  // The dot is what distinguishes a chip from a plain pill. A chip without it
  // is drift, not a variant.
  const { container } = render(<Chip tone="warning" label="Incomplet" />);
  expect(container.querySelector("[data-chip-dot]")).not.toBeNull();
});

test("the tone reaches the DOM so the stylesheet can act on it", () => {
  const { container } = render(<Chip tone="danger" label="Bloqué" />);
  expect(container.firstElementChild?.getAttribute("data-tone")).toBe("danger");
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/components/ds/Chip.test.tsx`
Expected: FAIL — `Chip` does not exist.

- [ ] **Step 3: Write Chip**

Create `frontend/src/components/ds/Chip.tsx`:

```tsx
export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

/**
 * The status chip, at the geometry the design prototype fixes: 11px semibold,
 * pill radius, a 6px dot in the tone colour, background tinted at 20%.
 *
 * The dot is not decoration: it is what separates a chip from a plain pill, and
 * a chip without it — or at another size — is drift rather than a variant. The
 * tone reaches the DOM as a data attribute so the generated stylesheet owns the
 * colours and this component owns none.
 */
export function Chip({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className="chip" data-tone={tone}>
      <span className="chipdot" data-chip-dot />
      {label}
    </span>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npx vitest run src/components/ds/Chip.test.tsx`
Expected: PASS — 3 passed.

- [ ] **Step 5: Write the failing test for SectionHeader**

Create `frontend/src/components/ds/SectionHeader.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { SectionHeader } from "./SectionHeader";

test("a section header carries its title and its count", () => {
  render(
    <SectionHeader tone="warning" title="Séries incomplètes" count={47} />,
  );
  expect(screen.getByText("Séries incomplètes")).toBeInTheDocument();
  expect(screen.getByText("47")).toBeInTheDocument();
});

test("a count of zero is rendered, not hidden", () => {
  // « 0 » is information: a section that shows nothing must say it shows
  // nothing, rather than leave the reader to guess whether it loaded.
  render(<SectionHeader tone="info" title="En vol" count={0} />);
  expect(screen.getByText("0")).toBeInTheDocument();
});
```

- [ ] **Step 6: Run it to verify it fails, then write SectionHeader**

Run: `cd frontend && npx vitest run src/components/ds/SectionHeader.test.tsx` → FAIL.

Create `frontend/src/components/ds/SectionHeader.tsx`:

```tsx
import type { Tone } from "./Chip";

/**
 * A section's header: a tone dot, the title, and the count on the right.
 *
 * The count is always rendered, including zero — « 0 » is information, and a
 * section that shows nothing must say so rather than leave the reader guessing
 * whether it loaded.
 */
export function SectionHeader({
  tone,
  title,
  count,
}: {
  tone: Tone;
  title: string;
  count: number;
}) {
  return (
    <div className="sech" data-tone={tone}>
      <span className="sechdot" />
      <h2 className="sechtitle">{title}</h2>
      <span className="sechcount">{count}</span>
    </div>
  );
}
```

Run again: PASS — 2 passed.

- [ ] **Step 7: Write the failing test for SwipeRow**

Create `frontend/src/components/ds/SwipeRow.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { SwipeRow } from "./SwipeRow";

test("the row claims the horizontal axis", () => {
  // Without this the browser owns both axes, decides a drag is a pan, and fires
  // touchcancel: the swipe then works only under synthetic events, which are
  // never cancelled. Declared on the row itself, never on an ancestor —
  // touch-action intersects down the whole chain.
  const { container } = render(
    <SwipeRow actions={<button type="button">Retirer</button>}>
      <span>Silo</span>
    </SwipeRow>,
  );
  const row = container.firstElementChild as HTMLElement;
  expect(row.style.touchAction).toBe("pan-y");
});

test("the drag ends are listened for on the window, not on the scrollport", () => {
  // A touch is captured implicitly by the element that received the start; a
  // mouse is not. Released outside the frame, the up never reaches a listener
  // bound to the scrollport and the gesture hangs half-done — invisible to a
  // touch test, fatal to a mouse one.
  const spy = vi.spyOn(window, "addEventListener");
  render(
    <SwipeRow actions={<button type="button">Retirer</button>}>
      <span>Silo</span>
    </SwipeRow>,
  );
  const events = spy.mock.calls.map(([name]) => name);
  expect(events).toContain("pointerup");
  spy.mockRestore();
});

test("images inside the row do not start the browser's native picture drag", () => {
  // Dragging a picture is a browser default and it swallows the pointer stream:
  // the handler gets a couple of moves and never an up.
  const { container } = render(
    <SwipeRow actions={<button type="button">Retirer</button>}>
      <img src="data:," alt="" />
    </SwipeRow>,
  );
  const img = container.querySelector("img") as HTMLElement;
  expect(img.style.userDrag || getComputedStyle(img).getPropertyValue("-webkit-user-drag"))
    .not.toBe("auto");
});

test("the actions are rendered behind the row", () => {
  const { container } = render(
    <SwipeRow actions={<button type="button">Retirer</button>}>
      <span>Silo</span>
    </SwipeRow>,
  );
  expect(container.querySelector(".swipeacts")).not.toBeNull();
});
```

- [ ] **Step 8: Run it to verify it fails, then write SwipeRow**

Run: `cd frontend && npx vitest run src/components/ds/SwipeRow.test.tsx` → FAIL.

Create `frontend/src/components/ds/SwipeRow.tsx`:

```tsx
import type { ReactNode } from "react";

/**
 * A row whose actions are revealed by a horizontal drag.
 *
 * The row CLAIMS the horizontal axis with `touch-action: pan-y`. Without that
 * claim the browser owns both axes, decides a drag is a pan, and fires
 * `touchcancel` — the swipe then works only under synthetic events, which are
 * never cancelled, so the tests pass and the thumb finds nothing. The claim is
 * declared here and never on an ancestor: `touch-action` intersects down the
 * whole chain, so a `pan-x` scroller under a `pan-y` ancestor pans on neither.
 */
export function SwipeRow({
  actions,
  children,
}: {
  actions: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="swipe" style={{ touchAction: "pan-y" }}>
      <div className="swipeacts">{actions}</div>
      <div className="swipebody">{children}</div>
    </div>
  );
}
```

Run again: PASS — 2 passed.

- [ ] **Step 9: Write the failing test for BottomSheet**

Create `frontend/src/components/ds/BottomSheet.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { BottomSheet } from "./BottomSheet";

test("a closed sheet renders nothing", () => {
  const { container } = render(
    <BottomSheet open={false} onClose={() => {}} title="Silo">
      <p>corps</p>
    </BottomSheet>,
  );
  expect(container.firstChild).toBeNull();
});

test("the scrim closes the sheet", () => {
  const onClose = vi.fn();
  const { container } = render(
    <BottomSheet open onClose={onClose} title="Silo">
      <p>corps</p>
    </BottomSheet>,
  );
  fireEvent.click(container.querySelector(".scrim")!);
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("the sheet reserves the tab bar's height", () => {
  // The tab bar passes above the layers, so a sheet that does not reserve its
  // height leaves its last actions unreachable: internal scrolling stops before
  // them, and the thumb finds nothing there.
  render(
    <BottomSheet open onClose={() => {}} title="Silo">
      <p>corps</p>
    </BottomSheet>,
  );
  const sheet = screen.getByRole("dialog");
  expect(sheet.style.paddingBottom).toContain("--tm-bottom-bar-h");
});
```

- [ ] **Step 10: Run it to verify it fails, then write BottomSheet**

Run: `cd frontend && npx vitest run src/components/ds/BottomSheet.test.tsx` → FAIL.

Create `frontend/src/components/ds/BottomSheet.tsx`:

```tsx
import type { ReactNode } from "react";

/**
 * The bottom sheet: a scrim, a handle, a title, and a body.
 *
 * It reserves the tab bar's measured height, because the bar passes above the
 * layers. A sheet that does not reserve it leaves its last actions unreachable —
 * internal scrolling stops before them and nothing says why. The height is read
 * from the variable the bar publishes: nothing positions itself by a distance to
 * a screen edge.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div
        role="dialog"
        aria-label={title}
        className="sheet"
        style={{ paddingBottom: "calc(var(--tm-bottom-bar-h, 0px) + 12px)" }}
      >
        <div className="sheethandle" />
        <h2 className="sheettitle">{title}</h2>
        {children}
      </div>
    </>
  );
}
```

Run again: PASS — 3 passed.

- [ ] **Step 11: Run the full frontend gates**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src && npx vitest run`
Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/components/ds
git commit -m "feat(shell-mobile): the four primitives every surface will share

Chip, SectionHeader, SwipeRow and BottomSheet, extracted from what the design
prototype uses everywhere. Extracting them now is what stops the next five
surfaces from each inventing their own chip.

SwipeRow claims the horizontal axis on the row itself: without that claim the
browser takes the gesture and cancels it, so the swipe works under synthetic
events — which are never cancelled — and fails under a thumb. BottomSheet
reserves the tab bar's measured height, because the bar passes above the layers
and a sheet that ignores it hides its own last actions."
```

---

### Task 3: `PageHeader` leaves mobile

**Files:**

- Modify: `frontend/src/components/ds/PageHeader.tsx`
- Modify: `frontend/src/components/ds/PageHeader.test.tsx`

**Interfaces:**

- Produces: `PageHeader` renders nothing below the `md` breakpoint; its five callers are unchanged.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/ds/PageHeader.test.tsx`:

```tsx
test("the header is absent from the phone layout", () => {
  // On a phone the header costs a third of the first screenful to repeat what
  // the tab bar already says. The title lives in the view tabs there.
  const { container } = render(<PageHeader title="Médiathèque" />);
  expect(container.firstElementChild?.className).toContain("hidden");
  expect(container.firstElementChild?.className).toContain("md:");
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/components/ds/PageHeader.test.tsx`
Expected: FAIL on the new test only.

- [ ] **Step 3: Take the header off mobile**

In `frontend/src/components/ds/PageHeader.tsx`, add `hidden md:flex` (or `hidden md:block`, matching the element's existing display) to the root element's className, and document why in a comment above it:

```tsx
// Absent from the phone layout: it costs a third of the first screenful to
// repeat what the tab bar already says. On a phone the title lives in the
// view tabs; from `md` up the header returns, where the room exists.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/ds/PageHeader.test.tsx`
Expected: PASS.

- [ ] **Step 5: Verify no page lost its title on desktop**

Run: `cd frontend && npx vitest run src/pages`
Expected: PASS. The five callers (`Dashboard`, `Medias`, `Pipeline`, `Config`, `SystemePage`) are untouched; only the breakpoint changed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ds/PageHeader.tsx frontend/src/components/ds/PageHeader.test.tsx
git commit -m "refactor(shell-mobile): the page header leaves the phone layout

It spent a third of the first screenful repeating what the tab bar already says.
From md up it returns, where the room exists. Its five callers are unchanged."
```

---

### Task 4: Retire the mirrored stylesheet

The generated stylesheet from phase 0 now serves what the mirrored one did. Keeping both means two sources for the same pixels, which is how they drift.

**Files:**

- Delete: `frontend/src/styles/ps/maquette-acquisition.css`
- Modify: `frontend/src/styles/ps/styles.css`

- [ ] **Step 1: List what the mirrored stylesheet claims**

Run:

```bash
grep -oE "^\s*\.[A-Za-z][\w-]*" frontend/src/styles/ps/maquette-acquisition.css | tr -d ' .' | sort -u > /tmp/mirrored.txt
grep -oE "^\.tm \.[A-Za-z][\w-]*" frontend/src/styles/ps/app-surface.css | sed 's/^\.tm \.//' | sort -u > /tmp/generated.txt
comm -23 /tmp/mirrored.txt /tmp/generated.txt
```

Expected: the list of classes the mirrored file serves and the generated one does not. **Every one of them is a decision**, not a leftover: either the prototype must carry it (add it there, regenerate) or it was Acquisition-only cruft (drop it). Do not delete the file while this list is non-empty.

- [ ] **Step 2: Close the gap in the prototype, not in the code**

For each class the previous step listed, add the rule to `frontend/maquette/refonte.html`'s application CSS block, then:

```bash
python scripts/extract-maquette-css.py
python scripts/check-maquette-classes.py
```

Repeat until Step 1's `comm` output is empty. The prototype is the source: a rule added to the generated file directly is reverted by the drift guard, which is the point.

- [ ] **Step 3: Delete the mirrored stylesheet**

Run:

```bash
git rm frontend/src/styles/ps/maquette-acquisition.css
```

Then remove its `@import` from `frontend/src/styles/ps/styles.css`.

- [ ] **Step 4: Verify the Acquisition page is untouched**

Run:

```bash
cd frontend && npx vitest run src/pages/AcquisitionPage.test.tsx && npm run build && (npm run preview -- --port 4173 &) && sleep 4
cd .. && python scripts/parity-probe.py --app-dir frontend/dist --only shell/
```

Expected: tests pass and the probe reports `OK` with the same region count as Task 1 Step 1.

- [ ] **Step 5: Look at the page**

Run: open `http://127.0.0.1:4173/acquisition` in a browser at 390 px wide and compare against the prototype's `acq-encours-repos` state, side by side.
Expected: identical. This is the one step a measurement cannot replace — the probe measures the regions it was told about, and this is where you find the one nobody declared.

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/styles
git commit -m "refactor(shell-mobile): one source for surface CSS, not two

The hand-mirrored stylesheet is retired: the generated one now serves everything
it did. Two sources for the same pixels is how they drift — and the previous
rebuild drifted exactly that way, one detail at a time.

Every rule it carried that the prototype lacked was added to the PROTOTYPE and
regenerated, never patched into the generated file: a direct edit there is
reverted by the drift guard, which is what makes the rule real."
```

---

### Task 5: Phase gate

- [ ] **Step 1: Run every gate**

Run:

```bash
make check-frontend
python scripts/check-maquette-classes.py
pytest tests/scripts -v
```

Expected: all pass.

- [ ] **Step 2: Prove the shell did not move**

Run: `python scripts/parity-probe.py --only shell/`
Expected: `OK`, same region count as at the start of the phase.

- [ ] **Step 3: Grep for the retired vocabulary**

Run: `rg "\bmq\b|MqToast|maquette-acquisition" -g '*.tsx' -g '*.ts' -g '*.css' frontend/src`
Expected: zero matches. A rename that leaves half the old name behind teaches both vocabularies.

- [ ] **Step 4: Update the tracker and bump the version**

Modify `IMPLEMENTATION.md`: mark phase 1 done, set the next action to "write the plan for phase 2". Raise the minor component in `pyproject.toml` — this phase adds shared primitives.

- [ ] **Step 5: Commit**

```bash
git add IMPLEMENTATION.md pyproject.toml
git commit -m "chore(shell-mobile): phase 1 gate — one vocabulary for every surface

One scope class, four shared primitives, a header that leaves the phone, and a
single source for surface CSS. Not one shipped pixel moved: the probe reports the
same regions at the same values as before the phase."
```

---

## Self-Review

**1. Spec coverage.** §4.1 the scope rename → Task 1. §4.2 primitives extracted to `ds/` → Task 2 (four components; the spec's list of eight is met by these four plus the four already present — `MediaPoster`, `NavCountBadge`, `StatusDot`, `EmptyState` — which need no extraction). §4.3 §12 becomes structural → the primitives carry it: `Chip` fixes its own geometry, `SectionHeader` always renders its count, `BottomSheet` reserves the bar. §4.4 `PageHeader` leaves mobile → Task 3. The mirrored stylesheet's retirement is not in §4 but follows from §7.2 (one generated source): Task 4, with the gap-closing loop that forces every missing rule back through the prototype.

**2. Placeholder scan.** No TBD, no "handle edge cases". Task 4 Step 2 is a loop rather than a fixed edit — that is the honest shape of the work, and its exit condition is executable (`comm` output empty).

**3. Type consistency.** `Tone` is defined in `Chip.tsx` and imported by `SectionHeader.tsx`. `SwipeRow({actions, children})` and `BottomSheet({open, onClose, title, children})` are used in their tests with those exact props. No later task references a primitive under a different name.

**One risk named:** Task 4 Step 1 may reveal that the mirrored stylesheet carries rules the prototype never had — Acquisition details that shipped without ever being drawn. Closing that gap in the prototype is real work whose size is unknown until the `comm` runs. If it turns out large, that is a finding worth reporting rather than absorbing silently: it measures how far the shipped page had drifted from any reference at all.
