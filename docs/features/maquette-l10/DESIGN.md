# L10 — The live relay

**Lot** `L10` of `docs/reference/frontend-architecture.md` § 4, Phase 3.
**Depends on** L09 — landed (`IMPLEMENTATION.md` § « Where the frontend work stands », row
« Landed, in order »).
**Branch** `feat/maquette-l10`. **Codename** `maquette-l10`. **Version** 0.98.47.

**The constitution's §§ this wave serves.** **§8 (« Rien en silence ») is the § of this lot** —
« Un "rien ne se passe" sans raison visible est un mensonge par omission ». A stream is the best
and the worst thing that can happen to that rule: done right it finally shows what arrives; done
wrong it puts a fresh-looking skin on a dead screen. §13 (the interface has no state of its own;
what it shows is derived from the data) — an event is the moment that derivation is renewed. §2
and §8's parent clause (a wait, a skip, a deferral is displayed with its reason). §15 (the
maquette is the product). NE-DOIT-PAS-1 and NE-DOIT-PAS-5: never lie, never fail silently.

---

## § 1 — What this lot is, measured on the day it opened

Every figure below carries the command that produces it. None is copied from a brief, and the one
figure a previous brief asserted in bold — that the oracle would move — is measured in § 7 rather
than predicted.

### The maquette has no stream at all, and no clock either

| | Maquette | Production |
| --- | ---: | ---: |
| Files naming `WebSocket` | **0** | 24 |
| Polling sites (`refetchInterval:` / `setInterval`) | **0** | **21**, over 17 files |
| Event → cache invalidation rule sites | **0** | 4 |
| `useQuery` / `useInfiniteQuery` call sites | **19** | — |
| `invalidateQueries` call sites (all mutation-driven) | **5** | — |

<sub>`grep -rln "WebSocket" frontend/maquette/design/src -g '*.ts' -g '*.tsx' -g '*.js' | wc -l` → 0 ·
`grep -rn "refetchInterval\|setInterval" frontend/maquette/design/src -g '*.ts' -g '*.tsx' -g '*.js' | wc -l` → 0 ·
`grep -rn "refetchInterval:" frontend/src -g '*.ts' -g '*.tsx' | grep -v "\.test\." | wc -l` → 21 ·
`grep -rn "useWsInvalidation(\[" frontend/src -g '*.tsx' -g '*.ts' | grep -v "\.test\." | wc -l` → 4</sub>

**« No polling remains where an event exists » is nearly free here and that is a trap, not a
gift.** The maquette polls nowhere because no surface has ever had a reason to — its data came
from a synchronous fixture until L09, and L09 set `staleTime: Infinity` with `refetchOnMount`
never overridden. A clause satisfied by absence is exactly B-085's shape: a green gate over
something nobody read. **So this lot does not report zero and move on. It arms the zero** — a
guard that refuses the first `refetchInterval` and prints the corpus it read, on the model of
`check-state-ownership.py`'s `effect-fetch` arm, which was written at zero for the same reason and
says so in its own docstring.

### The cache cannot heal itself, and that decides the relay's shape

`lib/query-client.ts` sets `staleTime: Infinity`, `refetchOnWindowFocus: false`,
`refetchOnReconnect: false`, `retry: false`. Each is argued in the file and each is right. Their
sum is a property this lot must design around: **a query that misses its invalidation is stale
until the process ends.** There is no clock, no focus event and no reconnect refetch behind it.

Two consequences, and both are structural rather than stylistic:

1. **A subscription mounted with a surface is a wrong subscription.** An event arriving while
   Médiathèque is unmounted would refresh nothing, and coming back to it would refetch nothing
   either — `staleTime: Infinity` makes the mount a no-op. Production's `useWsInvalidation` is a
   hook precisely because production polls underneath it: a missed event costs 60 seconds there
   and costs forever here. **The relay subscribes once, at boot, for the document's lifetime.**
2. **`refetchOnReconnect: false` is now a decision this lot owns.** It was written when nothing
   could tell the application it had been disconnected. Something can now — and the answer is
   still no, for a sharper reason: § 3.3 replays the gap instead, which is exact where a blanket
   refetch is a reload.

### The contract has no vocabulary for a stream

The maquette's own contract declares **50 paths and not one of them is the relay**; the backend's
generated contract declares 61 and has none either, because OpenAPI does not describe a
WebSocket.

