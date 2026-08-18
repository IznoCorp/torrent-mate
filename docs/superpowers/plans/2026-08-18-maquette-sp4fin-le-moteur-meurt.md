# SP4-fin — the engine dies — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `refonte.html` stops being a program. What it still carries — one 35 052-line inline
script and 289 lines of application markup — moves to real files under `design/src/`, and the
bridge that let a classic script talk to a module world is removed. What stays behind is the
stylesheet, and that is deliberate: the spec fixes the CSS contract as SP5's subject, not SP4's.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(§The waves — "**SP4-end — the engine dies**: Fragment empty; `refonte.html` retired as editing
source; bridge + `__rejouerLePont` + state alias removed; R72/R74 renegotiated (recorded);
`__go`/`__states` reimplemented shell-side").

**Recon:** measured 2026-08-18 on `main` at `e21462f4`, all four SP4d waves merged.

## What the recon settled, and why it splits the work in three

The fragment is **39 561 lines**, and it is three things, not one:

| Region        | Lines               | What it is                                                     |
| ------------- | ------------------- | -------------------------------------------------------------- |
| `<style>`     | 3–4216 (4 214)      | BLOCK 1 harness CSS + BLOCK 2 application CSS                  |
| static markup | 4219–4506 (289)     | the stage, the phone frame, the splash, the topbar, the layers |
| `<script>`    | 4507–39560 (35 054) | the engine                                                     |

The script is itself lopsided: **30 531 lines of DATA across 118 constants** (`FICHES_RAW` alone
is 20 538) against **4 507 lines of code across 135 functions**. That ratio is why "split the
engine into modules" is not the first move — 78 % of the volume is a fixture library that no
split makes clearer.

**The three waves, and the order is forced:**

1. **the engine leaves** — the script becomes a module under `src/engine/`.
2. **the markup leaves** — the 289 lines become shell-rendered.
3. **the bridge dies** — `window.__pont`, the state alias, `__go`/`__states` shell-side.

Wave 1 cannot be reordered around: the engine's top level calls `seedWorld()` and binds
document-level listeners, so any data extracted ahead of it would not exist when the classic
script ran. Everything must become deferred at once, or nothing can.

### What makes wave 1 safe, measured rather than assumed

- **It parses as an ES module under strict mode** — `node --check` on the extracted body.
- **Nothing in it reads parse timing** — zero occurrences of `readyState`, `DOMContentLoaded`,
  `document.write`, `currentScript`. Being deferred changes no branch.
- **The static markup carries one inline handler**, `onclick="return false;"` on the brand
  anchor, which needs no global.
- **Order is preserved by construction**: `shell.tsx` imports the engine, so the engine
  evaluates as a dependency — before the shell body that reads `window.__demarrerMoteur`.
  That is the order the engine already had.

### The one thing that is NOT free, and it is a seam

A classic script's 254 top-level declarations live in the realm's global scope, and **the
harness drives the engine through them by bare name** — `state`, `render`, `derived`, `world`,
`applyState`, `CATS`, `REGLAGES`, `REG_ETAT`, `PIPELINE`, `closeSheet`, `openFollowSheet`,
`libFiltered`, `sheetFor`, `deckOrdre`, and more, across some forty `page.evaluate` call sites.
A module's declarations are private, so every one of those rules would fail with a
ReferenceError instead of a verdict.

The engine therefore **republishes exactly the surface it already had** — no more, no less. Two
lists, and the split is measured:

- **230 by value.** A `const` cannot be reassigned, and no `function` here is either — checked,
  not assumed. (`toast` reads as reassigned only if `data-toast="…"` inside a template string is
  mistaken for an assignment; the lookbehind has to exclude the hyphen.)
- **24 by getter.** These the engine reassigns — `state` and `world` among them, which are also
  what the harness reads most. Published by value they would answer a world that no longer
  exists, silently.

Zero of the 254 names collide with a real `window` property — verified against Chrome, not
against Node's `globalThis`, which has a different surface.

**The seam narrows in wave 3, not before.** Narrowing it means rewriting the instrument that
measures the move, in the same change as the move.

## Global Constraints

- **Fidelity before deletion.** `fidelity.py --record` over every state named by
  `window.__states()`, `--host '#device'` so the comparison covers the whole phone frame —
  screens, sheets, drawer and topbar, not just `#view`. Replayed in the SAME order as recorded.
- **One mutation per amended rule.** A hold that cannot fail is not a hold.
- **The full suite is the gate**, at unchanged hold counts, plus `make check`.
- **`make check` is not optional** — `check-no-french.py` (four arms), module size, the
  extracted-CSS drift guard, the frontend typecheck.
- Everything in the foreground; the exit code is the verdict.

## Wave 1 — the engine leaves the fragment

- [x] Record all 82 states against `#device` on the pre-move tree.
- [x] Move the script body verbatim to `src/engine/legacy.js`; add the header explaining what
      it is, why it stays JavaScript, and why it publishes itself.
- [x] Append the publication block: 230 by value, 24 by getter, each list measured.
- [x] Delete the `<script>` element from the fragment, tag included.
- [x] `import "./engine/legacy.js"` in `shell.tsx`, with the comment that says why it is placed
      where it is.
- [x] `allowJs: true` in the maquette's tsconfig — the engine stays JS, and typing it would mean
      editing it inside a 35 000-line move nobody could review.
- [x] Compare all 82 states. **0/82, zero JS errors.**
- [x] Full rule suite: **49 green, 0 red**; holds 566 → 567 against `main`, and the
      only script that moves is `page_host.py` 43 → 44.
- [x] `make check` green.
- [x] Wave recorded; README rule table amended. `regions.json` needed nothing: its `source`
      names the CSS extraction's file, and the stylesheet did not move.

### An oracle defect this wave surfaced

The first comparison reported one divergence, on `acq-suivis-filtre-vide`, and it was the boot
hint toast: recorded with `.show`, compared without it. The toast's own clock is IDENTICAL on
both trees — raised 770 ms after load, hidden 5 775 ms after, within 5 ms across four runs. The
walk simply crosses that expiry between two adjacent states, and a fraction of a millisecond of
drift decides which side a state lands on.

`fidelity.py` dismissed the toast immediately after `load` — **before it is raised**, so the
click hit nothing and the toast then rode the whole walk as a floating overlay. It now waits for
the toast to exist and dismisses it then. Applied to both sides of the comparison, and the
pre-move tree was re-recorded with the corrected oracle before the verdict was taken.

The lesson generalises: an overlay on a timer is not part of any page, and an oracle that
samples it reports a divergence about a clock.

## Wave 2 — the markup leaves the fragment

The 289 lines are the app shell: `.stage`, `.device`, the splash, the login gate, the topbar and
its burger, the drawer, `#view`, `#screen`, the sheet and dialog hosts, the toast.

**It goes to `index.html`, not into React**, and the reason is the engine's boot. The engine
captures its containers at module evaluation — `view = F('#view')` and its siblings — and a
module evaluates BEFORE React has rendered anything. Markup drawn by a component would not
exist when the engine looks for it, and the shell would have to stop starting the engine before
its first render to fix that: a change to the boot contract, to move static markup. `index.html`
is the document Vite owns, it is real source rather than a fragment injected verbatim, and its
body is parsed before any module runs — exactly the order the markup has today.

- [x] Re-point `serve.py`'s login gate — **byte-identical output**, both states. It extracts FOUR CSS blocks (`login:font`, `palette`,
      `socle`, `style`) which stay in the fragment, and ONE markup block (`login:markup`,
      lines 4378–4427) which moves. So `login_page` reads two files afterwards, the way
      `design_source()` already does for the rules.
