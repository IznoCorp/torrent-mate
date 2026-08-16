# Bug register

Every defect the operator reports lands here **the moment it is reported**, before any work
starts. A bug leaves this file only through the `Fixed` column, and only with a rule that fails
when the defect comes back.

## Rules of this file

1. **Reported = written down.** No triage, no judgement first. An unwritten bug is a bug that
   comes back a third time.
2. **One bug is closed at a time**, and the operator confirms the fix before the next one starts.
3. **A fix is not a fix without a rule that bites.** The rule is mutation-tested: break the
   behaviour on purpose, confirm the rule falls and names the right defect, restore. A closing
   entry names the script and the mutation.
4. **The rule must cover the path the operator actually walks.** Several bugs below survived a
   green harness because the rule drove a named state instead of the real journey — a cold load,
   a real finger, a real browser menu.
5. **Repeats are counted.** `Reported` records every time the operator has had to say it again.
   A count above one is a failure of this register, not of memory.

## Status vocabulary

| Status       | Means                                                          |
| ------------ | -------------------------------------------------------------- |
| `open`       | Reproduced and diagnosed, not yet fixed.                       |
| `fixing`     | Being worked on right now. Exactly one bug may hold this.      |
| `to confirm` | Fixed, rule green, mutation proven — waiting for the operator. |
| `closed`     | Operator confirmed on a real device.                           |

---

## Open

| ID    | Defect                                                  | Reported    | Status       |
| ----- | ------------------------------------------------------- | ----------- | ------------ |
| B-019 | Many media sheets have lost their visual                | 1×          | `closed`     |
| B-020 | Actor portraits on media sheets are broken              | 1×          | `closed`     |
| B-021 | Signing out leaves the bottom panel on top              | 1×          | `to confirm` |
| B-022 | « Voir mes suivis » in the add search is inert          | 1×          | `to confirm` |
| B-023 | Médiathèque « Incomplets »: every visual broken         | 1×          | `closed`     |
| B-013 | The drawer's entries lead nowhere                       | 2×          | `to confirm` |
| B-014 | The drawer's current entry is unreadable                | 1×          | `to confirm` |
| B-015 | Back reopens the drawer that was just closed            | 1×          | `to confirm` |
| B-016 | Swiping a row right, then left, makes it jump           | 1×          | `to confirm` |
| B-017 | Closing a panel sends the list back to its top          | by mutation | `to confirm` |
| B-018 | On a desktop, dragging a row opens the panel            | 1×          | `to confirm` |
| B-024 | `data-go` settles ONE history entry, layers pile        | by review   | `open`       |
| B-025 | The screen half of the `data-go` fix has no Back rule   | by review   | `open`       |
| B-026 | A silent `catch {}` can let URL and UI disagree         | by review   | `open`       |
| B-027 | `resynchro.py` trusts `t:` first-match + naive braces   | by review   | `open`       |
| B-028 | `resynchro.py` says « 0 correction » for unknown titles | by review   | `open`       |
| B-029 | Counter rule misses suffix drift (« 1 » in « 11 »)      | by review   | `open`       |

**B-018 was written down as a regression from B-016, and that was wrong.** It has two ways in, one
of which is older than this work — the correction is recorded here rather than quietly amended,
because a register that only ever gets more accurate teaches nothing about how it goes wrong.

B-013 to B-015 arrived as **one** report about the navigation drawer. They are written as three
because a fix closes only with a rule that bites, and three symptoms with three causes need three
rules — merging them would let two hide behind the one that got fixed.

B-017 was reported by nobody. The mutation proving R65 bites found it, which is the whole reason
mutations are run against a rule rather than trusted to be green.

