# Phase 2 — The identities in the mock

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `wc -l frontend/maquette/design/src/mocks/seeds/account.json` → 5 lines (`name`, `email`, `avatar`); `frontend/maquette/design/src/mocks/handlers/authentication.ts` → 16 lines, 3 routes (`readAccount`, `signIn`, `signOut`).
- `sed -n 336,372p frontend/maquette/design/src/mocks/state.ts` → `MockDials` holds **9** dials, each « what the machine IS »; `mocks/state.ts` is 413 lines. `frontend/maquette/design/src/harness/drive.ts` (273 lines) resets the layer at line 75 (`window.__mocks?.reset()` at line 86).
- `grep -n -A5 '"ACCOUNT"' frontend/maquette/fixture-register.json` → the register carries one `ACCOUNT` entry (lines 21–25, « the signed-in account »). L17 marks its invented rows `x-unseeded` — the same word here.
- `git grep -l -i -E "readAccount|/api/auth/me|data-account|sheet-user" -- 'frontend/maquette/harness/*.py' | wc -l` → **11** harness files read the account.
- **Points ≈ 14.** `seeds/accounts.json`, five invented rows, ≈ 40 new lines (4) + their `x-unseeded` rows in `fixture-register.json`, ≈ 20 new lines (2) + four dials on `MockDials` (`setIdentity`, `setCeiling`, `setPlexReachable`, `setInventedRequests`), ≈ 25 new lines (3) + `readAccount` re-answered from the dial (1) + the driver's reset returns the dial to the Operator (1) + R-L18-a with its mutations (3).

**DESIGN § 2.2.** The mock gains its identities and every one is INVENTED (§ 13): neutral labels, `example.invalid` addresses, marked `x-unseeded`, readable **only while a named state turns the dial**. The Operator's row is the real one and stays `account.json`. The resting maquette — identity `izno`, dial off — is what it was: R-L18-a proves it.

## Red today

**R-L18-a — the account, from the answer; the resting maquette whole**: the avatar menu, Profil and (once L22 draws it) the requester line name the DIALLED identity; **at rest, no invented row is readable from any list**.

**Red against `main`**: no dial exists and the account answer is one constant.

## Move

The five accounts, their register rows, the four dials, `readAccount` reading the dial, the driver's reset. `python3 scripts/check-mock-seeds.py` in the same commit (its `provenance` arm holds the four-way correspondence between the register, the seed files and each operation's `x-seeded-from` / `x-unseeded`).

## Mutation

With the commit made first: print a constant name in `readAccount` → R-L18-a falls under a changed identity; leave an invented row in the resting seed (`setInventedRequests` default true) → its rest hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** — the dial's resting value is the Operator; no existing state reads another identity. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the mock holds five invented identities behind a dial, and the resting maquette is unmoved`
