# Phase a·9 — « Arrivées »

A CONVERSION: `ui/card.tsx` (new file) draws the card on « Arrivées » and on the resolution screen,
and `flux` converts on « Arrivées ». The engine's card callers there go (DESIGN § 2.5, § 2.6; § 3,
row 16; INDEX's page order, D-L07-7).

## The proof FIRST

- **The oracle**: zero divergence on every « Arrivées » and resolution-screen state. A divergence
  elsewhere is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  no movement. `arrivals.py` and `take.py` read the same cards, so their counts stay.
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.
- `python3 scripts/check-poster-box.py` exit 0.

## The move

- **`ui/card.tsx` (new file).** It is the card, drawn by variants: cover, top, body, title, subtitle,
  meta, reason, caption, and the foot from a·8. It is under 400 non-blank lines and knows no domain
  (invariant 10): the feature passes the title, the lines and the actions.
- **Switched to `ui/card.tsx` (new file)**: `features/arrivals/page.tsx`,
  `features/arrivals/resolution-cards.tsx` and `features/arrivals/resolution-screen.tsx`. Every
  `cardHTML` call in `features/arrivals/` goes, and so does the `dangerouslySetInnerHTML` site that
  rendered it.
- **`flux` on « Arrivées ».** The emitter at `features/arrivals/page.tsx` draws through a flux
  variant. The `.flux` rules stay while `features/account/page.tsx`,
  `features/maintenance/page.tsx` and `features/system/page.tsx` still emit the class (a·15).
- **`legacy.css` rules are deleted when their LAST emitter converts, not by name.**
  - The phase re-takes the emit scan of DESIGN § 2.6 over the card classes: `card`, `cbody`,
    `ctop`, `ctitle`, `csub`, `cmeta`, `cov`, `creason`, `caption`, and the helper-only
    `cannotations`, `ccol`, `crating`, `dlabel`, `folder`, `frac`, `freshtag`, `st`, `d`, `now`,
    `blocked` and `strip`.
  - A rule emitted only by « Arrivées » dies here.
  - A rule `cardHTML` still emits for the acquisition tabs and the add screen stays until a·11, and
    the commit body names which.
- **`act="resolve"`.** The foot the engine's `cardHTML` draws keeps its `data-*` names, because
  L13b's verbs read them.
- **No identity switch here.** The resolution crossing keeps its title key until a·14, and nothing
  reads `ids` in this phase.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit if the engine lost a caller-only branch.

## Gate

Per INDEX « Gates ». In addition, the commit body lists the card rules that died and the ones that
wait for a·11.

## Commit

`refactor(maquette-l13): arrivals and the resolution screen draw the card as a component`
