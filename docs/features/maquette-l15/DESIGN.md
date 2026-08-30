# L15 — The frame

**Codename** `maquette-l15` · **Branch** `feat/maquette-l15` · **Bump** patch, 0.98.54 → 0.98.55

**The contract is not here.** `docs/reference/frontend-architecture.md` § 4, entry
`#### L15 — The frame`, carries the objective, the part-by-part table, the four behaviour changes
and the « Done when ». A contract copied into a second file is a contract wrong in one of them.
This file says **how** the lot is built, what was **measured** before it opened, and the
**decisions** taken inside it.

**The § § of the constitution this wave serves.** §8 (« rien en silence » — the toast is the
interface's one general-purpose announcement channel, and it becomes a component with a live
region rather than an `innerHTML` write), §12 (« pensée pour le téléphone d'abord » — P1, P2, P10,
P14, P21, P28 of `MODEL.md` § 3 are the frame's own share of it), §16 (the back gesture — the
dialog gets the rung D1's third tier already gave it), and §15 (the maquette is the visual
reference: nothing here moves a pixel). The clause map's own instrument, B-142, is built here and
serves every clause at once.

---

## 1. What was measured before this design was written

Every figure carries the command. They were re-run on `main` at `43e9760a`, 2026-08-30, and the
« Done when » re-runs the first of them.

| Figure | Command | Read |
| --- | --- | --- |
| Markup writes in the engine | `SURVEY.md` § 1.1's command | **19 sites**, nine surfaces |
| Dialog producers | `grep -n "openDlg(" legacy.js`, minus the definition | **2** (`10788`, `10915`) |
| Toast callers | `grep -c "toast(" legacy.js` minus the definition, `grep -c "toastUndo(" legacy.js` minus its own | **29 + 5 = 34** |
| Bottom-panel producers | `grep -c "panel\.open(" legacy.js` | **10** — none of them this lot's (L19) |
| Named states | `python3 -c "import json;print(len(json.load(open('frontend/maquette/oracle-reference.json'))['measurements']))"` | **87** |
| Files at the ceiling | `python3 scripts/check-frontend-boundaries.py --arm size` | **6** — four L14's, two the engine's |
| `app/` domain words | `python3 scripts/check-frame-domain.py` | **98** against a ceiling of 98 |
| Register's next number | `python3 scripts/check-bug-register.py --next` | **B-244** |
| « Guards green » total | `grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md` | **98** |

**One figure of `MODEL.md` was re-derived and it holds**: the toast's 34 callers, which the model
gives as « 29 `toast(`, 5 `toastUndo(`, definitions subtracted ». `grep -c` reads 30 and 6; the
definitions are `function toast(msg)` and `function toastUndo(msg, undo)`. The count is right
because the subtraction was made.

---

## 2. Where the frame lands — the tree this lot leaves behind

Invariant 10 assigns the directory; `MODEL.md` § 2 assigns the part. Nothing new goes in `lib/`.

| New file | Part | What it is |
| --- | --- | --- |
| `app/navigation.ts` | 5 | **the one table** — id · path · component · label key · icon · group · in the bar · action button · `badge()`. Invariant 10's third named exception |
| `app/frame.tsx` | 6, 7, 9 | the frame COMPOSED: one element in the root, one installer for the hosts. It exists so `app/shell.tsx` (380 of 400 non-blank lines) does not grow — see § 5 |
| `app/tab-bar.tsx` | 6 | `<nav id="nav">`, React, reading the table and the store |
| `app/drawer.tsx` | 6, 7 | the drawer's own host and content: the table, the appearance control, the served identity |
| `app/action-button.tsx` | 6 | the floating action button and its two facts |
| `app/bottom-slot.tsx` | 6 | the place above the tab bar a feature may fill, and the registry it reads |
| `app/layer-registry.ts` | 4, 7 | what a layer registers with the ladder — a name, an `isOpen`, a `close(pop)`. **Not the handler**: L13 takes that |
| `app/dialog-host.ts` | 7 | `window.__dialog` — the descriptor verbs, `app/panel-host.ts`'s sibling |
| `app/toast-host.ts` | 7 | `window.__toast` — `{ message, undo? }` |
| `app/popover-host.ts` | 7 | `window.__popover` — `{ anchor, content }` |
| `app/splash.ts` · `app/sign-in.tsx` · `app/install.ts` · `app/appearance.ts` | 9 | the entry |
| `ui/drawer.tsx` · `ui/dialog.tsx` · `ui/toast.tsx` · `ui/popover.tsx` | 7 | the primitives, beside `ui/sheet.tsx` |
| `features/library/selection-bar.tsx` | 6 | the library's bar, portalled into the frame's slot |
| `scripts/check-intent-map.py` | — | **B-142's instrument** |

