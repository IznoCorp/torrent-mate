# L21 — where the wave stands, for whoever picks it up

Written at 54 % context by the session that opened the lot. Read `BRIEF.md`, `DESIGN.md` and
`plan/INDEX.md` first — this file says only what is TRUE NOW and what the plan does not.

**Branch** `feat/maquette-l21`. **Version** 0.98.74. **Base** `origin/main` at `7fecb0258`;
main has since moved to `ae1b8de48` (PR #570) and **this branch has not merged it yet**.

---

## 1. Done, with the reading that proves it

| Phase                               | State           | Proof                                                                                              |
| ----------------------------------- | --------------- | -------------------------------------------------------------------------------------------------- |
| 1 — the contract                    | **DONE**        | 3 operations + types + register together; § 2c added; mocks answer and MOVE state                  |
| 2 — the season grab (B-301)         | **DONE**        | R125 **16 holds, no violation**; mutation falls 6 holds naming the right defects                   |
| 3 — the journey's two verbs (B-302) | **DONE**        | R126 **16 holds, no violation**; red first at 9 violations; mutation falls exactly the stages hold |
| 4 — the five acts                   | **not started** | —                                                                                                  |
| 5 — the release take                | **not started** | —                                                                                                  |
| 6 — the pastille + R124             | **not started** | —                                                                                                  |
| 7 — B-313 + close                   | **not started** | —                                                                                                  |

**Gates on the current head**: `run.sh --contracts` → 18 rules + 27 guards, no violation. Oracle →
87 states × 34 regions, 2 958 measurements, **no divergence** (phase 1; not re-run since the
button landed — **expect and ACCEPT divergences on the states whose seasons panel or journey panel
gained a button**, D8, each with B-301 / B-302 as its reason). `tsc -b`, vitest 104, build,
`check-no-french` 15 arms, `check-mock-seeds` 7 arms, `check-markup-contracts` 87 tests: clean.

---

## 2. What this wave built that the plan did not foresee

**`lib/verbs.ts` — a tap registry, and phase 4 depends on it.** B-302's verbs had NO reader: a
panel action emits only `data-*`, `ui/panel` attaches no handler by contract, and every such
attribute was read by the dying engine — so a verb that never existed there needed a branch in
`legacy.js`, which D5 forbids. The registry is domain-free (`registerVerb(name, act)`) with one
delegated listener in capture, `stopPropagation` on a match so the engine cannot also act.
**Phase 4 moves the five acts onto this same registry** rather than inventing a mechanism then.

**`mocks/answered.ts` — the record a rule reads a CALL from.** See § 3.

---

## 3. The instrument facts that change how you write every remaining rule

1. **A mocked call reaches NO network.** `mocks/index.ts` replaces `globalThis.fetch`. Measured: a
   verb that demonstrably ran produced **zero** Playwright request events with an unfiltered
   listener attached. **Any hold written as `page.on("request")` or `page.on("response")` over a
   mocked operation is green whatever the interface does.** Read the call on
   `window.__mocks.answered()` instead.
   ⚠ **`busy.py`'s « no mutation was answered 409 » is vacuous for this reason.** It is phase 6's
   to repair, and until then R124's green has never included that clause.
2. **The message is NOT in `#toast`.** That element is the dying engine's; the message layer is
   React. Read `window.__toast.read()` — `{ message, shown }`, published for rules.
3. **`window.__go` RE-SEEDS the mock layer.** Put the machine to work AFTER driving the state, or
   the act lands against an idle layer while the « pipeline is busy » hold stays green over a
   reading already discarded.
4. **A panel producer has NO OBSERVER.** `invalidateQueries` refetches what is being observed and
   marks the rest stale; a producer is a function from the cache to a descriptor. Use
   `refetchQueries` or the sheet does not move.
5. **`mutate.sh` takes a rule PATH, not a name** — a bad path prints « NO RULE FELL. That is the
   finding. » See B-330. It cost a false finding that was nearly written down.
6. **The heavy floor**: `HEAVY_FREE_FLOOR_MB=3584` is approved by the steward for the mutation and
   the contracts tier at `TM_HARNESS_JOBS=1`; the full suite waits for 4096.
7. **A PUSH ON THIS REPOSITORY IS A HEAVY RUN** — the pre-push hook runs the whole pytest suite at
   `-n auto` (8 workers on 8 cores). Always
   `PYTEST_XDIST_AUTO_NUM_WORKERS=3 … sh scripts/heavy.sh l21 git push …`.
8. **Read the PUSH's own output, never the task notification's exit code.** Two pushes reported
   « exit code 0 » from the wrapper while git had refused the ref. `git ls-remote --heads origin`
   is the only proof.

---

## 4. Corrections to the brief, already written into it on this branch

- **§ 4's `busy.py` paragraph**: the repair it orders LANDED inside L19 (`raise_by_finger`,
  `9fa13da57`). L19's report § 6 row 16 records it and its § 9 says it was left undone — § 9 is
  the stale half. What remains is the ACTION click at `busy.py:172,222`, not hit-tested.
