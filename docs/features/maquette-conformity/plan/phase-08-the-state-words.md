# Phase 8 — Système's state words leave the seeds (the operator's OPEN 2 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q2, verbatim « A »):
Système's state words leave the seeds; the data carry a state CODE, the app takes the word from `fr.json` — ONE word
per state, visible to the vocabulary guard, so the four words for « reachable » become one. The backend demand (the
engine sends codes) is the orchestrator's to record. **Not a pure conversion** (the unified words are visible): the
oracle accepts them BY NAME.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -o '"value": "[^"]*"' -g '*.json' frontend/maquette/design/src/mocks/seeds/{services,schedulers,disks,index-health,dependencies}.json
  | sort | uniq -c` → **24** rows over five seeds: « à l'heure » 7, « en ligne » 5, « de la place » 3, « aucune » 2,
  and « réussi », « joignable », « disponibles », « connecté », « bientôt plein », « à nettoyer », « aucun disjoncteur
  ouvert », « la file est vide », « le relais d'événements répond », « rien ne reste à propager » once each.
- **Points ≈ 14.** 24 seed rows `value` → `state` code (≈ 24 lines edited, 5); the code → word and code → tone map,
  once (≈ 20 lines new, 2); the Système page reads the code (2); the mock contract's field (1); `fr.json` keys, one word
  per state (1); R-conformity-f (3). Above 15 at the opening: the sentence-shaped values (« la file est vide » …) are
  cut into their own phase, the orchestrator told.
- **Readers.** `machine.py` (R67) reads the Système lists against `pm2 jlist` and the engine — re-read at the opening;
  `levers.py`, `locks.py` read other rows.

## Red today

R-conformity-f over `system` and `system-error`: every state word Système draws is a `fr.json` value of the state
vocabulary, one word per code (« joignable », « connecté », « en ligne », « disponibles » → one) — falls.

## Mutation

Put a word back in one seed row → falls by name.

## Oracle: states that diverge, declared by name

Every Système state (built by script: page `sys`) — the unified words accepted by name.

## Midpoint (after this phase)

`--contracts` and the full suite; real falls repaired before phase 9; harness budget read (office, order 52).

## Commit

`feat(maquette-conformity): Système's states are codes, their words are the vocabulary's`
