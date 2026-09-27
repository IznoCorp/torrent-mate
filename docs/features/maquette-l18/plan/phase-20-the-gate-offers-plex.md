# Phase 20 — The gate offers Plex

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `sed -n 429,480p frontend/maquette/design/index.html` → the gate's markup: **52 lines** between `login:markup:start` and `login:markup:end`; `wc -l frontend/maquette/design/src/app/entry.ts` → **399**; the gate's style is the `login:entry` region of `styles/base.css`, lines **1067–1268**.
- `sed -n 349,395p frontend/maquette/serve.py` → `login_page` clones the extracted markup and posts it to its own `/login` (scrypt hash, `serve.py` 778 lines): **the host has no Plex**, so a Plex block INSIDE the extraction would appear on the real password page and could do nothing.
- `cat frontend/maquette/design/src/harness/states/entry.ts | wc -l` → 49 lines, 5 states (`pwa-android`, `pwa-ios`, `startup`, `signin`, `signin-error`); `README.md` § « The login gate reads each block where it lives » — `extract` raises on a missing marker.
- **Reads OPEN 2** (A — side by side; B — Plex first, the password behind a disclosure). B adds a disclosure (the password form behind « Utiliser un mot de passe »: ≈ 15 lines 2, one sentence 1, one state 1, the rule's extra hold 1 = 5 → 20): **cut into 20 and 20-bis** (the disclosure).
- **This phase edits FRAME code** (`app/`), the only lot after L15 that does; the plan says so rather than discovering it.
- **Points ≈ 15.** the Plex block in its own marker pair, ≈ 20 new lines in `index.html` (2) + `entry.ts`: the Plex act, ≈ 30 new lines (3) + `styles/base.css` `login:entry`: ≈ 20 new lines (2) + the `signInWithPlex` mock route, new (2) + two sentences (the offer, the separator) (2) + `signin-plex` new; `signin` and `signin-error` re-recorded (1) + R-L18-q with its mutations (3).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: the stylesheet's ≈ 20 lines go to their own phase.

**FRAME EDIT — the gate, the first after L15's, and the contract's `app/sign-in.tsx` is a name that never existed** (DESIGN § 8): the logic is `app/entry.ts`, the markup `index.html`. **DESIGN § 3.1.** A second way in that ADDS to the password form and replaces nothing (§ 17). The Plex block carries its own marker pair (`login:plex:start … end`) so the host's extraction and its password page are unchanged and offer nothing they cannot honour.

## Red today

**R-L18-q — the gate offers Plex, and the host's page is unchanged**: the gate draws both ways in (arranged per OPEN 2); **the design host's password page is byte-identical to the one before the phase and carries no Plex offer** (R72's bridge still passes).

**Red against `main`**: the gate draws a password form only.

## Move

The markup, the act, the style, the mock route, the sentences, the states.

## Mutation

With the commit made first: move the Plex block inside the extraction markers → the host hold falls; hide the password form when Plex is offered → the « adds, does not replace » hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**`signin`, `signin-error`** on `login/form` — « L18 § 3.1: the Plex block ». Any other divergence is STOP A. The accessibility tier is re-read.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the gate offers Plex beside the password`
