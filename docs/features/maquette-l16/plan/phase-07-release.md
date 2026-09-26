# Phase 7 — The obligation's release verb

« Libérer une obligation » (§ 18's own dictated action), with a confirmation — NE-DOIT-PAS-6, destroying a seed commitment without consent.
**The release operation is declared here**, with the surface that calls it (INDEX, « Why fifteen phases »): the third of the five demand rows
(DESIGN § 2.3 item 5). The external-removal case — an obligation released by a hand in qBittorrent — is phase 8's, the same clause read the
other way.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print('release' in str(d['paths']))"` → `False` — no release
  operation exists in the backend's own contract either; `python3 -c "import
  json;d=json.load(open('frontend/maquette/contract/openapi.json'));print('release' in str(d['paths']))"` → `False`. `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/features/library/delete-dialog.ts` → 183 and `features/library/verbs.ts` → 92: the codebase's own confirmation
  precedent (`openDeleteDialog`, `delete-dialog.ts:113`) — a transient state, no URL (D1); this phase's confirmation is the smaller case,
  ≈ 35 lines. `frontend/maquette/design/src/lib/verbs.ts` (120 non-blank lines) is the registry a `data-*` verb is declared in, spelled in
  the feature that owns it (`lib/` names no domain, invariant 10). `grep -n '^| B-144' BUGS.md` → `open`; `grep -n '^| B-257' BUGS.md` →
  `fixed #534` (already naming L16 as the consumer of the alert half this phase does NOT carry — phase 9's).
- **Points ≈ 15.** The release declared new 2 and its mock route new — it REMOVES the obligation from the open list it answers (DESIGN
  § 2.4) 2; the confirmation (≈ 35 new, naming what is lost) 3½; the verb — `features/trackers/verbs.ts` and its registration (≈ 15 new) 1½; the
  release button on the obligation row (≈ 8 edited) 1½; **one new rule, R-L16-b** with its mutation 3; the state `obligation-release-confirm`
  re-using phase 5's seed 1; `fr.json` (`screens.tracker.releaseObligation`, `.releaseConfirmCost`) 1. **At the ceiling; what to cut**: the
  confirmation (its copy and its state) as its own phase.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 5, both halves) 13 → this phase **15** and phase 8 **8**: moved by **the
  scale**; no ruling touched it. The first drawing kept a WRITE and a READ of an unseen state in one phase, « a single ruling in one commit »;
  on the scale the two do not fit under 15 together, and they are cut by KIND of change, the one rule L22 holds. The clause is unchanged.

A BEHAVIOUR change: no verb exists; this phase is the first to call it.

## The proof FIRST

Its label R-L16-b is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers/$name`, tap « Libérer l'obligation » on an open obligation, confirm.
- **What it reads.** The confirmation naming the ratio still owed (against the policy phase 6 put on screen); the operation CALLED
  (`window.__mocks.answered()`); the obligation gone from the open list in the SAME render the operation answers.
- **Red today.** No verb exists — the network hold fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` makes the confirm button message success without calling the release operation. The hold must fall.

## The move

- **The operation**, declared in the maquette's contract (`POST /api/acquisition/obligations/{id}/release`, or equivalent — an operationId
  proposal) and answered by a mock route that moves the obligation to `released_at` set, `breached_at` untouched (DESIGN § 2.4).
- **The release verb**, registered in `lib/verbs.ts` from `features/trackers/verbs.ts`: `data-obligation-release`, opening the confirmation
  (`obligation-release-confirm`, transient, no URL — D1b rule 1).
- **The confirmation's copy** names what is lost: the ratio still owed against the policy's own `min_ratio`, in words — never a bare
  « Confirmer ? ».
- **`i18n/fr.json`** — `screens.tracker.releaseObligation`, `.releaseConfirmCost`.

## Mutation

R-L16-b: message success without calling the operation (above).

## Register

§ 18's dictated release action reads `served`, reported by phase 15. DOIT-2's row is untouched here — its ratio-reason half is phase 11's.

## Oracle: states that diverge, declared by name

**None.** `obligation-release-confirm` is NEW, drawn over `tracker/body`; the obligation row gains a button, so `tracker-detail`'s recorded reading
(phases 4 and 5) changes by one control per open obligation — accepted, named, with the reason « L16 phase 7: an open obligation carries its
release verb ». Any other divergence is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `obligation-release-confirm`.

## Commit

`feat(maquette-l16): release an obligation early, after a confirmation that names what is lost`
