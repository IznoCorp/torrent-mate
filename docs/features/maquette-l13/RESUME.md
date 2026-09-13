# L13a — resume brief for the successor

Written by the twelfth L13a implementer when it stood down with the full gate RED (context 50 %). Read it after
`docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything. This file only records state, rulings
and traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90; `main` had not moved at 18:30). Oracle reference `f1e7ac66`.
- a·1 … a·17: see `git show c194fca54:docs/features/maquette-l13/RESUME.md` (and the RESUMEs it points to). Then
  this session:
  - **a·17-bis** `f4b0732ae` `refactor(maquette-l13a): the harness states panel dies — its opener, its five verbs, its rules and its readers`
  - **a·18** `e2f510a8b` `chore(maquette-l13a): legacy.css, its guard and the rule that compared it to the variants are deleted` (ruling 59)
  - **a·19** `56da59aee` `chore(maquette-l13a): refonte.html is deleted and R72 keeps its two holds`
  - **repairs** `a99af0309` `fix(maquette-l13a): three rules of the full suite follow the conversion` — NOT replayed alone, NOT gated
  - the commit that adds this file.
- Gates, logs under `/private/tmp/tm-l13a/`, each postdating its commit:
  - a·17-bis on `f4b0732ae`: contracts 19 + 27, no violation; oracle no divergence; `message_above_harness.py` alone 2;
    mutation `.hbtn` z-index 53 → 70 → R163 FELL.
  - a·18 on `e2f510a8b`: contracts 18 + 26; oracle no divergence; `resolution_card` 12, `press` 15, `touch` 25 alone;
    mutation (the child's `[.ptr.loading_&]` animation removed) → NO RULE FELL (a blind spot, written in phase-a18's
    amendment).
  - a·19 on `56da59aee`: contracts 18 + 26; oracle no divergence; `shell.py` 3, `switchover.py` 11 alone; R72's two
    mutations by hand on `dist/` with `R72_SKIP_BUILD=1` (`a19-r72-mutations.sh`): (b) the module tag duplicated →
    (b) ALONE fell « 2 match(es) found »; (c) the bundle deleted → (c) ALONE fell; rebuild → 3/3.
  - **Full suite on `56da59aee` (`a19-full-suite.log`, 18:32): EXIT 1, four rules** — below.
- Records: `engine/legacy.js` 3 593 non-blank (not moved by these phases). `legacy.css`, `refonte.html`,
  `legacy-css-residue.json`, `check-legacy-css-residue.py`, `residue.py` (R80, number retired), `test_residue.py`,
  `harness/rename.mjs` deleted. `harness/factories.py` + `tests/scripts/test_factories.py` born (ruling 59).
  `comment-references-baseline.json` re-recorded in each phase. `hold-counts-baseline.json` NOT re-recorded.
- Version NOT bumped. No pull request. Pushed at this boundary (the stand-down report carries `git ls-remote`).

## The full suite's four falls

1. `images.py` — REPAIRED in `a99af0309`: `lib/navigation-entry.test.ts`'s fixture cited `assets/posters/silo.webp`,
   which does not exist; it cites `00008728.webp`.
2. `navigation.py` (R76) — REPAIRED: the state-driver exemption named `legacy.js`; a·1 moved the driver to
   `harness/drive.ts`. Re-aimed, measured (2, 0, 1).
3. `address.py` (R68) — REPAIRED: since a·15 `#view`'s `textContent` glued « Adresse » + the address + the next
   sentence; the surface is read as `innerText`, docstring says why.
4. **`bugs.py` — STOP B, NOT repaired.** Step: `bugs.py:31`, « 2 — Voir la fiche from a follow sheet »:
   `__go('followsheet-gaps')` produces the follow panel for « Les aventures de Tintin », then clicks « Voir la fiche »,
   which is absent. The reading, verbatim: `features/acquisition/follow-facts.ts:121` computes
   `hasSheet: (follow.ids ?? heldIdentity(title)?.ids) != null` ONCE, at production. Tintin has no entry in
   `follows.json`, so `follow` is the fallback `{ t: title, k: "show", … }` with no ids, and the driver's reset has
   emptied the query cache, so `heldIdentity` is null → no « Voir la fiche ». The identity lands by ~400 ms
   (`__carriedFor(Tintin).ids = {tvdb 72668, tmdb 1570, imdb tt0179552}`, `/api/library/incomplete` and
   `/api/media/tvdb/72668` in success) and the panel is never re-produced; re-produced at 3.4 s it shows « Voir la
   fiche ». At `f1e7ac66` it read `reference.sheetFor(title) != null`, synchronously. Introduced at a·14. Product scope:
   a follow panel opened cold (typed `?panel=follow:<title>`, a named state) for a medium with no follow entry loses
   « Voir la fiche » until reopened. Probe: `/private/tmp/tm-l13a/a19-probe-tintin.py` (log `a19-probe-tintin.log`),
   run under the browser mutex.
   - **A second reading of the same root, to diagnose in the same unit:** the query cache in that state holds two
     requests PENDING with an empty provider and id — `["/api/media","",""]` and `["/api/media","","","seasons"]` — a
     query fired before the identity is known.
   - **The repair of the STOP B is the STEWARD's ruling, pending at hand-over: do not open the full gate before it
     lands.**

## First acts of `Agent : l13a 13`, in order

1. Handshake; read this file, the brief, and ruling 58–60 in your handshake answer.
2. Replay `images.py`, `navigation.py`, `address.py` ALONE at their baseline counts (2, 11, 15) under the browser
   mutex, then the phase gate (contracts + oracle) on the repair commit. Commit before any mutation.
