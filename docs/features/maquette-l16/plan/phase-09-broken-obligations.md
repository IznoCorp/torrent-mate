# Phase 9 — The tracker's broken obligations (round 10 Q4)

An obligation the ENGINE broke, whose torrent has already left qBittorrent, is not lost: it reads on
its tracker's own entry, in the « Trackers » tab, as « N obligations rompues », a nested disclosure
(title, date) that unfolds, and a per-row « vu » clears it from the alert badge (DESIGN § 4.2, § 4.5).
**This phase files the « vu » write** (DESIGN § 2.3 item 7), the last of this lot's writes, with the
surface that calls it.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `git grep -n -w 'vu\|data-.*-seen' -- frontend/maquette/design/src` — the codebase's
  own « × » dismiss precedent (a per-row seen mark elsewhere in this app; the same shape, not a second
  one invented here). `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → `breached_at`, `released_at`, `title`, `source_tracker` among the 13 — a « rompue » obligation is
  `breached_at` set, `released_at` never set, and its torrent already absent from the downloads read
  phase 1 declared: a JOIN over two reads already answered, drawing a NEW `broken_obligations` field
  phase 1 added to the tracker summary's own schema (a demand, not a behaviour, at that phase). `ls
  frontend/maquette/design/src/mocks/seeds | wc -l` → 48 — a seeded broken obligation (its torrent
  absent, its `breached_at` set) is a NEW seed row.
- **Points ≈ 9.** The « vu » write declared new 2 and its mock route new — it flips one
  `broken_obligations` row's `seen` to `true`, moving the summary read the badge itself reads (DESIGN
  § 2.4) 2; the nested disclosure — the count, the unfolded rows, the « vu » control (≈ 35 new,
  `ui/disclosure.tsx` reused a second time, nested under phase 3/4's own) 3½; **R-L16-d re-aimed**
  (the badge's fourth component) with its new mutation 3 — a re-aim of phase 8's own rule (a
  derivation growing by a term), not a second new rule, the same shape phase 10 already takes for its
  own fourth reader; the state `tracker-broken-obligations`, needing a new seed row 2,
  `tracker-broken-obligations-open` re-using it 1; `fr.json` (`screens.trackers.brokenObligations`) 1.
  **Nearly at the ceiling; what to cut**: the disclosure's own body is the count and the date only (no
  free-text reason — the row's own title already says what it was).
- **Re-cut (2026-09-27, on `5e5ecd052`).** No row of any prior reading names this phase: it is entirely
  new, born of the auditor's rulings-coherence round (`review-archive/rulings-coherence-2026-09-27.md`),
  relayed after this redraw's own first pass had already numbered phases 1–16. Its insertion shifts
  every phase from the prior 9 onward up by one (the prior 9–16 become 10–17); the steward is told in
  the same message that carries this file.

A BEHAVIOUR change: a fact the engine already owns (a broken obligation) is surfaced for the first
time, with the ONE write this lot still owes — marking it seen.

## The proof FIRST

R-L16-d re-aimed (its label was bound in phase 8).

- **What it drives.** A tracker with at least one unseen broken obligation: read its collapsed count,
  unfold the list, mark one row « vu »; read the Trackers tab's badge before and after.
- **What it reads.** The count equals the number of UNSEEN broken obligations for that tracker
  (never the seen ones, never obligations still open); marking one « vu » calls the write
  (`window.__mocks.answered()`) and the count — and the badge's own fourth component — drop by one in
  the SAME render.
- **Red today.** No broken-obligation fact is drawn anywhere — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` makes the « vu » control message success without calling the write.
  The hold must fall, naming the operation.

## The move

- **The « vu » write**, declared in the maquette's contract (an operationId proposal, taking the
  obligation's own identity) and answered by a mock route that flips `seen: true` on the matching
  `broken_obligations` row of the tracker summary seed.
- **`features/trackers/trackers-tab.tsx`** — the collapsed count (`data-part="trackers/broken-obligations"`),
  the nested disclosure (`ui/disclosure.tsx`, a second use beside phase 4's policy one — each opens
  independently), a row per broken obligation (`trackers/broken-obligation-row`: title, date) with its
  « vu » control (`trackers/broken-obligation-seen`, `data-obligation-seen`).
- **`features/trackers/queries.ts`** — `alertOf` re-aimed to add the fourth component: the count of
  UNSEEN rows across every tracker's `broken_obligations`.
- **`harness/states/trackers.ts`** — `tracker-broken-obligations`, `tracker-broken-obligations-open`.
- **`i18n/fr.json`** — `screens.trackers.brokenObligations`.

## Mutation

R-L16-d's fourth-component mutation: message success without calling the « vu » write (above).

## Register

§ 18's alert clause gains its fourth component; round 10 Q4 reads `served`. Reported by phase 17.

## Oracle: states that diverge, declared by name

**None.** `tracker-broken-obligations` and `tracker-broken-obligations-open` are NEW, nested under
phases 3–4's own recorded entry — accepted, named, with the reason « L16 phase 9: an entry with a
broken obligation carries its count and its unfolded list ». Any divergence on an entry with NO broken
obligation is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for both new states.

## Commit

`feat(maquette-l16): a tracker's broken obligations, unfolded and clearable`
