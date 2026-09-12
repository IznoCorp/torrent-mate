# Phase 4 — The levers (DOIT-3, DOIT-4)

The lot's subject. Pause, resume, the automatic trigger, and the path to the bound — acts, in the
host phase 3 built, over the state phase 3 draws.

## The rules FIRST, all red against `main`

`frontend/maquette/harness/levers.py` — new, three labels in one file because they walk the same
surface and a failure must say which question fell.

**R-L20-a — a lever ACTS.**

1. Each lever pressed **BY A FINGER**: `document.elementFromPoint` at the control's own centre, what
   covers it NAMED in the failure. *A `.click()` is a call and not a press: it lands on a node the
   document has, whether or not anything covers it* — the residue L21's phase 6 was repaired for.
2. **The OPERATION IS CALLED**, read on the NETWORK through `window.__mocks.answered()`. *The mock
   layer replaces `fetch`, so a hold written as `page.on("request")` is green whatever the interface
   does*, and a hold reading the SCREEN alone passes a build that messages and sends nothing — which
   is what B-383's four verbs are.
3. **The STATE MOVES** afterwards: pause becomes resume, the trigger's sentinel appears. Read on the
   state, never on a message — a toast can be right about nothing (NE-DOIT-PAS-1).

**R-L20-b — DOIT-4 on a lever.** With the lock held by a MAINTENANCE run (the precondition the
backend's own queueing needs, DESIGN § 3.2 point 3): the lever is accepted, its queueing is SAID,
**nothing answers 409**, and **nothing says « occupé »** — R124's word list reused, not re-invented
(`grep -n "REFUSALS" frontend/maquette/harness/busy.py`). And the scenario is checked REALLY busy
before any of it: a walk against an idle pipeline proves the levers work, which nobody doubts, and
nothing about the clause.

**R-L20-d — §13, no answer that is not held.** Under the `loading` phase: the bound, the lock state
and the trigger carry **no printed value** — not a zero, not a default, not « Libre » before the
read answered. *A label that cannot change when reality changes is a lie in waiting*, and a bound
printed as `0` while its read is in flight is that exact lie.

**R-L20-g's agreement half** is added to `harness/locks.py` here: pause is offered ONLY when the
pause sentinel is absent, and resume ONLY when it is present. One derivation, one question (§13).

**Seen red how**: no lever exists on `main`. Every hold fails there. **The mutations come after the
move** and each is run and recorded: make the handler message without calling (R-L20-a hold 2
falls, naming the operation); make the mock 409 the pause (R-L20-b falls); print `0` for the bound
while loading (R-L20-d falls); set the pause sentinel and leave pause offered (R-L20-g falls).

## The move

- **New file** `features/system/levers.tsx` — the four controls, rendered into phase 3's host:
  - **the bound**: a `topicRow()` showing « Tunnels en parallèle » and its value from the settings
    read, with « Régler » opening `?panel=setting:<settingId>`. **A PATH, not a control** — Q3's
    ruling: a setting is edited where settings are edited;
  - **pause / resume**: ONE state-dependent button, never both; and when nothing runs, neither —
    with « Rien ne tourne. » said, because §8 refuses a control that is simply absent;
  - **the automatic trigger**: two states, and when it is off the CONSEQUENCE in words — « Les
    téléchargements terminés n'ouvrent plus de passage tout seuls. » with the sentinel's age.
    DOIT-2: a « rien » with its reason.
- **New file** `features/system/lever-verbs.ts` — `registerVerb("pipeline-pause", …)`,
  `("pipeline-resume", …)`, `("watcher", …)` on `lib/verbs.ts`, the registry L21 built. **No line is
  added to the engine.** The verbs are English (D4) and their three ends — the markup, the
  `dataset.X`, the rules — move in ONE step.
- `features/system/queries.ts` gains the settings read for the bound. Invariant 7: Système does NOT
  import `features/settings/`; it reads the OPERATION, and a read on the contract is not a feature
  import.
- Copy in `fr.json`; `data-part` names per DESIGN § 4.1; `data-region="system/levers"` in
  `regions.json`.

States added: `levers-idle`, `levers-running`, `levers-paused`, `levers-queued`,
`levers-trigger-off`, `levers-loading`, `levers-error`.

**A state attribute is `data-x={value || undefined}`, never `data-x={value}`** — React renders
`false` as the string `"false"` and `[data-x]` then matches always, so a rule goes green while
measuring nothing (`harness/attrs.py` demonstrates it; ARM 4 of `check-markup-contracts.py` refuses
the spelling).

## Gate

`run.sh --contracts`; the three labels green with their holds counted; **every mutation run and its
falling hold named in the report** — a rule that never bit proves nothing. The oracle: Système's
four states diverge again on length, accepted with « L20 § 4.1: the levers land on Système »; every
other state at zero.

## Commit

`feat(maquette-l20): pause, resume and the automatic trigger, where their state is read`
