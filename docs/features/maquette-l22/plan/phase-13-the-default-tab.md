# Phase 13 — The default tab

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The four `acqTab: "now"` write sites: `app/arrival.ts:21` (the initial value),
  `features/acquisition/verbs.ts:109-111` (`fillLandingDoor` — « ARRIVING AT THIS PAGE OPENS ITS FIRST TAB, whoever asked
  for it »), `verbs.ts:73` (the `complete` verb, a deliberate destination), `add-screen.tsx:117` (`toFollows()`, deliberate).
  Walks that arrive at Acquisition without naming a tab:
  `git grep -l -E 'data-page=.?"?acq|nav button\[data-page=.acq|\[data-go=.acq|PAGE_PATHS\["acq"\]|HOME\b|/acquisition"|"acquisition"' -- 'frontend/maquette/harness/*.py' | wc -l`
  → **16 files** (of them `journey.py` 19 references, `panel.py` 5, `scroll_keeps_place.py` 2, `screen_addresses.py` 2,
  `add_footer.py` 1). At rest both scenarios hold a `blocked` card (`blocked.json` 1, `stuck.json` 2), so **every one of
  those walks lands on « À traiter » after this phase**.
- **Found (2026-09-26).** **R128** (`seeds_at_rest.py`, « the boot alone fills the arrivals ») asserts that a takeable
  arrival « is DRAWN » with no named state asked for: after this phase the boot opens on « À traiter » and the takeable
  card lives on « En cours ». R128 is re-aimed WITH the rule (DESIGN § 5.1). The phase's first act is to RUN the 16 files
  and name the ones that fall.
- **Points ≈ 13.** The default derivation and the two DEFAULT sites ≈ 20 lines 3; R-L22-a with its mutations 3; four
  states (`acq-entry-todo`, `acq-entry-clear`, `acq-todo-loading`, `acq-todo-error`) 4; the rules that fall, re-aimed at
  ½ each — **budgeted for six** (R128 and five of the 16) 3. **The pre-cut clause applies** (INDEX): if more than six
  fall, the phase reports it as STOP D with the list and the steward cuts the re-aims into a phase of their own.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: the four `acqTab: "now"`
  write sites (`app/arrival.ts:21`, `verbs.ts:109-111`, `verbs.ts:73`, `add-screen.tsx:117`) and the **16 files** that arrive at
  Acquisition without naming a tab — identical. **Points 13 → 13; OPEN 1 (ruled) leaves the rule whole and moves one sentence.**
  The row now reads « Suivis · En cours · À traiter · Découvrir », so the tab this rule may open by default is the THIRD, and
  `fillLandingDoor`'s comment (`verbs.ts:103`, « ARRIVING AT THIS PAGE OPENS ITS FIRST TAB ») stops being true of the value it
  writes (`"now"`, the second tab): it is rewritten in the same commit as the code it describes, because a comment that outlives
  its decision is read as current. The one harness site that reads the DOM order (`journey.py:117-118`, « the first tab whose
  value is not `now` ») answers `follows` whatever the default is, and is run by name with the 16.

Ruling 10: the tab opened by default is « À traiter » when it is not empty, otherwise « En cours ». **B-515 is read
here**: `acq-todo-error` carries the same retry trait as `arr-error` (no pending or busy sign) — whether the new tab
reproduces it is SAID in the report (DESIGN § 6.1).

## Red today

**R-L22-a — the default tab** (DESIGN § 5): a cold entry on `/acquisition` with no `tab` → « À traiter » open when its
count is not zero (`acq-entry-todo`), « En cours » when it is zero (`acq-entry-clear`); an explicit `?tab=follows` wins
over a non-zero count; **while the count is unread no tab is selected and none is printed** (`acq-todo-loading` drives it).

**Red against `main`**: the landing door opens « En cours » whoever asked.

## Move

The derivation replaces the two DEFAULT sites (the initial value and the landing door) and leaves the two deliberate
destinations alone; it is written in a NEW file (`features/acquisition/queries.ts` is 326 lines against a ceiling of
400). The four named states.

## Mutation

With the commit made first: derive the default from a constant → R-L22-a falls; invert the comparison → it falls; choose
before the count lands → the « nothing selected while unread » hold falls.

## Register

B-515 (read for `acq-todo-error`, above).

## Oracle: states that diverge, declared by name

**None expected** — the states reach their tab explicitly. A named state that diverges is STOP A.

## Gate

Per INDEX « Gates »; the 16 files are run by name at the opening and again at the gate.

## Commit

`feat(maquette-l22): Acquisition opens on « À traiter » when something waits`
