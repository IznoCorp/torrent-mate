# Phase 2 — The Trackers tab exists

A new page and **a button of the bottom bar** (DESIGN § 4.1, § 5 « Ruled »): the navigation row, its route, its address, the
page's shell, the empty roster — and the bar reading three buttons in equal shares. The roster's rows are phase 3's; this phase
proves the tab, the route and the bar on their own, before anything is drawn in the page.

**Reads OPEN 1 and OPEN 2 (DESIGN § 5).** The plan is written for the reading that is ruled when the phase opens; if neither is
ruled it is **STOP C**. What each reading costs THIS phase:

- **OPEN 1 — A** (the row in the bar from this phase): as drawn below, **15**. **OPEN 1 — B** (the row in the drawer, `inBar:
  false`, `group: "supervision"`; its badge later on the menu button): the row's value is the only change, R-L22-s is not re-run
  (−1) and the rule's tab half reads the drawer entry instead (same 3): **14**.
- **OPEN 2 — A** (no right on the row): as drawn. **OPEN 2 — B** (the row names the right that opens it): a declared value on the
  row and its read by the bar, ≈ 10 lines new + 4 edited = +2, and the rule gains a second mock identity's « hidden » half (a walk,
  not a new rule): **17 — over the ceiling, so the phase is CUT at its opening** (the pre-cut clause): the right's declaration and
  its read become their own small phase between this one and phase 3, the numbers after it shift by one, and the steward is told.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `ls frontend/maquette/design/src/features/` → `account`, `acquisition`, `arrivals`, `library`, `maintenance`,
  `media`, `releases`, `settings`, `system` — no `trackers`. `grep -n 'id: "' frontend/maquette/design/src/app/navigation.ts` →
  8 rows (`acq`, `lib`, `arr`, `sys`, `maint`, `cfg`, `profile`, `404`); `grep -c 'inBar: true'` → `4` (`acq`, `lib`, `arr`, `sys`),
  `grep -c 'inBar: false'` → `4`. **At this lot's opening, after L22b, the same commands read `inBar: true` on `acq` and `lib` only**
  (L22b phases 19 and 25) — re-taken then. `sed -n '/PAGE_PATHS/,/};/p' frontend/maquette/design/src/lib/addresses.ts` → 7
  entries (`acq`, `lib`, `arr`, `sys`, `maint`, `cfg`, `profile`), none named `trackers`. `ls frontend/maquette/design/src/routes/`
  → 14 files, no `trackers.tsx`. `ls frontend/maquette/design/src/harness/states/` → 11 files, no `trackers.ts`; the named-state
  total is **114** (`python3 -c "import glob,re;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"',open(f).read(),re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"`).
  `grep -n 'radar\|library\|inbox\|wrench' frontend/maquette/design/src/app/icons.ts` → four icons, none for a ratio or a
  tracker (the `inbox` icon goes idle when `arr` dies). `grep -c '"tracker"\|screens.tracker' frontend/maquette/design/src/i18n/fr.json`
  → `0`. `grep -c 'body' frontend/maquette/regions.json` → 59. `grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1`
  → `R201`. `app/tab-bar.tsx` draws `NAVIGATION.filter((row) => row.inBar)` and each button is `flex … min-w-0 flex-1 basis-0`, so the
  bar already shares its width equally whatever the count (L22 § 3.6, measured there).
