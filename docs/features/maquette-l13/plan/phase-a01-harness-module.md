# Phase a·1 — The harness module

A CONVERSION: the driving seams, the 87 named states and the ≡ panel leave the engine for `design/src/harness/`, and drive
exactly what they drove before (DESIGN § 4.1; § 3, rows 1–5).

## The proof FIRST

- `states.py` drives every id `window.__states()` answers, the same count before and after (DESIGN § 2.1): a count that
  moves is a finding, since nothing here draws. The oracle: zero divergence on every state.
- `python3 scripts/harness-hold-counts.py --compare`, with **`failed` read FIRST** (B-291), then the per-rule movement. None
  is expected. The rules that read `__reset`, `__measure` and `__blocked` (DESIGN § 3, row 3) and the rule lines that call
  `applyState(` or read `state.` (DESIGN § 2.4) keep their counts, because `harness/drive.ts` (new file) publishes those
  names unchanged. If a rule's text still has to change, it is RE-AIMED: « count unchanged » goes in its docstring and the
  re-aim is named in the commit body.
- **The lift-out, re-taken once** (DESIGN § 4.1; no guard is added). Build with `__MOCKS_BUILT_IN__` on and then off, record
  both byte sizes, and search the OFF build for the harness's own strings: `__etatsDetailles`, one named-state id, `hscen`.
  Zero hits is the proof that the switchover excludes the module. The figures go in the report, not into this plan.
- **B-352's refusal, replayed.** Add one state to `harness/states/system.ts` (new file), read
  `python3 scripts/check-frontend-boundaries.py --arm size` exit 0, and remove the state. That reading closes the entry.
- The ≡ panel is tapped by no rule (DESIGN § 1, Q2). Its proof is the operator's hand on the design host, and the report
  says so rather than claiming a hold.

## The move

- **New files** under `design/src/harness/`:
  - `harness/drive.ts` (new file): `__go`, `__states`, `__etatsDetailles`, `__reset`, `__measure`, `__blocked`, the
    `__navEchec` reset, and the published `applyState` and `state`.
  - `harness/states/<surface>.ts` (new files): acquisition, arrivals, library, media, settings, system, maintenance, entry,
    relay. Each stays under 400 non-blank lines, and the table is split by the surface a state drives, never by count.
  - `harness/panel.tsx` (new file): the ≡ panel (Q2 reading i), the `#notesBtn` and `#scenBtn` handlers, and the hint
    dismissal (`E:31629–31649`). Its five verbs `hclose`, `hgo`, `hscen`, `hphase` and `htmdb` are registered there with
    `registerVerb`. The registry answers in capture (DESIGN § 2.3), so their engine branches become unreachable and are
    deleted in this commit.
  - `harness/index.ts` (new file): one `installHarness(store, queryClient)`.
- **Reading (ii) of Q2**, if ruled: the panel component and its five verbs are not created; nothing else changes.
- **The latch crosses by a verb.** The engine exports `drivenWithoutHistory(run)`, the one addition INDEX allows; the driver
  calls it, and no product module reads harness state. Phase a·3 moves the verb with its three readers.
- **`app/shell.tsx` does not grow** (DESIGN § 4.1). `import "../engine/states.js"` is REPLACED by the harness import. The
  call `if (__MOCKS_BUILT_IN__) installHarness(…)` takes the place of the side effect, which needed no call.
- **Deleted**: `engine/states.js`. From `legacy.js`: `__recordStates` (it dies, its only caller is gone), `applyState`, the
  entry forwarders, `__go`, `__states`, `__etatsDetailles`, `STATES`, `__reset`, `__measure`, `__blocked`, `openHarness` and
  `closeHarness`. `__pages` moves to `harness/drive.ts` over the navigation table's ids (DESIGN § 3), for `drawer.py:108`
  and `page_host.py`, counts unchanged.
- **Still in the engine**: `hideLayers`, until a·3; the driver's `applyState` calls it through the engine's export.
- **B-071**: the notes toggle moves AS IT STANDS (DESIGN § 9.10). Nothing is repaired, and the steward closes the entry.
- **The size ledger.** In `scripts/frontend_size_ledger.py` the `engine/states.js` entry is removed, and `engine/legacy.js`
  is re-recorded DOWNWARD in the same commit.
- **The tree arm.** `harness/` is a new top-level bucket. The phase re-takes the `tree` arm's bucket table in
  `scripts/check-frontend-boundaries.py` before it creates the directory. A refusal there is STOP D.
