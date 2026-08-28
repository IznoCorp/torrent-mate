# Phase 3 — The relay client: connect, close, backoff, replay

## Steps

1. `design/src/lib/relay.ts` — transport and nothing else (D-L10-1). It names no domain word and
   does not know what a query key is.
   - connect to `/ws/events`; read the single `ws.hello`; keep `build_commit`.
   - reply to `ws.ping` with a text frame.
   - remember the last event id seen; reconnect with `?last_id=`.
   - close codes: `1000` is silence; **`4401` does not retry** — retrying an expired session is a
     loop that produces nothing and says nothing; everything else backs off, capped.
   - publish a connection state (`connected` · `reconnecting` · `lost` · `refused`) through
     `useSyncExternalStore`, never a `useEffect` — invariant 5, and the relay is installed at boot
     rather than mounted with a surface.
2. `app/live-updates.ts` — the composition table: one import per feature, handed to the relay.
   Empty of rules at this phase; phases 5–7 fill it.
3. Boot: install after the query client exists and before the engine starts. **`harness/boot_order.py`
   (R88) is on the `--contracts` tier and holds the boot's steps in order** — it is extended in
   this phase, with the reason the new step cannot move written beside the others.

## Why it subscribes once, at boot

`lib/query-client.ts` sets `staleTime: Infinity`, `refetchOnWindowFocus: false`,
`refetchOnReconnect: false`. A subscription mounted with a surface would miss every event arriving
while that surface is unmounted, and the remount would refetch nothing. **A missed invalidation
never heals here.** Production's hook shape is safe because production polls underneath it; this
does not.

## The rule

**R93 (`harness/replay.py`)** — drop the socket, assert the reconnect carries the last id seen,
replay a burst, assert the gap healed. And assert the reconnect did **not** invalidate the whole
cache: a blanket invalidation is one line, always correct, and indistinguishable from a reload.

**Mutation**: reconnect without `last_id`. The hold must fall naming the lost gap, not a
connection error.

## What this phase does NOT do

It maps no event to any key — the relay dispatches to an empty table and that is deliberate, so
phase 5 is the first phase where a cache entry moves and any movement is attributable to it.
