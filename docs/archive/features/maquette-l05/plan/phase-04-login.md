# Phase 4 — The sign-in screen gets its address

D1 says every page and every screen sits on a real path. The sign-in screen has none: it is a named
state (`signin`, `signin-error`) that `showSignIn()` draws. The operator arbitrated on 2026-08-22
that it be taken here rather than left to L13.

`serve.py` already serves `/login` (line 757) and `/logout` (line 753), and `harness/logout.py`
holds them — which is why that rule sits in the `--contracts` tier.

## The boundary with L13, stated so it is not crossed by accident

L13 keeps the splash, the document-level event delegation, the boot handshake and the republished
`window` surface. **This phase gives the sign-in screen an address; it does not convert it into a
component and does not touch `window.__startEngine`.** The two named states keep working exactly as
they do — what changes is that the screen is now reachable by, and reflected in, an address.

## Steps

1. Declare `/login`, one address one file.
2. `showSignIn()` navigates rather than merely drawing; the refusal state (`signin-error`) is a
   STATE of that address, not a second address — it is not a place one links to.
3. The design host's own `/login` POST handling is untouched: it is the gate, not the screen.

## The rule that bites

Extend `harness/logout.py`, which already reads both ends of these two routes, rather than adding a
second rule beside it. Its new hold: `/login` requested cold renders the sign-in screen, and the
address does not move on the way.

**Mutation**: leave `showSignIn()` drawing without navigating. The rule must fall and say the
screen is shown at an address that does not name it — the URL and the interface contradicting each
other, which is invariant 1.

## Done when

- ACC-19 (contracts tier, `logout.py` inside it), ACC-07 (R69 unbroken by the new address).
- ACC-03, ACC-04, ACC-05 green.
- `git diff main..HEAD -- frontend/maquette/design/src/app/shell.tsx` shows no change to the boot
  handshake — the L13 boundary held, shown rather than claimed.
