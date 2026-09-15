# Phase 5 — The obligation's release verb

« Libérer une obligation » (§ 18's own dictated action), with a confirmation — NE-DOIT-PAS-6,
destroying a seed commitment without consent — and the external-removal case read as HANDLED, never
a silent anomaly (NE-DOIT-PAS-5).

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `grep -n "openDeleteDialog\|data-.*-confirm" frontend/maquette/design/src/features/*/`
  — the codebase's own confirmation precedent (the delete dialog L13c's phase c·1 already reads);
  this phase's confirmation follows the same shape (a transient state, no URL, D1). `python3 -c
  "import json;d=json.load(open('frontend/openapi.json'));print('release' in str(d['paths']))"` →
  `False` — no release operation exists in the backend's own contract either; phase 1 filed it as a
  demand (DESIGN § 2.3 item 5). `grep -n B-144\|B-257 BUGS.md` → both `open`/`fixed #534`
  respectively (B-257 already closed, naming L16 as the consumer of the alert half this phase does
  NOT carry — phase 6's).
- **Points ≈ 13.** The confirmation + the release call + the row's removal from the open list ≈ 4;
  one new rule (R-L16-b, the release itself) with its mutation ≈ 3; a SECOND new rule (R-L16-c, the
  external-removal HANDLED read, its own seeded scenario since no mutation can produce it against
  `main`) with its own proof ≈ 4; two named states (`obligation-release-confirm`,
  `obligation-released-externally`) ≈ 2. Under 15, no cut.

TWO kinds of change share this phase deliberately: a WRITE (the release verb) and a READ of a
state the interface must recognise without ever having caused it (the external removal). Both are
§ 18's single dictated action — « release », caused by the operator or by his own hand in
qBittorrent — so DESIGN treats them as one clause (§ 4.4) and this phase keeps them together rather
than splitting a single ruling into two commits.

## The proof FIRST

Two rules, bound to the next two free labels.

- **R-L16-b — what it drives.** From `/trackers/$name`, tap « Libérer l'obligation » on an open
  obligation, confirm.
- **R-L16-b — what it reads.** The confirmation naming the ratio still owed; the operation CALLED
  (`window.__mocks.answered()`); the obligation gone from the open list in the SAME render the
  operation answers.
- **R-L16-b — red today.** No verb exists — the network hold fails against `main` for that reason.
- **R-L16-b — mutation.** `scripts/mutate.sh` makes the confirm button message success without
  calling the release operation. The hold must fall.
- **R-L16-c — what it drives.** A SEEDED obligation whose `released_at` is set with no release call
  anywhere in the session's own walk (phase 1's mock scenario, DESIGN § 2.4).
- **R-L16-c — what it reads.** The row reading « Libérée — retrait externe », never still-open,
  never blank.
- **R-L16-c — red today.** The row does not exist to read — fails against `main` for that reason;
  **no mutation is needed or possible** (there is nothing on `main` to mutate), the same shape
  L20's phase 1 rules held for surfaces that do not exist yet.

## The move

- **The release verb**, registered in `lib/verbs.ts` (the L21 registry, DESIGN § 4.4's own
  precedent for a domain-free tap): `data-obligation-release`, opening the confirmation
  (`obligation-release-confirm`, transient, no URL — D1b rule 1).
- **The confirmation's copy** names what is lost: the ratio still owed against the policy's own
  `min_ratio` (phase 4), in words — never a bare « Confirmer ? ».
- **The external-removal read**: `ObligationItem.released_at` set with no accompanying verb call
  reads `screens.tracker.releasedExternally` (« Libérée — retrait externe ») on the SAME row shape
  the open obligations use, distinguished only by its now-closed state — never a second list.
- **`i18n/fr.json`** — `screens.tracker.releaseObligation`, `.releaseConfirmCost`,
  `.releasedExternally`.

## Mutation

R-L16-b: message success without calling the operation (above). R-L16-c carries no mutation — its
proof is the seeded scenario read correctly, the same species as every other surface this design
records as NEW against `main` (DESIGN § 4.8's closing line).

## Register

§ 18's dictated release action and its external-removal HANDLED case both read `served`, reported
by phase 8. DOIT-2's row is untouched here — its ratio-reason half is phase 6's.

## Oracle: states that diverge, declared by name

**None.** `obligation-release-confirm` and `obligation-released-externally` are NEW, both drawn on
`tracker/body`'s own existing region (phase 3) — the region's CONTENT changes with the new rows,
which the oracle records as new, not as a divergence of an existing state (D8: a state that did not
exist cannot diverge). Any change to `tracker-detail`'s own recorded reading (the empty-active
state, the loading/error twins) is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for both new states.

## Commit

`feat(maquette-l16): release an obligation early, and read an external removal as handled`
