# Phase 6 — Retirer de qBittorrent

« Retirer de qBittorrent » (ORGANISATION RULING 18), REPLACING the prior reading's obligation-release
verb outright — confirmed round 10 Q3 = A, **F15 REPLACED, not merely corrected**: there is no
separate release operation. The operator's own gesture targets a TORRENT's entry, not an obligation
id, with « Supprimer les fichiers » checked by default, decheckable, and it CLOSES any running
obligation as `released_at` set, never left reading in breach (round 10 M4). **The removal operation
is declared here**, with the surface that calls it (INDEX, « Why seventeen phases »): the fifth of the
demand rows (DESIGN § 2.3 item 5). The SINGLE-entry case is this phase's; the grouped removal across
shared files and the external-removal read are phase 7's, the same clause split by kind of change.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print('release' in str(d['paths']), 'remove' in str(d['paths']).lower())"`
  → `False False` — no release AND no removal operation exists in the backend's own contract either;
  the same on `frontend/maquette/contract/openapi.json` → `False False`. `grep -cve
  '^[[:space:]]*$' frontend/maquette/design/src/features/library/delete-dialog.ts` → 183 (the
  codebase's own confirmation precedent, `openDeleteDialog` — a transient state, no URL, D1); this
  phase's confirmation is a smaller case, ≈ 30 lines, its default already decided (checked). `grep -n
  '^| B-144' BUGS.md` → `open`.
- **Points ≈ 15.** The removal declared new 2 and its mock route new — it REMOVES the entry from the
  downloads seed and moves the matching obligation to `released_at` set (DESIGN § 2.4), the
  SINGLE-entry case only 2; the confirmation, both its default copy AND its obligation-naming branch
  (round 10 M4, ≈ 30 new) 3; the verb and its wiring — `features/trackers/verbs.ts`, its registration
  in `lib/verbs.ts`, the button on the torrent row (≈ 20 new/edited) 2; **one new rule, R-L16-c** (the
  single-entry case) with its mutation 3; two states — `torrent-remove-confirm`, needing a new seed
  row (a torrent with no shared files, no running obligation) 2, `torrent-remove-confirm-obligation`
  re-using phase 1's own obligations seed (a torrent WITH one) 1; `fr.json`
  (`screens.torrents.removeFromQbittorrent`, the obligation-naming copy) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 7 (15, « the release verb ») is
  REPLACED, not renumbered: ruling 18 changes what the gesture targets (a torrent's qBittorrent entry,
  not an obligation id) and adds the file-deletion default the prior reading never had — F15's own
  finding (no id, no cause on the release) is answered by the new shape rather than patched onto the
  old one.

A BEHAVIOUR change: no removal gesture exists anywhere; this phase is the first to call it.

## The proof FIRST

Its label R-L16-c is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers?tab=torrents`, tap « Retirer de qBittorrent » on a torrent with a
  running obligation and no shared files, confirm with « Supprimer les fichiers » left checked;
  separately, the same tap with the checkbox UNCHECKED.
- **What it reads.** The operation CALLED (`window.__mocks.answered()`); the row gone from the Torrents
  tab, and its matching obligation's `released_at` set (never left `breached_at`-only, round 10 M4),
  in the SAME render the operation answers; the confirmation NAMES the tracker whenever a running
  obligation exists, whatever the checkbox reads (round 10 M4 — a minimum beyond ruling 18's own
  words).
- **Red today.** No gesture exists — the network hold fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` makes the confirm button message success without calling the
  removal operation. The hold must fall. A second mutation skips the confirmation's tracker name when
  the checkbox is unchecked but an obligation runs — the hold must fall too, naming the missing
  confirmation.

## The move

- **The operation**, declared in the maquette's contract (a removal verb, operationId a proposal,
  taking the entry's identity and the delete-files boolean) and answered by a mock route that removes
  the matching download and moves its obligation to `released_at` set.
- **The removal verb**, registered in `lib/verbs.ts` from `features/trackers/verbs.ts`:
  `data-torrent-remove`, opening `torrent-remove-confirm` (transient, no URL — D1b rule 1), «
  Supprimer les fichiers » checked by default, and NAMING the tracker whenever the entry carries a
  running obligation, regardless of the checkbox (round 10 M4).
- **`i18n/fr.json`** — `screens.torrents.removeFromQbittorrent`, the default confirmation's copy (a
  physical file deletion — the same weight NE-DOIT-PAS-6 already carries elsewhere in this codebase),
  and its obligation-naming copy for the checkbox-independent case.

## Mutation

Two, as above — each committed and restored separately.

## Register

§ 18's dictated release action, RESHAPED by ruling 18, reads `served` for the single-entry case; the
grouped removal and the external-removal read are phase 7's. Reported precisely by phase 17.

## Oracle: states that diverge, declared by name

**None.** `torrent-remove-confirm` and `torrent-remove-confirm-obligation` are NEW, drawn over
`trackers/body`; the torrent row gains a button, so `torrents-list`'s recorded reading (phase 5)
changes by one control per row — accepted, named, with the reason « L16 phase 6: every active entry
carries its removal gesture ». Any other divergence is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for both new states.

## Commit

`feat(maquette-l16): remove a torrent from qBittorrent, its files deleted by default`
