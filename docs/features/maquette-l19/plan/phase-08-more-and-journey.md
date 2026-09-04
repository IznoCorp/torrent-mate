# Phase 08 — Acquisition: « Veille et obligations » and the journey

## Objective

`openMoreSheet` (`legacy.js:31865–31892`) and `openJourneySheet` (`:31805–31848`) move to
`features/acquisition/panel-more.ts` and `features/acquisition/panel-journey.ts`, kinds `more`
and `journey`, the second addressed `journey:<title>`.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- **§20: the journey sheet IS the tunnel seen by the operator.** It is the surface DOIT-5 names
  and the one L21 will hang « Remettre en file » and « Re-scraper » off. **This lot adds
  neither** — a producer here offers exactly what it offered.
- **The 260 ms wait at `legacy.js:10215`** (`data-journey`: `panel.close()` then
  `setTimeout(() => openJourneySheet(…), 260)`) goes with the producer. The panel leaves inside
  the navigation's own commit, as `data-mediasheet` already does since L12.
- R103 gains a **refused floor on this path**: after the move, the gap between the scrim reaching
  zero and the journey arriving is zero frames. It keeps PRINTING the five sites this lot does
  not own (see `DESIGN.md` § 3.3).
- R100 hold (f) gains `sheet-more` and `sheet-journey`.

## The rules that bite

`harness/journey.py` (R82) already holds the journey's address. It gains the seam and the
descriptor's own facts. `exits.py` gains the refused floor.

The mutation for the floor puts the wait back:

```bash
sh scripts/mutate.sh frontend/maquette/design/src/engine/legacy.js \
  '<the 260 ms wait restored on the journey path>' frontend/maquette/harness/exits.py
```

Red, naming the frames of bare page. Restored.

## Verdict

**Landed** over two commits — the move, and one repair to R103's new hold found by its own
mutation.

### The journey's fixture really dies

The engine's producer carried its five stages as a literal while the mock already answered them
at `/api/acquisition/journeys/{infoHash}` and nothing called it. The literal is gone. `needs` now
accepts a FUNCTION of the subject beside a list, because a journey is read per medium and a boot
cannot ask for one without inventing a subject.

**Reading the layer raised a question the literal could not**, and `check-live-relay` asked it: a
surface reads that address and no event refreshes it, under `staleTime: Infinity`. §20 asks the
operator to be able to WATCH a tunnel, so `live.ts` refreshes it on the four events that advance a
stage it draws. **Two names were invented on the first attempt** — `ItemIngested` and
`ItemScraped` do not exist — and the guard said so in its own words: « a rule names it and the
backend emits nothing by that name — the rule is dead, and its surface will never refresh ».

### R103's own hold was vacuous, and its mutation said so

The first version drove `window.__panel.produce("journey", …)` directly. Putting the 260 ms wait
back beside `data-journey` fell **nothing** — the wait lives in the delegation branch that call
steps over. « A rule must cover the path actually walked » (BUGS.md rule 4), and the path is a
finger on an action carrying `data-journey`.

It taps one from the follow sheet now, and reads the frame at which the panel's CONTENT becomes
the journey's: a journey REPLACES the panel it was reached from, so « the sheet is up » is true
throughout and says nothing.

| | Frame the journey is drawn at |
| --- | ---: |
| as it stands | **3** |
| with the 260 ms wait put back | **19** |

The floor is 5, and a 260 ms wait at 60 Hz lands past 15.

### The five sites this lot does not own

R103 keeps PRINTING the gap for them and names each with its owner: 9792 and 10249 the arrivals',
9861 the releases', 9882 and 9885 the profile's. **The reversal the contract promises is complete
when the LAST site goes, and the last site is not this lot's** — a blanket refusal would have
been a rule against the wrong subject. Carried into `REPORT.md`.

### What did not move, said rather than inferred

`REOPEN.journey`'s `resolves` stays the engine's: it asks whether the interface holds the MEDIUM,
and the layer answers the same stages for any info hash — a `holds` built on that read would say
yes to everything.

« Veille et obligations » keeps its four facts as a declared fixture, each with the operation
that replaces it named beside it. Reading `obligations` / `downloads` / `history` here would be
drawing §18 in this lot's clothes; the clause map hands that to **L16**.

### Readings

oracle **2 958, no divergence** · contracts 14 rules + 26 guards, no violation · `exits.py` 17 →
**18** holds · `legacy.js` 32 256 → **32 192** · `states.js` 789 → **787**
