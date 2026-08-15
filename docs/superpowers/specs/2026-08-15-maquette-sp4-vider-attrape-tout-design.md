# Maquette SP4 — emptying the catch-all, surface by surface

**Status**: approved by the operator (2026-08-15, section-by-section review; every
arbitration below is theirs) · **Branches**: `feat/maquette-sp4a` → one per wave
**Scope**: sub-project 4 — the legacy engine leaves the catch-all route one surface at a
time. Screens and pages become real routes and real React components — FINAL code, not a
throwaway rewrite. SP4 ends when `refonte.html` is empty and retires as the editing
source (the end SP3 already named). It also settles the three evaluations deferred since
SP1: TanStack Store/DB (state ownership — settled in this spec), Konsta UI and Motion
(bounded spikes, verdicts recorded here by amendment).

## Context — what the code actually is (measured, not assumed)

- The legacy engine is ONE classic inline script of ~36,500 lines (refonte.html lines
  4504–40977): a global `state` object, a global `render()`, `applyState(patch)`
  redrawing everything. 270 `state.*` reads, 64 direct-write lines plus 3
  `Object.assign(state, …)` sites, a handful of data mutations (`follows.splice` /
  `unshift`).
- **Pages**: `PAGES_OF()` — `acq`, `lib`, `arr`, `sys` (+ maintenance / configuration
  off-bar), each with its `view*` render function. Addressed by
  `?page=&tab=&lens=&mode=&cat=&rub=` (`etatDeLURL`).
- **Screens**: `openFiche`, `openAddScreen`, `openResolve`, `openReleases`,
  `openProfil` — all through `openScreen(html, cle, rendre)` + the `pileEcrans` stack
  (R71). **No screen has an address today**: screens live only as history entries via
  `__pont.coucher("screen")`.
- **Layers**: `#sheet` (the derived panel), `#drawer`, `#screen` — history entries,
  never addresses.
- The SP3 shell: one catch-all route `/`, `validateSearch` over the six params,
  `component: () => null`, the legacy DOM outside the React root. The router is the
  single writer of the history; the 12 legacy nav sites speak `window.__pont` (five
  verbs) through a queue-and-replay pre-bridge in the envelope.

The opens named by the SP3 reviews, all settled by this spec: two query-string parsers
(§ ownership law), `commitLocation` as second writer (§ framed navigation), a route
table measured by nothing (§ addresses + SPA fallback), the pre-bridge's fail-silent
path (§ boot inversion), the CSS extraction frontier with SP5 (§ rendering
cohabitation), the maquette typecheck gate absent from CI, `/favicon.svg` 404, the
permanent `/assets/` portal rule (§ wave A housekeeping).

## Operator arbitrations (settled 2026-08-15)

1. **Delivery**: one PR per WAVE (SP4a, SP4b, …). Each wave merges with the full suite
   green; the design host always serves a complete, judgeable app.
2. **Pilots**: Profil first, then Ajout, both in wave A — the smallest screen pays for
   the machinery at minimal risk; Ajout then exercises what Profil does not (state →
   search params, typing, real results).
3. **Evaluations**: state ownership settled IN this spec (TanStack Store adopted —
   approach B below). Konsta UI and Motion: one bounded spike each at the head of wave
   A, throwaway code, verdict recorded here by amendment. Prior stated to the operator:
   Konsta imposes its own native visual language, in frontal tension with the
   pixel-reference maquette (R47 metrics) — expected verdict is no; Motion is judged
   only against a real animation need.
4. **Addresses**: hybrid — real PATHS name migrated screens, QUERY carries their
   internal state (`/fiche/Titre?saison=2`). Consequence accepted: SPA fallback lands
   in `serve.py` AND in the harness's static server, and the route table finally
   becomes measured.
5. **State**: approach B — a TanStack Store owns the state from wave A, under four
   binding conditions (below). The operator chose B over "legacy stays master with
   domain hooks" knowing the counter-argument (B invests in code scheduled for
   deletion); the measured write-site count (~70) made it tractable, and B buys a
   use-based Store verdict and no end-of-SP4 ownership flip.

## The waves

| Wave                             | Content                                                                                                                                                                                                                                                                                                                                                        | What it proves                                           |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **SP4a — the machinery**         | Konsta/Motion spikes (verdicts recorded); boot inversion (pre-bridge retired); the TanStack Store + synchronous alias + ~70 write sites; SPA fallback (`serve.py` + harness server); domain hooks; **Profil then Ajout** as real routes; new rules R75/R76, R73 amended; maquette typecheck gate into CI; `/favicon.svg`; the permanent `/assets/` portal rule | All the plumbing, paid once, on the two smallest screens |
| **SP4b — the fiche**             | The most connected screen, plus the **panel** (`openSheet`) migrated with it — the fiche is its biggest producer; legacy sites open the panel through the shell                                                                                                                                                                                                | The product's centre holds in React                      |
| **SP4c — resolution + releases** | The two arbitration-flow screens                                                                                                                                                                                                                                                                                                                               | The acquisition flow crosses both worlds                 |
| **SP4d… — the pages**            | One wave per page or pair, simplest first (fixed at plan time): sys/maint/config, arr, lib, acq; the **drawer** migrates with its last consumer                                                                                                                                                                                                                | The catch-all empties                                    |
| **SP4-end — the engine dies**    | Fragment empty; `refonte.html` retired as editing source; bridge + `__rejouerLePont` + state alias removed; R72/R74 renegotiated (recorded); `__go`/`__states` reimplemented shell-side                                                                                                                                                                        | Only final code remains                                  |

