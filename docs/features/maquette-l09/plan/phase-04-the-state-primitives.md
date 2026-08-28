# Phase 4 — The state primitives

**Loading, error and empty, once, in `ui/`.** Twelve surfaces are about to need all three; twelve
implementations of the same three is how two surfaces come to answer one question differently,
which §13 of the constitution forbids by name (« Une seule dérivation par question »).

## What lands

- `ui/` components for the three states, fed by query state and knowing no domain — invariant 7
  and invariant 10 both.
- Each takes its copy through `useTranslation()`, never a literal (CLAUDE.md § Language).
- The error surface **says the real reason** (NE-DOIT-PAS-4, NE-DOIT-PAS-5). The mock layer's
  failures carry a `title` and a `detail`; the surface shows them rather than a status code.
- « Réessayer » **works** — B-031 records it inert on every error surface today, and this is the
  phase where a retry has something real to re-ask.

## What they must reproduce

The engine already draws loading, error and empty states, and the named states drive them
(`phase: "loading" | "error"`). These primitives must render **what those states render today**,
because the oracle measures those states. The markup is transplanted where it carries `data-*`
the delegation reads.

## The rule that bites

A hold that drives a named error state, asserts the real reason is on screen (not a code), taps
« Réessayer » and asserts a second request was made. Mutate: make the retry a no-op, see the hold
fall naming the inert retry, restore.

## Done when

- The three primitives exist in `ui/`, importing no feature.
- B-031's retry is live on the surfaces converted from here on, and the hold proves it.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`.
