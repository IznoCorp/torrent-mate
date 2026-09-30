# Phase 4 — The close: the lot's gate, the documents, the pull request

**Opening measure**: R-navigation-a with NO `owed` row left (`grep -c "owed" frontend/maquette/harness/navigation_edges.py`
→ 0); the emitters of DESIGN § 0.2's command re-counted on the head, each an edge id; the harness budget of order 52 is
retired (`docs/reference/method.md`).

## What changes

1. **The documents that still describe the old rule** (DESIGN § 7): `frontend/maquette/README.md` § « A layer is not a
   route » (`:837–864` on `f71a44f7b`) says what a menu page, a bar page and an in-page link each do on Retour — the
   sentence « A back from the destination then reaches where one was before opening the drawer » becomes true for
   menu pages and is said with its exception (bar pages). `check-maquette-comments.py --record` if a maquette comment
   moved.
2. **B-577** closed in `BUGS.md`: « échappé de » no rule walked a navigation edge and its Retour; « famille réparée
   par » R-navigation-a (its completeness hold); R-navigation-b's red reading on `f71a44f7b` and its mutation.
3. **Listed for the steward's docs pull request** (not the lot's to edit): `docs/reference/frontend-architecture.md`
   D1b rule 2 (`:152–155`) and `docs/reference/frame-survey.md:147`; `docs/reference/product-intent-map.md` DOIT-10's
   row gains R-navigation-a beside R82.
4. The patch bump above `main`; `git merge --no-edit origin/main` first.

## Acceptance

- The full suite (CI's `test` job its authority), `--a11y`, `scripts/harness-hold-counts.py --compare
  frontend/maquette/hold-counts-baseline.json` (`failed` read FIRST), `check-bug-register.py`, `check-intent-map.py`,
  `check-docs-cited-paths.py`, read by OUTPUT; `make lint`; the pre-push pytest `-n 2`.
- Each rule of the lot re-run BY NAME: R-navigation-a, R-navigation-b, and the re-aimed R82, R239.
- The whole table walked once more by finger at 369 px, from cold, every row: the reader round replays it at the
  seven widths (order 85) with ten claimed mutations drawn at random (order 66).

## Commit, and STOP B

`chore(maquette-navigation): the close — B-577 closed, the README says the amended § 16`; the pull request READY,
citing § 16 and DOIT-10, reported the second it exists.
