# maquette-navigation — every edge against § 16, and the rule that walks them · DESIGN

Contract: B-577 (`BUGS.md`) — the operator, verbatim: « … quand je fais Systèmes => Réglage et que je reviens en
arrière … je reviens pas sur la page précédente mais à la racine sur Acquisions. C'est une violation du système de
routing demandé. Vérifier les autres cas également » — read against constitution § 16 as amended by #635 and #643
(`docs/reference/product-intent.md` § 16, the last paragraph of rule 2) and the rulings Q11 = A, Q12 = A of
`docs/features/maquette-conformity/rulings-2026-09-29.md`. The first reading is the conformity report's
§ C (`/Users/izno/dev/review-archive/conformity-80/REPORT.md`, 21 edges): every claim of it was re-read in the code
here, and this table supersedes it (§ 1.1 says what moved).

This document is written for a session that has none of the context it was produced in. **Nothing under
`frontend/maquette/` was touched to write it** — no code, no rule, no seed, no harness run: prose and numbers. Every
« what exists » carries its `file:line`, read on `main` at **`f71a44f7b`**; every count carries its command. Short
paths are under `frontend/maquette/design/src/`; harness paths under `frontend/maquette/harness/`.

The lot CHANGES behaviour (menu pages and in-page links stack), so it is not a conversion: its pull request cites
§ 16 and DOIT-10 (order 32).

---

## 0. What the lot owes, said once

