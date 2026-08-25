# Phase 16 — BLOCK 1 dies, `refonte.html` dies, §15 is amended

The lot's own words: BLOCK 1 « is deleted, not converted, and its disappearance is part of this
lot's proof rather than a later tidy-up ».

## What is deleted

| what | where it is today |
| --- | --- |
| the phone frame (`.stage`, `.device`) and its two desktop `@media` re-assertions | BLOCK 1 |
| the harness buttons (`.hbtn`) and the `html.measuring` hides | BLOCK 1 |
| the declared harness deviations (`.device .bottombar`, `.fab`, `.selbar` → `absolute`) | BLOCK 1 |
| the state panel (`.hpanel`, `.states`, 8 rules) | BLOCK 2, 3824–3882 |
| the design-notes overlay (`.note`, `.notes`, 4 rules) | BLOCK 2, 4009–4035 |

**The six app regions of BLOCK 1 are already out** — phase 1 moved them into the base layer, which
is the whole reason phase 1 exists. Nothing that ships is being deleted here.

## What remains, named and counted

`design/src/styles/legacy.css` — the residue of D-L07-5. It carries the sign-in gate (15 rules),
the splash (8 rules) and the markup the engine still draws, with the `login:*` markers `serve.py`
extracts. **Its contract is written at its top**: it names L13 as its death, and
`scripts/check-legacy-css-residue.py` refuses it growing.

The residue is a debt with a number and a date, not a leftover. The lot's « no hand-written
component stylesheet remains » reads as *for every surface this lot converted* — which is every
surface except the ones D5 assigns to L13.

## `refonte.html` dies

With the tokens in `theme.css`, the base in `base.css` and the residue in `legacy.css`, the file
carries a `<title>` and nothing else. `index.html` keeps the title and the file is removed.

**Fourteen files name that path and move in the same commit**: seven under `harness/` (including
`common.py`, which holds `DESIGN_SOURCES` — already widened in phase 1), five under `scripts/`,
plus `serve.py` and `vite.config.mjs`.
<sub>`grep -rln 'refonte\.html' --include='*.py' --include='*.mjs' --include='*.js' frontend scripts | grep -v node_modules | wc -l` → 14 on the day the wave opened, 0 at the close of this phase.</sub>

`vite.config.mjs`'s whole subject was injecting the fragment verbatim. With no fragment, the
plugin's `transformIndexHtml` half goes; its `closeBundle` half — the `dist/assets` symlink that
avoids copying 10 MB per build — stays, and says why in the same comment it says it today.

## §15 of the constitution is amended

§15 names `frontend/maquette/design/refonte.html` as the product. It cannot name a file that no
longer exists, and D3 already says what replaces it: **the tokens plus the component catalogue**.
The amendment adds what replaces it and names what it makes void, rather than quietly editing the
old text — that is § 7.1 of the architecture file, and it is the operator's document, so the
amendment is proposed in the pull request rather than assumed.

`IMPLEMENTATION.md` and `frontend/maquette/README.md` carry the same path in prose and follow.

## Mutation tests

- Add a class to `legacy.css` → `check-legacy-css-residue.py` exits 1 and names it. Restore.
- Re-add `.note` anywhere in the tree → the same check, or the compositor check, refuses the
  scaffolding coming back.

## Gates

The full wave list: ACC-04 through ACC-20. **ACC-14, ACC-15, ACC-17, ACC-18 and ACC-19 are
this phase's own** and are the lot's « Done when » read back as commands.

---

## Amendment — 2026-08-25, at the close of the wave

**This section is added rather than substituted for the text above.** § 7.1 of
`docs/reference/frontend-architecture.md`: what loses its subject is named and dated, never
quietly rewritten, because a plan silently corrected is a plan the next wave believes it followed.
Everything above this line is what the phase INTENDED. What follows is what it DID, and where the
difference went.

### 1. BLOCK 1 did not die into nothing — it became `src/styles/harness.css`

**What the text above says.** « the phone frame (`.stage`, `.device`) … the harness buttons
(`.hbtn`) … the declared harness deviations » are deleted, and ACC-15 reads back « exactly
`theme.css`, `base.css`, `legacy.css` — no fourth stylesheet ».

