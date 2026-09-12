# Phase 6 — The history list (DOIT-6)

Système already lists the passages. What it has no notion of is a run one can OPEN, a list that is
empty, and a list that is incomplete for a bad reason.

## The rule FIRST, red against `main`

`frontend/maquette/harness/run_history.py` — new, label **R-L20-e**, its list half here and its
detail half in phase 7 (one file, and its docstring says which holds belong to which phase).

1. **A row leads to its OWN address.** Tapped by a finger, the URL becomes `/run/<uid>` — read on
   the URL, not on a screen appearing. D1, DOIT-10.
2. **The composite line is COMPOSED from the counts**, not received as a sentence. The hold reads
   the layer's counts and the drawn line and refuses a line the counts do not produce.
   `frontend-backend-demands-stream.md` § 7: the narrative is the interface's, from codes and
   parameters, never French off the wire.
3. **`degraded: true` is SAID**, above the rows it qualifies. A short list drawn as a complete one is
   NE-DOIT-PAS-5, and this is the clause's new instance.
4. **The empty list is SAID** — « Aucun passage enregistré. » — never a heading over nothing.
5. **The trigger is in WORDS.** `"watcher"` reads « la veille », `"web"` reads « depuis
   l'interface », and so on. No legend: the trigger legend is a standing refusal (D12's list).

**Seen red how**: on `main` a row is inert (no `data-run`, no address), there is no degraded notion
and no empty case. Holds 1, 3 and 4 fail outright; hold 2 fails because the line comes from the seed
pre-composed.

**Mutation after the move**: drop the degraded line (hold 3 falls); compose the line from the drawn
rows instead of the answer (hold 2 falls).

## The move

- `features/system/page.tsx`'s « Les passages » section moves to **a new file**
  `features/system/run-list.tsx` — it gains rows that are paths, three states, and a composed line,
  and a section that grows inside a page file is a page file that grows. The heading and the
  cross-reference to Arrivées are unchanged.
- `features/system/queries.ts`'s `usePipelineHistory` takes the new shape: `{runs, total, degraded}`
  with `limit`/`offset`. **`degraded` is read and drawn**; a field read and not drawn is the same
  silence the clause forbids.
- `registerVerb("run", …)` navigates to `/run/<uid>` — the verb registry again, no engine line.
- Copy: the trigger sentences, the empty case, the degraded warning.
- `regions.json` gains `system/runs`.

States added: `runs-list`, `runs-empty`, `runs-degraded`. (`runs-loading` and `runs-error` are the
orthogonal `phase` dial's, which `harness/states.py` walks for every state — DESIGN § 5 says why
the levers' two ARE named and these are not.)

## Gate

`run.sh --contracts`; R-L20-e's list holds green, mutations named. The oracle: the section changes
(three new states, rows that are buttons), so `system*` diverges — accepted with « L20 § 4.4: the
passages become paths ». Every other state at zero.

## Commit

`feat(maquette-l20): a passage can be opened, an empty list says so, and an incomplete one admits it`
