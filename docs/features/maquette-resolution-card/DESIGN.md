# maquette-resolution-card — the candidate card is the gesture

Register: **B-393**. Constitution: DOIT-3 (« agir là où l'on observe ») and DOIT-7 (« une porte de sortie
à chaque impasse »). A micro-wave beside no lot.

## 1. The ruling

The operator, 2026-09-11, on a phone screenshot of « Candidats ambigus » for « Lucky », verbatim:

> « Le bouton de sélection prend trop de place, c'est toute la carte média qui doit être cliquable. »

Reading A was put to him and validated (« À validé »): the whole card is the tap target, the pill becomes a
compact affordance at the button system's icon size, and the safety net is the message's « Annuler ».
The orchestrator's GO added depth, recorded in § 4: `iconButton` is created with a closed size set, the
send waits for the undo window, and three anomalies of that window are repaired, each with its own hold.

## 2. The drawing

```
BEFORE                                          AFTER
┌──────────────────────────────────────┐        ┌──────────────────────────────────────┐
│ ┌──────┐ Lucky                       │        │ ┌──────┐ Lucky                  ┌──┐ │
│ │poster│ 2017 · Série · TVDB 331747  │        │ │poster│ 2017 · Série · TVDB …  │✓ │ │
│ │      │ synopsis, clamped…          │        │ │      │ synopsis, clamped…     └──┘ │
│ └──────┘                             │        │ └──────┘                             │
│ ┌──────────────────────────────────┐ │        └──────────────────────────────────────┘
│ │          C'est celui-ci          │ │         the whole card is ONE <button>; ✓ is
│ └──────────────────────────────────┘ │         32 × 32, 16 px drawing, aria-hidden
└──────────────────────────────────────┘
```

