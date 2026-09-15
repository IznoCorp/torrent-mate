# Phase b·8 — The gestures

A BEHAVIOUR move: the engine's gesture listeners leave it. These are the swipe rows, the suggestion
card, the deck, the drag guard, `__reposPTR`, and the pull indicator's open/close block. The
arbitration shape goes to `lib/`, and the choice of which surface uses it goes to the feature
(DESIGN § 3, row « gesture listeners »; § 2.2; § 10, B-337).

## The proof FIRST

- **Rules green before and after, counts unchanged**: R55 `touch.py`, R98 `gestures.py`, R112
  `press.py`, `deck.py`, `drag.py`, and R132 `pause_verb.py`.
  - The seven gesture getters on `window` (`cardDrag`, `openCard`, `openCardDx`, `clickAfterDrag`,
    `swallowClick`, `deckDrag`, `sugDrag` — DESIGN § 6) that these rules read are published by
    `harness/publish.ts` (new file, a·2) from the new modules, under the same names. The other nine
    left in a·1, a·3 and a·4.
- **Red first, against the engine.** Each rule is run with its engine listener deleted on purpose
  and before the new module is wired, and it falls naming the gesture that did nothing. Then the
  module is wired and the rule reads green.
- **B-337's hold, written here.** In `pause_verb.py`, a REAL touch driven over CDP through the
  browser's input pipeline performs a swipe: touch start, moves, a dwell, touch end. Then ONE tap
  lands on the revealed action, hit-tested at its centre. The hold reads that the ACT HAPPENED
  (the follow moves `pending → disabled`, once), not that the row opened.
  - R132 already read this negative once. The hold keeps that instrument in the suite across the
    move: **this is not « fixed »**. The device reading remains the operator's, and the entry stays
    open until it is taken on the phone. The report says so.
- **The capture order, re-taken.** The drag guard swallows the click that ends a drag in CAPTURE,
  and `lib/verbs.ts` answers registered verbs in CAPTURE too. Which runs first depends on
  registration order. The phase reads that order and proves with the one-tap hold that only the
  drag's own click is swallowed.
- **Mutation.** With the commit made first, `scripts/mutate.sh` changes the guard's travel threshold
  to 0: the one-tap hold falls, naming the swallowed tap. Removing the deck binding makes `deck.py`
  fall.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the B-337 hold named.

## The move

- **`lib/`, domain-free (invariant 10)**: the swipe and drag arbitration, with the travel and
  direction thresholds, beside `lib/press-arbitration.ts`; the drag guard; and `__reposPTR`'s
  repositioning inside `lib/pull-gesture.ts`.
- **The features bind them**:
  - the swipe row component (a·10) binds the swipe;
  - `features/acquisition/` binds the suggestion card's dismissal and the deck;
  - the pull indicator's open/close block moves with the pull gesture, and its fixed 1 100 ms timer
    moves AS IT STANDS, because B-331 is c·5's.
- **Deleted from `legacy.js`**: the gesture block (DESIGN § 2.2), the seven gesture getters (the
  `defineProperties` block is then empty and goes), and the classes it toggled (`dragging`, `armed`, `loading`), which the variants already
  carry (a·11, a·18). `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the same commit.
- **Invariant 7.** `lib/` knows no feature, and no feature imports another.

## Gate

Per INDEX « Gates ». In addition, the oracle shows zero divergence (STOP B otherwise), and the red
readings, the capture-order reading and B-337's one-tap reading go in the report.

## Commit

`feat(maquette-l13): the gestures leave the engine and one real tap after a swipe is held`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** the words the move declares (`guard`, `travel`, `indicator`, `dismissal`, `bind`) enter `code-vocabulary.txt` in the same commit or the names are built from words already there; `lib/` names no surface (`settingsPull` → `pull`); a `ui/` swipe row receives the feature's action as a prop (layering); the `#ptr` utilities erased by `__reposPTR`'s `className = "ptr"` at every driver reset are THIS phase's to repair (ruling 59).
- **Amended 2026-09-14 (b·8 as landed; rulings 88 and 89, with two of the phase's own proofs corrected by
  measurement):**
  - **Ruling 88's line, answered before the move:** on `document`, in CAPTURE, the answerers are the tap
    registry (`lib/verbs.ts`), the press's click-swallower (`lib/press-arbitration.ts`),
    `lib/stacked-surface.ts`'s replay and — until this phase — the engine's drag guard. The guard was
    registered FIRST and said `stopPropagation`, which reaches no listener beside it: so a click ending a
    drag has fired the verb under the finger ever since the registry began. It moves to `lib/` with
    `stopImmediatePropagation` and the boot installs it before the registry.
  - **« the one-tap hold » did not exist in a form that bites, and a touch hold cannot.** After a TOUCH
    drag the browser suppresses the click itself — the engine's own comment recorded it — so a touch
    measurement is green whatever the guard does: written with touch first, NEITHER mutation moved it.
    The hold is driven with a MOUSE (`press.py`, « the click that ends a drag opens no panel » + « and a
    click that travelled nowhere still opens it ») and falls by name on both mutations.
  - **The travel threshold to 0 is UNOBSERVABLE**, and the phase named it as the mutation: the axis dead
    zone is 6px, so a drag that commits to an axis has always travelled more than 4px, and lowering the
    threshold changes nothing any hold or any reader can see. The mutation that bites is the threshold
    raised beyond reach (never armed), which is the defect the guard exists against.
  - **B-337's hold was already written** (`pause_verb.py` hold 4, « acts on the FIRST tap »): the phase
    keeps it green across the move rather than writing it. The register row stays open.
  - The `defineProperties` block does NOT go empty: `store` and `state` are the product's own published
    reads and stay. Five of the seven gesture getters were read by no rule at all.
