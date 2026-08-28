# L09 — The data layer, surface by surface

**Lot** `L09` of `docs/reference/frontend-architecture.md` § 4, Phase 3.
**Depends on** L01, L05, L08 — all `LANDED`.
**Branch** `feat/maquette-l09`. **Codename** `maquette-l09`.

**The constitution's §§ this wave serves.** §13 (« L'interface reflète l'état réel des données…
Elle n'a pas d'état à elle : tout ce qu'elle affiche est dérivé des données ») — this lot IS §13
made structural. §15 (the maquette is the product). DOIT-2 and DOIT-5 (a « rien » shows its
reason; going to the end is visible), DOIT-4 (a legitimate action is always accepted — which is
what an optimistic path is for), NE-DOIT-PAS-1 and NE-DOIT-PAS-5 (never lie, never fail
silently — which is what a rollback is for).

---

## § 1 — What this lot is, measured on the day it opened

Every figure below carries the command that produces it. None is copied from a brief.

### The surfaces read the engine synchronously, at render

A surface calls `useXReference()` and reads `window.__referentiel` — one object the engine
publishes at definition time. There is no cache, no request, no loading that is not simulated by
a `setTimeout` inside the component. The mock layer L08 built answers 53 operations and **no
surface asks it anything**.

<sub>`grep -rn "useWorld\|useStoreContent\|useUiState" frontend/maquette/design/src/{features,app,ui,lib,routes} | wc -l` → 46 reads of the store; `grep -rn "fetch(" frontend/maquette/design/src/features | wc -l` → 0</sub>

### What the subtraction removes (D5)

The register classifies **41** of the 81 fixture families `served`. Bracket-matched in
`legacy.js`, **38** of them have a measurable top-level span and those spans cover
**26 277 of the file's 35 264 lines — 75 %**.

<sub>method: bracket-match every indented `const NAME = [` / `{` in `engine/legacy.js`, sum the spans of the families the register classifies `served`</sub>

That is what dies as surfaces convert. It does not die in one commit: **each surface's share dies
in the commit that wires that surface**, which is D5's whole shape.

### Server state living in the interface's own store

The store is an open bag — `type UiState = { page: string; [key: string]: unknown }` — so no type
declares what is in it. Measured from the WRITES instead: **39 distinct keys, 82 write sites**.

<sub>method: extract the object keys of every `writeUiState({…})` / `__store.write({…})` literal under `design/src`</sub>

Eleven of those keys name server state rather than interface state, and they are this lot's
falling ratchet:

`libCount` `libErr` `libLoading` `libFailedOnce` `sugCount` `sugGone` `sugLoading` `phase`
`added` `notFound` `pipe`

Invariant 4 says server state is never copied into client state. It is violated eleven times
today, by construction, and nothing measures it.

### The unit-test layer does not exist

`design/package.json` carries `dev`, `build`, `preview`, `typecheck`, `generate-contract-types`
and no test script. L04 measured **11** of 31 non-component functions pure and testable without a
browser, the meatiest being `epState` — **8 branches**, touched today by **3 assertions in one
browser rule**. The debt was recorded against this lot; the mock layer it was waiting for exists.

### `app/shell.tsx` has grown at every wave

**760** non-blank lines against invariant 6's hard ceiling of 400 — 794 counting blanks, and the
ceiling counts non-blank, so 760 is the figure that matters. It was 727, then 747, then 760. It is
grandfathered « until its surface's wave converts it » — this is that wave, and the shell is
phase 1 of it, because a file is split BEFORE it is added to, never after.

<sub>`grep -c . frontend/maquette/design/src/app/shell.tsx` → 760 · `wc -l` → 794</sub>

### B-090, measured rather than quoted

The register says « a four-element list becomes *multi, vf, vostfr +1* ». Measured over all
**159** settings fields: **59** differ from `String(raw)`, and only **2** lose information.
(This line first said 110 and 15. The 110 came from comparing `JSON.stringify(raw)`, which
counts the quotes around a string as a difference, and the 15 counted every elision-looking
rendering rather than the ones that actually elide. Both were corrected by re-running the
method this section states, which is the point of stating it.)

| Family | Count | What is lost |
| --- | ---: | --- |
| Truncated lists | **2** | `library.audio.profile_priority` (4 → « +1 »), `overlays` (18 → « +15 ») |
| Numbers | **7** | JSON carries `4`, the screen shows « 4.0 » — the float-ness is not in `raw` |
| Cron strings | **6** | `15 * * * *` → « toutes les heures, à la 15ᵉ minute » — a renderer, not a value |

The other 57 differences are **reproducible** from `raw`: a boolean renders « oui »/« non », a
short list joins on « , », an empty list renders « aucun », a list of objects renders « N entrées ».

