# Phase 19 — The close

**Reads every OPEN question the operator ruled**; the close re-reads them and reports which readings were taken.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `grep -n 'B-145' BUGS.md | head -3` → the register row (line 207) and its entry (line 10951); `grep -n 'DOIT-14' docs/reference/product-intent-map.md` → line 52, `to draw`, owner L17; `grep -n '^## ' frontend/maquette/README.md
  | sed -n 1,30p` → the README's sections (« Every state has a name » 402, « `regions.json` » 431, « What is real in here » 444); `sed -n 20,29p docs/reference/frontend-backend-demands.md` → the counters
  the close reads before and after; `python3 scripts/check-intent-map.py`, `python3 scripts/check-bug-register.py`, `python3 scripts/check-docs-cited-paths.py` (read by OUTPUT, B-346).
- **Points ≈ 8.** B-145 annotated (its reading half closed, its backend half owed) 1; the map's DOIT-14 row PROPOSED for the operator (surface `features/trackers` and the composed block, proof R-L17-a … k; `served`, or `partly`
  if OPEN 1 = B) 1; the demands register's counters before and after, per demand A–J filed 1; the README's cut table and its state list 1; the fixture register's « invented » rows counted 1; the hold counts' movement written
  down 1; `docs/reference/frontend-architecture.md`'s L17 entry reported against « Done when » 1; the report 1.
- **Found.** The close re-reads the map and the register rather than trusting what the phases claimed, and every rule's red reading against `main`.

## Red today

None.

## Move

1. Annotate B-145; propose the map row to the operator; regenerate the register and write its counters; update the README; report against « Done when » — the DOIT-14 row `served` with a rule; the declared routes
   in the contract and in the demands; the two events claimed; a refusal readable with its reason.

## Mutation

None.

## Register

B-145 annotated, never closed alone; B-144 read (L16's); B-539 left as a homonym.

## Oracle: states that diverge, declared by name

None.

## Gate

The « Before the pull request » gate of INDEX « Gates ».

## Commit

`chore(maquette-l17): close — the register, the map's proposal and the report`
