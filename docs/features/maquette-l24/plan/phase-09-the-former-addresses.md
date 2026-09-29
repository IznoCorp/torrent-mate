# Phase 9 — The former addresses (S4)

**STOP C: OPEN 4** — the three French aliases: reading A, they answer the not-found page (13 points); reading B,
each carries a `french-ok` pragma the operator's language rule must first admit (14).

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -n "\"/control\|\"/pipeline" frontend/maquette/design/src/lib/addresses.ts` → **nothing**;
  `grep -n "NOT_FOUND_PAGE)" …/lib/addresses.ts` → line **357**; the production table: `grep -c "path:" frontend/src/router.tsx`
  → **15** (eight pages, seven redirects, the sign-in and the not-found); `grep -cv '^\s*$' …/lib/addresses.ts` → **395** (+ phases 5 and 6 → 397).
- **Points ≈ 14 / 13.** R-L24-d 3; `lib/former-addresses.ts`, the table of DESIGN § 1.4 (≈ 40 lines new) 4; the
  lookup in `destinationOf` before the not-found fall (≈ 3 lines, 397 → 400 at most — over it is STOP D) ½; five
  states (`former-control`, `former-pipeline`, `former-pipeline-run`, `former-config`, `former-decision`) 5;
  reading B: `former-french-alias` and the pragmas 1; the report ½.
- **Readers.** R59 (`harness/back.py`) and R82 (`harness/journey.py`) read Back and the cold link; the not-found
  state `not-found` must stay what an unknown path answers.

## Red today

R-L24-d over `former-control`: `/control` answers the not-found page — `0 successor(s)`.

## Move

1. A former address REPLACES onto its successor (a redirect is not an arrival), the successor's parent synthesised
   (§ 16 rule 3); a dropped query is dropped silently, as D1 ignores an unknown dial.
2. `/control` lands on the ACCOUNT's entry page (§ 16 rule 2, 2026-09-27), never a fixed page.

## Mutation

Push instead of replace → the Back hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

The five (or six) new states. `not-found` at zero.

## Commit

`feat(maquette-l24): production's former addresses answer their successor`
