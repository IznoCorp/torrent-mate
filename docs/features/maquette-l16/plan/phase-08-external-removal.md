# Phase 8 — An external removal is handled

An obligation whose torrent the operator removed by hand in qBittorrent reads `released_at` set with **no release call ever made from this
interface** — drawn as « Libérée — retrait externe », never as an anomaly, never as a silent disappearance from the list (NE-DOIT-PAS-5;
DESIGN § 4.4). The reconciliation itself — the backend noticing the removal — is a demand, not this lot's; the interface's job is to read the
state honestly once the field says so.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → 13 fields, `released_at` and `satisfied_at` among them: the state is already answerable by the read phase 1 declared. `ls
  frontend/maquette/design/src/mocks/seeds | wc -l` → 48 — a seeded obligation with `released_at` set and no release call in the session's own
  walk is a NEW seed row (phase 1's seeds are open obligations); it is derived from a real obligation row the backend answers, and
  `python3 scripts/check-mock-seeds.py` reads it. No mutation can produce this state against `main`: nothing there exists to mutate.
- **Points ≈ 8.** The row's read of `released_at` with no verb — « Libérée — retrait externe » on the SAME row shape the open obligations use,
  distinguished only by its closed state, never a second list (≈ 15 new) 1½; the state `obligation-released-externally`, needing its new seed
  row 2; **one new rule, R-L16-c** (its own seeded scenario) 3; `fr.json` (`screens.tracker.releasedExternally`) 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (the second half of its phase 5) → this phase **8**: moved by **the scale** and the
  cut by kind of change (phase 7's note); no ruling touched it.

A BEHAVIOUR change on a state the interface must recognise without ever having caused it.

## The proof FIRST

Its label R-L16-c is bound to the next free number.

- **What it drives.** A SEEDED obligation whose `released_at` is set with no release call anywhere in the session's own walk (the phase's seed,
  DESIGN § 2.4).
- **What it reads.** The row reading « Libérée — retrait externe », never still-open, never blank, never an unexplained gap.
- **Red today.** The row does not exist to read — fails against `main` for that reason; **no mutation is needed or possible** there (nothing to
  mutate), the same shape L20's phase 1 rules held for surfaces that do not exist yet. After the move the rule is proved the usual way: draw it as
  still open → it falls; draw it with no explanation → it falls too.

## The move

- **The external-removal read**: `ObligationItem.released_at` set with no accompanying verb call reads `screens.tracker.releasedExternally`
  (« Libérée — retrait externe »); the release verb's button is absent on a closed row.
- **The seed** and **`harness/states/trackers.ts`** — `obligation-released-externally`.
- **`i18n/fr.json`** — `screens.tracker.releasedExternally`.

## Mutation

The two above (still-open, and no explanation), each committed and restored separately.

## Register

§ 18's external-removal HANDLED case reads `served`, reported by phase 15.

## Oracle: states that diverge, declared by name

**None.** `obligation-released-externally` is NEW, drawn on `tracker/body`'s existing region. Any change to `tracker-detail`'s own recorded reading
beyond phase 7's accepted control is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `obligation-released-externally`.

## Commit

`feat(maquette-l16): an obligation released by a removal in qBittorrent reads as handled`
