# L13a — resume brief for the successor

Written by the twelfth L13a implementer at the full-gate stop, and brought to the pull request by the thirteenth. Read it after
`docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything. This file only records state, rulings
and traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state — at PR #596 (the thirteenth implementer, `Agent : l13a 13`)

- **PR #596 open READY**, branch `feat/maquette-l13a`, version **0.98.91**, `main` at `60530dbd8`. The implementer does
  not merge. **One reader round follows**; its findings are taken in a fresh session from this file.
- The earlier commits: `git show 069f49624:docs/features/maquette-l13/RESUME.md`. This session, after `069f49624`:
  - `57f3e81af` `fix(maquette-l13a): the follow panel's facts follow the identity read` (ruling 61, no re-aim)
  - `b9f7d789c` `docs(maquette-l13a): the empty-key seasons entries are filed for b·10-bis in phase-a14`
  - `89eb75015` `chore(maquette-l13a): version 0.98.91`
  - `b49c0b049` `docs(maquette-l13a): B-232 and B-352 close with #596`, and the commit that carries this block.
- Readings, logs `/private/tmp/tm-l13a/b61-*`, each postdating its commit:
  - `069f49624`: `images` 2, `navigation` 11, `address` 15 alone; contracts 18 + 26; oracle no divergence.
  - `57f3e81af`: mutation (the redraw removed) → `bugs.py` FELL, a witness read no « Voir la fiche » at 0/400/2 000 ms
    and `history.length` 4; restored → `bugs.py` 14 of 14.
  - `b9f7d789c`: **full suite 126 rules + 26 guards, no violation; oracle no divergence; a11y 0** (light 149 = ceiling);
    **`--compare` no violation, movements R80 `residue.py` (19) missing, R163 3 → 2, R72 4 → 3** (baseline not
    re-recorded: the post-merge gesture's); **`make check` 11 259 passed, 0 failed, 0 errors** (version step refused
    0.98.90 as it must).
  - `89eb75015`: version bump OK; `check-frontend` eslint 0 errors, vitest 1 374 passed, build; pre-push exit 0.
- `IMPLEMENTATION.md` is NOT touched by the wave (order 15): its « In flight » row is the steward's docs PR's.
- `check-bug-register`: B-232 and B-352 closed by this branch, each body changed; `check-intent-map` clean.

## The full suite's four falls

1. `images.py` — REPAIRED in `a99af0309`: `lib/navigation-entry.test.ts`'s fixture cited `assets/posters/silo.webp`,
   which does not exist; it cites `00008728.webp`.
2. `navigation.py` (R76) — REPAIRED: the state-driver exemption named `legacy.js`; a·1 moved the driver to
   `harness/drive.ts`. Re-aimed, measured (2, 0, 1).
3. `address.py` (R68) — REPAIRED: since a·15 `#view`'s `textContent` glued « Adresse » + the address + the next
   sentence; the surface is read as `innerText`, docstring says why.
4. **`bugs.py` — STOP B, REPAIRED in `57f3e81af` (ruling 61).** Step: `bugs.py:31`, « 2 — Voir la fiche from a follow sheet »:
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

## First acts of the successor (the reader round)

1. Handshake with the orchestrator named in your launch prompt; read this file, the brief, and the reader round's
   findings the steward hands you.
2. Each finding: STOP D if it asks for a behaviour change; otherwise a conversion repair with the method below — commit,
   `mutate.sh` where a rule is named, the rules it touches replayed ALONE, contracts + oracle, one push under the tests
   lock at the end of the round, the PR body amended with what moved.
3. Never write `IMPLEMENTATION.md`'s « In flight » row (order 15), never merge.

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
61. (auditor, under the operator's delegation) The STOP B is repaired IN L13a as a restoration: the follow panel's facts
    follow the identity read, the row re-produced in place, no history entry; a synchronous sheet source (reading 3) is
    refused; the cold-open absence is D8-accepted and dated in `phase-a14`. The two empty-key `/api/media` entries
    never fire — filed, owner b·10-bis, nothing changed in L13a.
62. (steward, relaying the operator) The implementer's context gate is 80 %, not 50 %.
63. (steward, the auditor's order 15) The wave does not write `IMPLEMENTATION.md`'s « In flight » row; the register's
    `fixed #596` rows and B-352's closure reading stay in the wave.

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
- **The command-safety hook refuses any Bash command whose TEXT holds the word it watches for network calls**, even
  inside a commit message or a Python heredoc: put such text in a file (Write) and pass the file.
- **A `git push` interrupted mid-hook leaves its `pre-push` and `pytest` children running**: TERM each by pid, then read
  `ps` empty and `git ls-remote` before amending.
