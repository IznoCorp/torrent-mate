# Phase 12 — PR #484 fixes, review cycle 3

Two reviewers walked phases 10–11 with REAL taps at the design's own viewport, and the biggest
finding is about a premise: « the tab bar sits above the layers » — the sentence cycle 2's fix
was built on — is false. Hit-tested, every layer kind covers the tabs. What IS finger-reachable
is the drawer and the account menu, and § 16 rule 2 fails exactly there. Every finding below was
re-verified by the orchestrator against the reviewers' probes before being retained.

**The pull request must not merge until 12.1–12.3 are closed.** 12.4 rides along.

Phase 8's « How this phase runs » applies unchanged (four beats; build+copy WITH the `rm -rf`;
`legacy.js`/`.md` edits through Python writes; `ruff check` only on harness/scripts; English; no
phase/session/bug/wave reference in a source comment). Branch `fix/maquette-l05`.

## 12.1 — The not-found page's escape button spends the exit guard · CRITICAL

Cold `/nimportequoi` → the boot lays NO floor (`[guard, /typo]`, by design) → tap the surface's
own « Aller à Acquisition » (`data-go`) → `switchPage` sees « arriving home » and blind-steps
`__bridge.back()` — onto the GUARD. `armedExit` is set by an arrival the reader never saw as a
Back, and ONE Back later the application is gone. A regression inside this range: before
phase 11 that tap pushed.

Fix — decided: the boot records whether it laid a floor (one engine-scope boolean written by the
synthesis, false for a not-found arrival); `switchPage`'s back-to-home verb fires ONLY when the
floor exists; without it, the switch RECORDS (push) — stack `[guard, /typo, /acquisition]`, so
Back returns to the 404 as typed (8.2's contract intact — § 16 rule 1: the path taken beats the
floor, and the floor is « sans pile » only) and the next Back arms the guard. Holds in R69: the
walk above — after the tap, `armedExit` falsy and `history.length` grew by one; one Back → the
404 page, address as typed; the next Back arms the guard. Mutation: blind-step again → the hold
falls showing `armedExit` set on arrival.

## 12.2 — A page switch made FROM A LAYER never reaches the discipline · MAJOR

`data-go`'s `onLayer` arm and `data-navgo`'s `onDrawer` arm still replace the LAYER's entry in
place, leaving the abandoned page's nav entry sandwiched: drawer from `/media` → « Acquisition »
gives `[guard, acq, /media, acq]` — Back from the entry page lands on `/media` (rule 2 verbatim
forbids it), two acquisition entries, three Backs to leave. Same via the account menu. These are
the finger-reachable page switches from a layer; R69's hold (c) walks only the tab bar.

Fix — the OUTCOME is specified, the mechanism is measured on the spot: after a page switch from
a layer, the stack must be the rule-2 shape — `[guard, acq]` when the destination is home,
`[guard, acq, page]` otherwise — with the destination's state applied and no intermediate page
flashed. Candidate mechanisms, in order of preference: (i) replace the LAYER entry with the
destination AND replace the sandwiched nav entry on the way past — not possible with the History
API; strike it and say so; (ii) `__bridge.rewind(...)` to the floor then record the destination —
MEASURE how the unwind latch counts a multi-entry `go(-n)` (one traversal, one pop event) before
trusting it, and how the floor's state application interacts with `pilotage`; (iii) a two-step
(pop the layer entry, then switch as from the page) accepting one intermediate frame — only if
(ii) is unsound, and then the frame must be proven invisible (the oracle and no flicker in the
walk). If NO mechanism reaches the outcome without breaking a § 16 rule or R74's hard zero, STOP
and report — the operator arbitrates; never a half-application. Holds in R69 (or R65 for the
drawer): the drawer walk and the account-menu walk, each measured on `history.length`, where each
Back lands, and the guard's depth. Mutation: the old replace-in-place → the stack hold falls.

## 12.3 — The premise « the tab bar sits above the layers » is false, and two branches lean on it · MAJOR

Hit-tested at 390×844: the account menu, the follow panel and the drawer each cover
`#nav button[data-page]`'s centre. So (a) two `legacy.js` comments assert a stacking order the
interface does not have — rewrite them to the truth; (b) `switchPage`'s `onLayer` arm and the
BACK step-over branch of the direction-aware reopen are reachable only synthetically today —
KEEP the branches (they guard the stack against any future surface that exposes a switch over a
layer, and the Forward arm is real) but their comments must say what is measured: reachable by
`node.click()` and by future surfaces, not by a finger on today's layout; (c) the 10.1 tab-bar
holds in R56 stay (they drive by evaluate, which is exactly what they now claim to prove).
Re-measure after 12.2: if 12.2's mechanism makes the buried-sheet-entry shape impossible even
synthetically, say so in the step-over branch's comment — do not remove it in this phase.

## 12.4 — Smaller, confirmed

- Comment rot from the fourth seam (four boot writes; five comments still say three, D-8.5 says
  five writers): `url_state.py` items 10/§ blocks, `common.py` two sites (including « the first
  push of the load », now false), `legacy.js` « THE THREE WRITES BELOW », phase-8 D-8.5. One
  sweep, each corrected to what runs.
- Two wave references in harness comments added by this very wave (`common.py` « in the very
  wave that wrote the comment », `url_state.py` « two of this wave's defects ») — reworded
  undated.
- `screen_addresses.py` re-declares the model readers `common.py` now exports — import them.
- `common.py` hardcodes `HOME`/`HOME_PAGE`/`LIBRARY`/`ARRIVALS` five lines above the
  `PAGE_PATHS` it could derive them from — derive (`HOME_PAGE` from the model's
  `HOME_PAGE = "acq"` line or `PAGE_PATHS`), keep the names.
- The addressing reader (10.3) misses QUOTED keys: `({ "page": … })` and a quoted destructured
  key pass clean because `_strip_noise` blanks strings first — collect quoted keys at key
  position from the source slice; two red-first cases.
- `scratch_call_offenders` reads docstring prose as call sites (a docstring example
  `start_server(8918, ROOT)` is an offender) — strip comments/strings first; one case.
- R69's (e) hold name « leaves the surface instead of undoing it » overstates for the
  acquisition-tab iteration (the Back reaches the guard there) — name what all three iterations
  share (« never undoes it »).
- `raw?.["x"]` is matched but has no dedicated red case — add it.

## Ignored, with reason

- The 404 keeping no floor on its own walk (Back re-pushes the address as typed, then the guard):
  8.2's contract, § 16-compatible once 12.1 stops the blind step; deliberately unchanged.
- `BOOT_WRITES` in `common.py` as a fixture table: a mechanism's fixture, not a hold — left.
- `add-screen.tsx`'s `toFollows()` navigating with `page` in the query: pre-existing, invisible
  to the arm (feature file), recorded as an open point for the operator.
