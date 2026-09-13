# Phase b·10 — The panel's return

A BEHAVIOUR change: Back from a screen opened from a panel reopens the panel, and the return is
drawn as `panel-down` in reverse (DESIGN § 8, R-L13-c; § 10, B-275). It reads the entry that b·9
writes.

## The proof FIRST

- **Bind the label to a number first**: the next free rule number, re-taken against `origin/main` as
  INDEX says.
- **R-L13-c — the return is drawn.** Back from a media screen reopens the panel under
  `::view-transition-new(leaving-panel)` running `panel-down` in reverse. Under
  `prefers-reduced-motion: reduce`, there is no animation.
  - **Red today, with no subject**: before this phase the panel is not reopened, so the pseudo-element
    never runs.
  - **Mutation**: the reverse keyframes are removed. The rule falls, naming the missing animation,
    and it stays green under `reduce`.
- **B-275's own reading, as a hold in the same rule.** `/media?panel=follow:…` → « Voir la fiche » →
  `/media/tmdb/…` → Back lands on `/media?panel=follow:…` with `#sheet[data-open]` PRESENT.
  - **Red today**: Back lands on `/` with the panel absent.
  - The drive is `transition.py`'s `hold_the_panel_departs` (R115) followed by `page.go_back()`.
- **R115 (`transition.py`) keeps its departure hold unchanged.** The departure stays
  `::view-transition-old(leaving-panel)` running `panel-down`.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on the states that show the panel returned**, each accepted with
  « B-275 » (D8). Any other divergence is STOP B.

## The move

- **Back reopens the panel.** The back handler in `app/layers.ts` (new file, a·3) reopens the panel recorded on the
  entry it lands on (b·9's `{ layer: "sheet", kind, subject }`), through the panel host by import.
- **The reverse keyframes.** They are written beside the existing `panel-down` declaration (the phase
  re-takes where it lives), under the motion preference, and never as an unconditional animation.
- **The return is captured.** The panel is captured as `leaving-panel` on the way back, exactly as it
  is on the way out.
- **B-275 closes** with the rule's reading.
- **What this does NOT touch.** `legacy.js` is untouched unless a remnant reads the entry. If one
  does, `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, the rule number is bound, and the red reading under both motion
preferences and the mutation go in the report.

## Commit

`feat(maquette-l13): back from a screen reopens the panel it came from and draws the return`
