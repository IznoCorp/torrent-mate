# Phase 38 — The sentences that sent the reader to Arrivées

**Numbered 29, then 31, then 33, on 2026-09-27** (was 21; the triage's F51). **Carried at its opening, from the coherence triage (`review-archive/coherence-2026-09-27-triage.md` § B; texts in `coherence-2026-09-27.md`)**: F7 (the cross-references
land on the default-tab rule round 7 wrote, not on « the default tab »; `toArrivals` names `?tab=todo`); F54 (the quality
screen's sentence no longer promises a card reading « cherché, rien trouvé » — it edits i18n); F53 if this phase re-aims
R-L22-g / R-L22-j first (the Backrooms row; the Spider-Man game out of the seeds and the count; check `doc_fr_2026_final`).

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n -F 'data-go="arr"' -- frontend/maquette/design/src` → **3 emitters**:
  `features/acquisition/now-tab.tsx:106` (« En cours »'s own cross-reference), `features/system/run-list.tsx:183`,
  `features/system/run-screen.tsx:268`. The keys: `screens.system.introRest`, `screens.system.toArrivals` +
  `toArrivalsLink`, `screens.run.leftBehindLink`, `screens.acquisition.crossref*` (**8 keys**: `crossrefFromAcquisition` …
  `crossrefLink`), `verbs.maintenance.started` (« Commande lancée — suivez-la dans « Arrivées ». », read by
  `features/maintenance/action-verbs.ts:85`, whose comment also names Arrivées). Harness readers of the sentences:
  `git grep -n -E 'toArrivals|introRest|leftBehindLink|maintenance.started|suivez-la|crossref' -- 'frontend/maquette/harness/*.py'`
  → 3 lines, all in `page_host.py` (a « crossref » hold on the Arrivées page itself, which phase 35 re-homes).
- **Points ≈ 13.** Four sentences rewritten 4; `now-tab.tsx`'s cross-reference deleted (lines 104–121) 4 and its 8 keys 1; two
  emitters re-targeted 1; R-L22-p with its mutation 3.

Ruling 13 authorises two sentences of Système; the tree has five (DESIGN § 1.6). The proposed wordings are DESIGN § 3.7's
and adjust at the drawing; the ruling's own parenthesis (« À traiter », « Système ») is honoured.

## Red today

**R-L22-p — the sentences**: no rendered sentence on Système, its run detail, Acquisition or the Maintenance toast names
Arrivées; each cross-reference LANDS (address read) on Acquisition with « À traiter » open when something waits — a link never
sends the operator to a tab it knows to be empty.

**Red against `main`**: five sentences name the page.

## Move

Rewrite the four sentences; delete Acquisition's cross-reference and its keys (its subject — N arrivals entered without a
follow — IS the « À traiter » tab and its count); re-target the two Système emitters (`data-go="acq"`, landing on the
default tab).

## Mutation

With the commit made first: restore one `data-go="arr"` → R-L22-p falls.

## Register

—

## Oracle: states that diverge, declared by name

`system`, `system-outage`, `system-loading`, `system-error` and the run-detail states, on `system/body` if a sentence wraps
differently; `acq-now-idle`, `acq-now-loaded` on `acquisition/body` (the cross-reference leaves) — each accepted with
« L22 § 3.7: five sentences rewritten ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l22): nothing sends the reader to Arrivées any more`
