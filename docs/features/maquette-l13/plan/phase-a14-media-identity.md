# Phase a·14 — « Média »: seasons and identity

A CONVERSION with two halves. The season tree draws through variants, and every crossing reads the `ids` field
declared in a·6. As a result `SHEETS_RAW`, `OWNED`, `sheetFor`, `titleForProviderId`, `addressIdsFor` and `ownedFor`
die (DESIGN § 5.1, § 5.2; § 3, rows 15 and 18).

## The proof FIRST

- **The oracle**: zero divergence on every media, seasons-panel, episode-popover and follow-panel state. Any other
  divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
- **Harness readers, RE-AIMED to the served answers** (`readMediaSheet`, `readMediaSeasons`, the list's `ids`). Each
  keeps its count, said in its docstring:
  - `addressIdsFor`: `audit2.py`, `panel.py`, `priming.py`, `season_family.py`, `screen_addresses.py`,
    `url_state.py`;
  - `sheetFor`: `audit.py`, `audit2.py`, `follow_has_sheet.py`, `followed_sheet_act.py`, `pop.py`, `priming.py`,
    `season_grab_unfollowed.py`, `transition.py`, `season_family.py`, `screen_addresses.py`;
  - `ownedFor`: `audit2.py`, `priming.py`;
  - `titleForProviderId`: `audit2.py`, `transition.py`.

  INDEX's row names five of these files. The measured list above is the one the phase re-takes before moving
  anything.
- **R156 (`follow_has_sheet.py`) keeps its hold.** It asks the served sheet instead of the engine's resolver. It
  stays a GATE; it is not B-366's repair (c·7).
- **`window.SEASONS`** (read by `busy.py`, `followed_sheet_act.py`, `message_over_layers.py`, `priming.py`,
  `season_grab_unfollowed.py`, `queued_ask_mark.py`, `season_family.py`, `season_grab.py`, `seeds_at_rest.py`) is a
  constant under 100 lines: it dies with its last reader, and each rule is re-aimed to the seed the mock layer
  answers `readMediaSeasons` from, through `window.__mocks` (DESIGN § 4.2). The phase re-takes the reader list
  first; each re-aimed file keeps its count.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 with `SHEETS_RAW` and `OWNED` marked `converted`.

## The move

- **Identity readers.** Every reader switches to `ids` on the list item, or to the served sheet:
  - `features/media/panel-seasons.tsx`, `features/media/popover-episode.ts`, `features/acquisition/follow-facts.ts`
    and `features/media/queries.ts`, for sheet presence and episodes;
  - `features/media/media-screen.tsx`, for the sheet and the title;
  - `app/history-bridge.ts` and `features/media/media-verbs.ts`, for the address ids.
- **Owned episodes.** `features/media/season-list.tsx` and `features/media/panel-seasons.tsx` read
  `readMediaSeasons.owned` in place of `ownedFor`.
- **The season tree becomes variants in `features/media/variants.ts`.** Every file stays under 400 non-blank lines,
  and the rules are deleted in this commit. The classes:
  - `season`, `ep`, `eprow`, `epdot`, `eps`, `en`, `et`, `ed`, `sfr`, `legend`;
  - `sw-info`, `sw-muted`, `sw-success`, `sw-upcoming`, `sw-waiting`, `sw-warning`;
  - `miss`, `missing`, `acquiring`, `announced`, `in_library`, `pending`, `to_grab`, `unverified`;
  - `noinfo`.
- **Deleted from `legacy.js`**: `SHEETS_RAW`, `OWNED`, `SHEETS_IDX`, `sheetFor`, `titleForProviderId`,
  `addressIdsFor` and `ownedFor`. Their members also leave the media reference type and `lib/engine-drawing.ts`.
- **`popover`.** It keeps living in the engine until its verb leaves (b·3), and asks the cache.
- **The size ledger.** This is the largest subtraction of the lot (DESIGN § 2.2). `scripts/frontend_size_ledger.py`
  is re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition: `check-mock-seeds.py` exits 0; the residue ceiling is re-recorded; and the
re-aimed file list, with one count per file, goes in the report. STOP D if a title keyed crossing has no `ids`.

## Commit

`refactor(maquette-l13): every media crossing reads the provider identity and the engine's sheet table dies`

## Amendment — 2026-09-13 (ruling 50: the phase lands as two commits)

**a·14.1** — the season tree to variants (`season-list.tsx`, `panel-seasons.tsx` with `sw-*` and `legend`,
`popover-episode.ts`), their `legacy.css` rules deleted, and `SEASONS` dies with its harness readers re-aimed to the
seed the mock layer answers `readMediaSeasons` from. A pure drawing conversion: oracle zero, the ledger down.

**a·14.2** — the identity crossings: `SHEETS_RAW`, `OWNED`, `SHEETS_IDX`, `sheetFor`, `titleForProviderId`,
`addressIdsFor`, `ownedFor`, their product readers and their harness readers. It opened on a STOP D over two questions
this file did not settle — RULED the same day (ruling 51, below):

- **(a)** `features/media/queries.ts`'s `placeholderData` IS `reference.sheetFor(title)`, and R119 (`priming.py`'s
  INTERCEPT) thins it by wrapping `__referentiel.sheetFor`. With the resolver dead, « what the tap knew » needs
  another source (the tapped list item? the list read's cache?), and R119's thinning seam must move with it — a
  mechanism choice, not a reader switch.
- **(b)** `features/media/media-screen.tsx`'s title comes from `titleForProviderId` BEFORE the read lands
  (`data-key`, `aria-label`, the hero's title in flight); the served `MediaSheet.title` arrives only with the read.
  Whence the title in flight is the same question.

## Amendment — 2026-09-13 (ruling 51: (a) and (b) ruled; ruling 52: a·14.1 and a·14.2 re-cut)

**Ruling 51** (the auditor, under the operator's delegation) settles (a) and (b): the crossing carries what the tap
knew. The tapped list item's title, poster URL and ids (a·6's fields) are written into the navigation ENTRY
(`lib/navigation-entry.ts`, a·3's `ENTRY_DIALS`); `placeholderData` (`features/media/queries.ts`) and the in-flight
title (`features/media/media-screen.tsx`) read the entry; R119's thinning seam (`priming.py`'s INTERCEPT) moves to the
entry's publisher (`harness/publish.ts`). **One observable difference, D8-accepted: a TYPED address shows its ids at
once and a skeleton title until the read lands (the end frame identical).** It is a line of the a·19 reader brief and
one step of the operator's Mac walk (« type /media/<title> directly: ids at once, the title a skeleton for an instant,
then the sheet »). The entry carries title, poster URL and ids ONLY — no sheet body (`history.state` has a size ceiling
in Safari) — and a hold or the reader reads it; restore and Back on a typed address are walked by the reader.

**Ruling 52** re-cuts the two commits. a·14.1 is the season tree to variants ONLY (landed: `season-list.tsx`,
`panel-seasons.tsx`, `popover-episode.ts` emits no class, and the `noinfo` emitters of `media-details.tsx`,
`media-hero.tsx`, `media-cast.tsx`). **`SEASONS` moves to a·14.2**, because a PRODUCT reader this file did not list
reads it: `features/acquisition/follow-facts.ts:33` (the `window.SEASONS` declaration) and `:96` (the follow panel's
seasons block — `held`, `aired`, the fraction). There is no served read keyed by title for it: `readMediaSeasons` is
per address, so the panel asks it by the follow's `ids` — ruling 51's crossing, one crossing and not two. The
`window.__mocks` seed accessor DESIGN § 4.2 promises (`mocks/index.ts:303` has none) is a·14.2's to add — one
accessor — so the nine harness readers of `window.SEASONS` read the seeds the mock layer answers from.

## Amendment — 2026-09-13 (rulings 53, 54 and 55: a·14.2 as it landed)

**Ruling 53 amends ruling 52 on a measurement.** Read literally, « the follow panel asks `readMediaSeasons` by the
follow's `ids` » is a BEHAVIOUR change: the engine's `SEASONS` holds 10 titles and the follow panel read it at the
exact title, while the served answer by identity differs on 209 of the 402 list titles. On the 10 titles whose panel
draws a season block, the episode cells differ on 6 (Silo gains a fourth season, Dexter: Resurrection a second, House
of the Dragon, Star Trek: Strange New Worlds and Ted Lasso read 0 owned, Les Animaniacs gains two seasons) when the
triples are served, and on 0 when the triples stay `SEASONS`' and only the owned numbers and the episode catalogue are
served. Measured offline: `python3 /private/tmp/tm-l13a/a142-compare-seasons.py`. So a·14.2 stays a conversion:
`panel-seasons.tsx` and `popover-episode.ts` read the owned numbers and the episodes served by the follow's identity,
and **`SEASONS`, its read in `followFacts`, the `window.SEASONS` harness readers and the seasons half of the seed
accessor move to b·10-bis**, where the same function already converts `LIBRARY` and `INCOMPLETE` (ruling 41) — a
behaviour phase, its rule first, Silo's fourth season named there. This voids ruling 52's « `SEASONS` moves to a·14.2 ».

**Ruling 54: the ONE `window.__mocks` seed accessor of DESIGN § 4.2 lands in a·14.2, reduced to the sheets family**
(`mocks/mock-seeds.ts`: every sheet keyed by title, with its poster). Why: `__reset` clears the query cache, and the
named states open `Silo (2023)` and `Widow's Bay`, titles no served list holds, so the harness has no served answer to
ask an address of. It is read by the harness ALONE — the driver publishes `__carriedFor`, `__addressOf` and `__sheetOf`
from it — and `screens.mediaSheet(title, carried?)` takes the identity as a second argument when a state or a rule
knows it, and asks the query cache otherwise (`lib/held-identity.ts`, what a tap on a drawn card knew).

**Ruling 55, reading (A): a tap primes its title and poster only.** The entry carries `title`, `poster` and `ids`
(`lib/navigation-entry.ts`, a vitest test holds that the writer copies exactly those three). The auditor's reading (B)
— the entry also carries `year` and `kind` — had a precondition, and it failed: of the seven list schemas a tap comes
from, three carry both (`Follow`, `SearchResult`, `Suggestion`) and four do not (`QueueCard` and `LibraryItem` and
`LibraryRow` carry neither — `secondaryLine` is a composed string — and `IncompleteShow` has no `kind`), read from
`frontend/maquette/contract/openapi.json`'s `components.schemas`. **So the difference is on every tap, D8-accepted,
and named here: a tap primes title and poster only; year, genre, synopsis and cast are skeletons in flight; after a
failed read title and poster remain.** A TYPED address (ruling 51) shows its ids at once and a skeleton title until the
read lands. The end frame is identical in both. Three rules are re-aimed for it, each said in its docstring: R119 (d)
« what is carried is content, the rest a skeleton », R119 (e) « a failed read keeps the carried title and asserts
nothing » (its `cast` term dropped), R115 reads the hero's TITLE in flight — the title now comes only from the sheet or
from what the tap carried. R119's thinning seam moved from the engine's `sheetFor` to an entry the harness writes
(`harness/publish.ts`, `__openCarrying`).

**Ruling 56: the failure text that (A) made reachable.** With the complete sheet gone from the failure fallback, the
failed screen printed `screens.media.synopsisUnread`, « Synopsis inconnu. » — the one text of its family asserting
« unknown » where its key and its siblings (« année non lue », « Genres non lus », « Crédit non lu », « Distribution
non lue ») say « not read ». It becomes « Synopsis non lu. », and R119 (e) keeps its whole promise. And R119 (b-i)'s
exact count moves from 15 to 13: the thinnest entry carries the identity, whose two lines are then content.

**Amendment, 2026-09-13 — ruling 61 (the auditor's, under the operator's delegation): the follow panel's facts follow
the identity read.** At `f1e7ac66` a follow panel opened cold for a medium with no follow entry showed « Voir la
fiche » at once, because `hasSheet` read the engine's sheet table synchronously. a·14.2 answered it from the identity
instead (`follow.ids`, else what a landed list read carries), computed ONCE at production; opened cold, the panel is
produced when the follows land, before the list carrying the identity does, and the row stayed without « Voir la
fiche » until reopened — the full suite's `bugs.py` step 2 fell on it. The repair is a restoration, not a re-aim:
`frontend/maquette/design/src/features/acquisition/panel-follow.ts` waits, when the facts carry no identity, for a read
that does, and re-produces the panel IN PLACE through the panel's redraw (no history entry). A synchronous source for
the sheet is refused (reading 3): it is what a·14.2 removed. **The named difference, D8-accepted: on a COLD open (a
typed `?panel=follow:<title>`, or a named state) for a title without a follow entry, « Voir la fiche » is absent for as
long as the identity read takes to land (≤ 400 ms), then appears with the row refreshed in place.** The two
`["/api/media","",""]` / `["/api/media","","","seasons"]` cache entries read beside it were diagnosed in the same unit:
introduced at a·14.2 by `panel-seasons.tsx`'s first render before the identity is known, already gated by the
queries' `enabled` — `pending` with `fetchStatus` `idle`, no update, no observer, and no request to `/api/media` with
an empty segment leaves (a `fetch` spy saw only `/api/media/tvdb/72668` and its seasons). Nothing fires, so nothing is
repaired there.
