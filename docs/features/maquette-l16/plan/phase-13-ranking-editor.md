# Phase 13 — The ranking editor lists its criteria (B-298)

§ 18's « le ranking suit le ratio »: the screen `RankingPanel`'s production twin, under the settings page's own address (`frontend-architecture.md`'s L16 entry), listing the
criteria the ranking is made of — and the two dead ends B-298 names close in the same commit that draws it. The live preview is phase 14's.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `grep -rn 'rankingToast\|rankingTitle' frontend/maquette/design/src/features` → `features/releases/quality-screen.tsx:283`
  (`data-toast={t("screens.profile.rankingToast")}`) and `features/settings/page.tsx:305` (`t("screens.settings.rankingTitle")`, a `topicRow`): the two sites this phase closes
  together (B-298's own two halves); both files still carry the lines at the numbers the first drawing gave. `python3 -c "import
  json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print([k for k in d['screens']['settings'] if k.startswith('ranking')], [k for k in d['screens']['profile'] if k.startswith('ranking')])"`
  → `['rankingTitle', 'rankingSubtitle'] ['rankingToast', 'rankingWeights']` — the four existing keys stay where they are. `frontend/maquette/design/src/routes/settings.tsx` is 19 lines
  (`createRoute`, path `/settings`): the editor's address `/settings/ranking` is a route of its own; the phase's opening measure of that file decides between `features/settings/` and
  a `features/ranking/` the settings route composes, and the report says which. `grep -n '^| B-298' BUGS.md` → `open`. `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/features/settings/page.tsx` → 311 and `features/releases/quality-screen.tsx` → 288.
- **Points ≈ 15.** `ranking-screen.tsx`, the criteria list (≈ 70 new; each criterion: its field, weight, values or thresholds, `prefer`; analogue `features/settings/panel-field.tsx`,
  182) 7; `routes/ranking.tsx` (≈ 13 new) 1½; the rubric's row gaining its path (≈ 4 edited) 1 and the quality screen's toast removed and replaced by the same path (≈ 3 edited) ½;
  the `SCREEN_PARENTS` entry `"/settings/ranking": "cfg"` (≈ 1) ⅕ and `harness/screen_addresses.py`'s walk gaining the address (a rule file re-aimed) 1; three states — `ranking-editor` 1, `ranking-editor-loading` 1, `ranking-editor-error` 1; `fr.json` (the editor's own labels) 1. **At the ceiling; what to cut**: the quality screen's toast removal (½) and the rubric's link (1) as their own phase.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 7, whole) 13 → this phase **15**, with the preview (phase 14) **9** and the contract (phase 12) **9**: moved by **the scale**;
  no ruling touched it.

A BEHAVIOUR change: two existing sites (a rubric that leads nowhere, a toast promising a screen) both resolve to a real screen in this one phase — B-298 is a single defect with two symptoms, and this
design does not split its close across two commits. (Its LIVE half — the preview the toast also promised — lands in the next phase; the register line closes at phase 15.)

## The proof FIRST

- **What it drives.** From Réglages, the « Classement des releases » rubric; separately, from a quality screen, the ranking button.
- **What it reads.** Both open the SAME screen, `/settings/ranking`, and it lists the criteria `RankingConfig.criteria` answers.
- **Red today.** The rubric leads nowhere and the toast fires instead of navigating — both fail against `main` for that reason, which is B-298's own text. The hold is the address rule's
  (`harness/screen_addresses.py`, re-aimed by the new `SCREEN_PARENTS` entry — counted above) and needs no new rule of its own.

## The move

- **`features/settings/ranking-screen.tsx`** (or `features/ranking/`, per the opening measure) — the criteria list.
- **`routes/ranking.tsx`** — `/settings/ranking`'s address; **`lib/addresses.ts`** — `SCREEN_PARENTS["/settings/ranking"] = "cfg"`.
- **`features/settings/page.tsx:305`** — the rubric's row gains its path, replacing whatever led nowhere.
- **`features/releases/quality-screen.tsx:283`** — `data-toast` REMOVED, replaced by the same path.
- **`harness/states/settings.ts`** — `ranking-editor`, `ranking-editor-loading`, `ranking-editor-error`.
- **`i18n/fr.json`** — new keys for the editor's own labels (`rankingTitle` / `rankingSubtitle` on the rubric and `rankingWeights` wherever it already reads correctly stay, none retyped).

## Register

B-298 closes with phase 14, when the promise the toast names — the editor WITH its preview — is kept; this phase closes its two dead ends. Reported by phase 15.

## Oracle: states that diverge, declared by name

**None expected.** `ranking-editor` and its loading/error twins are NEW, on a brand-new region (`ranking/body`). The settings rubric's row may change LENGTH where its `href` replaces a dead end with a
real path: if the row's own text is unchanged the drawing does not change and the expectation is ZERO divergence; **if it diverges, that is a finding, not an acceptance**. The quality screen's own
region loses the toast attribute only — the button's rectangle and style are UNCHANGED (a `data-toast` swap for a path does not move geometry) — so the expectation there is also ZERO divergence.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the three new states.

## Commit

`feat(maquette-l16): the ranking editor lists its criteria, and B-298's two dead ends close`
