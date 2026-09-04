# Phase 02 — The producer seam, proved on the account menu

## Objective

Build the door every later phase walks through, and prove it end to end on the smallest producer
in the lot — `openUserSheet`, 26 lines, one caller, no address, one fixture family.

A first producer moved through a seam nobody has exercised is two experiments at once. This
phase separates them: the seam is built AND spent in the same commit, on the surface where a
mistake is cheapest to see.

## What changes

### `ui/panel/contract.ts` — the door, beside `registerBlock`

```ts
export type PanelCache = { held: <Result>(key: readonly unknown[]) => Result | undefined };
export type PanelProducer = (subject: string, cache: PanelCache) => PanelDescriptor | null;
export function registerProducer(kind: string, produce: PanelProducer): void;
export function producerFor(kind: string): PanelProducer | null;
export function refuseProducer(kind: string): never;
```

`PanelCache` is **structural**: `ui/` may not import a feature (invariant 7) and its domain-word
ceiling is ZERO (invariant 10). A `QueryClient` type would import the library into the primitive
and a query KEY would name a domain; `held` takes an opaque key.

`refuseProducer` mirrors `refuseBlock` for the measured reason `refuseBlock`'s own comment gives:
a kind nobody registered must raise loudly, because silence draws an empty panel and blames the
data — which is exactly what a forgotten registration looks like.

### `app/panel-host.ts` — who holds the cache

`installPanelHost(store)` → `installPanelHost(store, queryClient)`. **An EDITED shell line, not
an added one.** It publishes `window.__panel.produce(kind, subject?)`, which looks the kind up,
calls the producer with `{ held }` over the query client, and opens what it answers. A producer
answering `null` opens nothing — the honest reply for a subject the cache does not hold, and the
reply the engine's producers already give by returning early.

`kind` and `subject` are opaque strings here: `app/`'s domain-word count does not rise.

`window.__unknownProducer` publishes the refusal for the rule, as `window.__unknownPanel` does.

### `features/account/panel-account.ts` — the first producer

Reads `["/api/auth/me"]` from the cache, imports `icons` from `app/icons`, and answers the same
descriptor `openUserSheet` answers today. Its two strings — « Profil et préférences », « Se
déconnecter » — are **extracted** into `fr.json` under `panels.account.*`, read through
`i18next`'s own `t` (a producer is not a component).

Named in `app/shell.tsx` as a side-effect import, beside the two that are already there.

### The engine

- `legacy.js:10219` → `panel.produce("account")`; `openUserSheet` and its `ACCOUNT` reads go.
- `engine/states.js`'s `sheet-user` entry calls the seam, and stops importing `openUserSheet`.
- `ACCOUNT` leaves the engine's published reference if nothing else reads it (`--arm
  reference-slice` says).

## The rules that bite

1. **A new hold, `harness/producers.py`** — the seam itself: every registered kind is named, a
   kind nobody registered RAISES through `window.__unknownProducer`, and `panel.produce` on a
   registered kind opens a panel whose title is the subject's. It grows by one kind per later
   phase, which is what makes « the producer moved » readable from outside.
2. **R100's hold (f) gains `sheet-user`** with a floor on the panel's own nodes, so a panel
   drawing nothing cannot pass as kept.

## The mutations

```bash
# The seam: a registration removed — producers.py must fall naming the kind.
sh scripts/mutate.sh frontend/maquette/design/src/features/account/panel-account.ts \
  't.replace("registerProducer(\"account\"", "const unused = (")' \
  frontend/maquette/harness/producers.py
# Identity: the memo removed at the panel's markup site — persistence.py must fall on sheet-user.
sh scripts/mutate.sh frontend/maquette/design/src/ui/markup.tsx \
  '<the memo removed>' frontend/maquette/harness/persistence.py
