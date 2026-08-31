# Phases 4 and 5 — The outbox, its store, and its replay (P8)

## What lands

- `design/src/app/outbox-store.ts` — IndexedDB alone. It knows nothing about mutations.
- `design/src/app/outbox.ts` — the queue, the count it publishes, and the replay.
- `design/src/lib/query-client.ts` — `send()` tells a refusal from an outage.
- `design/src/mocks/index.ts` — the layer can be *offline*, and it deduplicates on a key.
- `harness/outbox.py` — **R107**, eleven holds.

## The three decisions inside it

**A refusal and an outage are not the same event.** A layer that *answers* — 404, 409, 500 — has
made a decision the operator must see: it is re-thrown untouched, the surface rolls back, and it
says why. A network that does not answer has decided nothing, so the mutation is held and the call
**resolves**: rejecting is what triggers L09's rollback, and rolling back a mutation that has not
failed erases an action that is still going to happen. Confusing the two would queue a mutation the
server already rejected and re-send it forever.

**Exactly once is two properties in two places.** The client forgets an envelope only *after* its
request has answered — at *least* once, all a client can promise, since a request whose answer is
lost is indistinguishable from one that never arrived. The layer records applied keys and replays
the first answer for a second arrival. R107 holds each separately, because they fail separately;
holding only the pair end-to-end would pass over a client that had stopped sending the key at all.

**The key travels on every mutation, not only on a replay.** A key added only when something is
re-sent is a key the layer never saw the first time, so « exactly once » would hold everywhere
except the one case it exists for.

## Where it deviates from MODEL Part 13, and why

Part 13 says *a feature's `queries.ts` enqueues*. The intent — the queue learns no domain — is kept
exactly; what changes is the number of writers. `send()` is the one seam all six mutation call
sites already pass through, so enqueuing there is the same behaviour with **one** writer instead of
six. A rule re-applied at every call site is a rule that will be missing from the seventh.

## Also in these commits

`app/shell.tsx` crossed invariant 6's 400-line ceiling (384 → 414). The split is on the **subject**
the file states about itself — it owns *when*, the module owns *what* — so the outbox publishes its
own seam, as `mocks/index.ts` and `engine/seams.ts` already do. 396 lines.

Twenty-seven words entered `scripts/code-vocabulary.txt`. That is the guard working: a name built
from a word nobody wrote down is refused, and adding one is a line under review.

## Done when

ACC-10 (survives a restart), ACC-11 (P8), ACC-12 (exactly once, on the layer's side), ACC-13 (no
rollback). R107 — 11 holds, no violation.