<sub>method: read `design/src/mocks/seeds/settings.json`, compare `raw` against `displayedValue` per field and group by what the difference is</sub>

**So the numbers are the only irreducible loss**, and they are irreducible in the SEED, not in the
interface: a precision the JSON cannot carry. The other two families are recoverable the moment
the interface does the formatting.

### The reference, before anything is touched

`frontend/maquette/harness/run.sh --oracle` on this branch's first commit: **83 states × 33
regions, 2 739 measurements, reference taken at `12a134ca`, no divergence.** Measured, not
assumed — every zero this document promises later is measured against this one.

---

## § 2 — Decisions

Three were arbitrated by the operator on 2026-08-26, before the wave opened. The rest are the
wave's, recorded here so they can be contested by name.

### D-L09-1 — The query cache is `@tanstack/react-query` (operator, 2026-08-26)

**Decided.** Server state lives in TanStack Query's cache. Mutations use its
`onMutate` / `onError` / `onSettled` shape for the optimistic path and its rollback.

**Why, and it is D9 rule 2 applied rather than a preference.** « A library is adopted for maths
nobody has written. Never for an arbitration already proved. » A query cache is the first: request
deduplication, staleness, invalidation fan-out, and — the part this lot must not get wrong — a
rollback that restores the exact snapshot a failed mutation departed from, across concurrent
mutations on one key. None of that is an arbitration this repository has proved; all of it is
code someone else has proved.

**It is the same family as what is already here** — `@tanstack/react-router` and
`@tanstack/store` are dependencies today — so the store the router already owns and the cache
share their reactivity primitive rather than contending.

**What it costs, recorded rather than discovered.** One dependency, and the bundle grows. The
figure is measured in phase 3 and written into the plan's ACCEPTANCE, never estimated here.

**Rejected: hand-rolling it on `@tanstack/store`.** Zero new dependency, and it re-writes
deduplication, invalidation and rollback as maquette code nobody will review as carefully as a
library that thousands of applications run. D9 rule 2 names this exact trade and refuses it.

### D-L09-2 — The unit-test runner is Vitest (operator, 2026-08-26)

**Decided.** Vitest, reading the maquette's own Vite configuration. Tests live where L04's target
tree already reserved them: `features/<domain>/*.test.ts`, plus `lib/*.test.ts`.

**Why.** It reads the config that BUILDS the maquette, so the path aliases, the TypeScript setup
and the `__MOCKS_BUILT_IN__` replacement are the real ones rather than a second declaration that
can drift from them. And `frontend/package.json` — the production app — already runs Vitest, so
this is the repository's runner and not a new one.

**It is collectable without a browser, and that is a gate condition rather than a nicety.** B-077
cost a wave: a test of the browser-free half of a rule could not be collected without a browser,
CI caught it and no local gate did. Every test this lot writes runs headless, in `make check` and
in CI.

**What it must NOT become**, and it is B-075's shape said for tests: a test that imports the thing
it asserts and re-derives the expected value from it. The seeds are the oracle outside the
tool — a formatter's test asserts against the `displayedValue` **committed in the seed**, which
was extracted from `legacy.js` and is held byte for byte by `check-mock-seeds.py --arm
correspondence`. That is what makes these tests non-vacuous, and it is the whole reason the debt
waited for L08.

**Rejected: `node:test` + `tsx`.** No new dependency, and it does not read the Vite config — the
aliases and the build-time replacement would be declared twice, which is the drift this file's
own § 6 traps warn about one directory over.

### D-L09-3 — B-090 is repaired here: the interface formats, `displayedValue` dies (operator, 2026-08-26)

**Decided.** The settings surface reads `raw` and formats it. `displayedValue` leaves the
contract. The formatter is a pure function in the settings feature, and its test asserts against
the 159 `displayedValue` strings the seed still records — which is why the field leaves the
CONTRACT and stays in the SEED until the last phase.

