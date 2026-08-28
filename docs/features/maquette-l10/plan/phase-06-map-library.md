# Phase 6 — The map: Médiathèque and Média

## Steps

1. `features/library/live.ts` and `features/media/live.ts`, same shape as phase 5.
2. Médiathèque's key carries the query, the category, the sort and the reversal
   (`["/api/library/items", query, category, sort, reversed]`). **A prefix invalidation covers
   every variant, and here that is right** — a dispatched item changes the underlying set for all
   of them. It is written down as a deliberate width, with the reason, because an unargued wide
   key and a correct wide key look identical in a diff.
3. Média's sheet is keyed per identity (`["/api/media", provider, identifier]`). An event about
   one title must not refresh another's sheet — the narrowest case in the wave and the one that
   proves the fan-out rule is doing something.

## The rule

R91 extended with these rules' holds, and one deliberately adversarial hold: emit an event about
title A and assert title B's cache entry did **not** move.

**Mutation**: key the invalidation on `["/api/media"]` alone. The hold must fall naming B's entry,
which is the "nothing else" clause catching a change that every type in the codebase agrees with.
