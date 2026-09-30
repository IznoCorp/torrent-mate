# Phase 5 — Système and the run screen

## What changes

1. **The runs list is `FactRows`** (D.1 #13, B-576 — the operator's « tableau coupé sur la droite »): label « when ·
   trigger », value the outcome CHIP, sub-line « what it did », `target: { run }`, `part: "runs/row"`; `runRow`,
   `runHead`, `runLine` die (`features/system/variants.ts:11–19`). The UA bevel goes with the `<button>`.
2. **The outcome is the chip** on the list AND on the run screen (D.1 #5): `runOutcome`, `runStepStatus` → one tone
   map shared by both (`features/system/run-screen.tsx:190`); « arrêté » / « interrompu » read one word (B.4).
3. **The raw log wraps** (OPEN 10 = A, B.5 R13): `runLog` `whitespace-pre-wrap`, breaking anywhere; the `tabIndex`
   that existed for the scroll goes; `raw_log.py`'s hold « the log block is the one allowed to scroll sideways » is
   RE-AIMED to « the log wraps, nothing scrolls sideways », said out loud.
4. **« actif / inactif »** (D.1 #2, OPEN 1 = A): the watcher RENAMED by what it does (the word chosen at the phase's
   opening, never « pipeline » nor « passage »), ONE row in the levers block — `FactRows`, the chip at the row's end,
   its button beside; the locks' watcher row goes; ONE pair of `fr.json` keys « actif / inactif » (success / danger)
   replaces `triggerOn/Off`, `watcherOn/Off`, `sentinelOn/Off` — « en pause » kept for the paused pipeline.
5. **The state words leave the seeds** (OPEN 2 = A): the 24 `value` words of `services`, `schedulers`, `disks`,
   `index-health`, `dependencies` become state codes; ONE code → word and code → tone map; one `fr.json` word per code.
6. **Its topic row** → `ui` `TopicRow` (`features/system/page.tsx:132–138`); **runs empty** → `emptyNote`
   (`run-list.tsx:161`, D.1 #10); **the veille's running dot** → `liveDot` in `liveStrip` (`watch.tsx:81`, D.1 #7);
   `features/system/variants.ts` imports `ui/cva` (D.1 #16).

## Acceptance — each item's rule read RED on the old code, then green

- R-conformity-a: the owed entries `bevel · runs/row`, `overflow · run/log` leave the list, green on every Système
  state (built by script: page `sys`, `run-*`).
- R-conformity-e (new, `harness/on_off.py`): on `levers-idle` and `levers-trigger-off` the watcher row's state is the
  chip « actif » / « inactif » at the row's end, read from the chip; the page draws the fact ONCE.
- R-conformity-f (new, `harness/state_words.py`): every state word Système draws is a `fr.json` value, one per code.
- R-conformity-h (new, `harness/empty_place.py`): on `runs-empty` the empty part is `emptyNote` (extended in 9).
- Re-aimed by name: `raw_log.py`, `levers.py`, `locks.py`, `run_history.py`, `machine.py` (the readers of the moved
  parts), each re-aim said in the commit body.
- The oracle accepts BY NAME the visible changes: the runs list's edge and chip, the renamed watcher row, the removed
  locks row, the unified words, the wrapped log, the veille's dot.

## Commit

`feat(maquette-conformity): Système — the runs as fact rows, one on/off pair, its words from the vocabulary`
