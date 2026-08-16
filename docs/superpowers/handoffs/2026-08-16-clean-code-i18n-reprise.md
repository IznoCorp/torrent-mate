# Clean-code / i18n wave — resumption brief

Paste-ready for a fresh session. Everything below is measured state, not memory.

## Where the work stands

Branch **`refactor/clean-code-i18n`**, based on `origin/main` = `ad366621` (v0.97.16);
the wave's single version bump is already applied (**0.97.17**). The branch is NOT pushed
as a PR yet. Plan: `docs/superpowers/plans/2026-08-16-clean-code-i18n.md` (amended
2026-08-16 to add Task 9 and the four-armed gate).

The wave answers a binding operator directive (2026-08-16): **the code contains no
French — identifiers, class names (code AND CSS), file names, tool messages — and no UI
string lives in code: French interface copy lives in i18n resources.** The rule must be
"respected, enforced, controlled and corrected", so it ends in an automated gate.

### Done and reviewed (each with its own adversarial review, all Approved)

| Task | What shipped                                                                                                                                                                   | Proof                                                                                          |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| T1   | react-i18next infra (`design/src/i18n/{index.ts,fr.json}`), pilot: releases screen                                                                                             | byte-identity on innerText AND textContent, 0 divergence                                       |
| T2   | Every UI string of the 6 components → `fr.json` (343 leaves; the 3 settings dictionaries = 156 entries)                                                                        | 81 states × 3 oracles, 0 divergence; dictionaries diffed table-to-table                        |
| T3   | `design/src` files, dirs and identifiers → English (`shell.tsx`, `store.ts`, `data.ts`, `components/{sheet,panel}.tsx`, `screens/{add,media,profile,releases,resolution}.tsx`) | frozen-seam set-equality on every family; 934-literal audit proves zero rendered-byte movement |
| T9   | The CSS vocabulary → English: 33 classes renamed, 3 deleted (dead), 6 frozen (data values), 13 kept with recorded reasons                                                      | `extract-maquette-css.py --check` green, suite 48/48, prod 1364 tests, one executed mutation   |
| T4   | 29 harness files renamed + `resync.py`, `rename.mjs`, prod `FollowsPanel.tsx`; ~90 references; the stale-prose carry                                                           | suite 48/48 with **485 holds — the same total as before the renames**                          |
| T5   | The harness's own identifiers, labels, `Journal` titles and printed formats → English, in 4 batches                                                                            | suite 48/48, 485 holds, per-batch counts identical to a pre-edit baseline                      |

**T5's review was still running when this session ended — read its verdict first
(`.superpowers/sdd/2026-08-16-clean-code-i18n/` is gone with the session; re-dispatch the
review if no verdict was recorded below).**

### Remaining tasks (in order)

1. **T6 — `serve.py` + `resync.py`**: English identifiers; the login page and build-failure
   page are UI → their French strings read from the SAME `fr.json` (one source of truth),
   served bytes identical. `serve.py` is live on the design host: after merge,
   `pm2 restart torrentmate-design`.
