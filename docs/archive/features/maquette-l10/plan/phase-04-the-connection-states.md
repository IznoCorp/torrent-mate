# Phase 4 — The connection states, drawn

**§8 is this phase.** « Un "rien ne se passe" sans raison visible est un mensonge par omission. »
The worst defect this lot can ship is not a lost event — it is a screen that looks current and is
not.

## Steps

1. Draw the indicator in the maquette first, with its named states, before it is coded.
2. `ui/` component — the frame, no domain word. It renders **nothing at all** while connected
   (D-L10-5): §8 asks that what is wrong be said, not that what is right be announced, and a
   permanent green dot is chrome that teaches the reader to stop looking.
3. Four named states in `engine/states.js`, driven by `window.__go`:
   `relay-reconnecting` · `relay-lost` · `relay-refused` — plus the connected case, which is the
   absence of the other three and is asserted as an absence.
4. Every string through `i18n/fr.json`. None retyped: a retyped string renders correctly while the
   reference is broken.
5. `relay-lost` says when the displayed information dates from, and offers a manual retry.
   `relay-refused` says the session is no longer valid and offers the way back to the sign-in —
   a real reason, never a code (NE-DOIT-PAS-5).
6. **Reduced motion is a drawn state** (invariant 14): the reconnecting state's activity has a
   defined still appearance under `prefers-reduced-motion`.

## The rule

**R92 (`harness/relay_states.py`)** — each state by its own text and its own control, on the model
of R90, which exists because the oracle recorded four loading and error states BLANK (B-108). A
rectangle is not enough for a surface whose whole job is to be noticed.

Holds: each state renders its text; each renders its control; the control does something; the
connected case renders nothing; the reduced-motion appearance is defined and different.

**Mutation**: make `relay-lost` render the reconnecting copy. The hold must fall naming the wrong
state, not a missing element.

## The oracle

Four states are ADDED. That is growth of the reference (`84 → 88`), not divergence. The 84
existing states are measured for divergence and the result is recorded in the close — **measured,
not predicted**: D-L10-5 argues the connected case renders nothing, and § 5 of the design says
that must be verified rather than assumed.
