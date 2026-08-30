# L11 — Offline and PWA

**The lot** is `docs/reference/frontend-architecture.md` § 4, *L11 — Offline and PWA · depends on
L09, L15*. Both dependencies landed: L09 as PR #509, L15 as PR #528. Its design is
`docs/features/maquette-l10-ter/MODEL.md` § 2 Part 13, its properties are P7, P8, P9, P27 and P30
of that file's § 3, and its entry points are the operator's Q4.

**One sentence.** The prototype keeps working when the network stops: the shell comes from a cache
whose freshness the design host can actually see, a mutation issued offline waits in a queue that
survives a restart and departs exactly once, and every entry point the platform offers an
installed application is declared or refused in writing.

---

## 1. What was measured before this design was written

Every figure below carries the command that produces it. Run from the repository root unless the
prompt says otherwise; all of them were read on 2026-08-30 at `bcd4ef9a`.

| Fact | Figure | Command |
| --- | --- | --- |
| The design host's worker caches exactly one page, `/offline.html`, and never the prototype | 1 | `sed -n '78,96p' frontend/maquette/installable.py` |
| The mock layer REPLACES `globalThis.fetch` — nothing under `/api/` reaches the network | 1 site | `grep -n "globalThis.f""etch" frontend/maquette/design/src/mocks/index.ts` |
| `send()` is the single mutation seam, and every mutation in the tree goes through it | 6 call sites, 3 files | `grep -n "send(" frontend/maquette/design/src/features/*/queries.ts frontend/maquette/design/src/lib/queue.ts` |
| The add screen already reads `?q=` from the address | 1 | `grep -n "get(\"q\")" frontend/maquette/design/src/features/acquisition/search-queries.ts` |
| `display-mode: standalone` is already read, by the install offer | 1 | `grep -n "display-mode" frontend/maquette/design/src/app/entry.ts` |
| **Nothing in the tree registers `beforeunload` or `unload`** — the two handlers that evict the back-forward cache | 0 | `grep -rn "beforeunload\|'unload'" frontend/maquette/design/src` |
| `served_identity()` computes branch, commit and dirt — and publishes them on the DOCUMENT, at no endpoint | 0 endpoints | `grep -n "def served_identity\|def with_served_identity" frontend/maquette/host_identity.py` |
| Rules in the harness | 75 | `ls frontend/maquette/harness/*.py \| grep -v common.py \| wc -l` |
| …of which end through `common.Journal` | 53 | `grep -l "Journal(" frontend/maquette/harness/*.py \| wc -l` |
| …of which start through `common.open_page` | 45 | `grep -l "open_page" frontend/maquette/harness/*.py \| wc -l` |
| `100dvh` anywhere in the tree | 0 | `grep -rn "dvh" frontend/maquette/design/src \| wc -l` |

**Two of those readings decide a design question each, and they are the reason this section is
first.** The mock layer replacing `fetch` means a freshness poll under `/api/` would be answered by
a fixture and could never fail — a green instrument reading nothing, which is B-085's species and
is avoided here by construction rather than caught later. And `lib/queue.ts` is **already taken**:
it is the *staging* queue, a domain module two pages read. L11's mutation queue cannot have that
name.

**One stale figure was found while measuring, and it is repaired in this wave.** `Makefile:200`
announces the contract tier as « 9 rules » where `CONTRACTS` in `run.sh` holds 12. It is B-254's
species — a hand-written figure — in a line B-254's own repair did not reach.
<sub>`grep -n "9 rules" Makefile` · `grep -o "[a-z_0-9]*\.py" <<<"$(grep '^CONTRACTS=' frontend/maquette/harness/run.sh)" | wc -l`</sub>

---

## 2. Where offline and the worker land — the tree this lot leaves behind

Invariant 10, and MODEL Part 13's own placement: *`app/` for registration, update discipline and
the queue; the worker source beside `index.html`; the manifest and the worker route in `serve.py`
until switchover.*

| File | What it owns |
| --- | --- |
| `design/src/app/worker-registration.ts` | Registering the worker, and the update discipline: a check on load, on `visibilitychange` and every 15 minutes; one reload |
| `design/src/app/build-stamp.ts` | The stamp this build was made with, baked at build time, and the poll that compares it to what the host serves |
| `design/src/app/outbox.ts` | The queue of mutations issued offline: opaque `{ key, request }` envelopes, its persistence, its replay, and the count it publishes |
| `design/src/app/outbox-store.ts` | The IndexedDB store alone — open, put, list, delete. It knows nothing about mutations |
| `design/sw.js` | The worker source, beside `index.html` as Part 13 places it |
| `frontend/maquette/installable.py` | The manifest gains the three entry points; `WORKER` stops being a literal and becomes the built worker |
| `frontend/maquette/serve.py` | `/build.json`, served without a session like the manifest |

