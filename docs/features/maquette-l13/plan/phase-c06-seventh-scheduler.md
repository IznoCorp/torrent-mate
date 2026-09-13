# Phase c·6 — The seventh scheduler

A BEHAVIOUR change: « Réglages » draws the seventh scheduler, the hold B-327 kept whole is restored,
and one job has one name (DESIGN § 10, B-327). It relies on `SETTINGS` being a seed since a·16, so
the missing row is one seed row.

## The proof FIRST

- **The hold B-327's entry keeps whole goes back into `machine.py` VERBATIM.** Its name: « every
  scheduler the machine runs has a row on Réglages, and no row names one it does not ».
  - It reads the drawn keys of `[data-part="setting/row"]` / `[data-part="setting/origin"]` on the
    `passages` topic as a SET, compared with the machine's real schedulers.
  - Its two seam reads (`window.SETTINGS_STATE.topic`, `applyState`) are re-taken against a·1 and
    a·16. Where the name moved, the hold is re-aimed and says so.
- **Red first.** Run it against the seed as it stands, and it prints the entry's FAIL: six drawn
  against seven real, `personalscraper-index-full` missing.
- **The single vocabulary.** The two holds #567 kept in `machine.py` (the label table names every
  scheduler; a label the table shares with « Système » keeps that name) stay green, with their
  counts unchanged.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes the new seed row. The
  restored hold falls, naming `personalscraper-index-full`.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the restored hold named.
- **The oracle may diverge ONLY on « Réglages »' `passages` states**, each accepted with « B-327 »
  (D8).

## The move

- **The seed.** The `passages` topic of `design/src/mocks/seeds/settings.json` gains the
  `personalscraper-index-full` row.
- **One job, one name.** The row is labelled in « Système »'s own words through `settings.labels`,
  so no third vocabulary appears. The phase re-takes the five names that differ between « Réglages »
  and « Système » (the entry lists them) and says whether this lot's ruling unifies them or keeps
  them accepted by name.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exits 0. The family is `converted`, so
  no engine correspondence remains to refuse the edit.
- **B-327's done-when.** « Réglages » draws seven, the hold is in `machine.py` and green, and one job
  has one name.

## Gate

Per INDEX « Gates ». In addition, B-327 closes with the restored hold's red reading and its mutation.

## Commit

`fix(maquette-l13): settings list the seventh scheduler and the held-back hold is restored`
