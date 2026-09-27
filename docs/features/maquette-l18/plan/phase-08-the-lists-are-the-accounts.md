# Phase 8 — The lists are the account's

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `wc -l frontend/maquette/design/src/features/acquisition/queries.ts frontend/maquette/design/src/features/acquisition/follows-tab.tsx frontend/maquette/design/src/features/acquisition/now-tab.tsx` → **342, 293, 142**; `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/follows.json'))))"` → **14** follows.
- `git grep -ci requester -- frontend/maquette/design/src` → no match today. **L22 phases 1 and 7 add the requester and draw its line; this phase's opening measure re-runs the grep** and reads what the answers carry by then.
- The reads that carry a list: `readAcquisitionQueue` (`/api/acquisition/to-handle`), `readFollows`, `readStaging` (the arrivals L22 turns into cards). `frontend/maquette/design/src/lib/queue.ts` derives the queue's counts in ONE place (`stagingKey`, `queueKey`, lines 102–106) — the single derivation the counts must keep reading.
- **Does not exist on this head**: L22's fourth tab « À traiter », its count and the bar's badge on it.
- **Points ≈ 15.** three handlers re-answered by identity — `readAcquisitionQueue`, `readFollows`, `readStaging` (3) + `seeds/invented-requests.json`, three cards and two follows requested by invented accounts (`x-unseeded`, read only under the dial), ≈ 60 new lines (6) + R-L18-g with its mutations (3) + three states — `acq-household`, `acq-household-sees-all`, `acq-operator-all` (3).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: the two invented follows go to phase 9.

**DESIGN § 3.4 points 1 and 3.** By default an account sees only what it requested; with the option it sees the rest read-only. The filter is the backend's (the answers differ by caller); the mock answers the dialled identity's subset. **Every count reads the same subset** — the tab counts, the bar's badge and the list (§ 13, one derivation). The invented requests exist only while `setInventedRequests(true)`: **no real row is re-attributed** and every existing state is unmoved.

## Red today

**R-L18-g — the lists are the account's, and every count agrees**: for each of `household-member`, `household-member-sees-all`, `guest` and `izno`, the cards and follows drawn are exactly the identity's subset, the tab counts and the bar's badge equal the list; **the option is proved on both values** (the pair of § 2.2).

**Red against `main`**: every identity reads every row.

## Move

The handlers, the invented seed, the three states.

## Mutation

With the commit made first: read the unfiltered answer → R-L18-g falls; count the unfiltered set in the badge → the count hold falls; ignore the option → the pair falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** — the invented rows are unreadable at rest and the Operator's lists are unchanged. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): an account's acquisition lists are its own, or all with the option`
