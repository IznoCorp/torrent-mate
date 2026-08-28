# Phase 1 — `app/shell.tsx` splits, on five subjects

**760 non-blank lines** against invariant 6's ceiling of 400. It is split BEFORE anything is
added to it, and it lands alone: a split proves the rendering did not change, and mixing an edit
into a move is what makes a diff unreviewable (§ 0).

**Split on a SUBJECT, never to pass under a bar.** `csstokens_login.py` is the model — L07-bis
split three guards this way and each came out under the SOFT ceiling without a line written for
the count's sake.

## The five subjects

Read off the file's own top-level declarations, not invented:

| File | What it owns | Today's anchor |
| --- | --- | --- |
| `app/shell.tsx` | boot: stylesheet order, i18n, the engine, mount, the seams installed | lines 1–100, 707–794 |
| `app/router-tree.tsx` | the router, its routes, `ScreenError` | `ScreenError`, `createRouter`, the 14 route imports |
| `app/history-bridge.ts` | `createBrowserHistory`, the `Bridge` and `Screens` implementations | `history`, `currentKey`, `panelAddress` |
| `app/scroll-restoration.ts` | `scrollPositions`, `restoreToken`, `entryKey`, `activePort`, `restoreScroll` | lines 399–444 |
| `app/panel-host.ts` | `openPanel`, `closePanel`, `isPanelOpen`, `openPanelOnCurrentEntry` | lines 605–673 |

**The stylesheet imports stay in `shell.tsx` and stay in their order.** Their order IS a cascade
decision (D3): tokens, base, residue, harness. Moving one into another module changes the emitted
order and the reset would then win over a component. The comment saying so moves with them.

**The engine import stays in `shell.tsx` too.** It runs for its side effect and its position is
load-bearing — the body reads `window.__startEngine`.

## What must not change

- The `window` seams — `__bridge`, `__screens`, `__panel`, `__go`, `__store` — are the harness's
  driving surface. Their names and their members are the seam and do not move.
- Every `data-*` the document-level delegation reads.
- The order in which the seams are installed relative to `window.__startEngine`.

## The rule that bites

`harness/shell.py` already holds the shell's contracts. Extend it with a hold that the five
modules are each reachable and that `installSeams` is called exactly once before the engine
starts — then mutate: call it twice, see the hold fall naming the double install, restore.

## Done when

- `grep -c . frontend/maquette/design/src/app/shell.tsx` ≤ 400, and each new file too.
- `python3 scripts/check-module-size.py --root frontend` clean.
- `python3 scripts/check-frontend-boundaries.py` clean — no cycle introduced by the split.
- **`python3 frontend/maquette/oracle.py --check` → `no divergence`.** A move that moves a
  rectangle was an edit.
- `frontend/maquette/harness/run.sh --contracts` green.