**Nothing lands under `features/`.** MODEL Part 13 names this the most likely misplacement of the
whole plan, and the reason is that the page one happens to be testing is not the thing being built.
The outbox is read by every mutation and belongs to none of them.

---

## 3. Decisions taken in this design

**D-1 — The worker precaches the shell, and the README's « the worker caches nothing » is amended
in the same commit.** That sentence is a real decision with a real reason — *a caching worker would
serve yesterday's prototype to someone judging today's design* — and P7 cannot hold while it
stands. It is not overturned by ignoring it: it is overturned by removing the failure it names,
which is what the update discipline is for. **Arbitrated by the operator on 2026-08-30.** CLAUDE.md's
expensive lesson applies literally — the directive changes in the same move as the decision, never
in a later tidy-up.

**D-2 — The freshness signal is the SOURCE STAMP, not the commit.** Production compares
`/api/version`'s `build_commit` to a baked `__BUILD_COMMIT__`, and that is right for production,
where every deploy is a commit. The design host is the machine the operator is *editing on*: a
dirty tree keeps the same commit across every edit of a session, so a commit-based check would go
blind exactly while the prototype is changing. `serve.py` already computes `mtime_sources()` and
already keys its document cache on it — the signal exists and is the honest one here. **Arbitrated
by the operator on 2026-08-30.** The commit and the dirt travel beside it, because they are what a
human reads.

**D-3 — The freshness endpoint is `/build.json`, and it is deliberately outside `/api/`.** See § 1:
the mock layer replaces `globalThis.fetch`, so `/api/version` would be answered by a fixture and
the poll could never fail. It is served without a session, for the same reason the manifest is.

**D-4 — The queue is `app/outbox.ts`.** `lib/queue.ts` is the staging queue and the name is taken;
`app/` is where Part 13 puts it. It holds `{ key, request }` and knows no domain word — the
`check-frame-domain.py` ratchet is the instrument that says so.

**D-5 — `send()` enqueues, and an enqueued mutation RESOLVES rather than rejects.** Rejecting is
what triggers L09's rollback, and rolling back a mutation that has not failed is precisely the
defect P8 exists to prevent. So on a network refusal `send()` writes the envelope and resolves —
**and the interface says so**, because a resolved mutation the operator can see and a departed
mutation are not the same thing and §8 forbids an interface that has stopped saying which it is.
The outbox publishes a pending count; the connection mark L10 already draws is where it is read.
Silence here would be NE-DOIT-PAS-1 with extra steps.

**D-6 — Exactly-once is made measurable, not asserted.** An envelope is deleted from the store only
after its request resolves, so a replay interrupted mid-flight is replayed again at the next boot —
*at least* once at the storage layer. The envelope carries an idempotency key; the mock layer
records the keys it has applied and answers a second arrival with the first answer. « Exactly once »
is then a property a rule can read on the mock's side, rather than a sentence in this file.

**D-7 — All three entry points, and what a rule can honestly prove of each.** Q4, answered
2026-08-30: `share_target` (GET, `action: "/add"`, `title`/`text`/`url` all mapped to `q`),
`launch_handler` (`navigate-existing`), `handle_links` (`preferred`). No rule can make an operating
system share into the application, and this design does not pretend otherwise. What is proved is
the pair: **the manifest declares it**, and **the address it names behaves** — `/add?q=Silo` opens
the add screen pre-filled, which `search-queries.ts:48` already implements and no rule reads today.
The half that needs a device is exercised on a device and written down with its date, like the
oracle's certification and L12's interaction budget.

**D-8 — Push notifications are declared NOWHERE, and this is the written reason the principle
demands.** The operator's principle is *every entry point the platform offers an installed
application is declared, unless a written reason says why not*, and a future ratio alert arriving
by FCM was named on 2026-08-30 as a real consumer. The reason not to declare it here: a permission
prompt with nothing to send trains the operator to refuse it, and the refusal is remembered by the
browser far longer than this wave. The consumer is §18's alert, which is **L16**. Recorded as a
register entry naming L16 so that it is declined in writing rather than forgotten.

