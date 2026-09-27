# Phase 37 — The death of Arrivées

**Numbered 33, then 35, then 37, on 2026-09-27** (was 25; the triage's F51). **Carried at its opening, from the coherence triage (`review-archive/coherence-2026-09-27-triage.md` § B; texts in `coherence-2026-09-27.md`)**: F8 — the bar reads at
THREE after Arrivées dies (Acquisition · Médiathèque · Découvrir; 19-bis-a put Découvrir in the bar), not two, and this
phase's mutation is re-written so it can fall; a new RULINGS entry records it.

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `ls frontend/maquette/design/src/features/arrivals/` → 11 files, 1 486 non-blank lines at the opening of the
  lot; after phases 2 to 24 what remains is `page.tsx` 311, `arrival-card.tsx` 124, `variants.ts` 64, and the leftovers
  of `queries.ts`, `types.ts`, `verbs.ts` (`pipe`) and `live.ts` — **re-taken at this opening** (STOP D if a file the
  design says is gone is still read). `routes/arrivals.tsx`; `app/navigation.ts:128` (the `arr` row);
  `lib/addresses.ts:23` (`PAGE_PATHS.arr`); `app/router-tree.tsx:14,69`; `app/live-updates.ts:29,79`;
  `app/panel-contributions.ts:32`; `app/shell.tsx:73`; `harness/states/arrivals.ts` (6 states left after phase 3);
  `harness/arrivals.py` (R66). `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(len(d['screens']['arrivals']), len(d['verbs']['arrivals']))"`
  → `36 7`; `navigation.pages.arr`. **The residual grep, before the first deletion**:
  `git grep -n -E 'features/arrivals|screens\.arrivals|"arr"|arr-|arrivalsBadge|ArrivalsPage' -- frontend/maquette scripts` must
  read ONLY the files this phase deletes.
- **Points ≈ 12.** Ten files deleted at ½ = 5; the row, the path, the route registration, the live-updates and
  panel-contributions lines, the shell's lookup ≈ 8 lines edited 2; `fr.json` (`screens.arrivals` 36, `navigation.pages.arr`,
  `verbs.arrivals.pipe*` 4 and the three survivors renamed to `verbs.acquisition.*`) 2; R-L22-o with its mutations 3.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: `ls
  frontend/maquette/design/src/features/arrivals/` → 11 files, 1 486 non-blank lines; `screens.arrivals` 36 keys and
  `verbs.arrivals` 7; the residual grep answers on 55 files at the lot's opening (it must shrink to the files this phase deletes
  before the first deletion) — identical. **Points 12 → 12; OPEN 5 and OPEN 6 (ruled A, A) moved what the phase says, not what it
  costs**: `/arrivals` needs no code (with the route gone it is an unknown address, drawn by `app/not-found.tsx`, and R68 —
  `harness/address.py` — already reads that an unknown address breaks nothing), and the launch bar's two acts die here with
  `data-pipe` and `verbs.arrivals.pipe*` (the four keys are counted above). The bar is read again by R-L22-s at TWO buttons, a
  re-run of the rule phase 19 wrote, at no new cost.

Ruling 2: the page dies, and its batch launch bar with it. **OPEN 6 was ruled A (§ 7.2): « Lancer » and « Arrêter » die with the
bar and this phase adds nothing in their place** — it deletes the bar's `data-pipe` emitters (`git grep -n -E 'data-pipe([^l]|$)'`,
which keeps Système's `data-pipeline-pause` and `-resume`, the levers, out) and `verbs.arrivals.pipe*`. **OPEN 5 was ruled A:
`/arrivals` is an unknown address like any other, the not-found page, with no redirect.**

## Red today

**R-L22-o — Arrivées is gone**: no `arr` row in the bar or the drawer; no `data-go="arr"` in the source; `screens.arrivals`
absent from the resources; the shipped source names no `features/arrivals`; **the address `/arrivals` draws the not-found page and is
NOT redirected** (the address stays as typed; OPEN 5, ruled A); and the bar, re-read by R-L22-s, draws two buttons of half the bar
each, no empty slot.

**Red against `main`**: the page, its row and its keys exist.

## Move

Delete the files; remove the row, the path, the route, the registrations and the lookups; delete the 36 keys and the
page's name; rename the three surviving `verbs.arrivals.*` keys under `verbs.acquisition.*` **through
`scripts/rename-identifiers.py`** (a value rename: its read-back is skipped, so the diff is re-read and the suite re-run).
**Run the residual grep again after — zero matches.**

## Mutation

With the commit made first: re-add the row → R-L22-o falls; add a redirect from `/arrivals` to `/acquisition` → its address hold
falls; put `inBar: true` on a third row → R-L22-s's tiling hold falls.

## Register

B-515 and B-531 die with the page; B-037 and B-038 die with `arrivals.py`. Their entries are amended by phase 39, not here
(`BUGS.md` is named, not edited, by this design; the lot edits it at its close).

## Oracle: states that diverge, declared by name

**None** (a dead page's code goes). The six `arr-*` records leave the reference in phase 38. Any divergence on a state that
still exists is STOP A.

## Gate

Per INDEX « Gates », plus the residual grep at zero (the standing check after any deletion), the design's `tsc -b`,
`eslint`, `vitest`, and `python3 scripts/check-frontend-boundaries.py`.

## Commit

`refactor(maquette-l22): the Arrivées page, its route, its launch bar and its strings are removed`
