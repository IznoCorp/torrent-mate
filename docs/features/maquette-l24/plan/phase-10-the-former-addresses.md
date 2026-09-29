# Phase 10 — The former addresses (S4)

**STOP C: OPEN 9** — where `/media?decision=<id>` lands: reading A (13 points), the query dropped, `/media`;
reading B (15), the decision's medium, read by its id. Ruled OPEN 4 = A (2026-09-29): `/medias`, `/systeme`,
`/controle` answer the not-found page, no redirect.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "\"/control\|\"/pipeline" frontend/maquette/design/src/lib/addresses.ts` → **nothing**;
  `grep -n "NOT_FOUND_PAGE)" …/lib/addresses.ts` → line **357**; the production table: `grep -c "path:" frontend/src/router.tsx`
  → **15** (eight pages, seven redirects, the sign-in and the not-found); `grep -cv '^\s*$' …/lib/addresses.ts` →
  **395**.
- **Points ≈ 13 / 15.** R-L24-d 3, its holds including `/controle` answering the not-found page; `lib/former-addresses.ts`,
  the table of DESIGN § 1.4 (≈ 40 lines new) 4; the lookup in `destinationOf` before the not-found fall (≈ 3 lines,
  395 → 398 — over 400 is STOP D) ½; five states (`former-control`, `former-pipeline`, `former-pipeline-run`,
  `former-config`, `former-decision`) 5; the report ½. Reading B: + the lookup over the settled read, landing on the
  journey or the Médiathèque sheet with its parent (≈ 10 lines new) 1, its hold 1.
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

The five new states. `not-found` at zero.

## Commit

`feat(maquette-l24): production's former addresses answer their successor`
