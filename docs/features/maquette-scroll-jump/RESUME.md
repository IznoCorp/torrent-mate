# maquette-scroll-jump — resume note

**Superseded.** The wave resumed from this note and carried every step below; `DESIGN.md` in this folder is the record, and this file is kept only because the brief names it.

Stood down on the operator's ruling of 2026-09-12 23:30 (at most two agents on the machine). Nothing is lost: this file,
the brief and the branch are the whole state. Read `BRIEF.md` first (its register block now reads B-490..B-494), then this.

## Head

Branch `fix/maquette-scroll-jump`, pushed; the head is the commit that adds this file (`git ls-remote origin
fix/maquette-scroll-jump`). Cut from `a2721935f` (0.98.86); `origin/main` NOT merged yet, version NOT bumped.

## Done — and the reading that holds each

1. **Reproduced and named, two mechanisms** (private bench, Chrome, setter trap on `Element.prototype.scrollTop`).
   - **B-490, the jump.** `app/scroll-restoration.ts` `restoreScroll()` re-applied the restored offset on the `load` of the
     last not-yet-complete `img` of `#port`, guarded only by the navigation token. Posters below the fold are lazy, so
     the last `load` fires when the reader scrolls to it. Path: `/acquisition` → « Résoudre → » on Lucky → Back → scroll.
     Probe lines (desktop 1440 × 900 in the frame, 40 px wheel steps):
     ```
     STEP  12 port=  480
           EVENT {"kind": "img-load", "src": "a406ec1c.webp", "loading": "lazy", "offset": 1280, "portTop": 520, "card": "Wicker"}
           EVENT {"t": 9012, "kind": "scrollTop=", "target": "main#port[data-part=viewport]", "before": 520, "value": 0, "after": 0}
     STEP  13 port=    0
     ```
     Phone 390 × 844: `before 520 value 240` (departure at 240), same stack `n.addEventListener.once`. Fresh arrival, a
     sheet opened and closed, or no detour: no write at all, 60 steps, port monotone to its end (720 phone, 722 desktop
     in frame, 557/357/157 out of frame at 900/1100/1300 high), `scrollHeight` constant, `activeElement` body. Out of the
     frame at 1440 × 900 every poster loads at once, so the path cannot jump there. The build identity of tm-design
     (`/build.json` = `3aebaead47d2`) equals its bundle's: no update-discipline reload. `lib/pull-gesture.ts` is touch
     plus a mouse DRAG on pointers; no wheel arms it.
   - **B-491, the double scroll.** Out of the frame `.device` has no `overflow: clip`; `#sheet` (absolute, translateY 43)
     and its `sheet/drag-band` end at `innerHeight + 89`, so `document.scrollingElement` is 989 / 900. Wheel over
     `[data-part="shell/header"]`: document 0 → 89, port 0; wheel over the port: port moves, document stays.
2. **R175** `harness/scroll_keeps_place.py`, README row added. Frames: phone, desktop 1440 × 900 in the frame (fresh
   arrival + return from the resolution), desktop out of the frame (fresh arrival + header). Gestures: CDP
   `synthesizeScrollGesture` touch, and `mouse.wheel`. **RED on the unrepaired tree: 40 holds, 6 violations** — the four
   return walks (phone finger 490 → 22, phone wheel 480 → 0, desktop finger 491 → 15, desktop wheel 480 → 0) and the two
   out-of-frame header holds (`moved ['document']`, 89 px). Commit `cc075350a`.
3. **Repair of B-490** (approved by the orchestrator): `landed = port.scrollTop` after the write; the late re-apply runs
   only if `port.scrollTop === landed`. **R175 after it: 40 holds, 2 violations** — the two header holds, B-491 only.
   Commit « fix(maquette-scroll-jump): the late re-apply of a restored offset runs only where the restore landed ».
4. **B-490 and B-491 filed** in BUGS.md, both `open` (B-490 becomes `fixed #<PR>` at delivery).
5. Cheap guards run by EXIT CODE on the touched files: `check-no-french`, `check-code-abbreviations`,
   `check-maquette-comments`, `check-bug-register`, `check-docs-cited-paths`, `check-module-size --root frontend` — 0.