**And what is SUBTRACTED from the engine**, which is the other half of every one of those rows:
`PAGES_OF`, `NAVIGATION`, `renderNav`, `refreshActionButton`, `paintSelBar`, `openDlg`/`closeDlg`,
`toast`/`toastUndo`/`setMessageShown`, `openPopEp`/`closePopEp`, `openDrawer`/`closeDrawer`,
`servedIdentityBlock`, `showSignIn`/`hideSignIn`, `showStartup`/`hideStartup`/`coverLoading`,
`showInstallation`/`proposerInstallation`, `APPARENCES`/`apparenceCourante`/`applyAppearance`, and
the viewport fallback. **Every engine edit in this lot is a subtraction or a call through a seam**
(D5). A line added to the engine that is neither is the defect.

---

## 3. The four behaviour changes, and why they are four commits

A conversion proves the rendering did **not** change; a behaviour change proves it **did**. The
oracle is what makes the distinction real, so it must never be asked both questions at once.

| # | Entry | What moves | Its rule |
| --- | --- | --- | --- |
| 1 | **B-229** | the dialog takes a rung on the ladder: `openDialog` pushes a layer entry, the back handler closes it first | a hold that opens a dialog, presses Back, and asserts the dialog closed AND the page did not change |
| 2 | **B-237** | the dialog's z-order: it paints ABOVE the tab bar, not under it | a hold that hit-tests the dialog's lower edge against `#nav` |
| 3 | **B-233** | `theme-color` follows the theme | a rule reading the meta under both themes |
| 4 | **B-230** | the viewport fallback that re-adds `user-scalable=no` is removed | a rule reading `legacy.js` for the directive, and axe's `meta-viewport` over the named states |

**The ladder's HANDLER stays in the engine.** `onEngineBack`, `unwindLayer`, `hideLayers` and
`__closeLayers` are L13's. What this lot adds is a REGISTRATION — `app/layer-registry.ts` — that
the drawer and the dialog enter and the engine's handler walks, exactly as the sheet already does
through `window.__panel`. Reaching into the engine to move the handler early would make L15 a
subtraction wave as well as a conversion wave, which is the mix § 5 refuses.

---

## 4. B-142's instrument — `scripts/check-intent-map.py`

Its shape is dictated by `MODEL.md` § 4 and is not re-decided here. What this design adds is the
**placement**, because the specification's own sentence — « it runs in the contracts tier, over the
`docs` filter » — describes a hole this lot found and had to close first.

**The hole, verified before it was believed.** `frontend/maquette/harness/run.sh`'s contracts tier
runs `check-implementation-state.py`. That guard reads `IMPLEMENTATION.md`. `IMPLEMENTATION.md` is
named by the `docs` filter of `.github/workflows/ci.yml`. The job that runs the contracts tier —
`harness-contracts` — is gated on the **`maquette`** filter, which does not name it. So a pull
request touching `IMPLEMENTATION.md` alone — which is exactly what a post-merge gesture is — runs
that guard in **no job at all**, and `tests/scripts/test_ci_filter_covers_the_guards.py` passes
over it because it asks « is this path named by ANY filter? » and never « by the filter that gates
the job that runs the guard? ». B-085's species, and the hold's own blind spot.

**What this lot does about it, and the boundary it respects.** The hole is filed (§ 6) and closed
in the same move the arm needs it closed: the three documents the new arm reads are added to the
**`maquette`** filter beside `BUGS.md` and `CLAUDE.md`, `IMPLEMENTATION.md` joins them, and the
hold in `tests/scripts/test_ci_filter_covers_the_guards.py` is strengthened to ask the second
question. Strengthening the hold is not scope creep: an arm placed in a tier that does not run is
an arm that proves nothing, and this lot is placing one.

