# Phase 17 — No destruction without consent (NE-DOIT-PAS-6)

**No STOP C.** A PROOF over every destructive verb, where one hold reads the library alone.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `git grep -ln "dialog?\.open" -- frontend/maquette/design/src/features` → **6** files
  (`acquisition/abandon-verb.ts`, `add-verbs.ts`, `delete-set-aside-verb.ts`, `library/delete-dialog.ts`,
  `settings/panel-setting.ts`, `settings/secret-verbs.ts`); `grep -n "no confirmation" frontend/maquette/harness/audit2.py`
  → line **287**, the library's single delete only; `BUGS.md` index → B-229 and B-237 **`fixed #528`**.
- **Points ≈ 5.** R-L24-j 3 — for each DESTRUCTIVE verb (a deletion, a replacement, an abandon; L16's « Retirer de
  qBittorrent » once it exists), the dialog opens before any write, and cancelling sends nothing, read on the
  network; the list of verbs built by the phase from the six files and Maintenance's write commands, each named in
  the rule's docstring 1; the report 1.
- **Readers.** `harness/selection.py:131–134` (the bulk dialog names the ticked media) — kept, not merged.

## Red today

Read at the opening; a verb that writes before its dialog is a DEFECT found, reported first.

## Move

The rule only.

## Mutation

Fire the staged folder's deletion before its dialog → the network hold falls by name.

## Register

The map's NE-DOIT-PAS-6 owed half is discharged by #528; the whole-clause proof lands here; proposed at phase 20.

## Oracle: states that diverge, declared by name

None.

## Commit

`test(maquette-l24): every destructive act asks before it writes`