**D-9 — P27 is drawn from what actually exists.** « Standalone hides browser-only chrome » has
exactly one subject in this tree: the install proposal, which exists only because a browser is
around it. Under an emulated `display-mode: standalone` it must be absent. Inventing further
subjects for the rule would be writing a rule against nothing.

**D-10 — P30 is measured before it is repaired, and it is expected to pass.** Nothing in the tree
registers `beforeunload` or `unload` (§ 1). The rule is therefore a RATCHET: it records that the
back-forward cache survives a walk out and back, and it falls the day someone adds the handler that
evicts it. A rule that only ever confirms good news is still the rule that catches the regression.

---

## 4. B-256 — the served copy's lock and its stamp

Placed on this wave by the operator on 2026-08-30. It is not a surface change and it is not this
lot's subject; it is the instrument every measurement in this wave rests on, which is exactly the
argument that put `settle` in the contracts tier.

The defect: `run.sh` rebuilds and re-copies `/tmp/tm-refonte/wrapped.html` unconditionally at every
invocation, with no lock and no stamp. A second session's `make maquette-oracle` mid-run made two
rules fall over a build they were not started against. **The dangerous direction is the other one** —
a rule can PASS over the wrong prototype just as silently.

**A lock prevents; a stamp detects. Both, because neither is enough alone.**

- **The lock.** `run.sh`, `oracle.py` and `a11y.py` take an exclusive lock on the served copy
  before building. `mkdir` is atomic on macOS and needs no `flock`; a lock whose holder is gone is
  broken with a message that names the stale holder rather than hanging forever.
- **The stamp.** `run.sh` writes `/tmp/tm-refonte/build-stamp.json` immediately after the copy: the
  built commit, the dirty flag, the source stamp, and a token unique to this run.
- **Read at three places, and the coverage of each is stated rather than implied.** The per-rule
  wrapper in `run.sh` reads the stamp before and after every rule and turns a change into a named
  failure — that is **75 of 75**, and it is the only reading that covers `audit2.py`, which uses no
  `common.Journal`. `common.open_page` asserts at the start and `Journal.summary` at the end — that
  is **45** and **53** respectively, and it is what protects a rule run BY HAND while debugging,
  which the wrapper cannot see.

A stamp that only the wrapper read would leave every hand-run rule unprotected; a stamp that only
`common.py` read would leave 22 rules unprotected and would have missed the very rule that started
the incident. The two figures are in § 1 for that reason.

---

## 5. The behaviour changes, and why each is its own commit

« One kind of change per wave » is not available to this lot: the whole lot is behaviour. The rule
that replaces it is CLAUDE.md's own — one kind of change per COMMIT — and it is what makes the
wave reviewable.

| # | Change | Its rule |
| --- | --- | --- |
| 1 | The worker precaches the shell (D-1) | P7 — `context.set_offline(True)`, reload, a named state renders |
| 2 | `/build.json` and the update discipline (D-2, D-3) | the poll sees a moved stamp and reloads once |
| 3 | The outbox, its store, its replay (D-4, D-5, D-6) | P8 — issued offline, departs once |
| 4 | The pending count reaches the connection mark (D-5) | the interface says what is waiting |
| 5 | The three entry points (D-7) | P9 — declared, and `/add?q=` pre-fills |
| 6 | B-256's lock and stamp (§ 4) | a mid-run swap is a named failure |

The `Makefile:200` figure and the README amendment ride commits 6 and 1 respectively — each is the
commit whose subject it belongs to, never a tidy-up commit of its own.

---

## 6. The gates

The wave's gate, at the close, and nothing merges before all of it is true:

- `frontend/maquette/harness/run.sh` — the full suite, plus the repository's cheap guards
- `frontend/maquette/harness/run.sh --a11y` — zero violations over every named state
- `frontend/maquette/oracle.py --check` — green, or every divergence named with the decision
  that produced it
- `make check` — exit 0
- `scripts/harness-hold-counts.py` — no rule loses a hold
- Every rule this wave adds is mutation-tested: the behaviour is broken on purpose, the rule is
  seen to fall AND to name the right defect, and the break is restored. `scripts/mutate.sh`
  refuses a dirty tree, so the commit comes first (L10's lesson).

**The oracle is expected GREEN throughout.** Nothing in this lot draws a pixel differently: the
worker changes what is fetched, not what is painted, and the pending count lands in a mark L10
already draws in four conditions. A divergence here is a defect until it is proved otherwise —
which is the opposite of L15's situation, where B-248 made 167 divergences the expected reading.