<sub>`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(len(d['paths']),[k for k in d['paths'] if 'ws' in k or 'event' in k])"` → `50 []`</sub>

So `scripts/compare-contracts.py`, which COMPUTES the demand register by diffing paths and
operations, is structurally blind to everything this lot touches. That is a finding, not a
blocker: it means the stream's contract has to be its own declared artefact and its demands have
to be filed by hand into `docs/reference/frontend-backend-demands.md` — and it means a demand
about the stream cannot be trusted to the computed register, which will keep saying nothing.

### What the backend already emits, and it is the reason the map is written and not guessed

**40 event classes** reach the bus and therefore the Redis stream.

<sub>`grep -rh "^class [A-Z]" personalscraper/{pipeline_events.py,verify/events.py,dispatch/events.py,trailers/events.py,acquire/events.py,indexer/events.py} | wc -l` → 40</sub>

Production maps **9 of the 40** to invalidations, in two named sets
(`PIPELINE_LIFECYCLE_EVENT_TYPES`, `SHELL_BADGE_EVENT_TYPES`). The other 31 reach the browser and
change nothing. **That inventory is this lot's reference for what the replacement must be able to
do — never a model to copy (D7)**: production's map is shaped by production's pages, and this
interface has different ones.

### B-140 sits on this lot's path

`app/scroll-restoration.ts:41` — `activePort()` is
`document.querySelector(".screen.open .port")`. Five React screens draw a `.port` through
`scrollport()`; the main pages scroll inside `#port`, declared at `index.html:224`, which is never
inside a `.screen.open`. So on a main page the save stores nothing, or stores the just-opened
screen's offset under the departing page's key.

<sub>`grep -rln 'scrollport()' frontend/maquette/design/src/features -g '*.tsx' | wc -l` → 5 ·
both anchors carry `data-part="viewport"`: `grep -rn 'data-part="viewport"' frontend/maquette/design/{index.html,src} | wc -l`</sub>

**A stream is what makes it hurt.** Content arriving under a reader who then opens an item and
comes back lands them at the top of a list that has also changed length. It is repaired here, in
its own phase, with its own rule — and it pays off B-104's first clause too (« programmatic
scrolling must have one path »), which `frontend-architecture.md` § 1 names as one of the three
things that keep the semantic scroll index's door open.

---

## § 2 — Decisions

Numbered `D-L10-n`, and each says what it refuses as well as what it chooses.

### D-L10-1 — The relay is transport in `lib/`, the map is domain in the features, and `app/` composes the two

**Decision.** Three layers, and the seam between them is invariant 10 read literally.

- **`lib/relay.ts`** — the transport and nothing else: connect, the handshake, the ping reply,
  the close codes, the backoff, the replay cursor, the connection state and its subscribers. It
  names no domain word. It does not know what a query key is.
- **`features/<domain>/live.ts`** — one small table per feature: which event types refresh which
  of that feature's query keys. This is domain knowledge and it lives with the domain.
- **`app/live-updates.ts`** — the composition table. One import per feature, handed to the relay
  at boot.

**What it refuses.** A single central map naming every domain, which is what production has and
what would put 40 event names and 20 query keys into `app/`. And a per-surface subscription hook,
refused on the evidence of § 1: with `staleTime: Infinity` a missed invalidation never heals.

