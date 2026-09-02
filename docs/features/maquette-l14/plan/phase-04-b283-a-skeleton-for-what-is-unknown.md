# Phase 4 — B-283: a skeleton for what is unknown · behaviour

**Owns**: B-283, D-L14-7, D-L14-8. **Constitution**: §13 (no assertion about data in flight), §12.
**Depends on phase 3.**

## What changes

1. `ui/variants/surfaces.ts` gains `skeletonLine` — the residue's `sk` shimmer (as `Skeletons`
   wears it), a height on the scale, a width variant (`full`, `wide`, `half`, `short`). One
   component `SkeletonLine` in `ui/state-surfaces.tsx` emits it with `data-skeleton=""` and
   `aria-hidden="true"`.
2. `media-screen.tsx` computes `inFlight = sheet.isPending || (sheet.isPlaceholderData &&
sheet.isFetching)` and `seasonsInFlight = seasons.isPending`, and passes them down.
3. In `media-hero.tsx`, `media-cast.tsx`, `media-library-facts.tsx`, `media-details.tsx` (phase 3's
   recorded deviation — the vocabulary arm refuses « Information »): every
   part that prints an « unknown » assertion draws `<SkeletonLine>` INSIDE the same element when
   its value is absent and the read is in flight. The trailer's no-info `<p>` and the cast's
   no-info `<p>` are replaced by a skeleton line of the same element while in flight — so
   `[data-part="no-info"]` is absent then and present after. The blocks and the body's child count
   do not change at any instant.
4. **R119 — `harness/priming.py`**, in the full suite (it drives a 2 000 ms latency; it is not a
   name contract). Holds, in this order:
   - (a) the reference publishes `sheetFor` and it can be wrapped — the thinning has a subject;
   - (b) with the thinned placeholder and 2 000 ms latency, at ~300 ms after navigation: the
     screen is open, the hero title is drawn, `[data-skeleton]` count inside the screen ≥ 6, and
     `[data-part="no-info"]` count = 0;
   - (c) after `window.__mocks.quiet()`: `[data-skeleton]` = 0 and exactly one no-info naming the
     trailer (Broadchurch, the title `screen_addresses.py` already uses);
   - (d) the CONTROL: the same walk with `sheetFor` restored draws 0 skeletons at ~300 ms — the
     placeholder is complete and nothing is unknown;
   - (e) no JS error.
5. `BUGS.md`: B-283 → `fixed #NNN` (the number once the pull request exists; written at the close
   if the number is not known yet — B-219's placeholder is refused by the register guard, so the
   row keeps `open` until the number exists and the body says why).

## Deviations, recorded here rather than discovered later

The design's § 3 and § 5 describe the instrument as it was first drawn. Three things about it
changed while it was being built, each because a reading proved the drawing wrong, and the design
is not edited to match — a design is what was decided.

- **The thinning is `{t}`, plus a SECOND walk keeping `{y}`**, not the `{t, k, y}` the design names.
  Keeping the kind and the year made the hero's own fields impossible to measure: the metadata line
  was gated on the whole sheet, and with those two present the branch that printed « année inconnue
  · Série » was never taken. The lean walk is the hardest case; the partial one is the only place
  « field by field » is decidable at all.
- **The control holds FEWER skeletons, not zero.** « The same walk with the FULL placeholder draws
  no skeleton at any moment » was red on its first run, and rightly: the seasons carry no
  placeholder of their own, so lines stand there whatever the sheet holds. It holds fewer than the
  thinned walk, plus the CONTENT the placeholder carries — the cast strip drawn, the synopsis a
  sentence.
- **The rating draws nothing in flight at first, and waits now.** The design lists it among the
  parts; it drew neither an answer nor a wait until round 3's pass. Recorded because it was a
  departure for two rounds.

The hold list in item 4 above is the instrument's FIRST shape, and so is the definition of done
under it — both describe holds and a mechanism that have since moved. What it holds today is `harness/priming.py`,
which prints its own holds; a second copy of them here is a copy that goes stale — as this one did.

## Definition of done

- `scripts/mutate.sh frontend/maquette/design/src/features/media/media-screen.tsx
't.replace("const inFlight =", "const inFlight = false && ")' frontend/maquette/harness/priming.py`
  → hold (b) falls naming the no-info count; restored.
- A second mutation on the cast file (`t.replace("inFlight ?", "false ?")` or its exact form) →
  (b) falls on the skeleton count; restored.
- The oracle: zero divergence (no named state shows the priming at rest). R115's priming hold
  still reads 8 children at 120 ms.
- `run.sh --contracts` green (R80's pair count may RISE by one — a floor); `npm run check` green;
  `check-css-tokens.py` green.
- Two commits: the drawing and the flag (`feat(maquette-l14): …`), then the rule
  (`test(maquette-l14): R119 …`) — the rule's mutation runs after both are committed.