---

## 5. Decisions taken in this design

**D-L15-1 — `app/frame.tsx` exists so `app/shell.tsx` does not grow.** `shell.tsx` reads 380
non-blank lines against invariant 6's hard ceiling of 400, and it is **not** one of the six
grandfathered files — so it may not cross it. The frame is composed in its own file: one import
and one element in the root, and the hosts' installers move there with it. `publishBarHeight()`
and `installDrawerDismissGesture()` move too, and the first of them **must**: it queries
`.bottombar` at boot, before the first React render, and once the bar is React-drawn that query
answers nothing and the `ResizeObserver` never attaches. R84's « exactly one publisher » is
preserved — `app/bar-height.ts` stays the publisher; only the moment it is called moves, into a
layout effect that runs after the bar exists.

**D-L15-2 — the layers are rendered at their own ids, inside `#shell`.** `ui/sheet.tsx` is the
precedent and its reasoning transfers verbatim: same ids, same classes, same tags, so the
stylesheet applies unchanged and every probe that selects them measures the React layer without
knowing anything moved. `#shell` sits inside `.device`, immediately before `#screen`, so a layer
rendered there keeps its stacking context. The static containers in `index.html` are removed in
the **same commit** as the component that replaces them — the engine captures `#nav`, `#dlg` and
their siblings at module evaluation, so a container removed a commit early is a null reference and
a container removed a commit late is two elements answering one id.

**D-L15-3 — a layer's open state is store state, and the DOM is never asked.** `panelOpen`
already is; `drawerOpen`, `dialogDescriptor`, `toastMessage` and `popoverDescriptor` join it. The
engine reads them through the seam rather than through `classList.contains("open")`, exactly as
`panel.isOpen()` already does — which is what makes an answer true at the instant a caller asks
rather than at the instant React last painted.

**D-L15-4 — the popover's LAYER converts and its CONTENT does not.** `openPopEp` builds both. The
layer — position, dismissal, the `#device`-relative clamp — is the frame's and moves. The sentence
it shows is a producer, and a producer is Part 12's, which is **L19's**. The seam therefore
carries `{ anchor, content }` where content is a descriptor of facts, and the engine keeps the
five lines that compute the facts until L19 takes them.

**D-L15-5 — the drawer alone, at every width.** Q1, answered by the operator on 2026-08-30, and
not frozen. No rail is drawn. B-235 is not a defect.

**D-L15-6 — `app/`'s domain-word ceiling rises, with its reason.** The one navigation table names
every page: that is invariant 10's third named exception, and the whole point of the table is that
the frame names its pages ONCE. The ceiling in `scripts/frame-domain-baseline.json` is raised to
the measured value at the wave's close, with the reason written beside it, and the four files that
carried the page list before it — `page-host.tsx`, `router-tree.tsx`, `lib/addresses.ts`,
`reference.d.ts` — are read again in the same move: a table that exists once should make that
number FALL in three of them.

---

## 6. The register, written during the wave

`BUGS.md`, from **B-244**. Filed as they are found, never in a commit message (L08 merged with
twenty findings that lived only in one and it took another wave to recover them).

Open at the design's writing:

- **B-244** — a guard in the contracts tier whose subject only the `docs` filter names runs in no
  job: `check-implementation-state.py` reads `IMPLEMENTATION.md`, the `harness-contracts` job is
  gated on `maquette`, and `test_ci_filter_covers_the_guards.py` cannot see it because it asks
  which filter names the path and never which filter gates the job. Closed by § 4.

---

## 7. The gates

**Per phase**: the oracle (`frontend/maquette/harness/run.sh --oracle`), the contracts tier
(`--contracts`, which folds in the repository's cheap guards), and the rule the phase writes with
its mutation seen red and restored.

**Before merging**: the FULL suite (`run.sh`, no flag), the `--a11y` tier, and `make check` at zero
failures and **zero errors**.

**The oracle's references are `Darwin/arm64`-bound.** This wave runs on that machine, so the
certification is real; a divergence is never re-recorded to make a step pass — it is named and
accepted, or it is a defect.
