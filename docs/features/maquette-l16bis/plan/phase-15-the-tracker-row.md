# Phase 15 — The tracker row and the one chevron

**STOP C: DECIDED 3** (2026-09-29, PR #637 — DESIGN § 5): the row opens a bottom PANEL, like the torrent card — the
activation switch stays on the row. **DECIDED 4**: the seasons' chevron becomes `ui/Disclosure`'s ONLY drawing.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `git grep -n "summary::before" -- 'frontend/maquette/design/src/*.ts'` → **3** drawings
  (`ui/variants/surfaces.ts:407`, `features/acquisition/variants.ts:48`, `features/media/variants.ts:226`);
  `grep -cv '^\s*$' frontend/maquette/design/src/features/trackers/trackers-tab.tsx` → **230**.
- **Points ≈ 13.** Per DECIDED 3: the row's body opens a panel `tracker:<name>` holding the policy rows (the
  `setting` door unchanged, RULINGS 2), the cross-seed and upload places, the broken obligations and « Voir les
  torrents » (≈ 50 lines edited) 6; `trackers-entry-open` and `tracker-broken-obligations-open` re-drawn as the panel
  2; R-L16-b and the broken-obligation holds re-aimed OUT LOUD onto the panel 2. Per DECIDED 4: `ui/Disclosure` draws
  the seasons' chevron (≈ 5 lines) 1; the report 2.
- **Readers.** `trackers/entry` is read by `trackers_alert.py`, `trackers_roster.py`, `deferred_reason.py`,
  `trackers_page.py`, `trackers_policy.py` — the part kept on the row; `deferred_reason.py` lands on
  `trackers:c411` and expects the entry OPEN — now the panel open (DECIDED 3).

## Red today

No rule of this lot — this phase re-aims L16's rules; the rule suite of the Trackers group is read red on the
re-aimed holds first.

## Move

1. The chevron is changed in `ui/Disclosure` only; the seasons and « par identifiant » are the conformity train's
   (the guard arm of DESIGN § 1.9).
2. A landing naming a tracker opens its panel (DECIDED 3).

## Mutation

Open the policy from a second, feature-drawn panel kind → R-L16-b's one-door hold falls.

## Register

The defect « a component redrawn » is closed for this page by phase 16.

## Oracle: states that diverge, declared by name

Every « Trackers » state and every state drawing a `Disclosure` (the chevron), declared by script.

## Commit

`feat(maquette-l16bis): the tracker row takes the app's form and its one chevron`