- [x] `export.py` slices the fragment at `</style>` to get « markup + JS ». That slice becomes
      empty — the third instance of this wave's recurring failure, and it must be re-pointed
      before it can report a silent green.
- [x] `startup.py` (R53) reads the fragment for declaration order and the `login:*` markers.
- [x] Record before, convert, compare: **0 / 82**.
- [x] R72 measured, not assumed — and it needed NO renegotiation: the fragment is still injected verbatim, so the rule may well
      survive untouched. Renegotiate only if the measurement says so, and record the reason.

## Wave 3 — the bridge dies

Measured on the branch, so the wave is sized before it is planned: **74 engine call sites**
cross a `window` seam — `__panneau` 41, `__ecrans` 26, `__pont` 7 (and `__routeur` 3,
`__releasePage` 1). `STATES` is **659 lines** and `applyState` 15.

- [ ] `window.__pont`, `window.__ecrans` and `window.__panneau` become direct imports. The
      engine is in the module graph now, so the seam that existed to cross worlds has no worlds
      to cross — but the shell already imports the engine, so the implementations must move to
      modules BOTH import, or the graph closes on itself.
- [ ] `__go` / `__states` reimplemented shell-side — they are the harness's driving API, so this
      is the wave where the published surface narrows and the rules that name bare globals are
      converted, one file at a time, each proven by its own suite run.
- [ ] R74 renegotiated and recorded.
- [ ] The residual debts, each named in the wave log: the deep-entry path (`relTitre`,
      `resolveTarget`), and the 240 ms dead delay on `data-suivante`.

## What SP4-fin does NOT do

**The stylesheet stays in `refonte.html`.** The spec is explicit — "The CSS contract (BLOCK 2,
extraction, `regions.json`) does not move — SP4 converts structure and behaviour at IDENTICAL
markup; the visual language stays SP5's question." `scripts/extract-maquette-css.py` reads
BLOCK 2 out of that file, and `make check` fails on drift; re-pointing it is SP5's opening move,
not SP4's closing one.

So at the end of SP4, `refonte.html` is a stylesheet and a title — the visual reference of
product-intent §15, and nothing executable.
