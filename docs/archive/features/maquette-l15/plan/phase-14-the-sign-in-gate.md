# Phase 14 — The sign-in gate

**Kind** conversion. **Part** 9. **Unblocks** L18 (§17 redraws this gate for Plex SSO, and D5
allows no addition to the engine).

## What lands

`app/sign-in.tsx` at `#login`, `data-part="login"`, `role="region"` — the form, the refusal state
and the wait that follows a submit. The address is written through the same single writer every
other address goes through, in **REPLACE**: signing in is not a step of the walk one goes back
through.

`index.html` keeps the `pwa:start…end` block the gate borrows — `serve.py` extracts it, and that
extraction is a contract `harness/logout.py` reads.

## What the engine loses

`showSignIn`, `hideSignIn`, `signOut`, the `#loginform` submit handler, and the `#login` reads in
`__go` and `proposerInstallation`. `signOut`'s `fetch("/logout")` moves with it; the route is
`/logout` on both sides since #456 and `harness/logout.py` holds both ends.

## The rules

- `harness/logout.py` is one of the eleven contracts rules. It is re-run: this phase moves the very
  code it reads.
- A hold on the refusal: an empty field shows `#loginerr` and does NOT navigate; a filled one hides
  the gate and covers the wait. **Mutation**: let the empty submit through and confirm the hold
  falls naming the address that moved.

## Traps

- **`pilotage`.** `showSignIn` must not write the address when the harness is driving —
  `window.__go` reaches the sign-in state without moving history, and R74 holds it. The flag is the
  engine's private latch; the seam carries the answer, not the flag.
- The gate is a LAYER over a built frame, not a page. `lib/addresses.ts` already says so and does
  not change.
