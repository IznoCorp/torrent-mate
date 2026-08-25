# L08 — The data contract and the mocks

**The lot is `docs/reference/frontend-architecture.md` § 4 → Phase 3 → L08, and that entry's
« Done when » is the contract this document serves. It is not restated here in other words** —
a requirement written twice is a requirement that drifts. What this file adds is: what the
ground actually looks like measured on the day the wave opened, the decisions taken over it, and
what the instruments this wave builds **do not read**.

- **Lot**: L08 — The data contract and the mocks · _depends on L04 (`LANDED`)_
- **Selected by** § 0's rule: the first lot not `LANDED` whose dependencies are all `LANDED`.
  No lot was skipped; none above it carries a blocking note.
- **Branch**: `feat/maquette-l08` · **Version**: 0.98.40 → 0.98.41 (patch)
- **Constitution §§ served**: §13 (the interface reflects the real state of the data — the whole
  reason the mocks are seeded and not invented), §15 (the maquette IS the product, and its
  « not connected to the backend while it is a maquette » ruling of 2026-08-20 is what this lot
  respects by mocking rather than wiring), §méthode (proof, not re-reading). DOIT-2, DOIT-5 and
  NE-DOIT-PAS-5 are served indirectly: the contract carries the reason a « nothing » is a
  nothing, and the mock layer serves failure so that a failure surface can be judged at all.

---

## § 1 — What this lot is, measured on the day it opened

**Every figure below carries the command that produces it.** They were taken on 2026-08-25
against `main` at `ec38ff49`.

### The maquette has no data layer at all, and that is deliberate rather than late

|                 | Production                   | Maquette                                                |
| --------------- | ---------------------------- | ------------------------------------------------------- |
| API modules     | 11 (`frontend/src/api/*.ts`) | **0**                                                   |
| Network calls   | 65                           | **1**, and it is the logout at `engine/legacy.js:11514` |
| WebSocket files | 24                           | **0**                                                   |

<sub>`IMPLEMENTATION.md` § THE OBJECTIVE carries these commands; the maquette's arm needs
`--include='*.js'` because its single call lives in the engine.</sub>

What stands in their place is **fixture literals inside the dying engine**.

```
node scripts/extract-maquette-fixtures.mjs --measure
```

**64 module-level fixture families, covering 28 776 of `legacy.js`'s 35 198 lines.**
Two further pure literals sit INSIDE a function (`steps`, the journey sheet's five stages, and
`TONS`) and are named separately below, because a fixture with no module-level name is invisible
to any extractor that walks declarations — and being invisible is exactly the property this
wave's guard must not inherit.

The ten largest, which are most of the mass:

| Family          | Shape  |  Lines | Entries |
| --------------- | ------ | -----: | ------: |
| `SHEETS_RAW`    | object | 20 538 |     326 |
| `SETTINGS`      | array  |  1 454 |       6 |
| `OWNED`         | object |  1 383 |     247 |
| `trailerIds`    | object |  1 315 |     288 |
| `SYNOPSIS`      | object |    672 |     340 |
| `LIBRARY`       | array  |    527 |     345 |
| `POSTERS`       | object |    415 |     401 |
| `SUGGESTIONS`   | array  |    388 |      38 |
| `HERO_IMAGES`   | object |    328 |     318 |
| `MAINT_ACTIONS` | array  |    236 |      26 |

**40 of the 64 are published through `window.__referentiel`; 24 are not.** The unpublished ones
are not lesser — they are `LIBRARY`, `FOLLOWS`, `SHEETS_RAW`, `OWNED`, `SUGGESTIONS` and the
seven arrivals arrays, reached by components only through the engine's own emitters and
`derived*()` arrows. This is the fact that decides where the extractor reads: **`legacy.js`, and
never `app/reference.d.ts`**, which says so itself.

### The fixtures are REAL DATA, and that is why inventing would be a loss