2. **T7 — the gate** `scripts/check-no-french.py`, wired into `make check` and CI, with
   **four arms**: strings, identifiers, **file names**, **class names** (code + CSS). The
   frozen exceptions must be CITED with their reason (they already are, in
   `regions.json`'s `$vocabulary`), never merely permitted. One executed mutation per arm.
3. **T8 — wave gate**: resync, full suite 48/48, `make check`, `make check-frontend`,
   residual sweeps, then **the rule written where it is enforced**: root `CLAUDE.md`
   (§Language / §Code Conventions), `frontend/maquette/README.md` (i18n section + the
   naming rule for new files/classes), `IMPLEMENTATION.md` (wave record). No second
   version bump (0.97.17 stands). Also: BUGS.md's B-027/B-028 table cells keep stale
   alignment padding after `resync.py` (cosmetic, fold in here).
4. **Then the PR**: full adversarial review of the whole branch, PR, CI green,
   squash-merge, post-merge live check (`pm2 restart torrentmate-design` because
   `serve.py` changed).

After this wave: **SP4d** (4 page waves: sys+maint+config → arr → lib with E-001 → acq),
then **SP4-end** (the legacy engine dies). Those waves are born under the new rules.

## Rulings made this session (all contestable)

- **Scope**: `design/src` + harness + `serve.py`/`resync.py` + all new code. The legacy
  fragment `refonte.html` is excluded from IDENTIFIER renaming (it dies at SP4-end) but
  NOT from CSS-class renaming (a class is a name shared by four worlds) nor from comments
  naming symbols that no longer exist.
- **Frozen, with reasons recorded**: the window seams (`__pont`, `__panneau`, `__ecrans`,
  `__referentiel`, `__magasin`, `__derouler`, `__annoncerPops`, `__demarrerMoteur`,
  `__navEchec`, …) and their object-literal KEYS; all `data-*` names and values; `__go`
  state ids; route paths; the 6 snake_case follow/episode-state tokens
  (`a_recuperer`, `en_attente`, `en_acquisition`, `en_mediatheque`, `non_verifie`,
  `annonce`) — they are DATA values class-ified, renaming them moves the data contract.
- **Commit messages stay French** (the lane's standing convention; the new CLAUDE.md
  §Language lists documents, not commits). Tool/harness messages became English.
- **Dated session records keep the old file names** (`docs/superpowers/**`,
  `docs/archive/**`, `docs/analysis/**`): rewriting a record would falsify it. Live
  surfaces are at zero.
- `bascule.py` → **`switchover.py`**, not `failover.py`: a _failover_ names the automatic
  fallback R73 explicitly forbids. `url_address.py` → **`url_state.py`** (R69's subject).
- `flux` is RECORDED, not renamed (a genuine English word, the `f*` family root; `flow`
  noted as the free alternative).

## The traps this wave paid for — re-read before touching a name

1. **A class name hides in a SPREAD** (`...reglage` → renamed → the whole Réglages page
   stopped rendering) and **in a template literal** (`class="fx${vide ? " fvide" : ""}"`)
   and **in a bare string inside a Python set** (R13's `OPT = {"trailer", …}`). Sweep for
   all three shapes BEFORE renaming, never after. Live collisions to watch next time:
   `...deck`, `...port` (and `...state` is a near miss — the class is `.states`).
2. **`#coquille` is a live DOM id** while `coquille.tsx` was a file name: a file rename
   must carry a lookbehind guard or it eats the id.
3. **Two kinds of French must never be confused**: the harness's own messages (become
   English) and the French text the app RENDERS which holds assert (stays byte-identical).
   A rename inside a rendered-word vocabulary goes **quiet**, not red — `"des erreurs"` →
   `"des errors"` was caught by a mixed-language literal grep, not by the suite.
4. **The hold count is the behaviour proof**: 485 across Tasks 4 and 5. A rename that
   changes what a script measures shows up there; run the suite per batch and compare.
5. **Undoing a mutation on a branch-modified file must be the INVERSE EDIT** — a
   `git checkout --` would destroy the branch's own edits to that file.
6. **A rule can go quiet without failing**: R8 lost the fiche when it left `#screen`;
   four scripts silently measured the page underneath (three different media reporting the
   same 1541 characters). Whenever a surface moves, add its identity rung the SAME wave.

## Ritual and environment (unchanged)

- Build + copy before any harness run:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
- Static server `127.0.0.1:8899` (already running); scratch ports 8913/8917/8918 only;
  **never** 8710/8711/8712. `command python3` (3.12.4), Node
  `/Users/izno/.nvm/versions/node/v22.13.1/bin`.
- The suite is **48 runnable rule scripts** (49 `.py` minus `common.py`, the only library;
  `server.py` IS a runnable self-tested rule). Run sequentially, in the FOREGROUND.
- `rg` ALWAYS with a `-g`/type filter (an unfiltered `rg` scans a 14 GB fixture dir and
  crashes the machine).
