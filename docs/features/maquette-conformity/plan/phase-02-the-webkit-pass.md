# Phase 2 — The rule's WebKit pass: the iPhone's engine, the frame's controls visible (auditor's order 89)

**Ordered 2026-09-29** (auditor's order 89, relayed by the orchestrator; rulings file § « TWO DEFECTS »): extend
R-conformity-a with a **WebKit** pass at iPhone format — viewport 390 × 844, `is_mobile` if WebKit accepts it — that
ALSO holds the VISIBILITY of the frame's controls (the hamburger, the bottom bar, the tab bars) in **light AND dark**.
Today only `drag.py` launches WebKit (`p.webkit.launch()`, **:80**); installed:
`ls ~/Library/Caches/ms-playwright | grep webkit` → `webkit-2336`.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `grep -n "PHONES\|WINDOWS\|def read_width" frontend/maquette/harness/responsive.py` → the Chromium
  widths the WebKit pass is added beside; the frame's controls by part: `shell/menu` (the hamburger),
  `shell/tab-bar`, `segment` — the exact parts read at the opening from `app/`.
- **Points ≈ 12.** The WebKit pass (a second browser, one width, two colour schemes) (≈ 30 lines, 3); the visibility
  hold — for each control: a non-zero box inside the window, the element found at its own centre
  (`elementFromPoint`), and its drawing's painted colour apart from the background under it (≈ 30 lines, 3); a
  mutation per new hold (2); the cost measured at its first pass — under 5 min it runs at every gate, else at the
  close and in CI (1); the RESUME (1); the owed entries the pass finds, each with its owner (2).
- **Readers.** `drag.py` (the one WebKit launch) — not changed.

## Red today

The WebKit pass's first red is expected to be the hamburger (the defects fast lane's, owed to it by name); every other WebKit red goes to the
owed list with its owner, told to the orchestrator.

## Mutation

Paint the hamburger's drawing the background's colour → the visibility hold falls by name in light and in dark;
drop the WebKit pass → the hamburger's red disappears (the pass is what reads it).

## Oracle

Nothing drawn moves: `run.sh --oracle` green, no accept.

## Commit

`test(maquette-conformity): the rule reads the iPhone's engine, and the frame's controls are seen in both themes`
