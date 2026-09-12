# Phase 7 — A run's detail, and its raw log FOLDED (B-296)

The screen the history leads to, and the one place the raw output of a passage is readable. B-296's
ruling is the whole of the drawing decision: **folded by default**, because DOIT-1 asks for clear
French and raw lines are not that.

## The rules FIRST, red against `main`

`frontend/maquette/harness/raw_log.py` — new, label **R-L20-f**:

1. **At rest the disclosure is CLOSED, and its text is NOT RENDERED.** Read as
   `offsetParent === null` on the content, **not** as « the `open` attribute is absent ». *An
   attribute's absence is a claim about markup; whether a reader can see the lines is the claim
   B-296 makes.*
2. **A tap by a finger opens it**, and the lines are then the layer's `outputTail` verbatim.
3. **`outputTail: null` draws the sentence** — « Sortie non conservée pour ce passage. » — and
   **never an empty box**. §13/§14: the interface says « inconnue », never « rien », and an empty
   log box reads as « nothing happened ».
4. **The block scrolls HORIZONTALLY and the page does not.** A raw line is wider than 390 px; DOIT-9
   allows exactly this — a code block inside its own `overflow-x` container — and refuses the page
   scrolling sideways.

R-L20-e's **detail half** is added to `harness/run_history.py`: the per-step counts drawn equal the
layer's `steps[]`, `reasons[]` are drawn as lines, and a run still running draws its remaining steps
as UNKNOWN rather than as done or not-done.

**R-L20-j** — seeded into the existing `harness/screen_addresses.py` and `harness/back.py` rather
than written as a new file: `/run/$runUid` is declared with `sys` as its parent; **opening the detail
PUSHES, asserted on `history.length`** and never on the address alone (D1b's own proof discipline —
a hold reading only the address passed two of L05's defects); **the fold ADJUSTS and pushes
nothing**; a cold `/run/<uid>` renders Système beneath it.

**Seen red how**: the screen does not exist on `main`, so every hold fails. **Mutations after the
move**: add `open` to the disclosure (hold 1 falls); answer `null` and draw an empty box (hold 3
falls); make the fold push an entry (R-L20-j's `history.length` hold falls).

## The move

- **New file** `ui/disclosure.tsx` + its variant in `ui/variants/` — a native `<details>`/`<summary>`
  behind the component API D2 asks for. **Used ONCE, here.** ⚠ Three feature files write `<details>`
  raw today (`features/acquisition/add-screen.tsx:350`, `features/media/season-list.tsx:247`,
  `features/media/panel-seasons.tsx:143`); **converting them is NOT this phase's** — a three-surface
  conversion inside a behaviour lot is exactly what « one kind of change per wave » forbids. It is a
  debt, named in DESIGN § 9 and in the report.
- **New file** `features/system/run-screen.tsx` — the head, the steps, the reasons, the folded log,
  and a `crossReference()` to Arrivées (« Ce que ce passage a laissé »). **That cross-reference is
  the LINK to L19's per-media half and this phase draws none of it** — no card progress, no
  journey, no blocked queue.
- **New file** `routes/run.tsx` — thin, as every route here is: it names `/run/$runUid` and composes
  nothing.
- `lib/addresses.ts`: `SCREEN_PARENTS` gains `"/run/$runUid": "sys"`. **That table is the single
  declaration the routes, the addressing rule and the offline guard are all held against** — a route
  with no entry, or an entry no route claims, is a violation.
- Copy under `screens.run.*`: the step names in French, the counts sentence with its parameters, the
  fold's label, the missing-log sentence, the not-found sentence and its way back (DOIT-7 — a door
  out at every dead end).
- `regions.json` gains `run/body`.

States added: `run-detail`, `run-detail-running`, `run-detail-failed`, `run-detail-log`,
`run-detail-no-log`, `run-detail-maintenance`. (`run-detail-not-found` is reached by the ADDRESS
`/run/nobody`, like `not-found` itself, and R-L20-j walks it.)

## Gate

`run.sh --contracts`; R-L20-f, R-L20-e's detail half and R-L20-j green, mutations named. The oracle:
six new states recorded; **Système's states at ZERO** — nothing on that page changed this phase — and
a divergence there is a finding.

## Commit

`feat(maquette-l20): a passage, step by step, with its raw output folded away`
