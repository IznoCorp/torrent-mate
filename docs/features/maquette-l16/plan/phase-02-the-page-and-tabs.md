# Phase 2 — The Trackers page and its two tabs

A new page, **a button of the bottom bar** (DESIGN § 4.1, § 5 « Ruled »), and **two dials** —
`tab` (`trackersTab`) and `tracker` (`trackersFilter`) — the whole mechanism ruling 19's two tabs and
their filter read and write. Neither tab's own content is drawn here: this phase proves the page, the
route, the bar and the dials on their own, before anything is drawn inside them.

**Reads OPEN 4 (DESIGN § 5) — NOT ruled: STOP C.** The two readings and what each costs THIS phase:

- **Reading A — « Torrents » opens by default**: `trackersTab`'s default value is `"torrents"`. As
  drawn below, **15**.
- **Reading B — « Trackers » opens by default**: `trackersTab`'s default value is `"trackers"`. Same
  cost, **15** — the dial's default is the only line that differs.

The phase reads DESIGN § 4.1's two readings to the steward, with this cost line, and does not choose.

**STOP C resolved, 2026-09-27** (DESIGN § 4.1, § 5): ruled C — neither reading A nor B; `trackersTab`'s
default value is `"trackers"` on first entry, then the last tab opened, kept in local storage under
try/catch, falling back to `"trackers"` — the same mechanism as Acquisition's default-tab rule
(`features/acquisition/tab-memory.ts`), reused rather than duplicated.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `ls frontend/maquette/design/src/features/` → `account`, `acquisition`, `arrivals`,
  `library`, `maintenance`, `media`, `releases`, `settings`, `system` — no `trackers`. `grep -n 'id: "'
  frontend/maquette/design/src/app/navigation.ts` → 8 rows (`acq`, `lib`, `arr`, `sys`, `maint`, `cfg`,
  `profile`, `404`); `grep -c 'inBar: true'` → `4`. **At this lot's opening, after L22b, the same
  commands read `inBar: true` on `acq`, `lib` and `discover` — three** (L22b's own phases 19, 25 and
  its porting of round 8 Q20) — re-taken then. `sed -n '/PAGE_PATHS/,/};/p'
  frontend/maquette/design/src/lib/addresses.ts` → 7 entries, none named `trackers`.
  `grep -n 'DIALS = \[' -A3 frontend/maquette/design/src/lib/addresses.ts` → one dial today,
  `{ parameter: "tab", field: "acqTab", default: "follows", of: "acq" }` — the precedent this phase's
  two dials follow. `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/lib/addresses.ts` →
  **395** non-blank lines, 5 under the 400 ceiling: two new dials (≈ 10 lines) fit; a `SCREEN_PARENTS`
  row would not have (F38 — and this design draws none, § 3). `ls
  frontend/maquette/design/src/routes/` → 14 files, no `trackers.tsx`. `ls
  frontend/maquette/design/src/harness/states/` → 11 files, no `trackers.ts`. `grep -n
  'radar\|library\|inbox\|wrench' frontend/maquette/design/src/app/icons.ts` → four icons, none for a
  ratio or a tracker. `app/tab-bar.tsx` draws `NAVIGATION.filter((row) => row.inBar)` and each button
  is `flex … min-w-0 flex-1 basis-0`, so the bar already shares its width equally whatever the count
  (L22 § 3.6, measured there) — this phase re-runs that rule at four, it does not rewrite it.
  `grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` → `R225`.
- **Points ≈ 15.** `features/trackers/page.tsx`, the shell — the tab strip (`segment()`,
  `role="tablist"`, the `AcquisitionTabs` precedent), the body region, the empty note (≈ 35 new) 3½;
  `routes/trackers.tsx` (≈ 15 new, the thin-route precedent) 1½; the navigation row, the `PAGE_PATHS`
  entry and a new icon (≈ 15 new, 8 edited — the header comment rewritten to name the bar's new
  order) 3; **two dials in `lib/addresses.ts`** (≈ 10 new) 1; **one new rule, R-L16-h** — the bar
  button REPLACES, the dials ADJUST and push nothing — with its mutations 3; the state
  `trackers-page`, needing a new seed row (an empty roster AND an empty torrents list, the page's
  first load) 2; **L22's `R-L22-s` re-run at four** — a rule file re-aimed, its walk gaining the
  fourth button 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 2 (15, « the tab ») drew ONE tab
  and its own row's `badge:` placeholder; this phase draws TWO dials and no badge (phase 10's). The
  point count lands the same by a different route: two dials cost less than the prior single-tab
  wiring, and the bar's insertion (ruling 20 — BETWEEN Médiathèque and Découvrir, not appended after a
  free slot) costs the header-comment rewrite the prior reading did not need. **OPEN 1 and OPEN 2**,
  which the prior phase 2 read as STOP C, are RULED (DESIGN § 5): this phase reads no more than OPEN
  4.

