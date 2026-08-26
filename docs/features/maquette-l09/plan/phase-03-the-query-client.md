# Phase 3 — The query client, and the settle PROVED

**This phase is the lot's hinge.** Everything after it rests on the oracle measuring a wired
surface at rest. That has never been exercised.

## What lands

- `@tanstack/react-query` (D-L09-1).
- `lib/query-client.ts` — the client and its cache policy. **In `lib/`, not under a feature**
  (invariant 10, D-L09-4): it is the application's shape, and the surface that motivated it is
  not its subject.
- The provider in `app/`, composed in the router tree — never in a page.
- The typed read and mutate helpers, generated against `mocks/contract-types.d.ts`, so an
  operationId that does not exist is a compile error.

## The cache policy, decided here and not per surface

Written down in one file so twelve surfaces cannot each invent one:

- **Fresh until a mutation says otherwise** — invalidation by mutation, not by a clock. The live
  relay (L10) is what will drive invalidation for real, and a staleness duration picked now would
  be a number nobody could defend later.
- **No retry.** A retry hides a failure the interface is required to show (NE-DOIT-PAS-5), and it
  would make the scenario surface's injected failure arrive three times late.
- **No refresh on window focus.** The oracle drives 83 states in one context; a focus-triggered
  refresh would put a request in flight during a measurement.

## THE PROOF, and it is the phase's real content

`window.__mocks.quiet()` is read by `oracle.py`'s settle today. **It resolves immediately, because
nothing asks the layer for anything.** Proving it works means making it not resolve immediately:

1. Wire **one** read — the cheapest surface's simplest query — behind the client.
2. Inject a latency through the scenario surface (`window.__mocks.setDefaultLatency`).
3. Measure: the oracle must read the **settled** rendering.
4. **Mutate**: disable the settle's read of `quiet()`. The oracle must now read the skeleton and
   **diverge**, naming the region. Confirm it names the right one.
5. Restore, re-measure, confirm zero.

**If step 4 does not diverge, the settle is doing nothing and this lot stops** (§ 7.1). Eleven
surfaces wired against an oracle that measures mid-flight would produce eleven accepted
divergences and no proof at all.

## The two arms, written here and driven down later

- **Invariant 4** — a count of store keys that name server state. It starts at **11** and is
  refused **upward**. It cannot be pre-satisfied; it has eleven real things to remove. It must
  REFUSE a computed key rather than skip one, and print how many engine writes it skipped.
- **Invariant 5** — no data request inside a `useEffect`. It is at zero the day it is written,
  which is B-075's shape, so it **prints its corpus size and refuses a corpus below a declared
  floor** (3 today).

## Done when

- The bundle figure with the client is MEASURED and written into this file — never estimated.
- Both arms run in `run.sh`'s repository-guard tier.
- The settle mutation was seen to diverge and to name the right region, then restored.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`, before and after.