- **§ 2's « one action per season row printed `to_grab` »**: there is **no `to_grab` cell anywhere
  in the fixture**. `epState` colours a hole by the FOLLOW's status. The mark is
  `[data-part="season/missing"]`, and the fixture holds exactly ONE subject: **Silo, season 3,
  7 aired, 6 held**.

---

## 5. Register numbers, and they are not the ones `--next` says

The steward and a micro-wave hold blocks. **Your next free is B-351+ and R128+.** B-329, B-330 and
B-350 are this branch's. `--next` on `main` disagrees with everyone until the merges — say so in
the pull request rather than renumbering.

Filed by this wave: **B-329** (the backend's generated contract does not declare the 409 its route
raises — so no diff can compute that demand, which is why B-302 keeps a HAND-written one),
**B-330** (`mutate.sh` cannot tell a typo from a rule that does not bite), **B-350** (a paused
series is dimmed and says nothing while a paused film says « en pause » — operator-reported,
measured, not this lot's doing).

---

## 5b. What phase 3 OWES, and it is phase 4's first task

**The registry now has its rule — LANDED, 2026-09-06.** The steward approved `lib/verbs.ts` on two
conditions: the decision recorded (DESIGN.md § 3.1d, with the alternatives refused) and a contract
rule refusing a `data-*` verb that markup emits and no feature registers, seen red once on purpose.
Both are done. The rule is **ARM 7** of `check-markup-contracts` (`scripts/markup_verbs.py`, the
emitting side parsed by `harness/panel_verbs.mjs`); it reads 34 verbs over 33 action targets, all
answered, and it was seen red by removing the `journey-requeue` declaration on the real tree — exit
1, naming `panel-journey.ts:92`, back to 0 on restore. **By hand, not through `mutate.sh`, which
cannot judge a guard (B-273).** Detail and the two shapes it had to be taught: DESIGN.md § 3.1d.

**And one correction to carry**: the phase-3 commit calls `ui/variants/controls`'s `actionButton`
an ORPHAN. It is not — it has two users (`app/not-found.tsx`,
`features/releases/releases-screen.tsx`) and both compose it with `cfoot`, which paints. It is a
LAYOUT variant; the defect was using it alone. DESIGN.md § 3.1e carries the correction; the commit
message cannot be edited and is wrong on that one sentence.

---

## 5c. OPEN, live, and unexplained — the operator's 10:36 reading

**« le bouton récupérer saison 3 de Silo ne semble rien faire, en tout cas il se passe rien
visuellement »**, on the design host on his Android, with Silo's panel showing « 6/7 · 1 manquant »
and the button drawn as a plain `sact`. **This is not closed and must not be assumed closed.**

What was RULED OUT, each by a reading:

- **Not a stale build.** The served bundle is `dist/vite/index-DHK4FCS-.js`, built **10:33**, three
  minutes BEFORE his reading, and `grep` finds both `grab-season` and `journey-requeue` inside it.
- **Not the mock layer being off.** `__MOCKS_BUILT_IN__` is `JSON.stringify(true)` in
  `vite.config.mjs:161`, so the layer is installed in that build; if it were not, the prototype
  would carry no Silo at all.
- **Not the press arbitration's swallow, as far as it can be reasoned.** `swallowClick` is armed
  only by a long press and is cleared by the FIRST click after it, whatever the distance — so a
  later, separate tap on the button is not the one it eats. *Reasoned, not measured — do not treat
  this as settled.*

What is TRUE on the harness: R125 taps that button at its hit-tested centre and the act fires — the
operation is recorded, the follow moves `pending → acquiring`, the message reads back through
`window.__toast.read()`. **And that is exactly the limit**: `page.touchscreen.tap` is a synthetic
touch with no movement and no dwell, so it cannot reproduce a finger, and **it therefore cannot
rule out the class of defect B-337 already documents** — a first tap that does nothing on a real
phone while every synthetic one works.

**Phase 4 owes a measurement on the real path**, not another synthetic tap: B-337 and this reading
are plausibly the same defect, and B-337 is already ratified into this lot.

---

## 6. What phase 4 must read before it starts

- **B-339** and **B-337** on `main` (ratified into L21 by the operator): a disabled panel action is
  drawn like an enabled one (`.sact` has no `:disabled`) — the queued state has no not-available
  form to inherit; and a swiped-open follow card ignores the FIRST tap on its revealed action,
  whose actions ARE `pause` and `remove`, this phase's verbs. **Measure with a real touch which
  listener eats the click**; if it is the swipe rather than the tap path, it goes back to L13 and
  the steward is told.
- **Merge `main` into this branch first** — it has moved by a whole pull request.
- **B-316 is RULED**: a TAP opens the media sheet, a LONG PRESS opens the suggestion panel,
  reusing L14's gesture, and the two attributes stop sharing a node. **B-315 (a) is now in
  scope** — the button's size, at the catalogue's scale for a secondary action in a feed footer.

---

## 7. The one thing not to repeat

Every defect this wave found was found by asking what a hold actually READS — never by a gate. The
rules were green, the guards were green, and the readings were empty: a network with no traffic on
it, a toast element nothing writes to, a query nobody observes, a mutation tool answering the same
sentence whether it measured something or nothing. **Ask it of every hold you write.**
