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

*(filled when the phase lands)*