**The editing source switches PER SURFACE, not at the end.** When Profil migrates, its
code leaves the fragment; from then on, for a migrated surface, "the design starts in
the maquette" means "starts in its component". The CSS contract (BLOCK 2, extraction,
`regions.json`) does not move — SP4 converts structure and behaviour at IDENTICAL
markup; the visual language stays SP5's question.

## Boot inversion — the pre-bridge retires

SP3 solved "the classic script runs before the module" with a recorder/replayer, whose
fail-silent path the reviews named: a module never evaluated leaves the verbs mute
under an app that looks alive. Wave A needs the store (a typed module under `src/`) to
exist BEFORE the engine reads state — the same problem, harder, because there are
reads.

Instead of stacking a second recorder, **the sequence inverts**. The fragment stops
booting itself; it defines everything and exposes `window.__demarrerMoteur(deps)`. The
shell — store created, real bridge installed — starts the engine once mounted.

- The queue-and-replay pre-bridge **retires** (nothing left to record); the `pret`
  probe goes with it; R74 amends accordingly — recorded in `regions.json`.
- The fail-silent path **dies structurally**: a module never evaluated leaves the
  startup screen on screen — a visible, truthful state the harness knows how to see.
- The startup screen covers the wait; it is declared first inside the frame for
  exactly this reason. No perceived cost.
- The boot order becomes a one-line explicit contract instead of a recorded
  choreography.

## State — approach B, four binding conditions

A TanStack Store (in `src/`, typed) owns the mutable state from wave A. The ~70 write
sites (64 direct writes + 3 `Object.assign` + the data mutations) convert to store
writes; the engine receives the store through the boot handshake.

1. **Domain hooks are the only door for components** — `useSuivis()`,
   `useFiche(titre)`, `useRecherche()`, … on `useSyncExternalStore`. No component ever
   reads the store directly. The hook boundary is what survives the backend-binding
   mission: the store carries SIMULATED data, so binding replaces hook internals, never
   components.
2. **The 270 legacy reads are not rewritten**: a module-global alias, resynchronised by
   subscription, keeps `state` always pointing at the store's current state. Only the
   write sites convert. Verified at plan time: the store's notification is
   **synchronous** (read-after-write within one function must hold).
3. **Legacy `render()` stays explicitly called**, never subscribed to the store —
   behaviour byte-identical, no re-render storms. Only React subscribes.
4. **Data mutations** (`follows.splice`, …) go through the store or notify it —
   otherwise a React surface showing follows does not redraw on a legacy action.

These four conditions are invariants of EVERY wave, not wave-A conveniences.

TanStack DB is **not** adopted in SP4: it answers live-data synchronisation, which is
the binding mission's question. Recorded as the evaluation's verdict for the DB half.

## Addresses

- **`/` remains the pages' route**, its legacy query intact — the existing R69
  assertions do not change by one byte.
- **Screens become paths**: `/profil/:titre`, `/ajout` (`?q=…&mode=identifier`),
  `/fiche/:titre` (query for internal state, e.g. the open season),
  `/resolution/:dossier`, `/releases/:titre`. Percent-encoding, **NFC** normalisation
  (the macOS trap already paid for on the indexer).
- **Title-as-identity is assumed**: it is the whole maquette's identity model
  (`data-panel="media:<title>"`). Known weakness, recorded as an assumed open — the
  binding mission brings real IDs; the route params change then, not before.
