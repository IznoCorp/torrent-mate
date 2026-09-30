# maquette-conformity — one need, one component; every state at every width · PLAN

Design: the conformity reading, `/Users/izno/dev/review-archive/conformity-80/REPORT.md` (§ B, § D), and the
operator's rulings, `/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` — cited, never copied. The
implementer is held to `docs/reference/implementer-office.md`, AMENDED by the auditor's orders 98 and 99 (below).
Orders served: 80 (one need, one component), 85 (the responsive rule), 89 (the iPhone's engine).

**Re-cut 2026-09-30 BY SURFACE** (orders 98, 99, approved by the orchestrator): phases 1–2 (the rule, its WebKit
pass) are done; the 24 phases that followed are replaced by ten, one per surface. The old plan is
`docs/features/maquette-conformity/plan/INDEX.md@f36b54795`; its correspondence is the last table.

## The operator's principles, and how this plan answers them (order 97)

| Principle, his words | Where this plan holds it |
| --- | --- |
| « 1 design système, 1 composant, de la cohérence ! » | phases 3–4 build each shared need ONCE in `ui/`; the surfaces consume it; phase 13 arms the guards |
| « on crée pas de nouveau composant on adapte » | every component is an ADAPTED existing one (`segmentTab`, `Disclosure`, `tabBarBadge`, `viewSwitch`, `chip`, `SurfaceError`) — `TopicRow` and `Tabs` compose existing variants |
| « l'existant est ce qui est validé » | `Tabs` is Acquisition's bar as it stands; Trackers and Médiathèque come to it |
| « tout doit être responsive … sur tous ! » | R-conformity-a: every state at 320 → 1280 px, and in WebKit light and dark, at every phase gate |
| « Rien d'essentiel n'est tronqué » (§ 12) | phase 8: titles, tiles, cast names wrap; phase 5: the raw log wraps |
| « Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » | one pair « actif / inactif », one word per state, one back control, one pick button; exceptions: none declared |
| « Mes retours sont des corrections sur ce qui est attendu » | each ruling and each defect found lands in the surface phase that already touches it, never a phase of its own |
| « trop de gates, trop de harnais, trop de sécurité » | ten phases, one light gate each; the heavy checks once per lot (below) |

## The phases — one surface each, sized by the context (gauge + cost ≤ 80), no point cap

| # | Surface | Page |
| ---: | --- | --- |
| 1 | The responsive rule — DONE (`eef05f5d7`) | [phase-01](phase-01-the-responsive-rule.md) |
| 2 | Its WebKit pass — DONE (`f36b54795`) | [phase-02](phase-02-the-webkit-pass.md) |
| 3 | Components I — tabs, chevron, badge, segmented size | [phase-03](phase-03-components-one.md) |
| 4 | Components II — tones, notice, legend, topic row | [phase-04](phase-04-components-two.md) |
| 5 | Système and the run screen | [phase-05](phase-05-system.md) |
| 6 | Réglages and Maintenance | [phase-06](phase-06-settings-and-maintenance.md) |
| 7 | Acquisition — then the MIDPOINT | [phase-07](phase-07-acquisition.md) |
| 8 | Médiathèque | [phase-08](phase-08-library.md) |
| 9 | The media sheet and the seasons | [phase-09](phase-09-media-sheet.md) |
| 10 | The frame and the menu | [phase-10](phase-10-frame-and-menu.md) |
| 11 | Découvrir and Trackers | [phase-11](phase-11-discover-and-trackers.md) |
| 12 | The harness consolidation — conversion only, the budget ≤ 0.60 (order 52; added 2026-09-30) | [phase-12](phase-12-harness-consolidation.md) |
| 13 | The close — the guard arms, the lot's gate, the PR | [phase-13](phase-13-close.md) |

## The gates (order 99, amending the office's « The gate »)

- **A phase gate**: the static guards on the files touched; the oracle ALONE, accepting only the states the page
  names; `run.sh --rules` on the rules of the surfaces touched — each item's rule read RED on the old code first,
  then green (that is its proof: no per-phase mutation, no per-phase a11y); R-conformity-a on the touched surfaces'
  states (`TM_RESPONSIVE_STATES`, built by script).
- **The midpoint, after phase 7**: `--contracts` and the full responsive sweep (Chromium + WebKit), once.
- **The harness consolidation, phase 12** (order 52): the lot's harness budget, read at the midpoint, brought to
  ≤ 0.60; the oracle « no divergence »; each merged hold still falling under its mutation.
- **The close, phase 13**: the full suite, `--a11y`, the full sweep, the hold counts; the ten random mutations, the
  finger walk and the principles check are the reader round's.
- Every browser run names `TM_HARNESS_JOBS=2` (order 88); every pytest `-n 2`.

## The stops

**STOP A** — the oracle diverging on a state the page did not name. **STOP B** — the pull request. **STOP D** — a
ceiling: `ui/variants/controls.ts` and `frame.ts` **397 / 400**, `surfaces.ts` **373**, `features/media/season-list.tsx`
**390** (`grep -cv '^\s*$'`): a phase landing there moves lines out. Anything outside these pages: STOP, ask.

## Correspondence — every element of the old plan, every decision, every owed red → its phase

| Element | → |
| --- | --- |
| old 3 runs list (D.1 #13), B-576 · old 7 raw log (Q10) · old 13 on/off pair (D.1 #2, Q1) · old 14 state words (Q2) | 5 |
| old 4 requester line · old 24 primary buttons (D.1 #15, Q8): the pick · the save | 7 · 6 |
| old 5 bar label 320 px | 10 |
| old 6 card title, R8 tile, R9 cast (§ 12) · old 9 « Récents » / « Incomplets » filters (the operator's decision, Q20) | 8 |
| old 8 tabs (D.1 #1): the component · the bars of Acquisition, Médiathèque, Trackers | 3 · 7, 8, 11 |
| old 10 chevron (D.1 #3, DECIDED 4): component · add screen · seasons · guard arm | 3 · 7 · 9 · 13 |
| old 11 switch (D.1 #4) + L16-bis § 1.7/1.8 correction · guard arm | 6 · 13 |
| old 12 status chip (D.1 #5): run outcome · muted → neutral · season marks | 5 · 7 · 9 |
| old 15 fact with its state (D.1 #6): count line · media facts | 8 · 9 |
| old 16 empty surface (D.1 #10): runs · media | 5 · 9 |
| old 17 notice (Q3): component · banners · identify · TMDB | 4 · 6 · 7 · 11 |
| old 18 back control (D.1 #12) | 6 |
| old 19 count badge (D.1 #8): component · bar, menu, drawer | 3 · 10 |
| old 20 legend (D.1 #9): moved to `ui/` · drawn on the season list | 4 · 9 |
| old 21 topic row (D.1 #11): component · Système · Réglages, Maintenance | 4 · 5 · 6 |
| old 22 tokens (D.1 #16): system `cva` · settings · add screen · media · the rest | 5 · 6 · 7 · 9 · 13 |
| old 23 segmented choice (D.1 #14, Q4): size · add screen · drawer | 3 · 7 · 10 |
| old 25 status dot (D.1 #7, Q9): tone · veille's dot · episode dots | 4 · 5 · 9 |
| old 26 close | 13 |
| the harness budget (order 52), over at the midpoint | 12 |
| B-578, a candidate's poster picks it (order 97(2), moved from the defects fast lane) | 8 |
| Q5, Q6 (the season recovery) · Q7 (Découvrir's swipe) · Q11, Q12 (navigation) | not this lot: `maquette-season-recovery` · L16-bis · the navigation lot |
| The operator's defects: the candidate's poster B-578, the iPhone hamburger B-579, the Appearance selector B-580 | the defects fast lane (owed `unseen · menu` stays in the rule) |
| Owed `bevel · runs/row` · `overflow · run/log` | 5 |
| Owed `cut · card/requester` | 7 |
| Owed `cut · card/title`, `card/subtitle`, `tile/title`, `cast`, `segment`, `segment/count` | 8 |
| Owed `cut · shell/tab-bar` · `bevel · shell/connection-notice` | 10 |
