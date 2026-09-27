# Phase 13 — The ranking editor reads the saved weights (B-298, F16)

§ 18's « le ranking suit le ratio »: the screen `RankingPanel`'s production twin, under the settings
page's own address (`frontend-architecture.md`'s L16 entry), listing the criteria `ranking.json5`
ACTUALLY HOLDS — corrected against F16, which found the prior reading drew a criteria list from
nowhere named, never wired to the file production's own twin already reads. The rubric's dead end and
the quality screen's toast — B-298's own two symptoms — close in this same commit; the SAVE is phase
14's.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `grep -rn 'rankingToast\|rankingTitle' frontend/maquette/design/src/features` →
  `features/releases/quality-screen.tsx:283` (`data-toast={t("screens.profile.rankingToast")}`) and
  `features/settings/page.tsx:305` (`t("screens.settings.rankingTitle")`, a `topicRow`): the two sites
  this phase closes together (B-298's own two halves). `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(d['paths']['/api/config/files/{name}'].keys())"`
  → `['get', 'put']` — `readConfigurationFiles` already answers a file's own content, already declared
  and mocked (phase 4's own finding, `mocks/handlers/configuration.ts:50`). `sed -n '1,20p'
  frontend/src/components/config/RankingPanel.tsx` — production's own comment: « Loading and saving
  reuse the S4 config write-path verbatim (`useConfigFile` / `usePutConfigFile` on `ranking.json5`) »
  — the exact mechanism this phase wires the maquette's own twin to. `find config.example
  -iname '*ranking*'` → `ranking.json5`, the file this read names. `frontend/maquette/design/src/routes/settings.tsx`
  is 19 lines: the editor's address `/settings/ranking` is a route of its own; the phase's opening
  measure of `features/settings/` vs. a `features/ranking/` the settings route composes decides which,
  and the report says so. `grep -n '^| B-298' BUGS.md` → `open`.
- **Points ≈ 15.** `ranking-screen.tsx`, the criteria list, READ from `ranking.json5` through the SAME
  `readConfigurationFiles` operation the settings feature already calls (≈ 60 new; each criterion: its
  field, weight, values or thresholds, `prefer`; analogue `panel-field.tsx`, 182) 6; `routes/ranking.tsx`
  (≈ 13 new) 1½; the `SCREEN_PARENTS` entry `"/settings/ranking": "cfg"` and `harness/screen_addresses.py`'s
  walk gaining the address (a rule file re-aimed) 1; the rubric's row gaining its path (≈ 4 edited) 1
  and the quality screen's toast removed and replaced by the same path (≈ 3 edited) ½; **one new rule,
  R-L16-f's read half** (the editor's criteria at open equal what the file answers, never a constant)
  with its mutation 3; three states — `ranking-editor` 1, `ranking-editor-loading` 1,
  `ranking-editor-error` 1 (all needing a seed row for `ranking.json5`'s own content, none yet
  seeded — folded into the read cost above, no extra charge); `fr.json` (the editor's own labels, the
  four existing keys stay where they are).
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's own phase 13 (15, the same title, the
  same B-298 close) is CORRECTED, not renumbered: F16 found it drew a criteria list from an assumed
  source and never named the read that must ground it. The point count lands the same (15, at the
  ceiling) because grounding the read in a real operation costs about what the prior reading's own
  unstated assumption would have, once measured honestly.

A BEHAVIOUR change: two existing sites (a rubric that leads nowhere, a toast promising a screen) both
resolve to a real screen that reads a real file, in this one phase.

## The proof FIRST

Its label R-L16-f is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From Réglages, the « Classement des releases » rubric; separately, from a quality
  screen, the ranking button.
- **What it reads.** Both open the SAME screen, `/settings/ranking`, and its criteria list equals what
  `GET /api/config/files/ranking.json5` answers — never a constant the screen invents.
- **Red today.** The rubric leads nowhere and the toast fires instead of navigating, and no screen reads
  the file — both fail against `main` for that reason, which is B-298's own text.
- **Mutation.** `scripts/mutate.sh` makes the screen draw a FIXED criteria list, ignoring what the read
  answers. The comparison must fall, naming the divergence.

## The move

- **`features/settings/ranking-screen.tsx`** (or `features/ranking/`, per the opening measure) — the
  criteria list, read through `readConfigurationFiles("ranking")`.
- **`routes/ranking.tsx`** — `/settings/ranking`'s address; **`lib/addresses.ts`** —
  `SCREEN_PARENTS["/settings/ranking"] = "cfg"`.
- **`features/settings/page.tsx:305`** — the rubric's row gains its path, replacing whatever led
  nowhere.
- **`features/releases/quality-screen.tsx:283`** — `data-toast` REMOVED, replaced by the same path.
- **`harness/states/settings.ts`** — `ranking-editor`, `ranking-editor-loading`, `ranking-editor-error`.
- **`i18n/fr.json`** — new keys for the editor's own labels.

## Mutation

R-L16-f's read half: the fixed-list mutation above — committed and restored.

## Register

B-298's two dead ends close here; the promise it names (the editor WITH its preview and its save) is
kept in full at phase 15, once the save (14) and the preview (15) both land. Reported precisely by
phase 16.

## Oracle: states that diverge, declared by name

**None expected.** `ranking-editor` and its loading/error twins are NEW, on a brand-new region
(`ranking/body`). The settings rubric's row may change LENGTH where its `href` replaces a dead end with
a real path: if the row's own text is unchanged the expectation is ZERO divergence; **if it diverges,
that is a finding, not an acceptance**. The quality screen's own region loses the toast attribute only
— ZERO divergence expected there too.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the three new states.

## Commit

`feat(maquette-l16): the ranking editor reads its saved weights, and B-298's two dead ends close`