**B-024 to B-029 arrived from an adversarial code review of commit `3e66fa66` (#434), not from
the operator** — same standing as B-017: found by tooling, written down before anyone walks into
them. None is reproduced on a device yet; each entry below records the walk that would.

- **B-024** — `data-go` (refonte.html ~17901) closes up to three layers but settles exactly ONE
  history entry (`__pont.remplacer` overwrites only the top). With two layer entries buried
  (screen over screen — the case the block's own comment claims to handle — or sheet over
  screen), one Back after the navigation lands on a stale `{layer}` entry and answers a
  legitimate Back with the « Encore un retour pour quitter » toast; a second Back exits the app.
  **Latent, non atteignable** — re-measured post-SP4a, walked control by control: the DOM carries
  exactly five `[data-go]` producers, no more. Four (12174, 12677, 12827, 12918) render only into
  page-body `#view` content (`viewAcquisition`, `viewArrivals`, `viewIntrouvable`, `viewSystem`);
  `#view` sits under every layer (`.screen` z-45, `.sheet` z-47 over `.topbar` z-40), so each is
  covered — and therefore untappable — the instant any layer is open, meaning zero layers, let
  alone two, ever precede their tap. The fifth is the user sheet's « Profil et préférences »
  (`cible:{go:"profil"}`, the only dynamic producer in the whole file — confirmed by grep) — its
  only trigger is the header avatar (`data-sheet="utilisateur"`), itself in `.topbar` and so
  covered the same way whenever a screen is already open (measured: `elementFromPoint` at the
  avatar's coordinates resolves to `.fichebar` inside `#screen`, not the avatar, and a click there
  opens nothing). One layer (the sheet itself) is therefore the most that can ever precede this
  control's tap; a fresh-boot walk confirms `history.length` is unchanged before and after tapping
  it, matching the single-entry case the fix already covers. No live call path stacks a second
  screen either: `openScreen`'s `dejaOuvert` branch (pushed layer on top of an already-open screen)
  exists in code, and `data-fiche` (18336-18349) is its one UNGUARDED trigger — when no sheet is
  open (`couche` false) it calls `openFiche(fiche)` directly, with no `closeScreen()` first, so a
  `[data-fiche]` element tapped from inside an already-open screen WOULD stack a second one. But
  no `[data-fiche]` element is ever rendered inside a screen today: its three producers —
  `cardHTML`'s poster (11578), `tileHTML`'s tile (15395), the Découvrir deck's poster (15855) —
  are called only from page-list/grid/deck builders (11555-15987), never from `openFiche`,
  `openResolve`, or `openReleases` (39527-40337, the only functions that build screen content);
  `openResolve`'s own cards (`releaseCardHTML`, 11613-11637) are marked `data-nonmedia` and carry
  `data-resolve`, not `data-fiche`, by design ("no medium here yet"). The sheet-to-screen half of
  `data-fiche` is guarded (`couche` true closes the sheet first, 18342-18344), and `data-refiche`
  reopens the SAME key (`memeEcran`, no new layer). The comment still overclaims — it is true of
  the DOM, not of history — but no reachable walk buries two entries under a `[data-go]` tap
  today. Fix shape unchanged: one loop, one entry per closed layer.
- **B-025** — harness `bugs.py` check 10b stops at the landing (`« Voir mes suivis » atterrit`)
  and never presses Back; only the sheet half (9b) is guarded. The `remplacer`-on-screen half of
  the fix — exactly what B-024 concerns — can regress without a single check falling.
- **B-026** — the `data-go` handler's outer `try { … } catch (error) {}` (house pattern from
  `data-navgo`) silences a `remplacer` failure: the page renders the destination while URL and
  history still describe the layer — a silent violation of the DOIT-10 claim that « the URL and
  the interface never disagree », with nothing logged.
- **B-027** — `resynchro.py` extracts a follow's title with the FIRST `t: "…"` match anywhere in
  the object and counts braces with no string-awareness. An object whose first `X: "…"` key is
  not the title, or a title containing `{`/`}`, silently skips or — worse — rewrites the WRONG
  follow's counter. Holds today only by convention (all 12 objects start with `t:`), asserted
  nowhere.