**Why `app/` composing is not a violation.** Invariant 10 blesses « whatever table the shell reads
to compose navigation », and `router-tree.tsx` is already one import per page. `live-updates.ts`
is the same species and the same shape: it names the features, never their events or their keys.
**The measurement is the proof and it is taken, not asserted** — the wave re-measures `app/`'s
domain-word count at its close (§ 7.1's duty) and states the delta.

**The precedent for registration already exists in this codebase**: `panel-seasons` and
`panel-field` are imported at boot for their side effect, each registering what draws it. Same
mechanism, same reason, same file.

### D-L10-2 — An invalidation names its keys, and the fan-out is measured rather than trusted

**Decision.** A rule is `{types, keys}`. A key is a PREFIX into the query cache. `invalidateQueries()`
with no `queryKey` is forbidden outright.

**« Exactly what it should and nothing else » is a measurable sentence and it is measured as
one.** The rule that holds it does not read the source: it drives a named state in a browser,
snapshots every entry in the query cache with its `dataUpdatedAt` and its invalidation state,
emits ONE event, and asserts the set of entries that changed is exactly the declared set. A
too-wide invalidation and a missing one both fall out of the same comparison.

**Why the source is not enough.** A map that reads correctly can still fan out wider than it says
— a prefix key one element too short covers siblings nobody listed, and it compiles, and its types
agree. That is the exact shape L09 paid for three times (B-124, B-125, B-136: a name that
compiles and reads the wrong thing).

### D-L10-3 — The stream is simulated at the TRANSPORT, not above it

**Decision.** The mock layer installs a **fake `WebSocket` class**, not a bypass. Driving happens
through `window.__mocks.stream` — open, emit, drop with a close code, hold — and the application's
own client connects to it exactly as it will connect to `/ws/events`.

**What it refuses.** A `window.__mocks.emit()` that hands an event straight to the relay's
dispatcher. It is half the work and it leaves the whole subject of the lot unexercised: the
handshake, the `4401` close, the backoff, the `?last_id=` cursor and the ping reply would all be
code no proof ever walks.

**And it is the declared cost of D-L08-2 refused twice.** L08 wrote down that its seam replaces
the network call in process, so caching, redirects and abort signals are not exercised. That was
the right trade for a mock of a REST call. Repeating it on the one lot whose SUBJECT is the
transport would leave this lot with no proof at all.

**The protocol is `docs/reference/web-ui.md` § WebSocket Protocol and the fake obeys it to the
letter**, including the two details that carry weight:

- **accept-then-close with code `4401`** on an auth failure. Closing before accept yields an
  opaque `1006` in a real browser, and the client's terminal-close branch would be dead code in
  production while passing every test. The fake reproduces accept-then-close, so that branch is
  walked.
- **`?last_id=` replay**, exclusive lower bound, in order, before live fan-out.

Anything the maquette needs and the protocol does not offer is a **demand** (D7), filed in
`docs/reference/frontend-backend-demands.md`. No backend file is edited by this wave.

### D-L10-4 — `quiet()` learns about the stream, and the stream stays silent unless driven

**Decision.** Two halves, and neither is sufficient alone.

- **The mock stream emits nothing on its own.** No timer, no seeded traffic. A named state is a
  world where nothing arrives unless the driver makes it arrive. This is what keeps 84 recorded
  states measurable at all.
- **`window.__mocks.quiet()` accounts for a delivery in flight.** Today it counts `fetch` calls
  (`mocks/index.ts`, `inFlight`), and a WebSocket delivery goes nowhere near `fetch`. An emit
  triggers an invalidation which triggers a refetch — and there is a window between the delivery
  and that refetch being issued in which `inFlight` is 0 and `quiet()` resolves over a world that
  is about to change. `releaseWaiters()` already defends the same gap for a read-render-read
  waterfall, with a macrotask, and its comment says exactly why. The stream gets the same
  treatment: a delivery is counted from the moment it is dispatched until the fan-out it caused
  has been issued.

**R89 (`harness/settle.py`) gets a new hold for it**, and R89 is on the `--contracts` tier
precisely because it is « the instrument every later phase's proof rests on ». **This is the first
lot where `quiet()` has to mean something**, and an instrument that starts meaning something is an
instrument that can start being wrong.

### D-L10-5 — Connection loss is a DRAWN state, and health is drawn as nothing

**Decision.** The shell carries one connection indicator. It renders **nothing at all while the
relay is connected and current**, and appears with its reason when it is not.

**The four states, named and drawn** (named states in `states.js`, measured by the oracle,
asserted by their own rule):

| State | What the operator sees | Why |
| --- | --- | --- |
| connected | nothing | § 3 below |
| `relay-reconnecting` | « la connexion a été perdue, reconnexion… » with the attempt | §8: a wait is displayed with its reason |
| `relay-lost` | the same, plus « les informations affichées datent de <heure> » and a manual retry | §8: the screen says it is not updating |
| `relay-refused` | the `4401` case: the session is no longer valid, with the way back to the sign-in | §8 + NE-DOIT-PAS-5: a real reason, never a code |

**Why healthy renders nothing, and it is a design argument before it is a measurement one.** §8
asks that what is WRONG be said, not that what is right be announced; a permanent green dot is
chrome that teaches the reader to stop looking at it, which is the precise mechanism by which a
dead screen looks fresh. That it also leaves the 84 recorded states untouched is a consequence and
is stated as one — **it is not the reason, and the § 7 measurement is what establishes it either
way.**

**Reduced motion is drawn, not degraded** (invariant 14): the reconnecting state's activity is a
declared transition with a defined still appearance under `prefers-reduced-motion`, and the rule
reads both.

### D-L10-6 — B-140 is repaired here, on the anchor both viewports share

**Decision.** `activePort()` resolves the OPEN SCREEN's viewport when a screen is open and `#port`
otherwise, anchored on `[data-part="viewport"]` — the attribute both already carry — rather than
on `.port`, which is a style class Tailwind variants own (D4, and invariant 2 read from the code's
side).

**Its own phase, its own rule, its own oracle line.** It is a behaviour change in a behaviour
wave, which is allowed; folding it into a relay phase would be an edit hidden inside a move.

---

## § 3 — How it behaves

### 3.1 — The connection

Installed at boot, after the query client exists and before the engine starts. It connects to
`/ws/events`, waits for the single `ws.hello`, and records `build_commit` — the value B-079 and
B-080 both want and neither has (they are not this lot's to close, and the relay is what will make
closing them possible).

**A close is not a failure.** Code `1000` on a deliberate teardown is silence. `4401` is
`relay-refused` and does **not** retry: retrying an expired session is a loop that produces
nothing and says nothing. Everything else is `relay-reconnecting`, with capped exponential
backoff, and it becomes `relay-lost` once the attempts have gone past the point where a reader
should be told the screen is cold.

**The ping is answered, and answering is the whole of it.** The server pings after 30 s of client
silence; the client replies with any text frame. A missed ping is the server's business, not the
client's — the client learns about it as a close.

### 3.2 — What an event refreshes

The map is built during the wave, feature by feature, from the surfaces that exist. Its shape:

```
features/arrivals/live.ts   PipelineStarted PipelineEnded PipelinePaused PipelineResumed
                            StepStarted StepCompleted StepErrored   → ["/api/pipeline/status"]
                            ItemProgressed                          → ["/api/staging/media"], ["/api/decisions/"]
features/library/live.ts    ItemDispatched LibraryScanCompleted     → ["/api/library/items"], …
features/acquisition/live.ts GrabSucceeded GrabFailed WantedEnqueued … → ["/api/acquisition/…"]
```

**The table above is the SHAPE, not the answer.** Each line is decided in its feature's phase
against that feature's own keys and written with the reason it refreshes what it refreshes — and
an event that refreshes nothing is written down as refreshing nothing, which is a decision rather
than an omission.

**Every event that reaches the browser and matches no rule is counted**, and the count is
surfaced. An event nobody handles is not an error; an event nobody handles that nobody can COUNT
is how a map silently stops covering its subject.

### 3.3 — Reconnection, and why it is a replay rather than a reload

On reconnect the client passes `?last_id=<the last id it saw>`. The server replays the gap in
order, exclusive of that id, then goes live. The relay applies replayed events through the same
map — so the gap heals precisely, and only the keys the gap touched are invalidated.

**The alternative is what this refuses**: invalidating everything on reconnect. It is one line, it
is always correct, and it is indistinguishable from a reload — it would throw away exactly what
L09 built, and it would do it at the moment the network is least able to pay for it. That is the
« rien d'autre » clause of the contract, met at the hardest point rather than the easiest.

**A replay burst is one render, and every event in it counts.** Production learned this
(FRONTEND-DATA-03: three hooks inspected only the newest event and dropped relevant ones buried in
a batch). Here the relay dispatches per event as it arrives, so the shape cannot occur — and a
rule emits a burst and asserts every key in it was invalidated, because « cannot occur » is a
claim and a rule is a proof.

### 3.4 — What it does NOT do

- **No optimistic anything.** That was L09's and it landed.
- **No offline queue, no service worker, no offline shell.** L11's, and invariant 10 already says
  where they live. A mutation issued while the relay is down behaves exactly as it does today.
- **No new surface.** The connection indicator is drawn in the shell; no page is added.
- **No backend edit.** The channel exists.

---

## § 4 — The rules this lot lands

Each is mutation-tested: break the behaviour on purpose, watch the rule fall AND name the right
defect, restore. **The mutation is committed against, never against an untracked file** (B-107:
`git checkout --` on an untracked file is a no-op and a mutation stayed in the tree).

| # | Reads | Falls when |
| --- | --- | --- |
| **R91** | the fan-out: cache snapshot, one event, exactly the declared keys changed | an invalidation is too wide or missing |
| **R92** | the connection states: the four named states, their text, their control, reduced motion | the indicator stops appearing, or appears connected |
| **R93** | replay: a drop, a reconnect carrying `last_id`, a burst, every key in it invalidated | a reconnect reloads, or loses the gap |
| **R89** (extended) | `quiet()` does not resolve while a delivery and its fan-out are in flight | the settle signal goes blind to the stream |
| **R94** | scroll restoration on a MAIN page, not only an overlay screen (B-140) | `activePort()` reads one viewport out of two |

**Guards.** `scripts/check-live-relay.py`, arms that each say what they do NOT read before what
they do:

- `no-polling` — refuses `refetchInterval` / `setInterval` under `design/src` outside the dying
  engine, **and prints the corpus it read with a floor beneath it**, because an arm written at
  zero that reads nothing reports the same word as an arm that read everything.
- `named-invalidation` — refuses `invalidateQueries()` with no `queryKey`.
- `map-completeness` — every event type the mock stream can emit is either mapped or explicitly
  listed as refreshing nothing. A map is only as honest as its unhandled list.

**Which tier.** R92 and R94 are name contracts (a state id, a `data-part` anchor) and join
`--contracts`. R91 and R93 drive a stream through a browser and belong to the full suite. R89 is
already on `--contracts` and stays.

---

## § 5 — Where this lot can break the instrument

**It can move the oracle, and the honest position is that nobody knows yet.** Two mechanisms
could: a connection indicator that renders in a healthy state (D-L10-5 says it renders nothing —
that is a design decision that must be VERIFIED, not assumed), and any content a wired surface
draws differently once the relay exists. **Neither is predicted here.** § 7 records what the
measurement said, with the command. A previous hand-over asserted in bold that the oracle would
move and it could not; a figure in a design carries the same duty as a figure in the plan.

**New named states GROW the reference, they do not diverge from it.** Four states added is
`84 → 88`, which `--record` writes and `--check` compares from then on. Growth is stated in the
close as growth.

**The re-record can only happen here.** `oracle-reference.json` carries
`"platform": "Darwin/arm64"` and `--check` refuses a cross-platform comparison. This wave runs on
that machine (`uname -sm` → `Darwin arm64`), so the gesture is this wave's to perform. Were it
not, the gesture would be handed back to the operator and said so in the pull request.

**And the instrument that this lot makes fallible is `quiet()`.** It has resolved immediately for
its whole life because nothing fetched, then counted `fetch` since L08. From this wave it also
answers for a transport it cannot see through the same counter. R89 is where that is held, and
R89 is on the per-pull-request tier for exactly this reason.

---

## § 6 — The register

**Written during the wave, not after it.** L08 merged with twenty findings living only in a commit
message and it took another wave to recover them (B-084). Every finding lands in `BUGS.md` in the
phase that finds it.

**B-085 is recounted at the close** — « guards green over what they do not read », total 40, of
which L09 contributed 14. This wave adds its own figure with the entry that establishes it, and
**zero is a real answer written with the same authority as six**.

**The forms already paid for, checked against every hold this lot writes**: a floor posted at the
current value (pre-satisfied); an empty read passing in silence; a corpus enumerated by hand; a
hold armed on one of two entry points; a grep that reads the markup without opening the stylesheet;
and a guard that answers differently depending on the machine — which measures the machine.

---

## § 7 — Done when

The lot's contract, from `frontend-architecture.md`, with what makes each line checkable:

1. **A server event refreshes exactly what it should and nothing else** — R91, over every rule in
   the map, comparing the cache before and after a single event.
2. **Reconnection and loss are handled visibly** — R92 (the four states, their text, their
   control, reduced motion) and R93 (the gap is replayed, not reloaded).
3. **No polling remains where an event exists** — `check-live-relay.py --arm no-polling`, printing
   its corpus above a floor.

And the wave's own duties: the design and plan archived, the « In flight » row moved, both
references re-recorded, B-085 recounted, invariant 10's `app/` measurement refreshed (§ 7.1),
`make check` at zero, the full rule suite green with unchanged per-rule hold counts.