- **The card is a `<button>`**, and that is not a styling choice: the engine's delegation answers
  `closest("button, a[data-navgo]")` and nothing else, so a `div` carrying `data-resolve` would be reached
  by no tap. Its hit area is the card itself — the full width of the list, never less than 44 px high
  (the card's own floor is far above it).
- **The affordance is decorative** (`aria-hidden`), at the right edge of `card/top`. A button inside a
  button is invalid markup and a control no assistive technology can name. It wears `iconButton()`, whose
  size set is closed: one branch, a 32 px box with a 16 px drawing — `searchClear`'s figure, the nearest
  icon control a finger already uses. A size outside the set is a compile error at the call site
  (B-315's ruling: « les boutons de l'interface doivent être des composants qui n'autorisent pas toutes
  les tailles »).
- **The sentence « C'est celui-ci » leaves `fr.json`**: `screens.resolution.pickThis` had one reader, the
  pill. The card's accessible name is what it shows — the title, the year, the provider, the synopsis.
- **Nothing else moves**: the tie note, the score shown only when it separates, the poster the candidate
  wears alone, the decision card, the manual search and « Laisser tel quel ».

### The contract, verbatim

```
data-resolve="<candidate title>"   on the element the finger taps (the card), not on a child
data-part="card"                   the card; data-part="card/top", "card/body", "card/poster" unchanged
data-part="card/pick"              the affordance, inside card/top
```

Its three ends move in one step: the markup (`resolution-cards.tsx`), the reader (`legacy.js`'s
`data-resolve` branch, unchanged — it reads `closest.dataset.resolve`, which is now the card), and the
rules that tap it (`decision.py`, `actions.py`, the new rule).

## 3. The named states

| State | What is on screen | How it is reached |
| --- | --- | --- |
| **idle** | the candidates as cards, each with its ✓ at the right edge | `__go("arr-decision")` — « Lucky », four candidates tied |
| **pressed** | the card under the finger at the base layer's pressed opacity | the finger down on any card; `base.css`'s `:where(button, …):active`, no JavaScript (D9) |
| **resolving** | the screen closes (one announced pop), the folder leaves « À traiter » and « Ça coince » at once | the tap commits; the delegation's `bridge.back()`, then the pick 240 ms later |
| **resolved-with-undo** | the page underneath, the message « Identifié comme « … » — le pipeline reprend jusqu'à la médiathèque. » with « Annuler », 6 s | the pick; the send waits (§ 4) |
| **undone** | the folder back in the queue at its place, with its « Candidats ambigus » chip; the resolution screen is NOT reopened | « Annuler » in the message, inside the window |
| **sent** | nothing changes for the reader; the layer moves the folder to the pipeline and the cache is refreshed | the window closes with no undo |

No state is added to `window.__states()`: `pressed` is a pseudo-class, and the three after it are the
consequences of a tap, which the rule drives with a finger rather than by name.

## 4. The send window

The contract has no inverse for a resolve (`continueStagedMedia` moves the folder to the pipeline and
nothing puts it back), so « Annuler » cannot undo a send that has left. The send therefore WAITS.

- **The queue gains a verb, `pick(title, choice) → undo`.** The tap takes the folder out of both cached
  lists at once (the existing optimistic `takeOutOfQueue`), the message shows with « Annuler », and the
  `POST` leaves only when the window closes — **7 s**, the message's own 6 s with a margin, on a timer the
  queue owns. No callback is added to the message host.
- **`resolve` is untouched.** « Associer » on the zero-candidate path (the manual search) still resolves
  at once, with its own sentence and no window: that path is not this wave's.
- **The producer lines in `legacy.js`**: the `data-resolve` branch calls the picking path, and
  `actionResolve` shows `toastUndo` with the undo it receives instead of `toast`.

Three facts keep the window honest, each held by its own hold:

1. **A fresh answer inside the window does not bring the folder back.** The staging and queue keys are
   invalidated by the live relay; a refetch answers the server state, which still holds the folder because
   the send has not left. The pending picks are held by title, and the retrieval is re-applied to every
   fresh answer of those two keys while the send waits.
2. **A cleared cache cancels the send.** `__reset` — every named state — and a sign-out remove the two
   queries; a send left pending would fire seven seconds later into a world that no longer holds the pick.
   A `removed` event on either key cancels it: the answer is lost, and the folder is ambiguous again.
3. **« Annuler » puts back ONE card.** Putting back the snapshot of both lists taken at the tap would also
   put back a second folder picked inside the first one's window, whose send is still pending. The undo
   re-inserts the one card at the index it held, in the lists it was in, when it is not already there.

**A reload inside the window loses the answer**: nothing was sent, so the folder returns ambiguous. That
is the safe side, and it is recorded as a backend demand — a resolve needs an inverse, « remettre en
attente » (`backend-demands-architecture.md` § 9).

## 5. The rule

A new harness file, **`harness/resolution_card.py`**, with a finger for every tap: the aim is hit-tested
at the element's own centre and the tap is `page.touchscreen.tap`, never `element.click()`.

| # | Hold | What it reads |
| --- | --- | --- |
| h1 | a tap at the centre of the card's BODY resolves the folder | the element under the finger has a `button` ancestor carrying `data-resolve` equal to the card's title, and the folder leaves the queue |
| h2 | the affordance is no larger than the icon size the system offers | the rendered box of `card/pick` against `iconButton`'s one branch, read from its declaration |
| h3 | « Annuler » in the message returns the folder to the ambiguous state | a finger on the undo; the folder back in « À traiter » with its « Candidats ambigus » chip, and no `continueStagedMedia` answered after the window |
| h4 | a screen with tied candidates offers the act on each card | every tied card is a reachable button carrying its own title in `data-resolve` |
| h5 | « Associer » still resolves at once | the manual path answers `continueStagedMedia` without waiting for a window |
| h6 | an invalidation inside the window leaves the card out | the two keys invalidated and refetched, the folder still absent |
| h7 | `__reset` inside the window sends nothing afterwards | the requests counted past the window |
| h8 | pick A, pick B, undo A: A at its index, B still out and pending | the lists and the requests, through the queue's seam — the interface shows only the latest message's « Annuler » |

**Seen red first on the unrepaired head**: the body does not resolve, the pill's box exceeds the icon
size. **Two mutations on a clean tree**, each restored with `scripts/mutate.sh`: the tap target back on
the pill alone (h1 falls), and the affordance given the pill's old size (h2 falls).

**Re-aimed**: `decision.py` R57's « one can pick a candidate » counted the sentence « celui-ci » on the
pill; it reads `[data-resolve]` on each candidate card. Its `.click()` on the first `[data-resolve]`, like
`actions.py`'s, stays true of the card; the finger's proof is the new rule's.

## 6. The two items the orchestrator's GO added

Both were ruled by the operator on 2026-09-11 and built after B-393, never interleaved with it.

### B-394 — the harness's chrome no longer covers the message

**What was wrong.** A message said while a layer is open is drawn along the top of the frame, and the
harness's two floating buttons — the design note and the states list — sit exactly there.
`styles/harness.css` declared them at `z-index: 70`, the splash's rank, so chrome that is in NO
production build was painted over the product's own answer to a verb.

**The drawing.** The buttons are 53: above the surfaces a verb is pressed from (a screen, the tab bar,
the bottom sheet), under the drawer, the confirmation and the message. The OPENED panel keeps 60 — it
is the instrument the prototype is driven with, and a message over the control one is reaching for
would be the same defect in the other direction. `ui/variants/frame.ts`'s ranked list named ONE thing
where the stylesheet declares two; it carries both entries now, each with the file that declares it.

| State | What is on screen | How it is reached |
| --- | --- | --- |
| **chrome at rest** | the two buttons at the frame's top right, over the page | any state, no layer |
| **answered under a layer** | the message along the top, painted OVER both buttons | a layer open (`sheet-user`), a message shown |
| **driving** | the states panel filling the frame, above the message | the states button pressed |

**What it costs, and it is a fact rather than a finding**: at 53 the buttons sit under the drawer and
the confirmation as well, so a drawer's scrim covers them until it is closed. No integer between 56
and 57 exists without re-spreading the frame's ranks.

**The rule, R163 (`message_above_harness.py`), was GREEN over this defect** until it lifted `inert`:
the frame marks the background inert while a layer is open, and `inert` takes an element out of
hit-testing without changing what is PAINTED. Measured both ways on the head declaring 70 — as drawn
the hit test answers the message on both buttons, inertness lifted it answers the button on both, in
two states. B-381's lesson, met on its own subject.

### B-395 — the library's selection survives the tab, and its bar stays home

**What was wrong.** `app/bottom-slot.tsx` draws the selection bar with no condition and the bar's own
reads `selMode` alone, so the selection bar sat over Acquisition — and the tab bar, hidden by that
same `selMode`, left no way back. Measured before the repair: on `acq` the bar is painted, the
deletion is under a finger, and the tab bar has no box at all.

**The drawing.** Two halves, and the ruling is that the SELECTION survives while the BAR does not
follow. The bar is drawn only while the Médiathèque is the page; nothing is cleared by navigating. The
tab bar hides only where something takes its place, which the navigation table says per page
(`slotReplacesTabBar`) — the shape `app/action-button.tsx` already reads its own condition with, and
what keeps the frame from naming a page.

| State | What is on screen | How it is reached |
| --- | --- | --- |
| **selecting** | the bar over the Médiathèque, the tab bar replaced by it | `__go("lib-selection")` — three titles ticked |
| **away** | no bar, the tab bar drawn, the selection untouched | the drawer, then Acquisition |
| **back** | the bar again, the same three titles ticked | the drawer, then Médiathèque |
| **emptied** | no bar, no selection | the bar's own cancel |

**The walk is through the DRAWER**, because the tab bar is hidden in selection mode — that is the path
a finger really has, and a rule taking a path the interface does not offer proves nothing.

## 7. The gate

Taken once, on the merged head — `origin/main` was merged BEFORE the gate, because the desktop-frame
squash re-recorded both the oracle's reference and the hold-counts baseline, and a gate taken first
would have measured against a reference that is no longer main's.

| Reading | Figure |
| --- | --- |
| `run.sh --contracts` | 18 rules and 27 repository guards, no violation |
| The full suite, `harness-hold-counts.py --compare --jobs 2` | 119 rules, no violation; 0 rule changed its hold count; 4 new since the baseline; 11 unparseable on both sides |
| `run.sh --a11y` | 87 states, 0 violations; under `data-theme=light`, 162 against a ceiling of 162 |
| `run.sh --oracle` | 87 states × 34 regions, 2 958 measurements, reference taken at `33cb259d` — no divergence |
| `make check` (`PYTEST_XDIST_AUTO_NUM_WORKERS=3`) | 11 202 passed, 8 skipped, 1 xfailed; the maquette's own 134 files / 1 374 tests; « All checks passed! » |
| `design/dist` | built |

**The hold-count tool exits non-zero, and it is the expected shape rather than a failure**: « 0 rule(s)
changed hold count » with « 4 rule(s) new since the baseline » — R161 (7 holds), R162 (17), R163 (3)
and R164 (8), which the baseline cannot know. Re-recording it belongs to the post-merge gesture, not
to this wave.

**One reading was taken twice, and the second is the one that counts.** `make check` fell the first
time on `tests/scripts/test_check_maquette_comments.py::TestTheCorpusFloor` — 353 recorded against 358
read — because the comments guard records how many files its corpus held and this wave adds five
(`lib/held-actions.ts` and the four rules). Measured rather than assumed: the record is consistent on
`origin/main` (353 = 353), so the staleness is this branch's own. It was re-taken with the guard's own
`--record`, which moved exactly one line, and no per-file count with it.

**The oracle is silent about the card, and it does read that screen.** `arr-decision` is measured and
`screen-resolution/body` is non-null there; the card itself is not one of the 34 regions, and the pill
sat in the card's SECOND grid column — 61 px wide beside the content rather than under it — so
removing it moves a width the oracle does not read.
