# Phase b·9 — One ladder shape

A BEHAVIOUR change: under decision D-L13-1, a layer left for an arrival KEEPS its entry, a redraw REPLACES
its entry, and the ten 240/260 ms close-then-wait timers go (DESIGN § 8; § 10, B-290 and B-397).

**STOP E: this phase does not open before the operator has read D-L13-1.** Phases b·1–b·8 do not wait for
it.

## The decision this phase executes

- **D-L13-1 (DESIGN § 8).** A layer left for an arrival keeps its entry, and Back onto that entry reopens
  the layer. The entry records `{ layer: "sheet", kind, subject }`, written by `app/panel-host.ts`, which
  already holds `openKind` and `openSubject`.
- **Telling the entries apart.** The handler (`app/layers.ts` (new file, a·3)) separates an entry left by an
  ARRIVAL, which reopens, from the leftover a tab-bar tap buries. That leftover is stepped over only when
  the page under it differs from the page it was opened on.
- **The rejected reading, so it is not re-proposed**: every sibling pops first. That keeps « one entry per
  gesture » and makes B-275 unanswerable.

## The proof FIRST

The labels are bound to numbers now:
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main`, and
the next free numbers are used.

- **R-L13-a — the pops are counted.** For each of the five openers from an open panel, three readings: going
  forward, `history.length` +1; Back ×1 lands on the panel, OPEN; Back ×2 lands on the list, closed.
  - **Red today** for the siblings (Back ×1 lands on the list), and for « Voir la fiche » (Back ×1 lands on
    the list with the panel shut, `__TSR_index` 3 → 1).
  - **Mutation**: the arrival pops the entry first. The rule falls, naming the opener and the entry crossed.
- **R-L13-b — a redraw does not stack.** Edit a setting three times in its panel, and one Back closes it.
  - **Red today** (B-397, the extra steps `settings_editing.py` walks).
  - **Mutation**: `redraw` pushes. The rule falls, naming the count of Backs.
- **`exits.py` (R103) refuses the gap instead of printing it.** Its inventory of the 240/260 ms timers
  becomes a hold that fails on any close-then-wait timer, which is R103's promised reversal.
  - **Red today** on the ten sites.
  - **Mutation**: one `setTimeout(…, 260)` restored. It falls, naming the file and the line.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and every
  new hold named.
- **The oracle may diverge ONLY on the states this decision redraws**, each accepted with « D-L13-1 » (D8).
  Any other divergence is STOP B.

## The move

- **Every sibling opener takes the one shape**: `mediasheet`, `journey`, `resolve`, `releases`, `profile`,
  and the take that B-290 names. The ten timers are deleted from the feature and frame verbs they moved into
  in b·1–b·7.
- **`producePanel`'s deferred path.** `openOnCurrentEntry`'s special case becomes the general path. B-398's
  counting in `switchPageFromLayer` stays, because it belongs to the page switch.
- **B-397.** Re-producing on the entry that already records the panel REPLACES it (D1b rule 1).
- **B-290 and B-397 close** with the rules' readings.

## Gate

Per INDEX « Gates ». In addition, the rule numbers are bound, and each rule's red reading and mutation go in
the report.

## Commit

`feat(maquette-l13): a layer left for an arrival keeps its entry and a redraw replaces it`
