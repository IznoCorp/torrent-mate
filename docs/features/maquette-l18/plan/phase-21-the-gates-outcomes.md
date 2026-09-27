# Phase 21 — The gate's outcomes

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `sed -n 316,340p frontend/maquette/design/src/app/entry.ts` → the gate's submit: an empty field shows the refusal, anything filled in walks through (« this surface demonstrates the SCREEN and not the check »); `signIn` answers the account whatever is sent (`mocks/handlers/authentication.ts`).
- `sed -n 238,242p docs/reference/frame-model.md` → « rights (§17) are a feature's to read from `/api/auth/me`, never the gate's »: **the outcome is drawn by the frame reading the account after the sign-in, not by the gate reading a role**.
- `setPlexReachable` is a dial of phase 2; `signInWithPlex` exists from phase 20.
- **This phase edits FRAME code** (`app/`), the only lot after L15 that does; the plan says so rather than discovering it.
- **Points ≈ 15.** `signIn` re-answered: a non-Operator's password refused with its reason (1) + `entry.ts`: the refusal's wording branch, ≈ 15 lines (2) + the Plex-unreachable line, ≈ 10 lines (1) + `signInWithPlex` re-answered for unreachable and for no rights (1) + the frame reads the account after the sign-in and lands accordingly, ≈ 10 lines (2) + two sentences (the refusal's reason, Plex unreachable) (2) + three states — `signin-plex-unreachable`, `signin-password-refused`, `signin-plex-bare` (3) + R-L18-r with its mutations (3).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: the landing (2) moves to its own phase.

**DESIGN § 3.1 points 2–4.** A password is for the Operator: a non-Operator's is refused **with a reason** (« ce compte se connecte avec Plex »), never a bare « Identifiants invalides » that would send the account to try again (§ 8). When Plex is unreachable the gate says so from the answer and the password form stays whole — the door of last resort. A Plex user with no right is admitted read-only and lands on the Médiathèque.

## Red today

**R-L18-r — the gate's outcomes**: a non-Operator's password is refused with its reason; Plex unreachable is said from the answer; a rights-less Plex user's first frame is the Médiathèque; **the Operator's password still signs in when Plex is unreachable**.

**Red against `main`**: any filled-in form signs in.

## Move

The refusal, the line, the landing, the states.

## Mutation

With the commit made first: let a non-Operator's password through → R-L18-r falls; drop the door of last resort → falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** for the existing states beyond phase 20's. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the gate refuses a password to a non-Operator, says when Plex is down, and admits a rights-less user to the library`
