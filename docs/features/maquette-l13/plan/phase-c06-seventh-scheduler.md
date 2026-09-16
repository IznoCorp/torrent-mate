# Phase c·6 — The seventh scheduler

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `python3 -c "…json.load(open('design/src/mocks/seeds/settings.json'))…"`, the
  `passages` topic → exactly SIX `schedule` rows (health-check, search, grab, follow-detect,
  index-enrich, backfill-ids) — `personalscraper-index-full` is absent, confirming the phase's "six
  drawn against seven real". `grep -n SCHEDULERS_AS_SYSTEM_DRAWS -A8 harness/machine.py` → the
  harness's OWN reference table already carries all SEVEN, `personalscraper-index-full` included with
  its label "Analyse complète de l'index" — this table is the "Système" cross-check (`journal.check`
  at `machine.py:555`), a DIFFERENT hold from the `passages`-topic one this phase writes, and it stays
  green untouched (matches the phase's own claim). No tsc probe: JSON seed + Python hold, no type
  change. `grep -n B-327 BUGS.md` → `open`, 1×; BUGS.md ll. 2580-2608 already carry the ruling's own
  measured prose (four refusals, the two-vocabulary gap) that "goes back into `machine.py`
  VERBATIM" per the phase's proof section.
- **Points ≈ 4.** 1 seed row + the `settings.labels` addition ≈ 1; one hold, described as a
  restoration of the register's own kept wording rather than built from nothing, with its mutation
  ≈ 3 (lower end of the 2-3 range for a re-derived rather than invented rule). No named state found
  opening the `passages` topic specifically — the rule reads the DOM through the existing settings
  navigation, not a new `window.__go` entry.
- **Found (2026-09-15).** The two mechanisms are cleanly separate on this tree already: `machine.py`'s
  `SCHEDULERS_AS_SYSTEM_DRAWS` (the "Système" page's cross-check) already lists all seven jobs and
  needs no edit; only the `passages` topic's SEED is short one row, exactly as the phase says — no
  contradiction found here, unlike c·3/c·4.
- **Landed (2026-09-16).** The seed row; B-327's kept hold restored in `machine.py` with two re-aimed
  reads (the rubric opened by its row, the key taken out of the origin); `format.test.ts`'s two pins
  moved; the oracle accepted `settings-field-schedule` by name; the five disagreeing names stay
  accepted by name and the seventh is named alike. B-327 `to confirm`.

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