- **L20's plan.** Its phase 2 creates `design/src/states/system.ts` (new file, L20's plan), which loses its subject here
  (DESIGN § 9.3). Re-targeting it is the steward's job; this phase does not touch L20's plan.

**Amended 2026-09-13, on a measurement the design missed** (the steward's ruling of the same day). `applyState` is PRODUCT code as well as the harness's: the engine's back handler restores a page through it, under the latch, on a popstate onto a nav entry (`grep -nE "applyState\(" frontend/maquette/design/src/engine/legacy.js`, inside `onEngineBack`). So it STAYS in the engine, exported, and `harness/drive.ts` imports it and publishes `window.applyState` for the seven rules that call it. This makes VOID « the published `applyState` » in the move's `drive.ts` item, « `applyState` » in its deleted list, and DESIGN § 3 row 4's home for it: the product never depends on the instrument. Phase a·3 moves it with `onEngineBack`. **The same holds for the `window.state` getter**, which DESIGN § 6 sends out in a·1: the engine reads the bare `state` itself (the boot's `Object.assign(state, …)`), so the getter stays published by the engine at evaluation — moved to the harness install, which runs after the boot, the boot threw « state is not defined » and the contracts tier fell on fifteen checks.

## Gate

Per INDEX « Gates ». In addition: `--arm size` no longer lists `engine/states.js`; the lift-out figures and the B-352 replay
are in the report. STOP D if one surface's states cannot fit under 400 non-blank lines in one file.

## Commit

`refactor(maquette-l13): the driving seams and the named states leave the engine for the harness module`

## Amendment — 2026-09-13, the operator's ruling on Q2

**Q2 is ruled (B): the ≡ harness panel dies.** The operator, verbatim: « Je ne l'utilise pas ! À la base
il était fait pour le contrôle des agents, pour vérifier facilement un état, pas pour moi. » The named
states stay reachable through `window.__go`, and the dials through the console. This phase is not
reopened: the panel landed in `design/src/harness/panel.ts`, and it leaves in ONE later commit of L13a,
**a·18-bis**, before a·19's full gate.

What a·18-bis deletes: `harness/panel.ts` and its five verbs (`hscen`, `hphase`, `htmdb`, `hgo`,
`hclose`), the « ≡ » button's markup, every `styles/harness.css` rule only the panel used (with any R80
pair it removes named), and the i18n keys only the panel read.

**« Tapped by no rule » above is not true**, measured on 2026-09-13 before any deletion
(`grep -nE "notesBtn|scenBtn|harness/bar|harness/panel" frontend/maquette/harness/*.py`):
`hiding.py` reads `#notesBtn`; `message_above_harness.py` reads `[data-part="harness/bar"]`,
`[data-part="harness/panel"]` and `#scenBtn`; `chrome.py` reads `[data-part="harness/bar"]`; `audit.py`
and `dest.py` exclude both parts from their sweeps. **Those readers go with the panel, in the same
a·18-bis commit** (the steward's ruling, 2026-09-13): the holds of `hiding.py`,
`message_above_harness.py` and `chrome.py` whose subject is the panel are removed with it, each named
in the commit body with the hold count it takes away, and the two exclusions in `audit.py` and
`dest.py` are dropped. a·18-bis runs the grep rule for every name it removes over `harness/*.py` before
its gate.

**Ruling 31 — 2026-09-13, the steward, on the grep re-taken that day. It makes VOID the paragraph above where they differ.** The operator's word kills the ≡ PANEL and nothing else. It goes: the panel half of `harness/panel.ts` and its five `h*` verbs, the « ≡ » opener `#scenBtn`, the `.hpanel` rules wherever they live (they are in `styles/legacy.css`, not `harness.css`), the i18n keys only the panel used, `scripts/markup_verbs.py`'s five `registerVerb h*` answers, `check-markup-contracts.py`'s `data-hscen`/`data-hphase` contract and its two test assertions, and `hscen` in `code-vocabulary.txt`. It STAYS: `[data-part="harness/bar"]` (the bar keeps the notes button) and `#notesBtn` « Notes de conception » with its toggle code — a reader's control, not an agent's, which the ruling never named. So `hiding.py` and `chrome.py` (R51) do NOT move; `message_above_harness.py` drops its `harness/panel` and `#scenBtn` reads and keeps `harness/bar`; `audit.py` and `dest.py` drop `harness/panel` from their exclusions and keep `harness/bar`. **ORDER**: the commit runs BEFORE a·18 and is renumbered **a·17-bis**, because a stylesheet cannot die while a component still needs its `.hpanel` rules; a·18 then deletes a file nothing reads.

