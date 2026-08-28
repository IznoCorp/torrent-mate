# L10 — implementation plan

The design is `../DESIGN.md`. This file owns the ORDER and the ACCEPTANCE criteria; each phase
file owns its own steps. `IMPLEMENTATION.md` owns the status — never this file, and never
`frontend-architecture.md`, which since 2026-08-28 carries the order and the dependencies and no
status at all.

## The order, and why it is this one

**The instrument comes before the subject.** Phase 1 builds the fake transport and phase 2 makes
`quiet()` answer for it — because from phase 3 onwards every proof in this wave rests on both, and
an instrument built after the thing it measures is an instrument shaped by what it found. That is
the order L09 learned the hard way when its settle rule (R89) went green over the exact defect it
names (B-105).

Phase 3 is the client, phase 4 the visible states, phases 5–7 the map surface by surface, phase 8
the guards, phase 9 B-140, phase 10 the close.

**B-140 sits at 9 and not at 1 on purpose.** It is a behaviour change of its own, and putting it
early would let a relay defect and a scroll defect arrive in the same measurement. Late, alone, in
its own phase, it is attributable.

| # | Phase | File |
| --: | --- | --- |
| 1 | The fake transport, and the protocol it obeys | `phase-01-the-fake-transport.md` |
| 2 | `quiet()` learns about the stream | `phase-02-the-settle.md` |
| 3 | The relay client: connect, close, backoff, replay | `phase-03-the-relay-client.md` |
| 4 | The connection states, drawn | `phase-04-the-connection-states.md` |
| 5 | The map — Arrivées and the pipeline | `phase-05-map-arrivals.md` |
| 6 | The map — Médiathèque and Média | `phase-06-map-library.md` |
| 7 | The map — Acquisition, Système, Maintenance | `phase-07-map-acquisition.md` |
| 8 | The guards: no polling, named invalidation, map completeness | `phase-08-the-guards.md` |
| 9 | B-140 — the scroll memory learns about pages | `phase-09-b140-scroll.md` |
| 10 | The close | `phase-10-the-close.md` |

## The gate, per phase

Run **after** the phase, never after a commit inside it.

```
frontend/maquette/harness/run.sh --contracts     # the name contracts + the repository's cheap guards
frontend/maquette/harness/run.sh --oracle        # the rendering did not move
```

Before the merge: `frontend/maquette/harness/run.sh` entire, `--a11y`, then `make check`.

`run.sh` rebuilds and re-copies the prototype first; a stale `/tmp/tm-refonte/wrapped.html`
measures the previous build in silence.

## ACCEPTANCE

Every criterion is an executable command with a documented expected output. A prose criterion is
invalid (`docs/reference/feature-lifecycle.md`).

| ID | Command | Expected |
| --- | --- | --- |
| ACC-01 | `python3 scripts/check-live-relay.py --arm no-polling` | exit 0, prints the corpus size above its declared floor |
| ACC-02 | `python3 scripts/check-live-relay.py --arm named-invalidation` | exit 0 |
| ACC-03 | `python3 scripts/check-live-relay.py --arm map-completeness` | exit 0, prints mapped + explicitly-unmapped = every emittable type |
| ACC-04 | `python3 frontend/maquette/harness/fanout.py` | R91 green, one hold per rule in the map |
| ACC-05 | `python3 frontend/maquette/harness/relay_states.py` | R92 green, 4 states × (text, control, reduced motion) |
| ACC-06 | `python3 frontend/maquette/harness/replay.py` | R93 green, gap replayed, no blanket invalidation |
| ACC-07 | `python3 frontend/maquette/harness/settle.py` | R89 green, with its new stream hold |
| ACC-08 | `python3 frontend/maquette/harness/scroll.py` | R94 green, main page AND overlay screen |
| ACC-09 | `frontend/maquette/harness/run.sh` | every rule green; per-rule hold counts ≥ `hold-counts-baseline.json`, the new ones declared |
| ACC-10 | `python3 frontend/maquette/oracle.py --check` | 0 divergence over the recorded states, or each divergence accepted with its reason in the close |
| ACC-11 | `make check` | exit 0 |
| ACC-12 | `python3 scripts/check-module-size.py --root frontend/maquette/design/src` | every new module under the 400-line hard ceiling (invariant 6) |
| ACC-13 | `python3 scripts/check-no-french.py` | exit 0 — every visible string through `i18n/fr.json` |
| ACC-14 | `python3 scripts/check-code-abbreviations.py` | exit 0 — names written in full |

## What this plan does NOT do

L11's service worker, offline shell and mutation queue. A new page. Any backend file. Any
re-argument of the arbitrations of 2026-08-25 to 08-28 (D3 widened, D10, D11, D8's limit,
invariant 10, the status leaving the plan).