**Why it cannot be deferred again.** A pre-formatted French value cannot feed a control. Wiring
the settings panel's eight field kinds to a string that says « 4 entrées » means the panel can
display and can never edit, and the surface is the last but one in the order. #503 fixed the NAME
(B-089's class); the VALUE is this lot's.

**The one thing that stays a demand.** Seven number fields render a decimal `raw` does not carry
(`4` → « 4.0 »). No formatter can recover that from JSON, so the contract gains a precision the
backend must supply, and `docs/reference/frontend-backend-demands.md` records it. D7's shape
exactly: carry what is knowable, record what is not.

**What is forbidden outright, and it is B-087's lesson:** re-deriving the truncated lists' hidden
elements from anywhere but `raw`. `raw` has all four; the renderer dropped one. Reading `raw` is
recovery, not re-derivation.

### D-L09-4 — Every generic thing this lot writes lives in `lib/` or `app/` (invariant 10)

The query client, its cache policy, the formatters that know no domain, the loading and error
primitives — none of them lives under `features/`, whatever surface they were first needed for.

**Why it is written down even though the invariant exists.** The invariant is **unarmed**
(B-100). Nothing counts it, so nothing stops the query client landing in `features/library/`
because the library is the surface that motivated it. This lot writes more generic code than any
lot before it, so it is the one most able to violate an invariant nobody measures.

**This lot does not arm it.** B-100 names the arm's shape and its two traps; building it is not
in this lot's `Done when` and folding it in would be a second kind of change in one wave (§ 0).
What this lot owes is to hold it, and to say at its close whether the counts moved.

### D-L09-5 — `app/shell.tsx` splits on a SUBJECT, in its own phase, before anything is added

Five subjects, each a file: the router tree, the history and the legacy bridge, scroll
restoration, the panel, the boot. `csstokens_login.py` is the named model — L07-bis split three
guards this way and each came out under the soft ceiling without a line being written for the
count's sake.

**It is phase 1 and it lands alone.** A split proves the rendering did not change; wiring proves
the data moved. One kind of change per wave is § 0's rule, and per PHASE is how a fifteen-phase
wave honours it. The oracle at zero is the split's entire proof.

### D-L09-6 — The oracle is proved to WAIT before the first surface is wired

`window.__mocks.quiet()` is read by `oracle.py`'s settle today and resolves immediately, because
nothing fetches. It is the single instrument this whole lot's proof rests on, and it has never
been exercised against a request in flight.

**So phase 3 does not end when the query client exists.** It ends when a deliberate latency —
injected through the scenario surface L08 built — is shown to make the oracle wait: measured
with the delay, the oracle reads the SETTLED rendering; measured with the settle disabled, it
reads the skeleton and diverges. Break it on purpose, see it fall, restore. Invariant 11, applied
to an instrument rather than to a rule.

**If it does not hold, the lot stops there and says so** (§ 7.1). Wiring eleven surfaces against
an oracle that measures mid-flight would produce eleven accepted divergences and no proof at all.

### D-L09-7 — A divergence is accepted by name or it is a defect

If a wired surface does not render what it rendered, the difference is understood, written down
with the reason, and accepted in the oracle's allowlist entry by entry — never explained by « the
data changed ». The mocks are seeded from the fixtures they replace and held byte for byte
(`check-mock-seeds.py --arm correspondence`), so « the data changed » is a statement that guard
would refuse.

---

## § 3 — What the instruments do NOT read

**Written before the guards, not after them.** The count of « a guard green over what it does not
read » stands at **26** across three waves (`BUGS.md` § Guards green over what they do not read),
nine of them in the last one and four of those inside instruments that wave had written itself.
This section is the pre-emption.

### The invariant-4 arm

**What it reads:** the object keys of every `writeUiState({…})` and `__store.write({…})` literal
under `design/src`, matched against a named list of keys that carry server state.

**What it does NOT read**, and each of these is a way for it to be green over the defect:

- **A key written through a variable** — `write({ [name]: value })` — is invisible to it. It must
  therefore REFUSE a computed key rather than skip it, and say so when it does.
- **The engine's own writes.** `legacy.js` writes the store too. Those are the dying half and are
  not the ratchet's subject, but the arm must say how many it skipped, or « 11 » silently becomes
  « 11 of the ones I looked at ».
- **A key that carries server state under an interface-looking name.** No arm can judge that. The
  list is named and reviewed; the arm holds the COUNT against the list, and a new key not on
  either list fails rather than passing.

**It cannot be pre-satisfied**, and that is the point: it starts at **11** and is refused
**upward**. A floor set where the count already sits is B-075's exact shape and this one is not
one — it has eleven real things to remove before it is at zero.

### The invariant-5 arm

**What it reads:** the body of every `useEffect` under `design/src`, refusing a fetch, a
`queryClient.fetchQuery`, or a call to any hook the query layer exports.

**It IS at zero the day it is written, and that is the danger.** The corpus is **3** `useEffect`
call sites today (`grep -rn "useEffect(" design/src/{features,app,ui,lib,routes} | wc -l`). An
arm that finds nothing and prints « no violation » is indistinguishable from an arm that read
nothing. So it **declares the corpus size on every run and refuses a corpus below a floor** — the
floor being the count at the phase it lands, which grows as surfaces wire and may never fall
silently.

### The formatter tests

**What they read:** the `displayedValue` strings committed in `mocks/seeds/settings.json`.

**What they do NOT read:** the engine's renderer. That is deliberate — the seed is the extracted
copy, held against `legacy.js` by an existing guard, so the test rests on a proved artefact rather
than on the code under test. **But it means a formatter and a renderer could both be wrong in the
same way if the extraction were wrong**, and the answer to that is the extraction guard, not a
second test here. Named so nobody adds a redundant one believing it adds a check.

### The oracle, in this lot specifically

It reads a rectangle and 19 computed properties, **at rest**. It does not see:

- a **loading state that flashes and settles** — by construction, and that is what the settle
  signal is for. A surface that renders its skeleton for 400 ms and then the data measures as the
  data. That is correct and it is also a blind spot: a wired surface could be slow in a way no
  measurement here reports.
- a **pseudo-element** (D8, B-061, arbitrated not to widen).
- **which request produced a rendering.** Two different queries answering the same bytes are one
  reading to it. The mutation tests are what tell them apart.

---

## § 4 — What the oracle will say

**Zero divergence, on every phase, and that is this lot's whole claim.**

The mocks are seeded from the fixtures they replace and held byte for byte, so a surface reading
the mock renders what it rendered reading the fixture. A movement is therefore a defect until
proved otherwise, and this is the one lot in the plan where that inference is sound.

**Three places where it may legitimately move**, named in advance so they are not discovered as
surprises and waved through:

1. **The settings surface (phase 11).** The interface starts formatting what the engine used to
   format. If the formatter is exact, nothing moves — that is the test's job, over 159 fields. If
   something moves, the formatter is wrong, not the data.
2. **A surface whose loading state now really exists.** Where a component simulated a delay with
   `setTimeout` and now awaits a query, the settled rendering is the same; the intermediate is
   not measured. No divergence is expected, and if one appears it means the settle did not hold —
   D-L09-6's failure mode, not an acceptable difference.
3. **The shell split (phase 1).** A move, so nothing may move. Any divergence here is the split
   having been an edit.

**No allowlist entry is written without its reason and the operator seeing it.**

---

## § 5 — Phases

Thirteen. The eight surface phases walk the order L07 fixed (its phases 5–15), because both lots
walk every surface and walking them in the same sequence is what makes the second pass reuse the
first one's understanding.

| # | Phase | What it lands | What proves it |
| --: | --- | --- | --- |
| 1 | The shell splits | `app/shell.tsx` 760 → five files on five subjects | oracle at zero; a move, not an edit |
| 2 | The runner | Vitest, and the pure functions L04 counted | collected without a browser, in `make check` and CI |
| 3 | The query client, and the settle proved | `lib/` client + `app/` provider; the quiet signal exercised against a real latency | oracle at zero before AND after; the settle seen to fall and restored |
| 4 | The state primitives | loading / error / empty in `ui/`, fed by query state | a rule that bites, mutation-tested |
| 5 | Arrivées, and its resolution screen | its queries, its mutations, its fixtures removed | oracle at zero |
| 6 | Médiathèque | the card, the tiles, selection, filters | oracle at zero |
| 7 | Acquisition — the deck and the follows | | oracle at zero |
| 8 | Acquisition — the add screen, releases, quality | | oracle at zero |
| 9 | Média — the sheet, the matrix, the popover | | oracle at zero |
| 10 | Système, and Maintenance | | oracle at zero |
| 11 | Configuration, and B-090 | the formatter, `displayedValue` out of the contract, the precision demand recorded | 159 fields asserted; oracle at zero |
| 12 | Compte, and the install proposal | | oracle at zero |
| 13 | The close | the two arms at their final counts, the demands recomputed, the register, the B-085 recount | full suite, `make check`, oracle |

**Every surface phase carries the same four things**: its reads through the cache, its mutations
with an optimistic path and a rollback (or a written reason there is none), its share of the
fixture removed in the same commit (D5), and a rule that bites.

**The gate is run AFTER the phase, never after a commit inside it.** L08-bis missed a three-command
split for exactly that reason.

---

## § 6 — Out of scope, named

- **Any backend work.** Divergences are recorded as demands (D7), never coded.
- **Harvesting `frontend/src`.** It is archived at switchover, never a model.
- **Arming invariant 10** (B-100). Named, held, not built here — D-L09-4.
- **The live relay** (L10) and **offline** (L11). This lot's cache is what they attach to; neither
  is started.
- **Bundle splitting** (L12), even though the build already warns about chunk size. It changes
  loading behaviour; this lot changes where data comes from.
- **Re-litigating** D3 widened, D8's limit, D10, invariant 10, B-061 not widened.
- **De-duplicating `BUGS.md`'s seven repeated rows and the two invariants numbered 10.** Both are
  real and both are recorded by this wave as findings. Neither is edited by it: § 7.1 says a
  record is corrected by what is added beside it, and the numbering belongs to whoever owns § 3.