`frontend/maquette/README.md` § « What is real in here, and what is not » records where each
family came from: the library titles, categories and counts from `library.db`; the twelve
follows with their true states from `acquire.db`; 247 series and 9 218 owned episode numbers from
`library.db`; 9 779 episode titles and air dates from TMDB; 288 trailer ids from TMDB `/videos`;
the grab cadence from the live scheduler. `scripts/refresh-maquette-fixture.py` exists precisely
because one of them keeps moving with the database it mirrors.

So the lot's binding clause — seed from the fixture, never invent — is not a proof technique
bolted on. **The fixtures are the only real data this interface has ever been drawn against**,
and a mock that departed from them would be a worse mock as well as an unprovable one.

### The existing backend contract, and the size of the gap

```
python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(len(d['paths']),sum(1 for p in d['paths'].values() for m in p if m in ('get','post','put','patch','delete')),len(d['components']['schemas']))"
```

**61 paths, 65 operations, 114 schemas.** D7 says the maquette's contract STARTS from this one.

**The largest divergence is visible before any work begins, and it is a whole page.** There is no
library endpoint of any kind: no listing of the 1 861 owned titles, no categories, no recents, no
incompletes, no season-by-season completeness. The Médiathèque — the second-largest surface in
the application — has no backend counterpart at all. That is a demand on the backend, recorded as
one; it is not a defect and it is not this wave's to build (D7: no backend work).

---

## § 2 — Decisions