**Cut at its opening (2026-09-28, on `c261da20d`, ≈ 18 > 15, the steward agreeing): 2a — the page, its route, its bar row, its readers, R260's bar holds; 2b — the two dials, the tab strip and the tab memory, R260 re-aimed with the ADJUST holds.** **2b re-cut at ITS opening (2026-09-28, ≈ 17): 2b — the dials, their travel on the entry and the restore, the strip, the tab verb; 2c — the tab memory, Acquisition's generalised into `lib/` and the single landing door made plural.**

A BEHAVIOUR change: the page did not exist; it now resolves, has its button in the bar, and its two
dials read and write.

## The proof FIRST

**Its label R-L16-h is bound to the next free number here** — this is the first phase that writes a
rule: re-take `git remote update origin >/dev/null && grep -rhoE '^"""R[0-9]+ '
frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main` now, bind `R-L16-a … h` to
consecutive free numbers, and write the mapping into the report.

- **What it drives.** Tap the bar's Trackers button from Médiathèque; read the bar; reload at
  `/trackers`; switch tabs; set the tracker filter.
- **What it reads.** The address `/trackers` and the page's region recording; the bar's buttons — four
  for an account holding the right, each an equal quarter, three for one that does not — and no empty
  slot; `history.length` before and after the bar tap (a page change REPLACES, § 16 point 2) AND
  before and after a tab or filter change (a dial ADJUSTS, D1b rule 1 — `history.length` UNCHANGED).
- **Red today.** `/trackers` resolves nowhere and the bar has no such button — the rule fails for
  exactly that reason against `main`.
- **Mutation.** `scripts/mutate.sh` makes the bar tap PUSH instead of replace — the `history.length`
  hold must fall. A second mutation makes a tab switch PUSH — the ADJUST hold must fall too, naming
  which dial pushed.

## The move

- **`features/trackers/page.tsx`** — the shell: the tab strip reading `trackersTab`, the body region
  `data-region="trackers/body"` (registered in `regions.json`), and the empty note.
- **`routes/trackers.tsx`** — the thin route.
- **`lib/addresses.ts`** — `PAGE_PATHS.trackers = "/trackers"`; `DIALS` gains
  `{ parameter: "tab", field: "trackersTab", default: <STOP C's answer>, of: "trackers" }` and
  `{ parameter: "tracker", field: "trackersFilter", default: "", of: "trackers" }`.
- **`app/navigation.ts`** — one row: `id: "trackers"`, INSERTED between `lib` and `discover` (ruling
  20 — the array order is the bar's own order), `path: PAGE_PATHS.trackers`, `Body: TrackersPage`,
  `root: "body"`, `region: "trackers/body"`, `labelKey: "navigation.pages.trackers"`, `icon:
  icons.<a ratio icon>`, `group: "supervision"`, `inBar: true` — **no `badge` yet** (phase 10) and no
  field for a right (DESIGN § 5, OPEN 2, ruled A). The header comment is rewritten: the bar's fourth
  place is Trackers, before Découvrir, never a free slot.
- **`harness/states/trackers.ts`** — `trackers-page`; **`harness/states/frame.ts`** — the bar reads at
  four.
- **`i18n/fr.json`** — `navigation.pages.trackers`, `screens.trackers.title`, and the two tabs'
  labels, `screens.trackers.tabTorrents` / `.tabTrackers`.

## Mutation

Two, as above — each committed and restored separately.

## Register

DOIT-13's row is not touched (no ratio is drawn). § 17 point 4 — « la barre du bas se compose par
droits » — is served for the Operator only; the hidden half is L18's (DESIGN § 5, OPEN 2).

## Oracle: states that diverge, declared by name

**None expected on existing states.** `trackers-page` is NEW. **The bar is on every state that draws
it** (`shell/bottom-bar`) — its geometry changes on all of them the moment a fourth button is added:
accepted, named, with the reason « L16 phase 2: the bar draws its fourth button, in equal shares
(organisation ruling 20) », on `shell/bottom-bar` and nowhere else; any divergence off that region is
**STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `trackers-page`.

## Commit

`feat(maquette-l16): the Trackers page joins the bar, with its two tabs' dials`
