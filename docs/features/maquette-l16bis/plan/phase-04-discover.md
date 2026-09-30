# Phase 4 — Découvrir: the header, and the swipe of Q7 (S8, S9)

**STOP C: OPEN 10** (DESIGN § 5) — written for its recommended reading A (one order, in the interface); under B this
page gains an operation, its mock, two states and a demand (≈ 3 points more). The operator's answer is read first.

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
`grep -n "liveStrip()\|pill/list" frontend/maquette/design/src/features/acquisition/discover-tab.tsx` → **107**,
**151**; `grep -n '"live[A-Z]' frontend/maquette/design/src/i18n/fr.json` → **858–862**;
`grep -n "const releaseList\|const releaseDeck" frontend/maquette/design/src/features/acquisition/card-gestures.ts` →
**169**, **185**; `grep -cv '^\s*$' frontend/maquette/design/src/features/acquisition/discover-feed.ts` → **382**
(STOP D near); `grep -cv '^\s*$' frontend/maquette/design/src/ui/variants/rows.ts` → **56**. **Read by finger
first**: the deck's two directions on tm-design (DESIGN § 0.3 item 1 was read in the code and in `deck.py`).

## What changes

1. **The header** (S8; DECIDED 8): the message leaves the body for the pill row's empty place, `liveStrip` with its
   `inline` value, one line ellipsised at the switch, its whole on a tap; it reads « n séries et m films à
   découvrir », both counted from the suggestions already read, split by kind; the four `live*` literals deleted.
   The TMDB notice stays where the train put it.
2. **The list's swipe** (S9; DECIDED 10): a LEFT travel passes — the row leaves, no notification; a RIGHT travel
   rejects — `dismissSug` and its « Annuler », unchanged; the back uncovers « Passer » on a left travel and « Pas
   intéressé » on a right one.
3. **Pass, one order** (OPEN 10 = A): the list draws by `sugOrder` as the deck does, so a passed row comes back at
   the back; nothing reaches the engine.
4. **The gesture declared in the design system**: `suggestionWrap` / `suggestionBack`
   (`features/acquisition/variants.ts:114–125`) → `ui/variants/rows.ts` `commitRow` / `commitRowBack`, the words the
   caller's; the list half of `card-gestures.ts`'s mechanics → a domain-free `lib/` module taking `{ onLeft, onRight }`;
   the feature keeps what each side means. The deck keeps its own pile.
5. **The two stale comments** (`card-gestures.ts:3–4`, `discover-cards.ts:96`) say what the code does.
6. **Its register row** (order 57): « Découvrir's header draws four `fr.json` literals as figures » (DESIGN § 6).

## Acceptance — red first on the old code, then green

- **R-L16bis-k** — red on `discover-header` (the message a child of `discover/body`, its figures `fr.json` strings).
- **R-L16bis-l**, holds in `harness/deck.py` — red on the list: a left swipe toasts and adds to `sugGone`; the back
  reads « Pas intéressé » on both sides. `deck.py`'s deck holds stay green throughout.
- Named states: every S8 and S9 id (`discover-list-passed-returns` under A); the oracle accepts every Découvrir state
  by name (the body lost its strip; the list's back words).
- Walked by finger at 369 px, list and deck: left, right, « Annuler »; the header's tap and Retour.

## Commit

`feat(maquette-l16bis): Découvrir says how many series and films wait, and its swipe passes left and rejects right`
