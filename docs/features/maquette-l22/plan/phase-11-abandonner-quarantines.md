# Phase 11 — « Abandonner » quarantines the folder

**Opening measure (2026-09-26, on `ba6a36cc9`; a phase born of the round-5 rulings, cut out of the first drawing's phase 9 by
OPEN 10):**

- **Commands.** `python3 -c "import json;p=json.load(open('frontend/maquette/contract/openapi.json'))['paths']['/api/staging/media/{mediaId}/discard']['post'];print(p['summary'], list(p['responses']['200']['content']['application/json']['schema']['properties']))"`
  → **« Leave a staged item where it is »**, answering `['ok']`: the maquette's contract declares `discardStagedMedia` as the
  opposite of what OPEN 10 rules. `sed -n 105p docs/reference/frontend-backend-demands.md` → the backend's operation answers
  `detail`, `journaled`, `media_id`, `quarantine_path`, none of which the interface declares. The mock:
  `frontend/maquette/design/src/mocks/handlers/staging.ts:108` (`discardStagedMedia`, 128 lines in the file), which walks the
  three lists (`FROM_REAL`, `FROM_DENSE`, `FROM_BLOCKED`) and answers `{ok}`. `git grep -n 'discardStagedMedia' -- frontend/maquette/design/src/features frontend/maquette/design/src/lib | wc -l`
  → **0**: nothing calls it. The confirmation's pattern: `features/library/delete-dialog.ts` (193 lines, the library's own
  dialog, which names what it deletes; the named state `Médiathèque — dialogue de suppression`, `harness/states/library.ts:108`),
  built on the shell's `dialog` door (`lib/shell-doors`) and the `DialogDescriptor` of `ui/dialog/contract` — which Acquisition
  may use, where it may not import the library (invariant 7). `git grep -n -w -i 'quarantine' -- frontend/maquette/design/src`
  → no match.
- **Points ≈ 12.** `discardStagedMedia` edited in the contract (its summary and the two fields the card and its toast read) 1;
  the mock re-answered, so the card leaves « À traiter » and the answer carries `journaled` and `quarantine_path` 1; the verb ≈ 20
  lines written 2; the confirmation, a descriptor for the shell's dialog door, ≈ 30 lines written 3; the words (the question that
  names the medium, the two buttons, the toast) as `fr.json` keys 1; one named state (`acq-abandon-confirm`) 1; the new rule with
  its mutations 3.

OPEN 10 (ruled B, 2026-09-26): « Abandonner » quarantines the folder — `discardStagedMedia`, journaled, `quarantine_path` — after
a confirmation that NAMES the medium (NE-DOIT-PAS-6: « Détruire sans consentement. Confirmation explicite + identité par
provider-ID »); the card leaves « À traiter ». The other reading (abandon the tunnel, leave the files) was refused. **This is not
a sixth demand row**: the register already has one for the operation (line 105), and re-declaring it to what the interface
requires makes that row shrink (DESIGN § 6.2).

## Red today

**R-L22-u — « Abandonner » quarantines, after a confirmation that names the medium** (DESIGN § 5), walked by finger on the
tunnel-error card of `acq-todo-loaded`:

- a tap opens `acq-abandon-confirm`, whose text contains the card's title, and NOTHING is sent yet (`window.__mocks.answered()`
  holds no discard);
- confirming sends `discardStagedMedia` (answered on the network, with its `quarantine_path`) and the card leaves « À traiter »;
- cancelling sends nothing and the card stays.

**Red against `main`**: the card has no « Abandonner » and nothing calls the operation.

## Move

1. The contract: re-declare `discardStagedMedia` to quarantine (its summary; `journaled` and `quarantine_path` in its answer),
   then `python3 scripts/compare-contracts.py --write`, `--check`, and the generated types. **Read the counters and put them in
   the report, before and after**: the operation's row in the register's « backend has and the interface does not use » column
   loses its two fields.
2. The mock answers `journaled` and a `quarantine_path` and removes the card from « À traiter » (D7).
3. « Abandonner » is drawn on the tunnel-error card, beside « Relancer »; the verb opens the confirmation through the shell's
   dialog door; only the confirmation calls the operation.
4. The named state `acq-abandon-confirm`, in `harness/states/tunnel.ts`.

## Mutation

With the commit made first: skip the confirmation → the « nothing sent yet » hold falls; confirm without naming the medium →
the name hold falls; send on cancel → it falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-todo-loaded` — the tunnel-error card gains « Abandonner » — accepted with « L22 § 3.3: « Abandonner » on a tunnel error ».
`acq-abandon-confirm` is NEW and recorded. Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`; `python3 scripts/compare-contracts.py --check`; `--a11y` over
`acq-abandon-confirm` (the dialog, both themes).

## Commit

`feat(maquette-l22): « Abandonner » quarantines the folder after a confirmation that names the medium`
