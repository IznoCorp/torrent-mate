# Phase 6 — The offline guard, and one subtraction

Two things that belong together because both are about what the tree is allowed to contain once the
addresses have moved.

## The ninth arm — `addressing`

Invariant 1 says the URL and the interface never contradict each other: no page identity in the
query, no sort or filter in the path. The lot's « Done when » asks for **both checked**. R69 checks
it at runtime, in a browser, over the states it drives. This arm checks it offline, over the
SOURCE, on every `make check` — the two do not overlap, and the offline one is the cheaper to act
on.

**It extends `scripts/check-frontend-boundaries.py`** — which already carries eight arms including
`one-address` — rather than sitting beside it as a second guard. That is L02's lesson, and it was
paid for once.

What it refuses:

1. a page id declared as a search parameter of any route;
2. a dial name (`tab`, `lens`, `mode`, `cat`, `topic`, `panel`, `q`) declared as a path segment;
3. an address declared in the source that no route file carries — the third end of a contract
   moving without the other two.

**Mutation**: declare `sort` as a path segment. The arm must fall and name the dial in the path,
not merely count a violation.

## The subtraction — `openScreen()`

It has zero callers: every screen migrated to a route. It is navigation machinery, and D5 says the
engine dies by subtraction as each surface converts. The moment a thing loses its subject is the
moment to remove it — machinery nobody can justify is machinery nobody dares delete, which is this
plan's most expensive recorded lesson.

Removed with it: whatever exists only to serve it. **Not removed**: `closeScreen`, `#screen` and
the `#screen.open` branch of `onEngineBack` — those still serve the layer ladder, and a subtraction
that takes a live path with it is not a subtraction. Each removal is justified by a grep showing
zero remaining readers, and that grep is reported.

## Done when

- ACC-08 (the arm alone), ACC-09 (all nine arms), ACC-13 (`openScreen` gone), ACC-17 (`make check`,
  which the arm now runs inside).
- ACC-03, ACC-04, ACC-05 green — the removal is invisible, and the oracle is what says so.
- The mutation has been seen to fall and been restored.
- For every removed symbol, the zero-reader grep is in the phase's report.
