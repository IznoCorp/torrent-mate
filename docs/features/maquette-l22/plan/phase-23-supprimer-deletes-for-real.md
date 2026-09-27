# Phase 23 — « Supprimer » deletes a set-aside folder for real

**Born 2026-09-27 as « 15b »** (the cut of phase 15 at its opening; the operator's round 8, question 16 = B),
**numbered 21 by the triage's F51, then 23** (B-556 and B-557 took 21 and 22). It carries **M2** (the auditor's decision-coherence round, 2026-09-27) and **F40**
(it edits the contract).

**Opening measure (estimate — RE-MEASURED at the opening; > 15 → cut, one message):**

- **Q16 = B**: « Supprimer » in the folded « Mis de côté » is a REAL deletion of the staging folder, behind a
  confirmation with the same care as the library's. It names the FOLDER (there is no provider identity, as with
  « Abandonner »). « Abandonner » keeps the quarantine.
- **M2 — the confirmation reads qBittorrent AT THE GESTURE, not the ingest row.** The ingest row (`action: copied|moved`,
  `ingest.py:549-561`: ingest COPIES a seeding torrent and MOVES any other) gives the provenance only. The new
  operation reads qBittorrent when the confirmation opens:
  - arrival copied, torrent present with its files → « le torrent garde ses fichiers dans qBittorrent »;
  - torrent absent, or arrival moved → « c'est le seul exemplaire »;
  - qBittorrent silent → « inconnu », and the folder is treated as the only copy.
- **Demand F** (DESIGN § 6.2): a journaled delete on `/api/staging/media/{mediaId}`, and the read it confirms from
  (qBittorrent at the gesture). Its operationId joins L18's `pipeline.control` row (L18's to write).
- **Three named states**, one per wording (`keeps-files`, `only-copy`, `unknown` — names fixed at the opening).
  « Gone from disk → gone from the section » already holds (DESIGN § 7.3 item 4, R226).
- **F40**: `notFound` and `doneToday` leave `AcquisitionQueue`, the mock state, the seeds and the handlers
  (`state.ts`, `handlers/acquisition.ts`, `lib/queue.ts`); types regenerated; `compare-contracts.py --write` then
  `--check`; `check-mock-seeds`' classification updated. `takeable` keeps its reader (`follow-facts.ts`).
- **Points ≈ 15–17** (Q16 ≈ 13–15 at 15a's cut, + M2's third wording, + F40) → **likely cut at the opening**
  (the operation and its three wordings / F40).

## Red today

**R227 — « Supprimer » deletes, and says what it deletes**: in « Mis de côté », « Supprimer » opens a confirmation naming
the folder and one of the three wordings, read from the gesture's qBittorrent answer; confirmed, the delete is ANSWERED on
the network and the card leaves the section and does not come back on a re-read. Red: no such verb.

## Move

The operation declared (contract, mock, demand F), the verb, the confirmation (the library's dialog pattern), the three
states; F40's removals.

## Mutation

With the commit made first: the verb toasts without sending → falls; the wording read from the ingest row instead of the
gesture's answer → the « torrent gone » hold falls; « inconnu » read as « garde ses fichiers » → falls.

## Oracle: states that diverge, declared by name

The three new states; any other divergence is STOP A.

## Commit

`feat(maquette-l22): « Supprimer » deletes a set-aside folder, and says what it deletes`