3. The STOP B repair per the ruling you will find in your handshake answer (and the empty-id queries with it), with its
   own gate; `bugs.py` alone at its baseline (14, a PASS/FAIL tally).
4. The full gate, in this order, telling the steward BEFORE `run.sh` no-flag, context ≤ 50 % at its opening:
   1. `TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class browser l13a sh frontend/maquette/harness/run.sh` — it exceeds a
      tool call's 10 min: run it in the background, output and exit code to files; no test beside it.
   2. `run.sh --a11y` at 0.
   3. `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json --jobs 2` under the
      mutex, `failed` read FIRST. Named movements: **R80 `residue.py` (19) gone; R163 `message_above_harness.py`
      3 → 2; R72 `shell.py` 4 → 3**; plus R80's PAIRS_FLOOR history (15 → 10 → 25 → 30 → 4 → 3) and any other,
      written in the commit body.
   4. `make check` under the tests lock (`HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder PYTEST_XDIST_AUTO_NUM_WORKERS=2
      sh scripts/heavy.sh --class test l13a make check`), zero failed AND zero errors.
   5. `python3 scripts/check-bug-register.py` and `python3 scripts/check-intent-map.py`, read by OUTPUT.
   6. `git remote update origin`; merge `origin/main` if it moved; bump `personalscraper/__init__.py` patch above main
      (0.98.90 → 0.98.91 if main has not moved; that file is the only one #595 bumped).
   7. Push under the tests lock (the pre-push hook runs the suite; background); open the PR READY with the imposed
      title `feat(maquette-l13a): what moves unchanged — the harness module, the ladder, the boot and the drawing leave the engine`;
      body per the brief, figures measured ONCE on the final head.
   8. `IMPLEMENTATION.md` « In flight » row written when the PR opens (wave, PR, version, brief, figures), set back to
      « None » in your LAST commit before the merge.
5. The reader line and the Mac-walk step owed since a·14 (in `c194fca54`'s RESUME, « Owed ») go to the PR body and
   the steward.

## Rulings — not to be reopened

1–57: see `git show c194fca54:docs/features/maquette-l13/RESUME.md`.

58. (steward) The lot's docs folder survives L13a — not the implementer's to act on.
59. (steward, a·18 STOP D) The reader half of `residue.py` moves as is into `harness/factories.py` for
    `resolution_card.py`; the pull's two engine-written states move onto the child `.spin` as parent-qualified
    utilities (`__reposPTR` resets `#ptr`'s class list). The same reset erasing `#ptr`'s own utilities is FILED for
    b·8. Dated amendment in `phase-a18`.
60. (steward, narrow authorizations) `docs/reference/frontend-architecture.md` may be edited ONLY to re-cite a deleted
    file's full path as `path@60530dbd8`, when `check-docs-cited-paths.py` refuses it; done at a·18 (line 592) and
    a·19 (two `refonte.html` lines). `CLAUDE.md` is never edited on a peer's word: the steward edits it.

## Owed to the steward (prose, not the implementer's)

- Ruling 61's named cold-open absence, for the reader brief and the operator's Mac walk, verbatim: « Open a follow panel
  cold (typed ?panel=follow:<title> or a named state) for a title without a follow entry: Voir la fiche appears once the
  identity read lands, the row refreshed in place, no new history entry. » / « ouvrir un panneau de suivi depuis une
  adresse tapée : Voir la fiche apparaît après un instant ».
- `CLAUDE.md`'s `design/refonte.html` mentions; the prose of `frontend-architecture.md` around the re-cited paths (R80,
  D3/D10, `legacy.css`, `refonte.html`); `frontend/maquette/README.md`'s `refonte.html` / ledger mentions.
- The a·18 blind spot (no rule reads that the pull's spinner turns) and a·14.2's two reads no rule fells, for the
  reader round.
- `harness/rename.mjs` deleted rather than re-aimed (its one input was the fragment's `<script>`), said in `56da59aee`.

## Method — unchanged, plus what this session added

- Everything in the earlier RESUMEs' « Method ».
- **`mutate.sh` cannot mutate a build output**: it rebuilds after mutating. A `dist/` mutation is done by hand over a
  fresh build with the rule's skip-build switch, then rebuilt (`a19-r72-mutations.sh`).
- **A path citation in a directive (`IMPLEMENTATION.md`, `BUGS.md`, `frontend-architecture.md`) of a deleted file is
  re-cited `path@60530dbd8`** — a sha on `main`, which survives the squash; a branch sha would not.
- **The full suite is the only tier that reads many rules**: three of its four falls were re-aims a phase gate
  (contracts + oracle) could not see. Replay the rules a phase's readers touch ALONE, not only the contracts tier.

## Traps met — each cost a run

- **A parallel tool call that `cd`s moves the shell for the others**: three runs in this session read the wrong
  directory (module-size exit 2, a residue record not found). Prefix every call with
  `cd /Users/izno/dev/worktrees/wave-l13a &&`, and never `cd` inside a parallel call.
- **zsh `====` in an echo is an expansion error**, and an unquoted `--include=*.py` is a glob error: quote them.
- **A non-vacuity floor falls when a conversion legitimately empties part of its scope** (`test_check_css_tokens`
  > 100 → 97; `check-viewport-directives` META_FLOOR 6 → 5; `check-poster-box` re-taken at 4): re-take at the measured
  count, said in the docstring and the body.
- **`check-docs-cited-paths.py` reads only backtick-terminated full paths**: `path::Test…` or a path followed by a
  space is not read; do not rewrite those.