| # | Subject | Source | Held in |
| --- | --- | --- | --- |
| 1 | Système → Réglages → Retour lands on Système (B-577) | the operator, 2026-09-29 17:07 | § 1, rows N1–N3; § 2, R-navigation-b |
| 2 | « Vérifier les autres cas également » — every edge of the maquette read against § 16 | the same words; order 81 | § 1, 35 edges |
| 3 | The pages the side menu opens STACK; Retour replays the arrival path | § 16 as amended (#635) | rows M1–M3, P1 |
| 4 | A bar page keeps the bar's rule from wherever it is opened — the rule reads by DESTINATION | Q11 = A | rows M4, M5, T4 |
| 5 | A link inside a page stacks, even towards the entry page; the exit guard arms only with the entry page at the bottom | Q12 = A | rows N4, N5, L3, Y5 |
| 6 | ONE family rule walking every edge and its Retour, plus B-577's own red rule | order 63; order 57 | § 2 |
| 7 | Every visible case a named state | orders 76, 77 | § 4 |

### 0.1 The machinery, read in the code

- **Three verbs switch a page**, all in `app/frame-verbs.ts`: `page` (`data-page`, `:69–76`) calls `switchPage`;
  `go` (`data-go` and a panel action's `target: { go }`, `:82–97`) and `navgo` (`data-navgo`, the drawer,
  `:102–110`) call `settleLanding` (`:56–65`), which routes to `switchPageFromLayer` when the tap came from a layer.
- **`switchPage`** (`app/page-switch.ts:198–252`) settles § 16 rule 2 for EVERY page: from the entry page it records
  (`:212–216`); to the entry page it steps back onto the floor (`:218–245`); between two other pages it REPLACES the
  top entry (`:250`). No line reads what KIND of page the destination is.
- **`switchPageFromLayer`** (`:278–303`) rewinds the layer's entry AND the page's (`(leaving === homePage ? 1 : 2) +
  stackedSurfaces()`, `:296`), then records the destination on the floor (`:302`): a page reached from the drawer or
  the account sheet always sits directly on `[guard, /acquisition]`.
- **What a page is** lives in `app/navigation.ts:121–230`: `inBar: true` for `acq`, `lib`, `trackers`, `discover`;
  `inBar: false` for `sys`, `maint`, `cfg`, `profile`. Neither switch reads it — the one fact the amended rule turns
  on is already declared, and unread.
- **An entry carries** `{ tm: "nav", page, …seven dials }` (`lib/navigation-entry.ts`, `navigationState`): nothing
  says how deep it is, so no verb can rewind « to the floor » from an unknown depth — today it never has to, because
  nothing stacks above one page.
- **Everything that is not a page pushes**: a screen (`lib/navigate.ts:72`), a rubric (`features/settings/topic-verb.ts:47`,
  `features/maintenance/topic-verb.ts:32`), a layer (`app/layers.ts`); its drawn Retour pops (`bridge.back()`).
- **The exit guard** (`app/layers.ts:296–318`): popping the guard arms it and shows « Encore un retour pour quitter
  TorrentMate. » (`i18n/fr.json:1178`, `message.oneMoreBack`); a second Retour within 5 s leaves.

### 0.2 The emitters, counted

```
rg -n -g '*.ts' -g '*.tsx' -g '!*.test.*' -g '!harness/**' \
  '(data-(page|go|navgo)=|"data-(page|go|navgo)"|target: \{ go: |store\.write\(\{ page|writeUiState\(\{ page)' \
  frontend/maquette/design/src | rg -v ':\s*//'
```
→ **16 lines**: 13 emitters (`tab-bar.tsx:80`, `drawer.tsx:143`, `not-found.tsx:28`, `system/page.tsx:107, 132`,
`system/locks.tsx:146`, `system/run-list.tsx:183`, `system/run-screen.tsx:268, 322`, `acquisition/card-markup.ts:214`,
`account/panel-account.ts:72`, `acquisition/verbs.ts:96`, `acquisition/add-screen.tsx:117`) and the three verbs'
own writes (`frame-verbs.ts:72, 87, 106`). Screen openers: `rg … 'screens\.(mediaSheet|resolution|releases|profile|add|run|ranking)\(|\bgo\(\{'`
outside `harness/` → 15 lines, two of them REPLACING a screen (`releases/verbs.ts:99`, `acquisition/resolution-verbs.ts:108`).

### 0.3 What the conformity train moves — read on `origin/feat/maquette-conformity` at `b3353ead2`

**No edge's behaviour.** The train is a conversion; so far it has not touched `page-switch.ts`, `frame-verbs.ts`,
`drawer.tsx` nor `panel-account.ts` (`git diff --stat origin/main...origin/feat/maquette-conformity -- <them>` →
empty), and its phase 10 plans only the drawer's badge and Appearance choice (`app/drawer.tsx:48, 150, 163`). It
MOVES emitter lines the rules must not anchor on: Réglages' row becomes the `ui` `TopicRow` with
`target={{ "data-page": "cfg" }}` (`features/system/page.tsx:141` there), Maintenance's cross-reference is `:112`,
`locks.tsx:138`, `run-list.tsx:168`, `run-screen.tsx:266, 320`, `add-screen.tsx:121–137`. The family rule anchors on
`data-page` / `data-go` / `data-navgo` values and `data-part`, never on a line or a class (D4). **This lot opens after
the train has merged** — its phases 5 and 10 touch Système and the drawer — and re-reads every line of § 1 there.

---

## 1. The edge table — B-577 first

Verdicts: **DEFECT** (the code contradicts § 16 as amended) · **coincides** (right only because the page left is
the floor) · **conforms** · **constraint** (conforms today; the fix must keep it true once pages stack) · **OPEN**
(§ 6). « Read » = the mechanism is read, the walk of phase 1's rule confirms it. The trail is written bottom → top,
the guard omitted.

| # | Edge (from → to) | Emitter | Today (mechanism) | Retour today | § 16 wants | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| N1 | Système › Réglages row → Réglages | `features/system/page.tsx:132` `data-page="cfg"` | `page` → `switchPage` → `replacePath` (`page-switch.ts:250`): `[acq, cfg]` | Acquisition | stack `[acq, sys, cfg]`; Retour → Système (Q12) | **DEFECT — B-577** |
| N2 | Système › « … Maintenance » → Maintenance | `features/system/page.tsx:107` `data-page="maint"` | same | Acquisition | Système | **DEFECT** |
| N3 | Système › Verrous › « … réparer » → Maintenance | `features/system/locks.tsx:146` `data-page="maint"` | same | Acquisition | Système | **DEFECT** |
| N4 | Système › passages « Acquisition → » → Acquisition · À traiter | `features/system/run-list.tsx:183` `data-go="acq" data-dial="todo"` | `go` → `switchPage` arriving home → rewind onto the floor (`:238–240`) | exit guard armed | stack `[acq, sys, acq]`; Retour → Système, guard NOT armed (Q12) | **DEFECT** |
| N5 | run screen « … laissés derrière » → Acquisition · À traiter | `features/system/run-screen.tsx:268` | same, the screen counted (`features/system/run-verbs.ts`, `countTheEntry`) | exit guard armed | stack; Retour → the run screen | **DEFECT** |
| N6 | run not found « Retour aux passages » → Système | `features/system/run-screen.tsx:322` `data-go="sys"` | the state under `/run/…` is `sys`: `arriving === leaving` → `replacePath` (`:208–210`) turns `/run/…` into a second `/system` | one Retour that lands on the same page (read) | the parent once — the control IS a Retour, as the screen's own (`run-screen.tsx:307`, `bridge.back()`) | **DEFECT (read)** |
| M1 | menu from Acquisition → Système / Maintenance / Réglages | `app/drawer.tsx:143` `data-navgo` | `navgo` → `switchPageFromLayer`: rewind 1, record (`:296–302`) | Acquisition | stack; Retour → Acquisition | coincides |
| M2 | menu from Médiathèque / Trackers / Découvrir → a menu page | same | rewind 2, record on the floor | Acquisition | the page left | **DEFECT** |
| M3 | menu from a menu page → another menu page (Système → Réglages, Réglages → Maintenance …) | same | same | Acquisition | the page left | **DEFECT** |
| M4 | menu → Médiathèque / Trackers / Découvrir, from anywhere | same | rewind to the floor, record | Acquisition | Q11: replace, Retour → the entry page — from ANY depth once pages stack | constraint |
| M5 | menu → Acquisition, from anywhere | same | rewind; the floor takes the address (`:302`) | exit guard | rule 2 — from any depth | constraint |
| M6 | menu → the page one is on | same | no equality test (`:278–303`): rewinds and re-records the same page | the same as before the tap | not an arrival: the drawer closes, nothing is written | constraint |
| M7 | menu from Réglages / Maintenance with a rubric open → another page | same; `stackedSurfaces()` counts the rubric (`:296`) | the rubric rewound with the page | Acquisition | the rubric kept on the trail, or given back first? | **OPEN 3** |
| P1 | account sheet « Profil et préférences » → Profil | `features/account/panel-account.ts:72` `target: { go: "profile" }` | `go` from a layer → `switchPageFromLayer` | Acquisition | § 16 names Profil among the stacking pages: the page under the sheet | **DEFECT** (coincides from Acquisition) |
| T1 | bar: Acquisition → a bar page | `app/tab-bar.tsx:80` `data-page` | `switchPage` records (`:212–216`) | Acquisition | rule 2 | conforms |
| T2 | bar: a bar page → another | same | replace (`:250`) | Acquisition | rule 2 | conforms |
| T3 | bar: → Acquisition | same | step back onto the floor (`:218–245`) | exit guard | rule 2 | conforms |
| T4 | bar: from a stacked trail (`[acq, lib, sys, cfg]`) → a bar page | same | replaces the TOP entry only (`:250`) | — (no trail today) | rule 2: the whole trail unwound, `[acq, page]` | constraint |
| T5 | bar: the page one is on | same | replace (`:208`) | unchanged | not an arrival | conforms |
| L1 | Acquisition card « Voir le tracker » → Trackers · that tracker | `features/acquisition/card-markup.ts:214` `data-go="trackers"` + `data-dial` | `go` → `switchPage` from home, record | Acquisition | an in-page link stacks (Q12): Acquisition | coincides |
| L2 | not-found « Acquisition » → Acquisition | `app/not-found.tsx:28` `data-go="acq"` | `arrivalWithoutFloor`: record (`:225–227`) | the typed address, then the guard | rule 3 and Q12 | conforms |
| L3 | follow panel « Compléter » (Médiathèque › Incomplets) → Acquisition · Maintenant | `features/acquisition/follow-actions.ts:60` → `features/acquisition/verbs.ts:95–101` | writes `page: "acq"` itself — `store.write`, `panel.close()`, `redraw()` — and calls NO switch: the panel's pop leaves Médiathèque's entry under Acquisition drawn (read; B-026's class) | Médiathèque's address under the Acquisition page | a link in a page's layer stacks (Q12), the layer's entry kept (D-L13-1): Retour → Médiathèque, the panel reopened | **DEFECT (read)** |
| L4 | add screen « Voir mes suivis » → Acquisition · Maintenant | `features/acquisition/add-footer.tsx:57` → `features/acquisition/add-screen.tsx:116–134` | `go({ to: "/acquisition", replace: true })` over `/add`: `[acq, acq·now]` | Acquisition again, on its former tab — a Retour that undoes a setting (read) | the screen closes (rule 1), the tab set as a setting: Retour → the guard | **DEFECT (read)** |
| S1 | a screen from a page: media sheet, resolution, releases, quality profile, add, run, ranking | `features/media/media-verbs.ts:130`, `features/acquisition/resolution-verbs.ts:63`, `features/releases/verbs.ts:92`, `app/action-button.tsx:81`, `features/system/run-verbs.ts:22`, `app/history-bridge.ts:324` → `lib/navigate.ts:72` | push | the opener | rule 1 | conforms |
| S2 | releases → quality profile | `features/releases/verbs.ts:96–99`, `app/history-bridge.ts:208–212` (`replace`) | the profile REPLACES the releases screen | under the releases screen | rule 1: opening a surface stacks | **OPEN 2** |
| S3 | resolution « manuel » → identification search | `features/acquisition/resolution-verbs.ts:106–108` (`screens.add(…, true)`) | the search REPLACES the resolution | Acquisition | same | **OPEN 2** |
| S4 | a screen's drawn Retour, and the acts that close one (a candidate picked, a release picked) | `features/media/media-screen.tsx:226`, `features/acquisition/resolution-verbs.ts:70, 87`, `features/releases/verbs.ts:76` → `bridge.back()` | pop | the opener | rule 1; 09-15 Q4 (the resolution closes) | conforms |
| S5 | connection lost → sign-in | `app/connection-notice.tsx:146` | push, covers everything | — | not a § 16 journey | conforms |
| S6 | a cold link to a screen | `lib/addresses.ts:71–79` `SCREEN_PARENTS`; `app/arrival.ts:215–240` | the parent synthesised under it | the parent | rule 3 | conforms |
| S7 | a cold link to a menu page | `app/arrival.ts:217–220` | `[acq, page]` | Acquisition | rule 3: a menu page belongs to no page but the floor | conforms |
| Y1 | a rubric of Réglages / Maintenance, and its drawn Retour | `features/settings/topic-verb.ts:47`, `features/maintenance/topic-verb.ts:32`; `features/settings/page.tsx:135, 177`, `features/maintenance/page.tsx:75` | push; pop | the page's root | rule 1 | conforms |
| Y2 | Réglages › « Poids du classement » | `features/settings/page.tsx:303` → the ranking screen | push | Réglages | rule 1 | conforms |
| Y3 | a panel, the drawer, a dialog | `app/layers.ts`, `app/panel-host.ts` | a layer entry; D-L13-1 reopens a panel left for an arrival | the surface under it | rule 1 + D-L13-1 | conforms |
| Y4 | an adjustment: tab, lens, filter, sort, mode | the `acqtab`, `lens`, `cat`, `pill`, `fmode`, `sugmode`, `trackers-tab`, `trackers-filter`, `setsort` verbs | replace | out of the page | rule 1 « régler remplace » | conforms |
| Y5 | Retour on the entry page | `app/layers.ts:296–318` | the guard arms | — | arms only when the entry page is at the BOTTOM: on `[acq, sys, acq]`, Retour → Système (Q12) | constraint |

**Counted** (`grep -cE '^\| [NMPTLSY][0-9] ' docs/features/maquette-navigation/DESIGN.md` → 35): **35 edges** — **11
DEFECTS** (N1–N6, M2, M3, P1, L3, L4; three of them read, to be confirmed by the walk: N6, L3, L4), **2 coincide**
(M1, L1), **19 conform** of which **5 are constraints** on the fix (M4, M5, M6, T4, Y5), **3 OPEN** (M7, S2, S3).

### 1.1 What moved from the report's § C

- Its rows 10–11 (OPEN 12) are DECIDED by Q12 = A → N4, N5 are DEFECTS; its row 6 (OPEN 11) by Q11 = A → M4, M5.
- Its row 12 (« to confirm ») is N6: the mechanism is read (`replacePath` on `arriving === leaving`) — a defect, the
  walk confirms it.
- NEW: M6 (the menu's current page), M7 (a rubric open), T4 (the bar from a trail), Y5 (the guard mid-trail), L4 (the
  add screen's exit), S2–S3 (a screen replacing a screen), S5, S7 — none was in the 21.

### 1.2 The readers of the behaviour this lot reverses (office: « the READERS, not only the writers »)

Read by a search subagent over the 30 rules reading `history.length`, `armedExit` or `data-navgo`
(`rg -l -g '*.py' 'armedExit|history\.length|navgo|data-navgo' frontend/maquette/harness` → 30), each flip re-read
here: **R82 `journey.py:524–525, 554–555, 562–564`** holds « one Back off Profil reaches the entry page, never the
page it was opened from » — the old rule, verbatim; it flips with P1. **R239 `no_sentence_to_arrivals.py:176–177`**
holds « the landing stands on the floor, no entry left underneath » after Système's `data-go="acq"` — it flips with
N4, N5. The 28 others assert no landing after a page switch into a menu page (R65 `drawer.py:182–183` walks from
Acquisition, so M1 coincides; `url_state.py`, `locks.py`, `seeds_at_rest.py`, `queued_by_hand.py` walk there but
assert only the arrival).

---

## 2. The rules that bite

Labels, never numbers: they bind to the range the steward reserves.

**R-navigation-a — every edge, and where its Retour lands (the family rule, order 63).** HOLDS in `journey.py`
(R82, « Back retraces the path taken (§ 16) »: the office's line — a new check on a surface with a rule is a hold in
that rule's file; `journey.py` holds 773 non-blank lines, so the edge table is DATA in a module beside it,
`harness/navigation_edges.py`, imported, one table and no second copy). One entry per edge id: the finger walk that reaches the
edge's origin from a cold `/acquisition` (taps only, never `__go`), the tap, the address and page expected after
ONE Retour (`page.go_back()`, the system gesture), and `window.armedExit` there. It walks every DEFECT, coincides,
conforms and constraint row; an OPEN row is walked under the ruling's reading once it lands. **Its completeness
hold**: the emitters of § 0.2's command, read from the source, each map to an edge id — an emitter the table does
not name fails the rule (the edge nobody classified is B-577's escape). **Its second hold**: nothing but the three
verbs writes `page` into the store (§ 0.2 counts 2 outside them today, `acquisition/verbs.ts:96` and `acquisition/add-screen.tsx:117` — L3 and L4, and they are the fix).

| Mutation | Falls on |
| --- | --- |
| **B-577's mechanism**: a stacking destination reached by `data-page` from a non-home page REPLACES again (`replacePath()` where the fix records) | N1, N2, N3 — and R-navigation-b |
| the layer switch rewinds to the floor for every destination (`(leaving === homePage ? 1 : 2)` restored) | M2, M3, P1 |
| a bar destination rewinds one entry instead of the trail | T4, M4 from a trail |
| an in-page link arriving home steps back onto the floor again | N4, N5, Y5 |
| `complete` writes `page` itself again | L3, the second hold |
| an unlisted `data-page="sys"` added to a page | the completeness hold |

**R-navigation-b — B-577, red first (order 57).** One hold, its own label because the register row names it: cold
`/system`, a FINGER on the Réglages row (anchored `[data-part="topic"][data-page="cfg"]`, true on `main` and on the
train's `TopicRow`, `ui/topic-row.tsx:33` there), Réglages drawn, ONE Retour → the address is `/system`, Système is drawn, `armedExit` is 0.
**Red on `f71a44f7b`** (read: `replacePath` at `page-switch.ts:250` → `/acquisition`). Mutation: B-577's mechanism
above → falls.

---

## 3. The mechanism the fix needs, and nothing more

- **The entry carries its trail** — the page ids from the floor up (`trail: ["acq", "lib", "sys"]`), written by
  `navigationState` beside the dials. A few ids, never a body (the ceiling `CARRIED_FIELDS` already respects), and it
  survives a reload because the history does. It answers the one question no verb can answer today: how many entries
  to rewind to reach the floor from here (T4, M4, M5).
- **Two facts decide, both read, never re-declared.** The ORIGIN: a tap in the bar (`app/tab-bar.tsx`,
  `data-part="shell/tab-bar"`) or the menu (`#drawer`) is a DESTINATION choice; a tap anywhere else — a page, a
  screen, a panel — is an IN-PAGE LINK. The `page` verb serves both the bar and Système's rows (`frame-verbs.ts:69`),
  so the verb passes the origin, read from the tapped element's ancestry, to the switch. The DESTINATION's class:
  `rowFor(page).inBar` (`app/navigation.ts:247`). Then: an in-page link STACKS, whatever it leads to (Q12 — L1 to
  Trackers included); from the bar or the menu, a bar destination unwinds the trail (rule 2, Q11) and a menu page
  stacks (§ 16); the page one is on writes nothing (M6, T5).
- **`switchPage` and `switchPageFromLayer` stay the two doors**; L3 and L4 go through them. No new verb, no new
  component: N6's control becomes the screen's own Retour (`backAction` + `bridge.back()`, already `run-screen.tsx:307`).
- **An entry without a trail** (written before the fix) reads as `[floor, page]` — no migration (no backward
  compatibility, 2026-09-29).

## 4. Named states — what is visible

A named state is DRIVEN and writes no history (`app/page-switch.ts:98–105`). The three `nav-*` below are the first
that POSE a trail under what they draw, so the operator presses Retour on tm-design and watches the path replay (orders 76,
77): an adaptation of the state driver (`harness/drive.ts`), a `poseTrail(pages)` writing the entries once the
drive is done — said here, as the office asks of an adaptation.

| Id | Label (catalogue) | What is drawn | What Retour does from it |
| --- | --- | --- | --- |
| `nav-exit-armed` | « Navigation — Retour sur la page d'entrée : la garde de sortie armée » | Acquisition, the notice « Encore un retour pour quitter TorrentMate. » | a second Retour within 5 s leaves |
| `nav-trail-settings` | « Navigation — Réglages ouverts par Système, lui-même ouvert depuis la Médiathèque » | Réglages over the trail `[acq, lib, sys, cfg]` | Système, then Médiathèque, then Acquisition, then the guard |
| `nav-acquisition-over-system` | « Navigation — À traiter ouvert par le lien de Système : Retour ramène à Système » | Acquisition · À traiter over `[acq, sys, acq]` | Système — the guard NOT armed (Y5) |
| `run-not-found` | « Passage introuvable — un lien vers un passage que le moteur ne connaît plus » | the run screen's « introuvable » note and its control (`features/system/run-screen.tsx:316–324`) — a case drawn today with NO named state (`rg -n -i 'not.found' frontend/maquette/design/src/harness/states/system.ts` → 0) | Système, once (N6) |

No state for M6, T5: nothing visible changes.

## 5. Conformity to the operator's principles (order 97) — read BEFORE the plan

His principles are `docs/reference/operator-method.md` § 1; each row says where this design holds it, and the phase.

| Principle, his words | Where this design holds it | Phase |
| --- | --- | --- |
| § 16 — « Les retours se font toujours par le même chemin d'arrivé. Si je passe par système je repasse par systèmes, sinon non. » | menu pages and Profil stack (M1–M3, P1); in-page links stack, even to Acquisition (N1–N5, L3); bar pages replace from anywhere (M4, M5, T4) — each walked by finger, R-navigation-a | 1 · 2 · 3 |
| « Mes retours sont des corrections sur ce qui est attendu » — « Vérifier les autres cas également » | B-577 is one row of 35; the family rule's completeness hold makes an unclassified edge a failure, so the next one cannot escape | 1 |
| « Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » | one reading per KIND of edge: a link stacks, a bar destination replaces, a Retour control pops (N6 becomes one); OPEN 1–3 ask where two readings would make two behaviours | every phase |
| « on crée pas de nouveau composant on adapte » | no new element: the exit notice is the existing toast, N6 the existing `backAction`; the only adaptation is the entry's `trail` and the driver's `poseTrail` (§ 3, § 4) | 1 · 3 |
| « seule une maquette montrant tout les cas possibles est utile » | § 4's four states (`run-not-found` a missing case found here), in the catalogue with their French labels | 1 · 3 |
| « tout doit être responsive … sur tous ! » | nothing drawn changes width; R-conformity-a runs on the four states at their phase's gate | 1 · 3 |
| « design et ergonomie d'application mobile natif » | Android's system Retour drives the walk (`page.go_back()`); the bar keeps Android's `popUpTo(startDestination)`; iOS gives no Retour between tabs, which rule 2 already follows | 1 · 2 |
| « A, pas de gestion de rétro-compatibilité ! » | an entry with no trail reads as `[floor, page]`, no migration | 1 |

## 6. OPEN — to the operator, one round

**OPEN 1 — coming back to a page already on the trail.** Système → Réglages → menu → Système. **A** — stack again,
literally: Retour walks Système → Réglages → Système → Acquisition; the same rule as Q12 (Système's link to
Acquisition stacks although Acquisition is at the bottom). **B** — cut the trail back to that page's entry: Retour
from Système → Acquisition; no page twice on the trail, but the entry page stays the exception Q12 made, so two
behaviours. Cost: A nothing beyond § 3; B a search of the trail and a rewind. **Recommended: A** — his words
(« toujours par le même chemin ») and one behaviour with Q12.

**OPEN 2 — a screen that takes another screen's place (S2, S3).** Releases → « profil de qualité » and resolution →
« identifier à la main » REPLACE today (`features/releases/verbs.ts:93–99`, `features/acquisition/resolution-verbs.ts:106–108`),
so Retour skips the screen one came from. **A** — they stack (rule 1: opening a surface is an arrival); Retour from
the profile → the releases, from the search → the resolution; after a pick in the search, the list comes back, as a
resolution's pick does (09-15 Q4). **B** — keep the replacement, declared as his exception. Cost: A two `replace`
flags removed and the search's pick rewinding two entries; B none. **Recommended: A** — uniform with every other
screen.

**OPEN 3 — leaving Réglages or Maintenance by the menu while a rubric is open (M7).** **A** — the rubric stays on the
trail: Retour → the rubric. **B** — the rubric is given back first, as an in-page control already does
(`lib/stacked-surface.ts`, `giveTheEntryBackFirst`, B-398): Retour → the page's root. Cost: A counts it and keeps
it; B the drawer's tap adopts that existing order. **Recommended: B** — the existing, validated behaviour of the same
gesture from inside the page, and § 16 keeps no stack INSIDE a page.

## 7. The documents that still describe the old rule — changed at the close

- `docs/reference/frontend-architecture.md:152–155` (D1b rule 2: « Back from any page lands on `/acquisition` »)
  and `docs/reference/frame-survey.md:147` (« a top-level page REPLACES ») — `docs/reference/*` is not a lot's to
  edit: listed for the steward's docs pull request.
- `frontend/maquette/README.md:837–864` (« A layer is not a route »: « A back from the destination then reaches where
  one was before opening the drawer ») — the lot's, phase 4: the sentence becomes true for menu pages.
- `app/frame-verbs.ts:99–101` (« a drawer entry is a top-level destination like any other ») and
  `app/page-switch.ts:173–197, 254–277` (the two docstrings, « § 16 rule 2 … for every page ») — the code's, phase 2
  and phase 1.
- `BUGS.md` B-577 closed with R-navigation-b's red reading and its mutation (office: a row a phase closes is closed
  in it).
