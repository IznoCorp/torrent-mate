# Phase 5 — « Relancer la veille » and DOIT-6's figures (B-383)

DOIT-6 asks for a SEQUENCE — « lancé → en cours → X détectés, Y disponibles, Z récupérés » — and the
202 phase 1 gave `runDetection` is what makes the middle state drawable. It is also the phase that
closes B-383's veille half: the button exists today and sends nothing.

**The plan's own correction applies here** (DESIGN § 8.1): « relancer la veille » is
`POST /api/acquisition/detect`, not `POST /api/pipeline/watcher` — which is phase 4's automatic
trigger and answers no figure.

## The rule FIRST, red against `main`

`frontend/maquette/harness/watch_run.py` — new, label **R-L20-c**. Four holds:

1. **The act lands from BOTH emitters.** The « ⋮ » sheet's « Veille et obligations » panel (named
   state `sheet-more`, copy `panels.standby.runNow`) and the levers section. Each pressed by a
   finger, each read on the NETWORK. *A verb emitted from two surfaces and registered once is §13
   satisfied; a verb that works from one of them is a half-repair, and B-383 is what a half-repair
   looks like a wave later.*
2. **The three numbers DRAWN equal what the layer ANSWERED.** Read from
   `window.__mocks.answered()` for the run's identifier, then from the detail the interface received
   — never from a constant, never from the seed by name. *A build printing three plausible numbers
   passes any hold that only checks three numbers are there.*
3. **The zero case is SAID** — « Rien de nouveau. » — and it is a different drawing from the
   figures, not the figures with zeros in them.
4. **A dead run says so, loudly**, and **no success message appears on it**. NE-DOIT-PAS-1's own
   example: « pas de toast de succès sur un run mort ».

**Seen red how**: on `main` the button answers with a canned sentence and no call (B-383), so hold 1
fails on the network read for the panel emitter and holds 2–4 fail for want of a surface. **That is
this lot's clearest red**: the defect is on `main` and the rule names it.

**Mutation after the move**: return different counts from the layer (hold 2 falls on the
comparison); print a constant (falls); answer zero and draw the figures (hold 3 falls).

## The move

- **New file** `features/system/watch-run.ts` — the mutation over `runDetection`, the run identifier
  it answers kept, and the detail read for its figures. **The figures arrive by the STREAM, not by a
  poll**: `features/system/live.ts`'s run-lifecycle rule gains the ACTIVE run's detail key.
  NE-DOIT-PAS-8, and `scripts/check-live-relay.py`'s poll arm would refuse a clock here.
- `registerVerb("watch-now", …)` — ONCE, in that file. The « ⋮ » panel's existing button gains the
  attribute; the levers section emits the same one. **Neither emitter gets a handler of its own.**
- The levers section gains the veille's block: its last run, its last figures, and the button.
- Copy: `panels.standby.runNow` is **EXTRACTED, never retyped** — a retyped string renders correctly
  while the reference is broken. New keys for the four result sentences, with `{detected}`,
  `{available}`, `{grabbed}` as parameters and their plural forms.

States added: `veille-idle`, `veille-running`, `veille-figures`, `veille-nothing`, `veille-error`.

## Gate

`run.sh --contracts`; R-L20-c green, its mutations run and named. The oracle: the levers' section
grows, so Système's four states diverge on length again — accepted with « L20 § 4.2: the veille's
figures »; `sheet-more` gains an attribute and no pixel, so it is expected at ZERO, and **a
divergence there is a finding, not an acceptance**.

## Commit

`feat(maquette-l20): the veille says what it found, and the button that said nothing now sends`