- **Points ≈ 15.** `features/trackers/page.tsx`, the shell — a title, the body region, the empty note (analogue `features/account/page.tsx`,
  79 non-blank lines; ≈ 30 new) 3; `routes/trackers.tsx` (≈ 15 new, the thin-route precedent) 1½; the navigation row (≈ 12 new), the
  `PAGE_PATHS` entry and a new icon path (≈ 3 new), and the header comment of `app/navigation.ts` rewritten to say « the bar holds the
  pages one goes to SEE, by rights » (≈ 8 edited) → 3; **one new rule, R-L16-h's tab half** — the tab is a bar button whose tap
  REPLACES (§ 16 point 2) and the page resolves and its region records — with its mutation 3; the state `trackers-empty`, needing a
  new seed row (an empty roster) 2; **L22's R-L22-s re-run at three buttons** — a rule file re-aimed, its walk gaining the state 1;
  `fr.json` (`navigation.pages.trackers`, `screens.trackers.title`, `.empty`) 1. **At the ceiling; what to cut** if the opening
  re-measure exceeds it: the R-L22-s re-aim and the state move to phase 3.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 2, « The trackers list, and its host ») 9 → this phase **15**
  and phase 3 **13**: moved by **the scale** (the list's page and four states alone are ≈ 20 on it) **and by ruling 11**: the row is a
  bar button, so the bar's count, the tab's replace-not-push and R-L22-s enter the phase; the first drawing's « `inBar` per the
  ruling, or Reading B (the drawer) by default » is gone — the ruling is in, and it is not Reading B.

A BEHAVIOUR change: the page did not exist; it now resolves, has its tab in the bar, and draws its empty roster.

## The proof FIRST

**Its label R-L16-h is bound to the next free number here** — this is the first phase that writes a rule: re-take `git remote
update origin >/dev/null && grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main`
now, bind `R-L16-a … h` to consecutive free numbers, and write the mapping into the report.

- **What it drives.** Tap the bar's Trackers button from Acquisition; read the bar; reload at `/trackers`.
- **What it reads.** The address `/trackers` and the page's region recording; the bar's buttons — three, each with an equal
  share of the width — and no empty slot; `history.length` before and after the tap (a page change REPLACES, § 16 point 2).
- **Red today.** `/trackers` resolves nowhere (no route, no `PAGE_PATHS` entry) and the bar has no such button — the rule fails for
  exactly that reason against `main`.
- **Mutation.** `scripts/mutate.sh` makes the tab's tap PUSH instead of replace — the `history.length` hold must fall; and a
  second, `inBar: false` on the row — the « three buttons » hold must fall, naming the count.

## The move

- **`features/trackers/page.tsx`** — the shell: the title, `data-region="trackers/body"` (registered in `regions.json`), and the
  empty note « Aucun tracker configuré. » (`screens.trackers.empty`), a real state: a fresh install's `config.example/tracker.json5`
  ships two, but a config can hold zero.
- **`routes/trackers.tsx`** — the route file, thin, per the existing precedent (`component: () => null`, the body drawn from
  `NAVIGATION.Body`).
- **`lib/addresses.ts`** — `PAGE_PATHS.trackers = "/trackers"`.
- **`app/navigation.ts`** — one row: `id: "trackers"`, `path: PAGE_PATHS.trackers`, `Body: TrackersPage`, `root: "body"`,
  `region: "trackers/body"`, `labelKey: "navigation.pages.trackers"`, `icon: icons.<a ratio icon>` (`app/icons.ts` gains one — the ratio's
  own, not reused from an unrelated domain), `group: "supervision"`, `inBar: true` (OPEN 1) — **no `badge` yet** (phase 10) and no
  field for a right (OPEN 2 — A). The header comment is rewritten to the bar's new sentence.
- **`harness/states/trackers.ts`** — `trackers-empty`; `harness/states/frame.ts` — the bar reads at three.
- **`i18n/fr.json`** — `navigation.pages.trackers`, `screens.trackers.title`, `screens.trackers.empty`.

## Mutation

Two, as above, each committed and restored separately (INDEX's « commit before every mutation »).

## Register

DOIT-13's row is not touched (no ratio is drawn). § 17 point 4 — « la barre du bas se compose par droits » — is served for the
Operator only; the hidden half is L18's (DESIGN § 5, OPEN 2).

## Oracle: states that diverge, declared by name

**None expected on existing states.** `trackers-empty` is NEW — the reference records it and proves nothing about it (D8). **The bar is
on every state that draws it** — its region is `shell/bottom-bar` (`frontend/maquette/regions.json`) — so its geometry changes on all of them
the moment a button is added: at L22b's end the bar draws two buttons, and this phase makes it three. That divergence is **accepted,
named, with the reason** « L16 phase 2: the bar draws its third button, in equal shares (organisation ruling 11) », on `shell/bottom-bar`
and nowhere else; any divergence off that region is **STOP A**.

## Gate

Per INDEX « Gates ». Additionally: `python3 frontend/maquette/oracle.py --record` for `trackers-empty`.

## Commit

`feat(maquette-l16): the Trackers tab joins the bar, and the page resolves`