```

Both are run through `scripts/mutate.sh`, which refuses a dirty tree, rebuilds, republishes under
`served_copy.py`'s lock and restores from the index (B-303). **Committed before every mutation.**

## Gates

The oracle at **zero divergence** · `producers.py` · `persistence.py` · `--contracts` · the size
arm re-recorded downward for `legacy.js` and `states.js` · the shell's line count written below.

## Verdict

**Landed** over three commits — the seam and the first move, the `needs` mechanism the harness
forced, and one repair to R120 found by R120's own mutation.

### What the harness found that the design had not

**A producer reads the cache synchronously, and the design never said who FILLS it.** The account
menu is raised from the header on every page; its query belongs to the account PAGE. So
`held(['/api/auth/me'])` was `undefined` everywhere but there, the producer answered `null` —
correctly — and the menu opened nowhere. **Three rules fell at once**: `producers.py`,
`persistence.py` (h) and `logout.py`, the last of which had been green for months over a menu it
could still reach.

The repair is a producer DECLARING what it needs, beside itself:
`registerProducer(kind, produce, needs)`, with `window.__refillProducers` published by the panel
host. It is the same problem `app/engine-data.ts` answers for the engine with ONE list in
`app/`, and declaring it per producer is exactly what lets that list empty entry by entry
instead of growing a line per conversion — which the design's § 9 asked for and could not have
reached the other way.

**Two orderings were measured rather than foreseen**, and each cost a full run:

1. The first fill cannot be `installPanelHost`'s: it is installed BEFORE `installMockNetwork()`,
   so a request started there leaves before there is a layer to answer it. `installEngineData`
   makes the first call, after the mocks.
2. `window.__go(id)` CLEARS the cache and a named panel state produces in the same tick. The
   engine's producer had its fixture in hand; a cache-backed one has nothing yet. So `produce`
   asks for what the kind needs and opens when it lands — nothing new drawn, identical on a warm
   cache, and a subject the layer genuinely lacks still opens nothing.

### The mutations

Every one through `scripts/mutate.sh` — dirty tree refused, rebuild, republish under
`served_copy.py`'s lock, restore from the index (B-303). Committed before each.

| # | Mutation | Rule | Fell with |
| --- | --- | --- | --- |
| 1 | `registerProducer("account", …)` removed | `producers.py` | « missing ['account'] · registered [] » |
| 2 | the producer reads `["/api/nothing"]` | `producers.py` | « drawn None · expected 'izno' » |
| 3 | `PanelContent` keyed on the store version | `persistence.py` (h) | « 7 captured, 7 after, **0 same**; lost: IMG, sheet/action, path » |
| 4 | `refuseProducer` returns instead of throwing | `producers.py` | see below |

**Mutation 3 is the one worth reading twice.** It fell on the `write` door and NOT on `touch` —
which is the docstring's own sentence about the two doors, confirmed from the other side: a
surface reading `useUiState()` bails out of a version bump. Hold (h) drives both, so the
insensitive door does not hide the sensitive one.

### R120 certified the crash it was written to prevent — found by its own mutation

**Mutation 4 exposed a vacuity in this phase's own new rule.** « A panel kind nobody produces is
REFUSED » read `refusal is not None` — i.e. « something threw ». With `refuseProducer` returning,
`produce` is null and the very next line calls it, so a `TypeError` arrives and the check PASSED
over a refusal that had stopped existing. It reads the named thrower's own message now
(`unknown panel producer:`), which is the only reading that separates a refusal from a crash;
re-mutated, both checks fall and print « i is not a function » — what came back instead.

Recorded rather than quietly fixed: **a rule that accepts any throw certifies the crash it was
written to prevent**, and this one was written in the wave whose office rule says a green gate is
a reason to look.

### Readings, on the phase's head

| Gate | Reading |
| --- | --- |
| **oracle** | 87 states × 34 regions, **2 958 measurements, NO DIVERGENCE** |
| `run.sh --contracts` | **14 rules and 26 repository guards, no violation** |
| `tsc --noEmit` | clean |
| `vitest run` | 5 files, 94 tests passed |
| `app/shell.tsx` | 398 → **397** — it only falls |
| `engine/legacy.js` | 32 461 → **32 436**, re-recorded in the ledger in the same commit |
| `engine/states.js` | 791 → **790**, re-recorded |
| `check-frame-domain.py` | `ui/ 0, lib/ 18, app/ 129` — unmoved; `kind` and `subject` are opaque strings in `app/` |
| vocabulary | 8 words added, one line each — `cache`, `need`, `needs`, `produce`, `producer`, `producers`, `registered`, `translate` |

### Deviations

**(1) `registerProducer` takes a third argument the design did not draw.** The design said « a
producer is a function from the cache to a descriptor » and stopped there. It is that, plus a
declaration of what must have landed — forced by the measurement above, and the mechanism that
lets `app/engine-data.ts` shrink.

**(2) `producePanel` waits.** The design said a producer answering `null` opens nothing, full
stop. It still does when the layer has nothing; what changed is that the kind's needs are asked
for first. Written into the code with the measurement that forced it.

**(3) The rule count moved.** The contracts tier is 14 rules where it was 13: R120 joined it,
because a producer registration is a name with three ends — the registration, the delegation's
kind string, and the scenario table's entry.