## Left, in order

1. **B-491's repair**, a SEPARATE commit in `design/src/styles/harness.css` (orchestrator's condition): confine `.device`
   on the y axis out of the frame (e.g. `overflow-y: clip` on the unscoped `.device`, or scoped to the checked state)
   WITHOUT moving the absolute layers — read that the closed sheet's translate and its drag band still work in and out
   of the frame, and that the switch's shape is untouched. R140 (`desktop_frame.py`) holds that block's declarations by
   value and reads `harness.css` as TEXT: edit it with a script and read the diff (the formatter hook reformats beyond an
   edit). R175's header holds read green after it.
2. **The mutation** the orchestrator asked for, on the repaired tree: remove `&& port.scrollTop === landed`, rebuild,
   publish to the bench, run R175 — the four return walks must fall (the unrepaired run above is the same code and fell
   4 + 2; write the count of the formal mutation), restore, rebuild.
3. **Probe (a), confirmatory**: repaired tree, port parked at Lucky's level for 30 s with the relay idle; one line.
4. **DESIGN.md** in this folder: § 1 the mechanism with the probe lines above, § 6 the gate figures written once.
5. **The gate** on the final head: `run.sh --contracts`; the full suite once; `--a11y`; the oracle (zero divergence — a
   divergence is a STOP); `harness-hold-counts.py --compare --jobs 2` (`failed` first; R175 « new since baseline » is
   expected); `make check` at 2 workers under the tests lock.
6. **Merge `origin/main`**, re-read the version (settings and mock-layer land 0.98.87/88), bump the patch above it.
7. **Push** under the tests lock (a production file is on the branch: no `--no-verify`), open the PR READY with the
   brief's title, B-490 row → `fixed #<PR>`, report.

## The envelope

- Browser mutex for `run.sh` (any tier), the oracle, hold-counts: `sh scripts/heavy.sh --class browser scroll-jump <cmd>`,
  `TM_HARNESS_JOBS=2`; announce each run to `Orch : TM frontend` one line before and after.
- Tests lock for `npm ci`, builds, `make check`, pytest, push:
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder sh scripts/heavy.sh --class test scroll-jump <cmd>`,
  `PYTEST_XDIST_AUTO_NUM_WORKERS=2`.
- Private bench, one browser, outside the mutex: build `design/dist` under the tests lock, then
  `TM_SERVED_COPY=<scratchpad>/bench python3 frontend/maquette/harness/served_copy.py --publish`,
  `python3 frontend/maquette/harness/server.py --serve 8902 <scratchpad>/bench` (background), and run a rule with
  `TM_PROTOTYPE_URL=http://127.0.0.1:8902/ TM_SERVED_COPY=<scratchpad>/bench`. Kill the host after; prove with `lsof`.
- `frontend/node_modules` and `design/node_modules` are installed in this worktree; `design/dist` is built (delete it
  and the bench copy before the final report).

## Traps met here

1. **Headless Chrome needs `channel="chrome"`** — the bundled headless shell of this Playwright is not installed.
2. **Out of the frame at 1440 × 900 the lazy posters all load at once**: a return walk there reads green over a path
   that cannot jump. R175 holds « posters still loading on the return » for that reason and walks the return only
   where it can fall.
3. **The resolve foot carries `data-act`, not `data-resolve`**: R175 finds the blocked card by the title its seed
   (`mocks/seeds/blocked.json`) carries.
4. **A harness comment may not carry a date** (`check-maquette-comments`).
5. **A file under `docs/` is globally ignored** (B-251): a new file there is added with `git add -f`, and a citation of a
   file no commit holds fails `check-docs-cited-paths`.
6. A `cd` inside a compound command moves the session's working directory: absolute paths only.
7. **The first push was refused by the pre-push suite, 7 failed**: R175 carried an ESCAPED part selection
   (`[data-part=\"card/foot\"]` inside a Python string), which `check-markup-contracts` refuses, and a new harness file
   raises the comment corpus's `read` count, re-taken with `check-maquette-comments.py --record` in the same commit. Run
   ALL 27 cheap guards of `run.sh` by exit code before a push, not the ones that look related — and pass each guard's
   arguments as separate words.
