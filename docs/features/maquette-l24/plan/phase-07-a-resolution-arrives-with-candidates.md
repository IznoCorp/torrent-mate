# Phase 7 — A resolution arrives with candidates (S5, DOIT-7)

**No STOP C.**

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -rn "enqueue" frontend/maquette/design/src/features` → **nothing**;
  `grep -n "journey-requeue\|journey-rescrape" …/features/acquisition/panel-journey.ts` → lines **117, 122** — the
  sheet's two acts; `grep -cv '^\s*$'` on `panel-journey.ts`, `journey-verbs.ts`, `lib/verbs.ts` → **129, 112, 120**.
- **Points ≈ 10.** R-L24-e 3; the third act on the journey sheet, offered only on a medium identified
  automatically and not yet « rangé » (≈ 8 lines edited) 1½; its verb in `journey-verbs.ts`, registered through
  `lib/verbs.ts` (L21's registry), calling `enqueueForResolution` then opening `/resolution/$folder` (≈ 25 lines new)
  2½; `fr.json`, the act and the refusal's sentence 1; states `acq-resolution-enqueued`, `acq-resolution-enqueue-failed`
  (phase 2's seed) 2.
- **Readers.** R57 and `harness/ident.py` (186 lines) read the resolution screen's arrival from a card; R126
  (`harness/journey_verbs.py`) counts the sheet's acts — re-aimed out loud from two to three.

## Red today

R-L24-e over `acq-resolution-enqueued`: no act calls `enqueueForResolution` — `0 call(s)` on the network.

## Move

1. The act calls the operation, then opens the screen; the screen shows the candidates the call filed, or the
   pre-filled manual search when none (§ 3's invariant, DOIT-7).
2. A refused call draws its reason; the screen does not open on nothing.

## Mutation

Open the screen without the call → the network hold falls by name.

## Register

The map's DOIT-7 « unproved » half is proved; the row is the operator's to move (phase 19 proposes it).

## Oracle: states that diverge, declared by name

`sheet-journey` (the third act), and the two new states.

## Commit

`feat(maquette-l24): a doubted match is sent to arbitration, with its candidates`
