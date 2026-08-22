# Phase 4 — Focus manager and keyboard paths

## Gate

Produced by Phase 3:

- `a11y.py --check --rules button-name,link-name,image-alt,label` at 0 over 83 states.
- `check-no-french.py` green — every component label in `fr.json`.
- Oracle at 0 divergence.

Names before focus: a focus manager that lands on an unnamed control has moved focus to
« bouton », which is not a destination.

## What this phase does

The only genuinely new mechanism in the lot, and the one that has to outlive the engine.

**The keystone, measured rather than designed around**: `data-open` is already the universal
layer signal. `setOpen(element, on)` (`legacy.js:9501`) toggles the `open` class *and* the
`data-open` attribute, for `#drawer`, `#screen`, `#dlg` and `#scrim`; on the React side
`components/sheet.tsx` and the five screen components emit it themselves. So the manager
**observes an attribute that already exists** — it needs no new call from the engine, it anchors
on `data-*` as D4 requires, and it survives L13 because it knows nothing about the engine.

**The second measured fact that shapes this phase**: the engine's click delegation opens only to
`event.target.closest("button, a[data-navgo]")` (`legacy.js:11694`). Clickable things are already
native buttons and anchors, therefore already focusable. **The keyboard hole is in the layers and
the shortcuts, not in the targets** — and there is no keyboard handling anywhere: 0 `keydown`,
0 `Escape`, 0 `onKeyDown`, in React and in the engine's 34 650 lines alike.

## Sub-phases

### 4.1 — The focus manager

A TypeScript module in `design/src/`, installed once at boot. For each layer root it watches
`data-open` and, on an opening: records the element that had focus, moves focus to the first
sensible target inside the layer, and marks the background `inert` (React 19 supports the
attribute; for engine-drawn nodes it is set imperatively). On closing: removes `inert` and
**returns focus to the recorded trigger**.

It is a pure observer of markup state. No engine call site changes.

Commit: `feat(maquette-l03): a layer takes focus when it opens and gives it back when it closes`

### 4.2 — `Escape` closes the top layer

`Escape` calls `window.__closeLayers` — **the verb already exists** (`legacy.js:11188`) and this
phase does not write a second one. The engine's own back ladder already unwinds drawer, then
screen, then sheet; `Escape` enters that ladder rather than competing with it.

Commit: `feat(maquette-l03): Escape closes the layer that is on top`

### 4.3 — The remaining keyboard paths

The tab bar navigable from the keyboard. The sheet's drag handle, which today answers only a
pointer, given a keyboard equivalent for the dismissal the drag performs. Anything that is not
already a native control answers `Enter` and `Space`.

Commit: `feat(maquette-l03): the interface is reachable without a pointer`

### 4.4 — The rule that holds it

A harness rule under `frontend/maquette/harness/`, in the shape of its neighbours (`common.Journal`,
one hold per assertion). For every state that opens a layer it holds: focus moved inside the
layer, the background is inert, `Escape` closes it, and focus returned to the trigger.

**axe cannot see any of this.** An automated audit reads the markup of one moment; focus
management is a sequence. The two instruments are not redundant, and this rule is the only thing
that measures the sequence.

Commit: `test(maquette-l03): a rule holds that focus enters a layer and comes back`

## Verification

| ID | Command | Expected |
| --- | --- | --- |
| ACC-10 | `python3 frontend/maquette/harness/<the focus rule>.py` | 0 failures: focus in, background inert, focus restored, for every layer that opens |
| ACC-11 | same rule | `Escape` closes the top layer in every layered state, 0 failures |
| — | `python3 frontend/maquette/oracle.py --check` | 0 divergence — `inert` and `tabindex` change no computed style |
| — | `frontend/maquette/harness/run.sh` (full suite) | no rule falls; `inert` on the background must not blind a rule that drives through a layer |

## ⚠ What this phase actually cost, recorded because the next one will meet it

**Six defects, and the rule found five of them.** The sixth — the one the rule could not find —
is the interesting one.

| Found by | Defect |
| --- | --- |
| R81, first run | Focus was never restored: `focus()` on an element inside an `inert` subtree does nothing, silently, and every trigger sits in the background the layer had just marked. The mark comes off first now |
| R81, first run | The skip link moved the view and not the focus. `<a href="#port">` should focus a target carrying `tabindex="-1"`; the router owns the URL and the hash never reaches default handling |
| R81, first run | …and one was in the RULE: it tabbed from wherever the layer holds had left focus. The browser's sequential focus starting point is set by the last CLICK and `blur()` does not move it |
| **Reading the code** | **`LAYERS` selected the screen as `#screen`.** One legacy screen carries that id; FIVE migrated ones are `<section data-part="screen">` with no id. The manager was blind to five of its six layers and R81 was green, because R81 drove the drawer and the sheet and nothing else |
| R81, once pointed at a screen | `Escape` did nothing: `__closeLayers` closes the three layers the scrim covers and deliberately not a screen, which is a history entry closed by a back |
| R81, once pointed at a screen | The stack never unwound. `isOpen()` read `data-open` alone; a migrated screen is UNMOUNTED, and a detached node keeps every attribute it had |

**The lesson is the repository's own, paid again**: a rule proves what it READS. The manager and
the rule were written together from the same mental model, so the rule inherited its blind spot
exactly. What broke the loop was reading the code against the markup — not another gate.

## Risk this phase carries

`inert` on the background could break rules that click through an open layer. The harness bar
(`.hbtn`) sits outside the layer roots, so the driving surface is unaffected — but the full suite
and the hold-count comparison are what prove it, not that sentence.

## Out of scope for this phase

Live regions and busy states (Phase 5). Making the a11y floor hard (Phase 6).