**What landed** (`83765d3c`). The harness's own rules left the fragment, but they could not be
deleted: **the instrument that proves every other claim in this lot is built out of them.** The
oracle measures the prototype inside the phone frame at 390 × 844; the rule suite drives the
harness buttons; `html.measuring` is what makes a measurement repeatable. Deleting them in the
commit that also claims « the rendering did not move » would have destroyed the only thing able to
say whether it moved. They are `frontend/maquette/design/src/styles/harness.css`, imported once
and by nothing that ships.

**What this makes void.** **ACC-15 as written** — « no fourth stylesheet » — is void. Its subject
was « no hand-written component stylesheet survives the conversion », and that claim holds: the
fourth file carries no surface, only the measuring apparatus. Read it as **exactly four, and the
fourth ships nowhere**, held by ACC-17 (`grep -c` over `frontend/`'s built CSS → 0).

**This is the lot's one deviation, and it is deliberate.** Recorded here, in the PR body, and in
`IMPLEMENTATION.md`'s state row — three places, because a deviation named in one is a deviation
the next reader meets as a surprise.

### 2. `refonte.html` is NOT deleted by this phase — and the premise above is why

**What the text above says.** « the file carries a `<title>` and nothing else. `index.html` keeps
the title and the file is removed. »

**That premise is measurably false at the close of the wave.** The file is 120 lines and carries
**zero style rules** — that half is true and verified (`grep -c '{'` → 1, the `@layer` opening
brace). But the remaining hundred lines are not empty: they are the **conversion ledger** this
wave wrote as it went, one entry per region, each naming where that region's rules went and the
reason the choice was made — the shell whose direction of truth is inverted and why; the `port`
class kept as an identity anchor with no style, and the nine-hundred-lines-below container query
that depends on it; the media card's 33 engine-owned class names; the gallery tiles' container
reasoning; Découvrir's three things that must survive it. **Deleting the file deletes that index**,
and a third of its entries point at `legacy.css`, whose own death is L13's.

**§ 7.1 is explicit about this shape**: « When you find a lot that no longer has a subject — its
premise was reversed — stop and report it. Do not execute it. » The premise here was not reversed
by someone else; it was **measured wrong when the plan was written**, which asks for the same
stop.

**The second reason, and it is the one that needs an operator.** **R72's whole subject is this
file.** Its hold (a) — « the fragment appears byte-for-byte verbatim, exactly once, in
`dist/index.html` » — is what makes source and build interchangeable for every later measurement;
holds (b) and (c) do not mention it and survive untouched. Removing the file retires hold (a) with
nothing in its place, and **retiring a hold is a rule renegotiation recorded in
`frontend/maquette/regions.json`**, taken deliberately and mutation-tested — not a tail-of-session
edit inside a 47-commit wave that is already green.

**The cost is measured, not guessed.** Twelve live readers name the path — `serve.py` (`PROTOTYPE`,
and the build-input list), `design/vite.config.mjs` (the `transformIndexHtml` half), `harness/`'s
`common.py` (`DESIGN_SOURCES`), `palette.py`, `rename.mjs`, `switchover.py`, `shell.py`, and
`scripts/`'s `check-css-tokens.py`, `csstokens_login.py`, `check-compositor-css.py`,
`check-tailwind-confinement.py`, `nofrench_lexicon.py` — plus roughly thirty comments across the
component tree that cite it as provenance.

**What this makes void, and what it defers.**

| criterion | status |
| --- | --- |
| **ACC-14** — `test ! -f frontend/maquette/design/refonte.html` | **deferred**, not met, not silently dropped |
| **ACC-18** — §15 no longer names the file | **met** — the constitution was amended (`9c7e7379`); the file survives its own constitutional mention, which is the right order |
| **ACC-19** — no `.py`/`.mjs`/`.js` under `frontend`/`scripts` names the path | **deferred** with ACC-14; the count is 12 live readers, not the 14 the wave opened on |

**Where the deferred work goes: L13 — « The engine's residue ».** Not arbitrarily. A third of the
ledger's entries name `legacy.css` as their home and L13 as its death; `serve.py`'s sign-in gate is
built by text extraction from markers that live in that residue; and the fragment is the
engine-era document. The fragment, the residue and the ledger resolve in one move there, or they
resolve three times. **Any earlier wave may take it** — nothing depends on waiting — provided it
carries R72's renegotiation and a home for the ledger, and does not fold either into a conversion
commit.

**Recorded, so it cannot be lost with this branch**: `IMPLEMENTATION.md`'s state row names it, the
pull-request body names it, and § 4 of `docs/reference/frontend-architecture.md`'s L13 entry is
where the next wave will read it.
