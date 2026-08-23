# Phase 4 — The move to the target tree

**No logic changes in this phase, by construction.** Its whole proof is that the oracle did not
move. Anything that cannot be moved without an edit is not moved here — it is reported.

## The target, and where each file goes

The rule that decides it, quoted: **a file lives with what makes it change**; never a folder for a
KIND of file.

| Target                                                             | From                                                                                                                                        |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/`                                                             | `shell.tsx` (what remains of it after phase 1), `store.ts`, `focus.ts`, `pages/host.tsx`, `pages/not-found.tsx`, `reference.d.ts` (phase 3) |
| `routes/`                                                          | the six `createRoute` blocks now inside `shell.tsx` — **one address, one file**                                                             |
| `features/acquisition/`                                            | `pages/acquisition.tsx`, `screens/add.tsx`, `panel-seasons.tsx` (phase 2), its `model.ts` + `reference.ts` (phase 3)                        |
| `features/library/`                                                | `pages/library.tsx`, `screens/media.tsx`, + its `model.ts` / `reference.ts`                                                                 |
| `features/arrivals/`                                               | `pages/arrivals.tsx`, `screens/resolution.tsx`, `screens/releases.tsx`, + its `model.ts` / `reference.ts`                                   |
| `features/settings/`                                               | `pages/settings.tsx`, `settings-labels.ts`, `screens/profile.tsx`, `panel-field.tsx` (phase 2), + its `model.ts` / `reference.ts`           |
| `features/system/` · `features/maintenance/` · `features/account/` | `pages/system.tsx` · `pages/maintenance.tsx` · `pages/account.tsx`                                                                          |
| `ui/`                                                              | `components/icon.tsx`, `components/sheet.tsx`, `panel/` (phase 2)                                                                           |
| `lib/`                                                             | `navigate.ts` (phase 1), `store-access.ts`, `engine-drawing.ts` (phase 3)                                                                   |
| `engine/`                                                          | `legacy.js` **unmoved**, plus `states.js` and `seams.ts` moving in beside it                                                                |
| `i18n/`                                                            | **unmoved**                                                                                                                                 |

**Two placements that needed the rule rather than a habit.** `not-found.tsx` renders the shell's
own answer to an unknown page id, belongs to no domain, and changes when the shell changes → it is
`app/`, not a one-file feature. `screens/profile.tsx` is the quality-profile screen, reached from
Configuration and changed by it → `features/settings/`, even though what it configures is read
later on the acquisition path.

## The pointers that move with the files, and they are the risk

Each is a contract with more than one end. **Each moves in the SAME commit as its file.** This
list is enumerated before anything moves, and re-derived afterwards — a pointer found later is a
pointer that was already broken.

| Pointer                              | Reads                                          | Because of                                            |
| ------------------------------------ | ---------------------------------------------- | ----------------------------------------------------- |
| `design/index.html:77`               | `<script type="module" src="/src/shell.tsx">`  | `shell.tsx` → `app/shell.tsx`                         |
| `harness/navigation.py`              | `shell.tsx` by name                            | already moved in phase 1 for `go()`; re-verified here |
| `scripts/check-no-french.py:572`     | `SHELL / "states.js"` (French-debt allow-list) | `states.js` → `engine/states.js`                      |
| `engine/legacy.js:35`                | `from "../seams.js"`                           | `seams.ts` → `engine/seams.ts`                        |
| `states.js:45`                       | `from "./engine/legacy.js"`                    | it moves into that directory                          |
| `harness/panel.py` header            | names `design/src/components/panel.tsx`        | the panel moved in phase 2                            |
| `harness/common.py` `DESIGN_SOURCES` | `design/src/engine/legacy.js`                  | **unchanged** — `legacy.js` does not move             |

**`legacy.js` staying put is the point of D-L04-6**: its path is the most-cited in the repository,
and the architecture file has already ruled on this exact trade for the harness's flat files —
« a real cost for a gain in comfort […] it waits for a stronger reason than tidiness ».

## One address, one file

The six routes leave `shell.tsx`. Each `routes/*.tsx` declares exactly one `path:` and imports
its parent route from `app/`, which does not import `routes/` — so the router assembly in `app/`
imports both without a cycle.

The six addresses are unchanged: `/`, `/profile/$title`, `/add`, `/mediasheet/$title`,
`/releases/$title`, `/resolution/$folder`. **Adding addresses is L05's work, not this lot's.**

## Proof

- The tree arm reports every file inside a declared bucket, 0 strays.
- The one-address arm reports 0 files declaring more than one `path:`, 0 address declared twice.
- `python3 scripts/check-no-french.py` and `python3 scripts/check-markup-contracts.py` exit 0.
- `npm run typecheck` exits 0; `npm run build` succeeds.
- **The oracle reports 0 divergence.** A move that changed nothing is the only acceptable result;
  a divergence here means an edit was hidden inside a move, and is reverted rather than accepted.

## Trap met here

**A rule that greps one file greps the wrong thing.** Four rules once stayed green after their
subject moved out of the file they grepped. Every pointer above is verified by being seen RED — a
rule pointed at the OLD path must fail — before it is repointed. A repointed rule that was never
seen red proves only that it agrees with the new tree.
