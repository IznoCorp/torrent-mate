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

**Landed.** Thirteen functions become `discover-cards.ts` and `discover-feed.ts`; the engine
imports them back. `engine/legacy.js` 31 909 → **31 654** — 255 lines, the largest single
subtraction of the wave.

### The finding — B-247's producer half was LIVE, on the surface nobody owned

R100's hold (i), written for this phase, fell on the code as it stood: **all sixty tiles of
`acq-discover-posters` were new nodes after any store write.** `discover-tab.tsx`'s effect runs on
every commit and asks for the feed to be filled; the deck branch already refused to rewrite a pile
that was there, and the list and poster branches rewrote unconditionally. **A tap landing between
`pointerdown` and `click` was lost, silently, on the one surface built to be browsed with a
thumb.**

The repair is `ui/markup.tsx`'s one layer down — write only when the string CHANGES — with a named
door (`forgetDrawnFeed`) for the three moments that mean to rewrite. Mutated away, the hold falls
again: « 60 captured, 60 after, **0 same**; lost: tile, IMG, tile ». `deck.py` does not catch it,
correctly: it measures the gesture, not identity.

### A type that lied

`lib/engine-drawing.ts` declared `tileHTML`'s badge as `{ tone, text }` while `tileHTML` reads
`badge.txt`, and named neither `panel` nor `dismiss` — both of which it reads. Invisible for one
reason: **the only caller was untyped JavaScript inside the engine.** The first TypeScript caller
asked the question.

### A guard refused the move, and the exemption is CHECKABLE

`check-state-ownership` counted the feed's two store keys as « a COMPONENT copying server state »
— right for what it could see. A module the ENGINE IMPORTS BACK renders nothing and its writes are
the writes the engine was already making, at the same moments.

**What makes the exemption safe rather than a hole**: an entry is honoured only while
`engine/legacy.js` REALLY IMPORTS the module. Nobody can grant it to themselves, a stale entry is
refused outright, and every entry expires on the day the engine goes. Read by hand, both ways:

```
as it stands                          → exit 0
the import repointed elsewhere        → exit 1, two violations:
    "recorded as the engine's own and the engine does not import it"
    "2 server-state key(s) written by a COMPONENT against a ceiling of 0"
restored, git status empty            → exit 0
```

### Readings

oracle **2 958, no divergence** · contracts 17 rules + 26 guards, no violation · `persistence.py`
41 → **47** holds · `deck.py` green · `legacy.js` **31 654**

### Deviations

**(1) The technique is unchanged, deliberately.** The design said the feed's imperative half stays
imperative; this is that, and the phase file records that it is a decision rather than an
unfinished conversion.

**(2) `check-state-ownership.py` was opened**, which no phase planned. It is the instrument that
refused the move, and the repository's own rule is that the wave which touches a tool takes its
debt — here, the absence of any way to say « this is the engine's code, wherever it lives ».
