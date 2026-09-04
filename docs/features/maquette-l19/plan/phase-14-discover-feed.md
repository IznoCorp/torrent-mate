# Phase 14 — The Découvrir feed

## Objective

The one feature surface still drawn by `innerHTML` after L15: `deckHTML`, `mountDeck`,
`refreshDeck`, `advanceDeck`, `fillSug` and `sugFoot` — the seven inventory sites between
`legacy.js:8315` and `:8540` — move to `features/acquisition/`.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular, and it is the whole difficulty

`features/acquisition/discover-tab.tsx` draws the containers and the fragment fills them, and its
header says why in a sentence that is a measurement rather than an excuse: **`advanceDeck` mutates
the deck's own DOM in place — it inserts a card at the back, decrements every `data-depth`,
writes an inline transform on the outgoing card and removes it 440 ms later — and a REPLACED node
cannot animate.** React owning that markup would restore the string it last rendered on the next
repaint and undo the gesture four rules measure.

**So the gesture's imperative half is not converted into a re-render.** What moves is WHO OWNS
the nodes and WHERE the markup is built: the feature builds the deck's markup and the feature
mutates it, through one module, with React rendering zero children into the container exactly as
it does today. The arrangement `paintSelBar` already has, one level down, and the arrangement
this file keeps — **the difference is that both halves are now the feature's**, which is the
whole of the move.

- **`window.__suggestions` and `installSuggestionsLookup` die here.** The shell loses an import
  and a call.
- **R100 hold (f) gains `#sugitems` and the deck** on `acq-discover-posters` and
  `acq-discover-deck` — the containers its own docstring names as « the producers' half of the
  same defect ». That docstring is corrected in the same commit: it stops saying no surface owns
  them.
- The end mark's sentence and the « Charger 30 de plus » button move to `fr.json`.

## The rules that bite

`harness/deck.py` already drives the gesture. It is re-read against the moved code without being
weakened — **its assertion count may not fall** — and gains a hold that the pile's nodes SURVIVE
a store write, which is the property the imperative arrangement exists to protect and which
nothing reads today.

The mutation rebuilds the deck's markup on every commit (the defect the file's header describes)
and both `deck.py` and `persistence.py` must fall.

## Verdict

*(filled when the phase lands)*