- **B-028** — `resynchro.py` cannot say a title went unmatched: a FOLLOWS title absent from the
  DB reads exactly like « already in sync », prints `0 correction(s)` and exits 0. Especially
  live once vo-title (#435) changes which spelling a follow carries — the operator running the
  documented remedy gets silence instead of « 4 of 12 titles never looked up ».
- **B-029** — `contenu.py`'s counter rule tests `f"{n} recherche" in faits`: « 1 recherche » is a
  substring of « 11 recherches », so whenever the real count is a suffix of the embedded one the
  drift the rule exists to name is never named.

---

## B-019 / B-020 / B-023 — The visuals family

**Reported** 1× each, in one report (2026-08-15), after the SP3 merge. **Status** `open` —
written the moment they were reported; diagnosis follows in this order, one at a time.

Three symptoms, three entries — the B-013/014/015 precedent: merging them would let two hide
behind the one that gets fixed. They plausibly share a cause (the SP1 hash-named files under
`assets/`, the SP2 `dist/assets` symlink, or the host's asset routing since the bascule), and
that is a hypothesis to MEASURE, not a diagnosis.

- **B-019 — Many media sheets have lost their visual.** The sheet opens without its artwork
  where it used to carry one.
- **B-020 — Actor portraits on media sheets are broken.** Cast entries show broken images.
- **B-023 — Médiathèque « Incomplets »: every visual broken.** The lens renders with all its
  posters dead.

**The operator's standing instruction with this family**: a FULL tour of the visuals — every
image the interface can draw, across the named states, checked as RENDERED (the request
resolves and the browser decodes pixels), not as referenced. R70 holds that every `assets/`
reference in the SOURCE resolves to a file, and it is green — so if these reports reproduce,
the defect lives past R70's reach (the build, the serving path, or references R70 does not
read), and the closing rule must measure what the operator's eye measures: the drawn image.

**Investigated 2026-08-15 — does not reproduce on any path reachable from here.** All
executed, none assumed:

- 924/924 unique `assets/` references resolve to files on disk; zero runtime-built references.
- The full tour, 81 states, images forced eager, oracle « complete && naturalWidth === 0 »
  plus every HTTP response ≥ 400: **zero broken images** on the static harness path AND
  through a scratch `serve.py` with a real session (only the known `/favicon.svg` 404).
- The artwork maps (`POSTERS` 400, `HEROS` 319, `ACTEURS` 170, `trailerIds` 288) are
  key-identical to the pre-SP1 version (`c49e7ada`); the resolution rate over the embedded
  library is byte-for-byte the same before/after: 326/345 titles.
- The live pm2 process runs this checkout's `serve.py`; Caddy is a bare reverse-proxy; the
  service worker intercepts navigations only, network-first — no cache to serve a stale copy.

What remained unruled was the operator's own device — and the operator ruled it.

**CLOSED — operator confirmed on a real device** (the fiches, the cast carousel and the
« Incomplets » lens all draw their visuals). No artifact was ever broken: every measurable
path was clean throughout, and no fix was applied. The retained cause is a TRANSIENT
serving state — this host serves the working tree LIVE, and the report was made while a
conversion wave was actively editing it. There is deliberately no closing rule beyond R70
and the tour: a rule cannot hold a state that no longer exists and never lived in the
sources. What the episode leaves behind is the tour itself (every drawn image, as RENDERED)
as a reusable probe, and the reminder that the live host shows mid-work states — a report
made during a wave is dated evidence, to be re-checked against a settled build.

---

## B-021 — Signing out leaves the bottom panel on top

**Reported** 1× (2026-08-15). **Status** `to confirm` — `harness/bugs.py` checks 9/9b.

**What the operator sees.** From the user panel, reach the profile, sign out: the panel never
seems to leave the foreground.

**What actually happens**, measured on the journey: tapping « Profil et préférences » in the
user sheet changed the page to `?page=profil` UNDER the sheet and left the sheet on top
(`elementFromPoint` said `sheet`). Everything tapped from there happens under a stuck panel.
The sign-out itself, measured alone, closes the sheet and lands on the entry screen — the
stuck panel comes from the step BEFORE it.

**Why.** The `data-go` handler predates the layer rules: it navigated (`state.page`, `render`,
`noterLeChemin`) without closing the layer it may sit in, and pushed its nav entry ON TOP of
the layer's buried history entry. The drawer already had the settled pattern for exactly this
(`data-navgo`): close every layer WITHOUT touching history, and the destination TAKES the
layer's entry through `remplacer` — an unwind-then-push would race, the asynchronous pop
landing after the push.

**The fix.** The `data-go` handler now follows the drawer's pattern: `fermerTiroir(true)`,
`closeSheet(true)`, screen stack emptied then `closeScreen(true)`, render, then `remplacer`
when a layer entry was on top, `noterLeChemin` otherwise.

**Why no rule caught it.** `bugs.py` check 3 proves the BOTTOM BAR closes layers on
navigation (`data-page` calls `hideLayers()`), and every driven state reaches pages directly —
nothing walked a `data-go` control INSIDE a layer.

**Mutation.** Removing `closeSheet(true)` from the block → checks 9 and 9b fall naming the
stuck sheet. Pushing instead of replacing → check 9b alone falls (back no longer reaches the
page one stood on before the sheet). Both executed, both restored.

**Observation recorded, not fixed here**: `data-page` (bottom bar) hides layers but does not
settle their buried history entries either — masked because the DOM closes. Unreported, left
open deliberately; SP4's ownership law re-founds this bookkeeping.

---

## B-022 — « Voir mes suivis » in the add search is inert

**Reported** 1× (2026-08-15). **Status** `to confirm` — `harness/bugs.py` checks 10/10b.

**What the operator sees.** On the add-media screen, after adding a media, the « Voir mes
suivis → » footer link answers a tap with nothing.

**What actually happens.** Same defect as B-021, other layer: the footer's `data-go="acq"`
changed the page to Acquisition UNDER the still-open add screen. The page did move — behind
a screen that never left, which reads as « nothing happened ».

**The fix.** The shared `data-go` fix above. The journey test walks the real path: results →
card body → panel → « Ajouter » (confirming the replace dialog when the result is owned) →
footer appears → tap → the screen leaves and Acquisition renders.

**Mutation.** Covered by the B-021 mutations — the same handler, measured on this journey by
checks 10/10b.

---

## Requested evolutions (not defects — recorded here so they are not lost)

- **E-001 — Médiathèque sort inversion** (2026-08-15): every sort type must be reversible —
  A→Z and Z→A each way. An evolution, so it is maquette-first: drawn and measured in the
  prototype before any conversion work touches it. **Arbitrated by the operator
  (2026-08-15): folded into the Médiathèque wave of SP4**, where that page is drawn into
  its final component.

---

## B-013 — The drawer's entries lead nowhere

**Reported** 2× — the second time this surface has been reported inert. **Status** `to confirm` — R65, `harness/tiroir.py`.

**What the operator sees.** The navigation drawer opens, and its entries are not clickable: a tap
on a menu entry goes nowhere.

**What actually happens**, measured on the journey rather than read: tapping « Médiathèque » left
the bar's current tab on « Acquisition » at +60 ms and again at +560 ms. The entry was never
inert — the page changed and was put back.

**Why.** The close unwound the drawer's own history entry with `history.back()`, which is
**asynchronous**. Its pop therefore landed AFTER the arrival had rendered, and the popstate
handler read that pop as a back gesture: it applied the entry underneath, which describes where
one already was. One frame of Médiathèque, then Acquisition again.

A second cause, on one entry only: « Config » pointed at an id `PAGES_OF` does not carry, and
answered a tap with a message saying the page was out of scope. Réglages exists and is drawn; the
entry now names it.

**Why no rule caught it.** R59 covers the back gesture and was green throughout. It drives named
states; nothing walked the journey of opening the drawer and tapping an entry.

**And it is the SECOND time this surface has been reported inert.** `regions.json` →
`$reportedDefects` already carries `inert-drawer`: « the hamburger opened nothing and the drawer
links were not clickable: event delegation looked only at `<button>`, and a navigation link is an
`<a>` ». That cause was fixed and a comment left beside it. A different cause produced the same
symptom, and nothing had been left behind that would notice — the fix was recorded, the BEHAVIOUR
was not. That is precisely the difference between a note and a rule.

**The fix.** The destination TAKES the drawer's history entry (`replaceState`) instead of the
close unwinding and the arrival pushing in the same task. And our own unwind now announces itself,
so the popstate handler consumes it rather than interpreting it.

**Mutation.** Point an entry at an id no page carries → « chaque entrée nomme une page qui
existe » falls, naming `config`.

---

## B-014 — The drawer's current entry is unreadable

**Reported** 1×. **Status** `to confirm` — R65, `harness/tiroir.py`.

**What the operator sees.** The entry marking where one currently is cannot be read.

**What actually happens.** Its label and its background are the **same colour** —
`oklch(0.808 0.158 79)` on `oklch(0.808 0.158 79)`. Contrast **1.00**. A label written in
invisible ink.

**Why.** `background: var(--sidebar-accent, var(--primary))`, and `--sidebar-accent` is defined
nowhere — so the background falls back to `--primary`, which is what the label is coloured with.

**Why no rule caught it.** This is the family of B-007, and R61 exists for it — but R61 forbids
only **bare** `var()`. A fallback makes a phantom token look like a considered choice, and the
rule looks away. Two other `--sidebar-*` references had the same shape with harmless fallbacks;
they are gone too, because a landmine that has not gone off is still a landmine.

**The fix.** « You are here » is the brand colour on the label — the mark the bottom bar already
uses — over a **tint** of that mark rather than the mark itself. Measured: contrast **7.66**,
above AA and above AAA.

**Mutation.** Restore the fallback → the contrast check falls at 1.0, naming the current entry.

---

## B-015 — Back reopens the drawer that was just closed

**Reported** 1×. **Status** `to confirm` — R65, `harness/tiroir.py`.

**What the operator sees.** Close the drawer, then use the back gesture: the drawer comes back.
« Ce n'est pas une route. »

**What could not be reproduced.** The drawer never reopened under measurement — five ways of
closing it, on Chromium **and** WebKit, `go_back()` after each. That is recorded rather than
hidden: what follows fixes the bookkeeping the report points at, and only the operator's phone
can say whether it was the whole of it.

**What was found instead**, on every one of those paths: after using the drawer, ONE back landed
on the root-exit warning. The drawer had eaten the operator's navigation history — its entry sat
between the page and everywhere they had been.

**The fix.** The drawer leaves nothing behind: the destination replaces its entry, so a back from
there reaches where one was before opening it. Closing it without going anywhere restores the
history exactly as it was.

**Mutation.** Make the destination push instead of replace → « retour ramène au départ » falls on
all four entries.

---

## B-016 — Swiping a row right, then left, makes it jump

**Reported** 1×. **Status** `to confirm` — R64 extended, `harness/glisse.py`.

**What the operator sees.** Swipe a card right, then swipe it left: the card jumps. What it should
do is settle back to rest, so that a second, deliberate left swipe is what reveals the actions on
that side.

**Measured.** The row rests at **+84**; the finger's first 15-pixel step puts it at **−168**. A
leap of **252 pixels** — the width of both drawers — before the finger has travelled a centimetre.

**Why.** A drag beginning on an open row has to resume from where the row IS. The origin was
deduced from a side instead of read from the row — `-largeurTiroir(sw, -1)`, the right drawer's
width, whichever side the row was actually open on. A row open on the LEFT therefore started its
travel from the far side.

**Why no rule caught it.** R64 covers one swipe in one direction, and both of its ends were
correct. A jump is a **discontinuity**: a probe that reads only the resting positions certifies
it. The rule now samples during the gesture.

**The fix.** The resting offset is recorded when it is set, and the drag resumes from it. And an
open row can only be CLOSED by a drag — its travel is clamped between where it rests and zero —
so a swipe the other way settles it back instead of crossing rest and opening the opposite drawer
in one gesture. That is the operator's own prescription: « elle devrait se replacer normalement et
je reswipe à gauche si je veux voir les actions à gauche ».

A third instance of the same class was found while fixing it: the quick-action buttons cleared the
row's transform by hand without clearing what was RECORDED about it, so the next drag resumed from
a drawer that was no longer open. They close through the shared close now.

**Mutation.** Restore the deduced origin → « une ligne ouverte suit le doigt sans sauter » falls at 252. Remove the clamp → « le glissé inverse la ramène au repos » falls.

---

## B-018 — On a desktop, dragging a row opens the bottom panel

**Reported** 1×. **Status** `to confirm` — R64 strengthened, `harness/souris.py`.

**What the operator sees.** On a DESKTOP, dragging a row left or right opens the bottom panel
instead of revealing the row's actions. The drag is read as a tap.

**Measured.** On a library row dragged to the right, a click reaches the document with
`defaultPrevented: false` — **the click is not swallowed**. On the same row dragged left, and on a
follows row either way, it is.

**Why.** The guard that stops a drag from also firing the tap was armed on how far the ROW moved:
`|dx - depart| > 4`. A row is free to refuse to move — a library row has no drawer on its left, so
a right drag ends exactly where it started — and then nothing is armed, the click goes through, and
the panel opens over the row.

**Two ways in, and only one is mine.** The right drag on a row with no left drawer has behaved this
way from the beginning. The fix for B-016 added the second: since an open row can now only be
CLOSED by a drag, dragging one further in the same direction also ends where it started. Calling
the whole thing a regression, as this entry first did, was wrong.

**Why no rule caught it — and this is the part worth keeping.** Two reasons, and they compound.

1. **After a touch drag, the browser suppresses the click by itself.** Every finger measurement was
   therefore green over the hole. Only a mouse can see it, and R64 already knew that — its own text
   says a touch probe cannot tell a swallowed click from one that never happened.
2. **`souris.py` asserted the weaker thing.** It checked that no panel appeared. A panel can fail to
   appear because the release landed a few pixels off the card, which is exactly what happened in
   the first four attempts to reproduce this: the click went through, unswallowed, and hit a `div`.
   The rule now asserts the click was **actively swallowed**, which is the property that was
   promised.

**The fix.** The guard is armed on what the FINGER travelled, never on what the row moved. The
distinction between a drag and a tap belongs to the pointer.

**Mutation.** Restore the row-displacement test → « une ligne de médiathèque, glissé droite : le
clic n'est pas avalé » falls. Disarm the guard entirely → all four fall.

---

## B-017 — Closing a panel sends the list back to its top

**Reported** by nobody. **Status** `to confirm` — R65, `harness/tiroir.py`.

**What happens.** Open a bottom panel from a card halfway down a list, close it: the page
underneath is rebuilt and the list is scrolled home. Measured — a marker planted in the view was
gone, and the scroll offset went 22 → 0.

**Why.** The same root cause as B-013, seen from the other side. Closing any layer popped its own
history entry; the handler read that pop as a back gesture and re-applied the state underneath,
which re-renders the page one is standing on.

**How it was found.** By the mutation proving R65 bites. The first pass of that mutation did NOT
fell the rule, which said the guard it targeted was load-bearing for nothing — so under « what no
mutation can fell is removed », it was about to be deleted. Measuring whether it was load-bearing
for the OTHER layers is what turned a deletion into a defect.

**Mutation.** Remove the unwind guard → four checks fall, naming both the rebuilt page and the
lost scroll offset, on the panel and on the drawer.

## B-001 — The list poster is still too small

**Reported** 2×. **Status** `closed` — confirmed 2026-08-14. Closed together with B-008, which replaced the question:
the poster is no longer a fraction of anything, it is bled to the card's edges. 63px wide, +50% on
the original 42.

**What happens.** Measured on the four pages at 390 px: every list poster is **49 × 74 px**. It
was 42 px, so it did change — by 17 %, which reads as "unchanged" on a phone where 49 px is 12.5 %
of the width.

**Why it is still wrong.** The size came from a derivation pinned to the median card's TEXT
height, so the poster can never grow past the text beside it. The operator had explicitly lifted
that constraint — « quitte à faire des cards plus hautes » — and the derivation kept it anyway.
The number is the honest output of the wrong question.

**Why no rule caught it.** R47 checks the poster matches the derivation. Whatever number the
derivation yields, the rule agrees with it. **A rule that checks arithmetic against itself cannot
report that the arithmetic answers the wrong question.**

**What closing it requires.** Re-derive with the card height free, then a rule that pins the
poster to a share of the CARD, not of the text column, so shrinking it back is a failure.

---

## B-002 — The startup bar is never seen on a real load

**Reported** 2×. **Status** `closed` — confirmed 2026-08-14.

**Fixed.** The screen now comes off when the wait it covers RESOLVES, through a named seam
(`window.__chargementTermine()`) called by a timer the length of the bar here and by whatever
knows the interface is ready in the app. The early exit is not a second path: resolving sooner
ends it sooner. Measured on a cold load: visible at 0 ms, still up at 5.1 s, the bar monotonic
from 0 to 99 %, gone at 5.4 s; and resolving at 800 ms ends it at once. Rule R53 extended,
`harness/demarrage.py` — 27 checks, three mutations proven: the screen dropped on the first
render (the original defect), the bar filling in one second, the seam made inert.

**A rule was asserting the defect.** « retiré par le premier rendu, sans le harnais » certified
that the screen vanished immediately, and the suite called that conformity. What a rule asserts is
a decision — writing down the behaviour that exists is not the same as writing down the one that
is wanted. Twenty-eight harness scripts now close the startup wait through the same seam rather
than racing it.

**What happens.** Measured on a cold load: at the first frame the splash is visible with the bar
at 0.4 px; by 300 ms it is **hidden** and the bar reset to 0 %. The five-second fill exists and
plays for about one frame.

**Why.** `masquerDemarrage()` is called **synchronously** on the line after the first `render()`.
In the prototype nothing is fetched, so the first render returns immediately and the screen it
was covering is already there.

**Why no rule caught it.** R53 measures the splash through `__go('demarrage')` and through the
login submit, which holds it on a 1100 ms timer. Both put the screen up artificially. **No rule
ever loaded the document and watched.**

**What closing it requires.** A floor on how long the screen stays — the bar reaching 100 % in
five seconds, leaving earlier only when loading finishes — and a rule that measures a COLD LOAD,
sampling the bar's width over time.

---

## B-003 — In Arrivées a poster does not lead where a poster leads

**Reported** 2×. **Status** `closed` — confirmed 2026-08-14.

**Fixed.** A folder is not a medium, so it no longer wears a poster: it wears a FOLDER, in a
poster's footprint so the row still lines up, saying « DOSSIER » rather than miming an artwork
nobody has. Its card is marked `data-nonmedia="dossier"`, the way a release candidate's already
was, and it addresses its own panel — never a `media:` one, which would promise a subject that
does not exist. Rule R46 extended, `harness/cartes.py` — 137 checks over every named state, three
mutations proven: the folder back as a poster (the original defect), the folder addressing no
panel, the folder addressing a media panel.

**The two kinds of non-medium had been merged**, and that merge is what made the defect hard to
see: R46 said a non-medium promises neither sheet nor panel, which is right for a release
candidate and wrong for a stuck folder — a folder has its own actions. Splitting them is what let
the rule state the real invariant.

**What happens.** Arrivées cards do come from `cardHTML`, the same builder as everywhere else. But
their poster is `poster sansfiche`, carrying `data-panel`: it opens the **bottom panel**. Every
other poster in the interface opens the **media sheet**. Same object, same look, two destinations.

**Why.** A stuck folder has no medium yet, so it has no sheet to open. Rather than saying so, the
poster was pointed at the panel — which gave it a destination and broke the one invariant the
whole card system rests on: « the poster opens the media sheet ».

**Why no rule caught it.** `cartes.py` checks each card against its own shape. Nothing checks that
one visual element keeps ONE behaviour across pages. **The invariant was written in prose and
never made executable.**

**What closing it requires.** Decide what a poster with no medium does — most likely not be a
poster at all — and a rule that walks every page and fails when the same element leads two ways.

---

## B-004 — Dragging the sheet handle down no longer closes the panel

**Reported** 2×. **Status** `closed` — confirmed 2026-08-14.

**Fixed.** The handle claims its axis with `touch-action: none` and captures the pointer, and its
target is a 22px strip rather than the 4px bar it draws — a thumb aims at the bar and lands in the
strip, and the events used to stop the moment the finger left it. A cancel springs the sheet back
instead of closing it. Rule R55 extended, `harness/doigt.py` — 25 checks, four mutations proven:
the axis unclaimed (the original defect, under a real finger), the closing threshold dropped to
10px, the pointer capture removed (which only a MOUSE drag can catch — touch gets an implicit
capture), and a cancel treated as a lift.

**Two mutations passed at first and each named a hole in the rule.** Removing the capture changed
nothing under touch, so the rule had to grow a mouse drag. Treating a cancel as a lift changed
nothing because nothing cancelled any more, so the rule had to drive a real cancelled touch —
a hand-built PointerEvent carries an id no pointer owns, and the capture throws on it.

**What happens.** Reproduced under a real finger driven through CDP: a 150 px downward drag from
the handle delivers `pointerdown` ×1, `pointermove` **×2**, then `pointercancel`, and `pointerup`
**never**. The touch stream survives it — `touchmove` ×14, `touchend` ×1. `closeSheet()` hangs off
`pointerup`, so the sheet stays open.

**Why.** The handler reads the pointer stream, takes no `setPointerCapture`, and the handle
declares no `touch-action`. The compositor claims the vertical axis and cancels the pointer
stream — the exact mechanism that had already cost the pull-to-refresh and the view swipe.

**Why no rule caught it.** R55 was written for that mechanism and covers the pull-to-refresh and
the page swipe. **The sheet handle is a third gesture and no rule looked at it.** The lesson was
recorded, then not applied where it applied next.

**What closing it requires.** Read the finger from the touch stream, or capture the pointer and
claim the axis; then extend R55 to every draggable surface, sheet handle included.

---

## B-005 — A long press on a poster raises the browser's own menu

**Reported** 2×. **Status** `closed` — confirmed 2026-08-14.

**Fixed.** `contextmenu` is now refused across the whole frame, except inside a text field where
pasting has no other route. Measuring it turned up a second defect the report had named without
either of us knowing why: the press listeners lived on the SCROLLPORT, and every layer above it —
sheet, screen, drawer, dialog — sits outside, so four states drew a poster no press could reach.
Both listeners moved to the frame. Rule R55 extended, `harness/doigt.py` — 18 checks, four
mutations proven: the refusal removed, the refusal reaching into text fields, the refusal back on
the scrollport, and the press listeners back on the scrollport.

**Two rules were thrown away before one worked**, and both failures are the same failure: asserting
the panel is open AFTER the lift proves nothing, because on those surfaces a tap opens it too. The
oracle for a press is that the panel is open while the finger is STILL DOWN. A first attempt also
read the target's position before closing the sheet, and closing re-lays the screen out, so the
press landed on whatever had moved underneath.

**What happens.** On a phone, a long press on a poster raises the browser's copy / open-image
menu instead of, or on top of, the bottom panel.

**Why.** `grep contextmenu` over the whole prototype returns **nothing**. `user-select: none` is
set and stops text selection; `-webkit-touch-callout: none` is set and only ever answers iOS
Safari. Android Chrome raises its menu from the `contextmenu` event, which nothing prevents.

**Why no rule caught it.** The long-press rule asserts the PANEL OPENS. It never asserts the
browser's own menu is refused — and a synthetic touch never raises a native menu, so **no script
written that way could have seen it.** The observable fact to assert is that `contextmenu` is
prevented, not that a native menu is absent.

**What closing it requires.** Refuse `contextmenu` on everything that answers a long press, and a
rule that dispatches `contextmenu` and fails when `defaultPrevented` is false.

---

## B-006 — Two different sign-in screens: arrival and sign-out

**Reported** 1×. **Status** `closed` — confirmed 2026-08-14.

**Fixed.** Measured, the two renderings differed in more than the palette: the host restated the
typography too, so the wordmark had `line-height: normal` there against 1.35 here, and the whole
screen rendered at 16 px instead of 14. The reset is now extracted through `login:socle` markers
like the palette, and the host contributes only `.loginscreen { position: static }` and the
startup screen's positioning — what a page needs that a layer does not. Rule R62,
`harness/entree.py` — 10 checks comparing RENDERINGS, two mutations proven: the host taking back
a palette of its own (the original fault), and the host dropping the typographic extract. A third
mutation did not bite and earned its keep: removing the type scale I had first pinned on
`.loginscreen` changed nothing once the reset was extracted, so that declaration was removed
rather than left as something no rule defends.

**What happens.** Arriving at the design host serves `serve.py`'s gate page. Signing out inside
the prototype shows `#login`. They are two documents and they do not look the same.

**Why.** `page_connexion()` extracts the prototype's login markup and styles — correctly — and
then adds a hand-written `socle` block defining a palette of its own. The prototype's screen never
gets that block.

**Why no rule caught it.** `deconnexion.py` checks that signing out LANDS on the entry screen.
Nothing compares the two renderings of the same screen. **A surface that exists in two places was
verified in one.**

**What closing it requires.** One screen, extracted once, with the host adding only what a page
needs that a phone frame does not; and a rule comparing the two renderings.

---

## B-007 — `--accent` is referenced 11 times and defined nowhere

**Reported** 1× (as "the sign-out screen has no TorrentMate style"). **Status** `closed` — confirmed 2026-08-14.

**Fixed.** The eleven references now name `--primary` / `--primary-foreground`. The host stopped
retyping the palette and EXTRACTS it, through new `login:palette` markers around `:root`. Rule
R61, `harness/palette.py` — 8 checks, three mutations proven: one reference back on the old name
(the static check names it), the wordmark recoloured while staying defined (the painted check
names it), the install button losing its background (the sweep over every state names it).

**What happens.** On the prototype's sign-in screen the funnel is **white** instead of orange,
« Mate » is white, and « Se connecter » has **no background**. Measured: `var(--accent)` appears
**11 times** in `refonte.html` and `--accent:` is defined **0 times**. Every reference is invalid
at computed-value time, so the colour silently falls back and the background disappears.

**Why it was invisible.** `serve.py` retypes `--accent: #f5a524` into its `socle`, so the host page
— the only place the screen had been looked at — renders correctly. The prototype's own screen
was never looked at after the palette was renamed to `--primary`.

**This is the project's own rule broken.** « CSS is extracted, never retyped »: a retyped value
made the host look right and hid a defect in the reference.

**Why no rule caught it.** `export.py` checks class coverage. **Nothing checks that every custom
property referenced is defined**, so a whole palette can be dangling and every screen still
renders "something".

**What closing it requires.** Define the accent once, or point the eleven references at
`--primary`; then a rule collecting every `var(--…)` in the file and failing on any name never
defined. Seven other references live outside the login screen and must be checked with it.

---

## B-008 — The card poster should bleed to the card's edges

**Reported** 1×. **Status** `closed` — confirmed 2026-08-14.

**Fixed, with one limit measured rather than argued.** The card carries no padding of its own any
more; it moved onto the column holding the text, and the poster reaches the card's top and left
edge. The poster's own height is the card's FLOOR, so a card at that floor is bled on three edges;
a taller card is bled on two.

**Full height AND the 2:3 ratio cannot both hold.** That was asked for and attempted: a full-height
2:3 poster means deriving the width from a height the text decides, and a grid sizes an `auto`
column BEFORE the row's final height is known. Measured, on a 219px card the poster computed 146px
against a column of 89 and ran over the text — on seventeen states. A `max-width` cap did not save
it; the overlap merely shrank to one pixel. The ratio was kept, because a stretched poster stops
being a poster; the bottom bleed is what gave way, and only on cards the text makes taller.

One trap paid on the way: the artwork must contribute no intrinsic size of its own, or its pixels
set the column — in flow, a 240px-wide picture made a 240px poster and dragged the card with it.

Rule R47 rewritten, `harness/cartes.py` — 142 checks over every named state, three mutations
proven: the padding restored around the poster, the ratio broken, the width shrunk back to 42.

**Asked for.** The poster grows by DROPPING the padding around it: it touches the card's top, left
and bottom edges. The rest of the card's content keeps its margins.

**Why this is the right shape and not just a bigger number.** B-001 sized the poster against the
text column and then against a card-anatomy notch, and both are the same kind of answer — a
fraction of something else. Bleeding it to three edges makes the CARD the measure: the poster is
as tall as the card, whatever the card's content makes the card. There is nothing left to derive.

**What closing it requires.** The poster spans the card's own height with no padding on three
sides, its corner radius follows the card's on the two corners it now owns, and the text column
keeps its padding. A rule that measures the poster's box against the CARD's box — top, left and
bottom flush — so restoring a margin fails.

---

## B-009 / B-010 / B-011 — The row's drawer

**Reported** 1× each. **Status** `closed` — confirmed 2026-08-14.

**B-009 — both directions, scoped with the tap.** The right drawer holds what one does to a
medium; the left holds the one thing the row is for — a follow with nothing to look for has no
left drawer, and the row does not travel that way rather than opening an empty one. The click
after a drag is swallowed, identified by its POINT.

**B-010 — one row at a time.** Starting a drag anywhere puts the previously opened row back.

**B-011 — the iOS rendering.** Reproduced on WebKit and measured: the drawer was pushed right by
an automatic margin, and WebKit sizes it without honouring its children's `flex-basis` — 148px for
two 84px buttons — so they spilled twenty pixels past the rounded card. An explicit `width` leaves
nothing to infer. Both engines now measure 168px, zero overflow.

Rule R64, `harness/glisse.py` — 18 checks on BOTH engines, four mutations proven: the automatic
margin restored (the iOS defect), one direction only, two rows open at once, the tap not scoped.

**Two things the suite caught that I had just broken.** Clearing the swallow mark after the guard
that ignores presses outside a row meant a press anywhere else never cleared it — a swipe made the
interface miss the next tap on the navigation bar. And a bare flag stays armed until some click
happens, which ate a button in a dialog; it is now identified by its point, the same answer the
long press had already needed.

**One line was removed rather than kept.** The exemption for the drawer's own buttons cannot be
reached: the row follows the finger one for one, so a release is always over the row and never
over what it uncovered.

**Asked for.** A media card answers a horizontal swipe, left and right, revealing its quick
actions. The tap that opens the bottom panel keeps working; the two gestures are scoped so neither
steals the other.

**What is already there.** Follow rows answer a swipe today (`souris.py` measures
`matrix(1,0,0,1,-168,0)`), and the deck answers one. What is asked is the same gesture on the
media card, alongside the tap that opens the panel — which is exactly where a scope conflict
lives: a horizontal drag must not fire the tap, and a tap must not be read as a drag.

**What closing it requires.** The swipe reads the touch stream and claims only the horizontal axis,
so a vertical scroll still scrolls; a drag past the threshold never fires the card's click; the
panel still opens on a plain tap. Rules driven with a real finger for all three, and a mutation for
each — the axis unclaimed, the click not swallowed, the threshold dropped to nothing.

---

## B-012 — The startup screen plays a second time once loaded

**Reported** 1×. **Status** `closed` — confirmed 2026-08-14.

**What happened.** The screen covers one wait — the gap between asking for the application and
having an interface — and that wait spans TWO pages: the gate paints the screen when the form is
submitted, then the new document paints it again from its own markup. Held on a timer in the new
document, the bar filled once while the document downloaded and then restarted from zero on an
interface that was already rendered.

**This is my own over-correction.** Closing B-002 I gave the boot a five-second timer so the bar
could be seen; that turned the pace into a floor, and a floor in a document that is already
rendered is a delay, not a startup screen. What ends the screen is the interface being there. The
five seconds remain the bar's PACE — a bar half full means half way — and a duration is passed
only where the wait is played rather than observed, which is the sign-in inside the prototype.

**One implementation trap on the way.** The seam that ends the screen was declared inside the
function that plays a wait, so at boot it did not exist at all and the screen never came off.

Rule R53 corrected, `harness/demarrage.py` — 27 checks, three mutations proven: the timer back at
boot (the reported defect), the screen never painted, the played sign-in made instant. The rule
itself has now been wrong in both directions, and both times it said what the code did instead of
what the screen is for.

---

## Closed

Confirmed by the operator on a real phone, on `tm-design.iznogoudatall.xyz`. What each one did,
why no rule had seen it, and what proves it now stays in the sections above: a closed bug whose
history has been erased is a bug that will be made again.

| ID    | Defect                                                    | Reported | Closed     |
| ----- | --------------------------------------------------------- | -------- | ---------- |
| B-001 | The list poster is still too small                        | 2×       | 2026-08-14 |
| B-002 | The startup bar is never seen on a real load              | 2×       | 2026-08-14 |
| B-003 | In Arrivées a poster does not lead where a poster leads   | 2×       | 2026-08-14 |
| B-004 | Dragging the sheet handle down no longer closes the panel | 2×       | 2026-08-14 |
| B-005 | A long press on a poster raises the browser's own menu    | 2×       | 2026-08-14 |
| B-006 | Two different sign-in screens: arrival and sign-out       | 1×       | 2026-08-14 |
| B-007 | `--accent` referenced 11 times, defined nowhere           | 1×       | 2026-08-14 |
| B-008 | The card poster should bleed to the card's edges          | 1×       | 2026-08-14 |
| B-009 | Swiping a media card should reveal its quick actions      | 1×       | 2026-08-14 |
| B-010 | Only one row open at a time                               | 1×       | 2026-08-14 |
| B-011 | The drawer renders wrong on iOS                           | 1×       | 2026-08-14 |
| B-012 | The startup screen plays a second time once loaded        | 1×       | 2026-08-14 |

**What these twelve cost, and what is worth keeping from them.** Seven had been reported
**twice** before being written down here — what was missing was this register, not memory. Four
were invisible because the rule measured a named state instead of the path actually walked: a cold
load, a real finger, a real browser menu. One — B-012 — was my own over-correction of the one
before it. And two rules had to be thrown away before one held, for the same reason both times:
asserting that a panel is open AFTER the finger lifts proves nothing, since a tap opens it too.
