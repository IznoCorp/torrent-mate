# Phase a·19 — `refonte.html` and R72

A CONVERSION by deletion: `refonte.html` is deleted, R72 keeps holds (b) and (c), each mutation-tested, and the ledger lives
in history (DESIGN § 7). This is the LAST phase of L13a.

## The proof FIRST

- **R72 (`shell.py`), renegotiated.**
  - Hold (a), « the fragment is injected verbatim once », has no subject. It is retired in
    `frontend/maquette/regions.json`'s R72 entry, with the reason and the mutation of record removed.
  - Holds (b) and (c) stay. With the commit made first, each is seen to fall ALONE through `scripts/mutate.sh`:
    - **(b)**: remove the one module script tag from the build output → (b) alone falls;
    - **(c)**: delete the bundle under `dist/vite/` → (c) alone falls.
  - Restore after each, rebuild, and read R72 green. The two fall readings go in the report.
- **R73 (`switchover.py`) keeps its count.** Its copied build input and its « the edited source is rebuilt » probe move to
  `index.html`, said in its docstring.
- **The oracle**: zero divergence.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST. The only expected movement
  is R72 losing hold (a), written in the commit body.

## The move — the sixteen path readers (DESIGN § 7)

- **The build**:
  - `vite.config.mjs:38`: the injection goes;
  - `build-identity.mjs:26`: the path leaves the hash inputs, and `tests/scripts/test_build_identity.py:35` mirrors the
    tuple.
- **The host.** `serve.py:112`: the « missing » page goes, with its copy in `frontend/maquette/design/src/i18n/fr.json`.
- **The harness**:
  - `shell.py:49` (R72, above);
  - `common.py:152`: the path leaves the design-source corpus;
  - `palette.py:30`: an unused constant, deleted;
  - `switchover.py:61,222` (R73, above);
  - `rename.mjs:25`: the fragment leaves the tool's inputs.
- **The scripts**:
  - `scripts/check-css-tokens.py:80`: it fails on absence today, so its fragment input goes;
  - `scripts/csstokens_login.py:33`, `scripts/csstokens_ranks.py:61`, `scripts/nofrench_lexicon.py:51`,
    `scripts/check-tailwind-confinement.py:92` and `scripts/check-compositor-css.py:115` each drop the path.
- **Beside those sixteen, re-taken rather than assumed.** The `refonte` word exemption in `scripts/nofrench_lexicon.py`,
  and the comment citations in `design/src` that name the file as the reference, are rewritten to cite it by commit.
- **The ledger's home is history.** No document is created, because a copy in the tree is the archive the documentation
  model removed. L13a's post-merge gesture cites `frontend/maquette/design/refonte.html@<L13a's squash parent>` from the
  plan's L07 entry, which the steward amends.
- **The reference docs** (`CLAUDE.md`, the plan) that name `design/refonte.html` are the steward's to amend. The report
  lists them.

## Gate

Per INDEX « Gates ».

**Before L13a's pull request (STOP C)**: the full suite (`run.sh`, no flag) with no failure; the `--a11y` tier at 0;
`harness-hold-counts.py --compare` with `failed` read first and every movement of L13a written; `make check` at zero
failures and zero errors; `python3 scripts/check-bug-register.py` and `python3 scripts/check-intent-map.py` read by
OUTPUT. The steward is told before the full-suite run. **STOP C: the pull request.**

## Commit

`chore(maquette-l13): refonte.html is deleted and R72 keeps its two mutation-tested holds`