Four were arbitrated by the operator on 2026-08-25, before a line was written, as §15 of the
constitution requires (« Les choix fonctionnels ET techniques soumis à l'opérateur »). Six more
are taken here with their reasons, and each says what it would cost to be wrong.

### D-L08-1 — The contract is an OpenAPI 3.1 document of the maquette's own (operator, 2026-08-25)

The artefact is `frontend/maquette/contract/openapi.json`, written by hand and owned by the
maquette. TypeScript types are GENERATED from it by `openapi-typescript`, which this repository
already runs for production (`make openapi`, `frontend/package.json` → `gen-api`).

**Why, and it is the reason the alternative lost.** « Divergences from the existing backend
contract are recorded as demands » is a Done-when clause, and a register written by hand is a
register that rots the first time either contract moves. Two OpenAPI documents can be diffed by a
script: the demands are **computed**, per operation and per schema, and re-computed on every run.
A register nobody recalculates is a register nobody can trust — this repository has watched a
hand-kept figure drift by seven inside the pull request that introduced it as a control.

**What it costs.** The contract must be written in a format that is verbose to author by hand. It
buys the diff, the generated types, and a document whose shape a backend implementer already
knows how to read.

### D-L08-2 — The mock layer intercepts through one in-process seam; there is no service worker (operator, 2026-08-25)

A single module installs a `fetch` implementation over a handler table. No service worker, no
new runtime dependency.

**Three reasons, and the first is the one that decides it.** The oracle measures at first paint,
and a service worker's registration is asynchronous — a page can render once before the worker
controls it, which is a race the oracle cannot be asked to absorb. L01's own entry says the
oracle « then depends on L08 »; handing it a non-deterministic first response would be the
opposite of delivering that dependency. Second, **L11 owns the real service worker**, and two
workers contending for one scope is an arbitration nobody needs to hold for three lots. Third,
the harness reads a MANUAL static copy at `/tmp/tm-refonte/` served by `server.py`, and the
design host is `serve.py` — a worker script would have to be served correctly at the root by both,
which is two more places for a stale copy to hide.

**What it costs, and it is real.** The mocks do not exercise the browser's own network stack, so
what a real `fetch` does with caching, redirects and abort signals is not proved here. That is
recorded as a limit rather than papered over: the seam is one module, and the switchover replaces
its implementation rather than its call sites.

### D-L08-3 — The wave covers every surface, reads and mutations (operator, 2026-08-25)

The contract declares what the whole interface requires — nine pages, five screens, and the
mutations each offers. The mock layer serves every shape the contract declares: seeded where a
fixture exists, and **registered as a gap where none does**.

**Why the shorter version lost.** L09's Done-when includes « every mutation has an optimistic path
and a rollback ». A mock layer that served reads only would leave L09 to invent the mutation
responses itself — which is precisely the hand-built fake this lot exists to prevent, moved one
lot later where it would be harder to see.

### D-L08-4 — No unit-test runner lands here; it stays L09's (operator, 2026-08-25)

The architecture file assigns it explicitly: « **THIS LOT OWES THE UNIT-TEST LAYER** » under L09.
That reading is confirmed rather than reopened, and the ambiguity is settled before the wave
rather than during it.

**And L08's own proof is better without one.** The correspondence this lot must hold is between
`legacy.js` and a committed artefact. A guard that **re-derives the artefact from the source and
compares** is an oracle OUTSIDE the tool. A unit test written beside the projection would import
the projection and assert what it returns, which is the shape B-075 named five times over: an
instrument reading its own output. The guard is Python, needs no browser, and is therefore
collectable in CI without one — the lesson B-077 charged for.

### D-L08-5 — The projection is a rename and a regroup, never a re-derivation

A fixture entry becomes a contract shape by **renaming its keys into full English words and
grouping them into the resource the contract declares**. No value is recomputed, reformatted,
parsed or split.

**Why this is the whole proof, and why the tempting alternative destroys it.** The fixtures carry
presentation as well as fact: `SERVICES` entries hold `ton: "success"` and
`s: "depuis ce matin 09 h 36"`; `DISKS` holds `s: "1,8 To libres · 15 To · rempli à 88 %"`;
`LIBRARY` holds `f: "2026 · Film"`. A contract that decomposed those into facts — free bytes,
total bytes, a timestamp — would be a better contract and would **forfeit the zero-divergence
proof**, because rendering them back would depend on formatters this lot has no business writing
and L09 would have to guess at. A contract that carried them verbatim as facts would be a lie
about what a server sends.

The resolution is the one D7 already prescribes and the operator restated: **carry the value,
record the ugliness as a demand.** The contract declares the field the fixture actually holds; the
divergence register records « the backend must supply the underlying fact and the interface must
format it ». The demand is the future specification. The proof survives intact.

**What it costs.** The maquette's contract will contain fields no sane backend would serve, each
one carrying its demand. That is the visible, dated form of a debt — which is better than a clean
contract that nobody can wire at zero divergence.

### D-L08-6 — Every fixture family is classified, and the classification is TOTAL

The 64 module-level families plus the 2 function-local ones are each classified into exactly one
of four classes, in a committed register:

| Class        | Meaning                                                                                                              |
| ------------ | -------------------------------------------------------------------------------------------------------------------- |
| `served`     | server state — a seed derives from it and a handler serves it                                                        |
| `vocabulary` | interface copy, labels, tones, orderings — it belongs to i18n and to the components, and a server must never send it |
| `asset`      | artwork, poster and trailer maps — served as part of a media payload, never as its own resource                      |
| `unserved`   | not served, with the reason written out                                                                              |

**An unclassified family is a violation.** This is what makes the guard impossible to pre-satisfy:
it holds a NAMED INVENTORY, not a count. A family added to `legacy.js` tomorrow fails the guard
the day it is written, and a family that disappears fails it too. A floor placed at today's
number would be satisfied by construction on the day it is written and could only ever catch a
later decrease — which is the exact shape B-075 found five times.

**The vocabulary class is not a convenience.** `ST_LABEL`, `REASON_LABEL`, `TRIS`, `EP_LABEL`,
`VIA_LABEL`, `MOIS` and the tone maps are French the reader sees. Routing them through a mock
would put interface copy on the network, which the constitution forbids in both directions: the
interface would be asking a server for its own words, and `check-no-french.py` would be reading
a JSON that is not i18n. They stay where they are, classified, and L09 moves them to `i18n/`.

### D-L08-7 — Seeds are committed JSON, re-derivable; the mocks never import `legacy.js`

Each `served` family is extracted once into `design/src/mocks/seeds/<name>.json`, committed, and
served from there. `mocks/` imports nothing from `engine/`.

**Two reasons, and they point the same way.** The engine dies — by subtraction at L09, entirely at
L13 — and a mock layer that imported it would die with it, which is backwards. And an import would
make the correspondence check **vacuous**: comparing a derivation against the thing it was derived
from at run time proves nothing. A committed copy CAN drift from its source, and holding that it
does not is a check with something to do.

**What this obliges, and it is a standing duty rather than a one-off.** `refresh-maquette-fixture.py`
rewrites `FOLLOWS` from the live `acquire.db`. After it runs, the seed must be re-extracted in the
same commit — the guard will say so, and the design records it here so the next reader is not
surprised by a red guard after a data refresh.

### D-L08-8 — Failure and latency are a declared scenario, driven in the page

The seam carries a scenario: which operations fail, with what status, and what latency each
response is held for. It is set synchronously, in-page, through a published seam — the same way
the harness already drives `phase: "loading" | "error"` and `scen: "real" | "loaded"` through
`applyState`.

**Why in-page and synchronous.** The engine's existing surfaces already have their loading and
error states, driven by the store: 6 named states set `phase: "loading"`, 5 set `phase: "error"`
(`grep -n 'phase:' frontend/maquette/design/src/engine/states.js`). When L09 wires a surface, the
same named state must produce the same surface — which it can only do if the mock's failure is
decided before the request is made, not negotiated across a thread boundary.

### D-L08-9 — The layer publishes a quiet signal, and the oracle consumes it while it is still a no-op

The seam publishes a fact — no request is in flight — and `oracle.py`'s settle signal reads it.

**Why now rather than at L09.** L01's entry says it in as many words: « When real data replaces
the fixtures (L09), determinism moves to the mock layer — **the oracle then depends on L08**, so
plan the two together rather than against each other. » Today nothing fetches, so the signal
resolves immediately and no measurement can move. Adding it at L09, in the wave that also wires
surfaces, would mean a change to the instrument inside the wave the instrument is measuring.

**Its risk is named and its gate is explicit**: the oracle must report zero divergence before AND
after the change. If it does not, the change is reverted and the seam is left published for L09
to consume — reported, not smoothed over.

### D-L08-10 — `mocks/` is imported by `app/` alone, and imports no feature

A new arm of `scripts/check-frontend-boundaries.py`. `mocks/` may read `lib/` and its own seeds;
nothing in `features/`, `ui/`, `lib/` or `routes/` may import it.

**Why it needs an arm at all.** L04 already declared `mocks/` a legitimate root — the bucket table
carries « handlers and fixture seeds (L08) » — but no arm says what may cross its boundary. A
feature importing a mock seed directly is how a fixture survives its own removal, and it would
render identically while making L09's proof meaningless. Invariant 11: every change lands with a
rule that bites.

---

## § 3 — What the instruments do NOT read

**This section is written before the guard, not after it.** L07 found the shape six times in its
own instruments; L07-bis found it five more (B-075), two of them inside the reader of the rule the
wave was writing at that moment. A guard is green for two reasons and only one of them is good.

The correspondence guard is `scripts/check-mock-seeds.py`. Asked « what does it not read? », six
answers, each with the arm that covers it or the limit that is accepted:

| It does not, by itself, see…                                                              | Answered by                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| whether a handler actually serves the seed it names — a handler could return a literal    | **arm `handlers`**: no data literal in a handler module; every payload traces to a seed import                                                                                                                                 |
| a fixture family that no seed claims — the coverage hole                                  | **arm `classification`**: the inventory is named and total, unclassified is a violation                                                                                                                                        |
| a seed file with no source family — an invented seed                                      | **arm `provenance`**: every seed names its family, and the family must exist                                                                                                                                                   |
| a projection that silently drops a key                                                    | **arm `lossless`**: every fixture key is either in the declared mapping or in the declared `dropped` list with its reason                                                                                                      |
| a fixture the extractor cannot see — a literal inside a function, like `steps` and `TONS` | **not covered by extraction, and named**: both are listed in the register by hand, as `unserved` with their reason, and the arm refuses the register naming a family the extractor does not know unless it is one of those two |
| values the fixture computes at run time — the `derived*()` arrows, the getters, `TODAY`   | **accepted limit**, written down: they are not literals, so they are not seeded. They become scenario responses, declared in the handler and covered by the harness rule, never by the seed guard                              |

**And the guard's own floor is a named set, never a number.** `--list` prints the inventory it
holds; the register is that list. Both directions are checked: a name in the tree and not in the
register fails, and a name in the register and not in the tree fails.

**The harness rule R85 has the same question asked of it.** It drives the seam directly, because
L08 wires no surface — so it does not read whether any surface displays anything, and it must not
pretend to. What it reads is: the same request twice returns byte-identical bodies; a declared
failure scenario produces the declared status; a declared latency is observed; the quiet signal
goes false while a request is in flight and true after; and no handler reaches the real network.

---

## § 4 — What the oracle will say

**Zero divergence, at every phase, and that is the lot's own proof.** L08 wires no surface and
displays nothing. Every rectangle and every one of the 19 computed properties is untouched by
construction.

There is exactly one way this lot could move a measurement, and it is D-L08-9: the settle signal.
It is gated on the oracle reading `0 divergence` before and after. **If a measurement moves, the
wave stops and reports** — it does not re-record. And it cannot re-record anyway from anywhere but
the operator's machine: `oracle-reference.json` carries `"platform": "Darwin/arm64"` and `--check`
refuses to compare across a mismatch.

---

## § 5 — Phases

The plan owns the detail (`plan/INDEX.md`). The shape is: the contract before the seeds, the seeds
before the handlers, the guards with what they guard, and the register last because it is computed
from the two contracts once both are final.

| #   | Phase                                                    |
| --- | -------------------------------------------------------- |
| 1   | The extractor, and the classification of all 66          |
| 2   | The contract — the artefact and its generated types      |
| 3   | The seeds, extracted and committed                       |
| 4   | The seam — one `fetch`, no service worker                |
| 5   | The handlers, reads                                      |
| 6   | The handlers, mutations                                  |
| 7   | Failure, latency, and the quiet signal                   |
| 8   | The guards: `check-mock-seeds.py`, the boundary arm, R85 |
| 9   | The divergence register, computed                        |
| 10  | The wave's closing: documentation, state row, gates      |

---

## § 6 — Out of scope, named

Named so that each absence is a decision and not an omission.

- **No backend work.** Nothing under `personalscraper/` is touched. D7 is explicit and the
  operator restated it: divergences are recorded, never coded.
- **No surface is wired.** That is L09. This lot delivers the contract and the layer; the
  connection is the next lot's, and merging the two would destroy both proofs (§ 5 of the
  architecture file, « what is refused »).
- **`frontend/src` is not harvested.** Its 11 API modules are a reference for what the replacement
  must be able to DO, never a model to copy (D7). It is archived at switchover.
- **No unit-test runner** (D-L08-4).
- **The oracle is not widened.** B-061 stays `open` by the operator's arbitration of 2026-08-25;
  nothing here reopens it.
- **B-068** (the prose inventory) and **B-071** (the design-notes toggle, which lives in the dying
  engine and belongs to L13) stay `open` on purpose. They are not this wave's.
- **The `/control` and `/pipeline` pages** are surfaces still to be drawn, outside this file's
  scope by § 1 of the architecture document. The contract does not invent operations for pages
  that have not been drawn.
