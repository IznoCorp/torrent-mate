# Phase 24 — « Comptes » — the roster

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `readAccounts` exists from phase 10; the six accounts of § 2.2 are its seed (the five invented ones readable under their dial only).
- `ls frontend/maquette/design/src/features/account` → 6 files today; `roster.tsx` is new. The row form reuses the follows' row idiom (`features/acquisition/follows-tab.tsx`, 293 lines) or `ui/fact-rows`; the opening measure names the one it takes.
- **Does not exist on this head**: the place (phase 23) the roster mounts into.
- **Points ≈ 15.** `roster.tsx`, new, ≈ 70 lines (7) + three sentences (title, « sans droits », empty) (3) + the row's Plex-link line (1) + one state, `accounts-roster` (1) + R-L18-t with its mutations (3).

**DESIGN § 3.9 points 1 and 4.** One row per account: its name, its role, whether it is linked to a Plex account, its two options as they stand. **A Plex user admitted with no right is a row** — « sans droits », so the Operator sees who is in and has not been qualified (an account admitted read-only is not a hidden one, § 8).

## Red today

**R-L18-t — the roster, from the answer**: one row per account of the answer; role, link and options read from it; change the seed, the row follows.

**Red against `main`**: no roster exists.

## Move

The component, its sentences, the state.

## Mutation

With the commit made first: print a constant row → R-L18-t falls under a changed seed; drop the « sans droits » row → falls.

## Register

—

## Oracle: states that diverge, declared by name

`accounts-roster` is new. **None** otherwise. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the Operator sees every account, and who has no right yet`
