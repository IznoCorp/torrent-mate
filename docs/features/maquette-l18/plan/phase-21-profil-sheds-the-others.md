# Phase 21 — Profil is the connected account

**Amended 2026-09-27** (renumbered from the first drawing's phase 18): the ROLE line now names an actual ROLE
(never a raw rights list, never compared) — ruling 20's own guarantee that it never lies. Re-estimated at **11**
(unchanged).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `wc -l frontend/maquette/design/src/features/account/page.tsx` → **83**; `python3 -c "import json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print(len(d['screens']['accountPage']), [k for k in d['screens']['accountPage'] if k.startswith('others')])"` → **21** keys, three of them `others`, `othersEmptyTitle`, `othersEmptyBody`.
- `grep -n -B1 -A3 '"account/body"' frontend/maquette/regions.json` → the region's note still reads « the one real account, and the place of the others » (line 208): a comment that outlives its decision is read as current (the species `CLAUDE.md` records).
- `harness/states/account.ts` holds `profile`; `grep -c '"account/body"' frontend/maquette/oracle-reference.json` → 114 (one per recorded state — the region is in every record).
- **Points ≈ 11.** `page.tsx`: the section deleted and the role line added, ≈ 15 lines (3) + three keys deleted from `fr.json` (1) + one new sentence (the role) (1) + `regions.json`'s note rewritten (1) + two states — `profile-household`, `profile-guest` (2) + R-L18-p with its mutations (3).

**DESIGN § 3.8, organisation ruling 14** — Profil is the connected account and its preferences, for everyone; the reserved empty place for the others goes, with its keys, **removed and not kept « just in case »** (`frontend-architecture.md` § 2, the paragraph that opens it: what loses its subject is removed). The role reads from the model.

## Red today

**R-L18-p — Profil**: Profil draws no other account and no reserved place for them; it names the role of the connected account, for each identity.

**Red against `main`**: the section exists.

## Move

The page, the keys, the region's note, the states.

## Mutation

With the commit made first: draw « Les autres comptes » → R-L18-p falls; print a constant role → falls under a changed identity.

## Register

—

## Oracle: states that diverge, declared by name

**`profile`** (the Operator's, on `account/body`: the section is gone and the role line added) — « L18 § 3.8: the others' place leaves ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`refactor(maquette-l18): Profil is the connected account only — the others' place leaves it`
