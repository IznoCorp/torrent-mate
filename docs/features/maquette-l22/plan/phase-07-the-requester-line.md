# Phase 7 — The requester line

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -ci requester -- frontend/maquette/design/src` → no match before phase 1 (the field does not
  exist); phase 1 adds it to the contract, and the handler fills it from the account and the follows. `seeds/account.json`
  → `{name: "izno", email, avatar}` (the mock's single account, the Plex owner by construction). `card-markup.ts` is 109
  non-blank lines; the card's last text line today is the reason or the caption. `surfaces.card.*` in `fr.json` holds the
  card's own sentences.
- **Points ≈ 7.** The requester line in the card markup ≈ 8 lines 2; the seed's requester variation for the rule 1; the
  new rule with its mutation 3; one state (`acq-card-requester`) 1.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: no `requester` match
  before phase 1, `account.json` `{name: "izno", email, avatar}`, `card-markup.ts` 109 lines by `wc -l` (105 non-blank; the first
  drawing wrote « non-blank » for the `wc -l` figure) — identical. **Points 7 → 7; OPEN 11 (ruled B) confirms the phase's own
  boundary and adds nothing**: L22 draws the « ajouté par … » line only, and the reassign gesture is born with L18's rights
  model (DESIGN § 7.1).

Ruling 9: a card born of a direct add in qBittorrent reads « ajouté par Izno, dans qBittorrent »; a card born of a
request reads its requester's name. **The line is composed from the answer's requester and origin, never a constant**
(§13). **The gesture that REASSIGNS a request is L18's (OPEN 11, ruled B) and is not drawn here.**

## Red today

**R-L22-k — the requester, from the answer**: on `acq-card-requester`, the line reads « ajouté par <name>, dans qBittorrent »
and the name is the answer's requester — the seed changed to another name, the line follows.

**Red against `main`**: no card carries a requester line.

## Move

The card markup draws the requester line (last text line; it never competes with the title, the figure or the reason —
§12); the named state `acq-card-requester`.

## Mutation

With the commit made first: print a constant name → R-L22-k falls under the seeded change.

## Register

—

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded` (the arrival cards gain a line) with « L22 § 3.2: the requester line ». Any other
divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l22): an arrival card says who asked, from the answer`