- **Deep entry**: a cold `/fiche/Titre` renders the fiche above the default opening
  page; back closes the screen and lands on that page. A screen path is written only
  while a screen is open (R69's spirit: only what differs is written).
- **SPA fallback**: `serve.py` serves `dist/index.html` for any unknown non-asset path
  (same session gate); the harness's static server does the same with the copy. The
  route table becomes measured: R75 drives real deep paths.

## One owner per address — the cohabitation law

> **Each address shape has ONE owning world, and the address names its owner.**

- The query of `/` belongs to the **legacy** parser (`etatDeLURL`) while any legacy
  page remains; `validateSearch` stays passive (validation without driving) until
  pages migrate — then ownership flips page by page.
- Screen paths belong to the **router** alone (`useParams`/`useSearch`).
- **The pop dispatcher follows the same law**: on a pop, the shell looks at the landed
  address — a screen path → the router renders, nothing is forwarded to the legacy;
  `/` with a nav entry → forwarded to `surRetour`, the legacy redraws as today. This
  is what keeps `applyState` from misreading a React screen's entry, and conversely.
- **The first `navigate()` is framed**: `commitLocation` pushes without `flush()` and
  merges same-task writes — but the legacy unwinding logic COUNTS entries. So: every
  programmatic navigation goes through one shell helper (`aller(...)`) that navigates
  AND flushes; a bare `navigate()` is forbidden in `src/` (source-read assertion, the
  same gesture as R74's "zero raw history calls"). One history entry per logical
  navigation, by construction and by rule.

## Rendering and data cohabitation

- **A migrated screen renders inside the React root** (`#coquille`) with the SAME
  markup the legacy emitted — same tag+class chains (`.screen > .port`, the same
  BLOCK 2 classes). That is what keeps the CSS unchanged and the rules green at
  unchanged rule code. Real, final JSX — not a wrapper around `cardHTML` — but at
  identical emission.
- **Cross-world stacking** works through z-index and the shared history: the legacy
  `#screen` overlay stays above the React root (a legacy screen opened from a React
  screen covers it); a React screen pushed above a legacy screen covers it without
  closing it — back replays the ownership law.
- **Legacy sites that open a migrated screen** call a shell-exposed function
  (`__ecrans.profil(titre)` → `aller(...)`); the call site changes one line, the logic
  stays.
- **The boot handshake**: `__demarrerMoteur(deps)` receives the store and the bridge,
  and publishes back the embedded data and the engine's actions (`donnees`,
  `actions`). Domain hooks read the store for the mutable, the handshake for the
  static and the actions. Each wave, what migrates leaves the fragment for `src/` and
  leaves the handshake.

## Rules and measurement

- **Every wave's gate**: R59, R69, R71 green at UNCHANGED rule code — the proof a
  migration does not break navigation. Any exception is a recorded amendment in
  `regions.json`, never a workaround.
- **New rules in wave A**:
  - **R75 — screen addresses**: deep entry lands on the promised state; back lands on
    the page underneath; the path is written only while a screen is open; real deep
    paths driven through BOTH servers' SPA fallback (the route table is thereby
    measured).
  - **R76 — framed navigation**: zero bare `navigate()` in `src/`; one history entry
    per logical navigation. Mutation: removing the helper's flush must fell an
    entry-counting hold naming the mechanism.
  - **R73 amends** for `serve.py`'s SPA fallback.
- **Rules amended along the waves, recorded**: R74 shrinks with the bridge (pre-bridge
  retired in wave A, bridge dies at SP4-end); R72 keeps holding the fragment verbatim
  ×1 — a shrinking fragment is still the fragment. At SP4-end, `__go`/`__states`
  reimplemented shell-side keep the 74 states drivable — otherwise the whole harness
  goes dark with the engine.
- **CI**: the maquette typecheck gate enters the workflow (today carried by
  `make check` only); `/favicon.svg` served; the permanent `/assets/` portal rule
  written — the SP1/SP3 debts close in wave A.
- **Execution discipline**: subagent-driven as on the four previous PRs — exit code is
  the verdict, every report re-derived, one mutation per rule, output pasted.

## Delivery

Branches `feat/maquette-sp4a` → one per wave; one PR per wave; Conventional Commits,
scope `(shell-mobile)`, French messages; patch version bump every PR; squash-merge on
green CI + clean adversarial review (standing operator instruction). The Konsta/Motion
spikes at the head of wave A: throwaway code, verdicts recorded here by amendment. The
design host serves this checkout live — every merged wave leaves the app complete and
judgeable.

## Verification (all executed, none assumed)

- Per wave: full suite green (45+ rules) measuring the rebuilt copy; `make check`
  green; R59/R69/R71 green at unchanged rule code; new/amended rules
  mutation-verified with the result pasted; push SHA verified after every push
  (SIGPIPE 141); PR, CI green, squash merge, post-merge live check on the design host.
- Wave A additionally: boot-inversion mutation (module never evaluated → startup
  screen stays, harness sees it); store-alias synchronicity proven before the write
  sites convert; R75/R76 mutations; both spikes' verdicts recorded in this spec.

## Out of scope

- The visual language (semantic CSS vs Tailwind, BLOCK 2's future) — SP5.
- Binding to the backend, real IDs in routes, TanStack DB — the binding mission.
- Any behavioural or visual change to a surface while it migrates: conversion at
  identical markup and behaviour. A design change remains a separate, maquette-first
  edit.

## Assumed opens (named, not hidden)

- Title-as-identity in screen paths (real IDs at binding time).
- "Forward is not a return" stays as the faithful legacy trait (SP3 decision).
- `history.block()` would defeat `flush()` — still true; nothing in SP4 introduces it.
