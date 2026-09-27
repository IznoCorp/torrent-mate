# Phase 6 — Retirer de qBittorrent

« Retirer de qBittorrent » (ORGANISATION RULING 18), replacing the prior reading's obligation-release
verb outright: the operator's own gesture targets a TORRENT's entry, not an obligation id, with «
Supprimer les fichiers » checked by default, decheckable. **The removal operation is declared here**,
with the surface that calls it (INDEX, « Why sixteen phases »): the fifth of the demand rows (DESIGN
§ 2.3 item 5). The SINGLE-entry case is this phase's; the grouped removal across shared files and the
external-removal read are phase 7's, the same clause split by kind of change.

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
  SINGLE-entry case only 2; the confirmation (≈ 25 new, the default-checked copy) 2½; the verb —
  `features/trackers/verbs.ts` and its registration in `lib/verbs.ts` (≈ 15 new) 1½; the button on the
  torrent row (≈ 8 edited) 1½; **one new rule, R-L16-c** (the single-entry case) with its mutation 3;
  the state `torrent-remove-confirm`, needing a new seed row (a torrent with no shared files, the
  simple case) 2; `fr.json` (`screens.torrents.removeFromQbittorrent`, the default confirmation copy)
  1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 7 (15, « the release verb ») is
  REPLACED, not renumbered: ruling 18 changes what the gesture targets (a torrent's qBittorrent entry,
  not an obligation id) and adds the file-deletion default the prior reading never had — F15's own
  finding (no id, no cause on the release) is answered by the new shape rather than patched onto the
  old one.

A BEHAVIOUR change: no removal gesture exists anywhere; this phase is the first to call it.

## The proof FIRST

Its label R-L16-c is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers?tab=torrents`, tap « Retirer de qBittorrent » on a torrent with
  no shared files, confirm with « Supprimer les fichiers » left checked.
- **What it reads.** The operation CALLED (`window.__mocks.answered()`); the row gone from the Torrents
  tab, and its matching obligation's `released_at` set, in the SAME render the operation answers.
- **Red today.** No gesture exists — the network hold fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` makes the confirm button message success without calling the
  removal operation. The hold must fall.

## The move

- **The operation**, declared in the maquette's contract (a removal verb, operationId a proposal,
  taking the entry's identity and the delete-files boolean) and answered by a mock route that removes
  the matching download and moves its obligation to `released_at` set.
- **The removal verb**, registered in `lib/verbs.ts` from `features/trackers/verbs.ts`:
  `data-torrent-remove`, opening `torrent-remove-confirm` (transient, no URL — D1b rule 1), «
  Supprimer les fichiers » checked by default.
- **`i18n/fr.json`** — `screens.torrents.removeFromQbittorrent`, the default confirmation's copy (a
  physical file deletion — the same weight NE-DOIT-PAS-6 already carries elsewhere in this codebase).

## Mutation

R-L16-c: message success without calling the operation (above).

## Register

§ 18's dictated release action, RESHAPED by ruling 18, reads `served` for the single-entry case; the
grouped removal and the external-removal read are phase 7's. Reported precisely by phase 16.

## Oracle: states that diverge, declared by name

**None.** `torrent-remove-confirm` is NEW, drawn over `trackers/body`; the torrent row gains a button,
so `torrents-list`'s recorded reading (phase 5) changes by one control per row — accepted, named, with
the reason « L16 phase 6: every active entry carries its removal gesture ». Any other divergence is
**STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `torrent-remove-confirm`.

## Commit

`feat(maquette-l16): remove a torrent from qBittorrent, its files deleted by default`
