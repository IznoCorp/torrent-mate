# Phase 7 — The ranking editor (B-298)

§ 18's « le ranking suit le ratio »: the screen `RankingPanel`'s production twin, under the
settings page's own address (`frontend-architecture.md`'s L16 entry), with the live preview the
backend already computes — and the promise B-298 names is kept in the same commit that draws it.

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `grep -n "rankingToast\|rankingTitle" frontend/maquette/design/src/features/*/`
  → `features/releases/quality-screen.tsx:283` (`data-toast={t("screens.profile.rankingToast")}`),
  `features/settings/page.tsx:305` (`t("screens.settings.rankingTitle")`) — the two sites this
  phase closes together (B-298's own two halves). `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['RankingConfig']['properties']))"`
  → `bonuses`, `criteria`, `min_seeders`, `size_thresholds_by_type` — the editor's own field set,
  already typed. `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['RankingPreviewResponse']['properties']))"`
  → `known_trackers`, `ranked` — the roster the tracker-keyed criterion (phase 1's demand item 4)
  will populate once it lands; this phase draws the editor with `field: "provider"` as its worked
  example and the ratio-aware field WIRED IN once the backend answers it, per D7 (the interface
  declares, the backend follows). DESIGN § 2.1's own count — 4 existing `ranking*` keys in
  `i18n/fr.json` (`rankingToast`, `rankingWeights`, `rankingTitle`, `rankingSubtitle`), 0 for a
  criteria-editor screen itself — is the fr.json baseline this phase adds to.
- **Points ≈ 13.** New screen + route + settings-page link (replacing the dead-end row) + the
  quality-screen toast's removal ≈ 4; the live-preview wiring to `POST
  /api/acquisition/ranking/preview` ≈ 3; one new rule (R-L16-f, the preview's own agreement) with
  its mutation ≈ 3; three named states (`ranking-editor`, loading, error) ≈ 2; fr.json keys ≈ 1.
  Under 15, no cut.

A BEHAVIOUR change: two existing sites (a rubric that leads nowhere, a toast promising a screen)
both resolve to a real screen in this one phase — B-298 is a single defect with two symptoms, and
this design does not split its close across two commits.

## The proof FIRST

Its label is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From Réglages, the « Classement des releases » rubric; separately, from a
  quality screen, the ranking button.
- **What it reads.** Both open the SAME screen (`/settings/ranking`); a criterion's weight changed
  in the editor and POSTed to `ranking/preview`; the rows drawn compared against
  `RankingPreviewResponse.ranked`, with `excluded` rows sunk last and still visible (the backend's
  own ordering, DESIGN § 2.1).
- **Red today.** The rubric leads nowhere and the toast fires instead of navigating — both fail
  against `main` for that reason, which is B-298's own text.
- **Mutation.** `scripts/mutate.sh` makes the preview draw a constant ranking regardless of the
  POSTed criteria. The comparison must fall. A second mutation hides `excluded` rows instead of
  sinking them — the visibility hold must fall too (a live preview must never silently drop a row,
  the backend's own docstring, DESIGN § 2.1).

## The move

- **`features/settings/ranking-screen.tsx`** (or `features/ranking/`, composed by the settings
  route — the phase's own opening measure of `routes/settings.tsx`'s current shape decides which,
  and the report says so) — the criteria list, each with its field, weight, and values/thresholds;
  a live preview panel reading `RankingPreviewResponse.ranked`.
- **`routes/ranking.tsx`** (or the settings route extended) — `/settings/ranking`'s address.
- **`features/settings/page.tsx:305`** — the rubric's row gains its path, replacing whatever led
  nowhere.
- **`features/releases/quality-screen.tsx:283`** — `data-toast` REMOVED, replaced by the same path.
- **`i18n/fr.json`** — new keys for the editor's own labels (the four existing `ranking*` keys stay
  where they are — `rankingTitle`/`rankingSubtitle` on the rubric, `rankingWeights` wherever it
  already reads correctly — none retyped).

## Mutation

Two mutations, as above, each committed and restored separately.

## Register

**B-298 closes** — both symptoms named in the opening measure resolve to the same screen. § 18's
ranking clause reads `served` for the WEIGHTS half; the ratio-aware criterion itself (phase 1's
demand item 4) stays a filed demand until the backend answers it — the design draws the editor so
that field slots in without a second wave once it does (D7).

## Oracle: states that diverge, declared by name

**None.** `ranking-editor` and its loading/error twins are NEW, on a brand-new region
(`ranking/body`). The settings rubric's row (`system` — wait, `settings/body`) may change LENGTH by
one line where its `href` replaces a dead end with a real path — if the row's own text is
unchanged, the drawing does not change and the expectation is ZERO divergence; **if it diverges,
that is a finding, not an acceptance** (the same standard L20 § 7 set for `arr-queued`'s
precondition move). The quality screen's own region loses the toast attribute only — the button's
own rectangle and style are UNCHANGED (a `data-toast` swap for an `href` does not move geometry),
so the expectation there is also ZERO divergence.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the three new states;
`python3 scripts/check-bug-register.py` read by OUTPUT for B-298's closure line (B-346 — never by
exit code alone).

## Commit

`feat(maquette-l16): the ranking editor, live preview, and B-298's two dead ends close`
