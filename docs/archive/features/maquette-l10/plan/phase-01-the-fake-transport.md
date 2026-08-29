# Phase 1 — The fake transport, and the protocol it obeys

**Why first.** Every proof after this phase drives a stream. An instrument built after the thing
it measures is an instrument shaped by what it found.

## Steps

1. `design/src/mocks/stream.ts` — a `WebSocket` replacement installed alongside the `fetch` seam,
   obeying `docs/reference/web-ui.md` § WebSocket Protocol:
   - **accept, then validate, then close `4401`** on a refused session. Never close before accept:
     a real browser reports `1006` and the client's terminal branch becomes dead code that passes
     every test.
   - one `ws.hello` carrying `build_commit`, before anything else.
   - `{id, type, data}` per event.
   - `ws.ping` on demand from the driver; any text frame from the client is a pong.
   - `?last_id=` honoured with an **exclusive** lower bound, in order, before live fan-out.
2. `window.__mocks.stream` — the driving surface, and the ONLY way in:
   `open()`, `emit(type, data)`, `emitBurst([...])`, `drop(code)`, `pong()`, `sent()`, `state()`.
3. **It emits nothing on its own.** No timer, no seeded traffic (D-L10-4). A named state is a
   world where nothing arrives unless the driver makes it arrive.
4. Wire the install into `installMockNetwork()` so it lifts out with the layer under
   `__MOCKS_BUILT_IN__` — the flag L08 measured at 1 235 723 bytes of difference.

## The rule

Fold into `harness/mocks.py` (the layer's own rule) a hold per protocol clause: hello arrives
once and first; a `4401` arrives AFTER an accept; `last_id` is exclusive; a burst arrives in
order.

**Mutation**: make the fake close before accepting. The hold must fall AND say the close preceded
the accept — not merely "connection failed".

## What this phase does NOT do

It wires no client. Nothing connects to this yet; `window.__mocks.stream` is driven by the rule
and by nothing else. It touches no backend file: a clause the protocol does not offer is a demand
in `docs/reference/frontend-backend-demands.md`, filed by hand (§ 1 of the design: the computed
register is structurally blind to a WebSocket).
