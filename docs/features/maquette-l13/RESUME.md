# L13a — resume brief for the successor

Written by the first L13a implementer when it stood down at the a·1 boundary. Read it after
`docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything; this file only records
state, rulings and traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`.
- `origin/main` merged at `60530dbd8` (#595, 0.98.90): the hold-count baseline and the oracle
  reference are the true ones (127 rules, 2 776 holds, `failed` 0; oracle reference `f1e7ac66`).
- **a·1 is done** at `123816c93`, pushed with this file (the push report to the steward carries
  `git ls-remote --heads origin feat/maquette-l13a`, since a file cannot name the commit that holds it): one commit, `refactor(maquette-l13a): the driving seams and the named states leave
  the engine for the harness module`. Its gate, on the shared mutex: `run.sh --contracts` 19 rules and
  27 repository guards, no violation; `run.sh --oracle` 87 states × 34 regions, 2 958 measurements, no
  divergence. `--compare`, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·2** (`plan/phase-a02-seams-become-imports.md`), then a·3 … a·19 in order.
- Version not bumped (bump above whatever `main` reads at a·19). No pull request.

## Rulings taken during a·1 — not to be reopened

1. `harness` is a declared bucket of `scripts/check-frontend-boundaries.py` (`BUCKETS`).
2. `design/src/harness/` is in the language guard's harness scope for the STRING arm only
   (`scripts/check-no-french.py`, `check_strings`); identifiers stay held. `engine/states.js` left the
   unread-JavaScript allowed set.
3. **The product never depends on the instrument.** `applyState` and the `window.state` getter STAY in
   the engine: `onEngineBack` restores a page through `applyState`, and the boot writes
   `Object.assign(state, …)` on the bare name. `harness/drive.ts` imports `applyState` and publishes
   `window.applyState`. a·3 moves `applyState` with `onEngineBack` (both phase files amended).
4. `drivenWithoutHistory(run)` is the engine's one addition; the word `driven` is in
   `scripts/code-vocabulary.txt`.
5. `currentRender = null` was not carried: its three writes are all null and nothing reads it.
6. The `window.__navEchec = false` initialisation stays in the engine (a load-time flag the boot's
   writes set). **This makes void the a·2 phase file's « a·1 gave the reset to `harness/drive.ts` ».**
7. `installHarness()` takes no argument; the ≡ panel is `harness/panel.ts`, the same imperative markup
   moved, not a React component (reading (i) of Q2 as a move).
8. The named states are eleven files under `harness/states/`, each a function returning its array (no
   module-level code, so the bundler drops the directory), composed in the original table order by
   `harness/index.ts`. `settings.ts` reads `SETTINGS`, `SETTINGS_STATE` and `settingId` through
   `window.__referentiel`, which types them.

Readings for the pull request body, taken on a·1's head:

- Lift-out, measured once: JavaScript under `vite/` 2 917 767 bytes with `__MOCKS_BUILT_IN__` on,
  1 651 314 off; the off build holds 0 files naming `__etatsDetailles`, `acq-now-idle`, `hscen` or
  `no mock route`.
- B-352's refusal replayed: one state added to `harness/states/system.ts`,
  `python3 scripts/check-frontend-boundaries.py --arm size` exit 0, state removed. B-352 is closed by
  a·1; its register row reads `fixed #<PR>` when the pull request opens.
- `engine/legacy.js` 31 444 → 31 208 non-blank (ledger re-recorded); `comment-references-baseline.json`
  `legacy.js` 27 → 26.

## Traps met — each cost a run

- **The Bash tool keeps a `cd`.** A `cd scripts && …` in one call left every later relative path in
  `scripts/`. Absolute paths, always; never `cd` into `design/src` (B-384).
- **Edit the engine through Python, never Edit/Write.** The formatting hook reformats beyond the edit.
  Anchor every replacement on text asserted unique; an assertion that fails writes nothing, so re-read
  the result before committing (one commit went out with a fix that had not been applied).
- **`vite build --outDir` elsewhere exits 1** in the `build-worker` plugin's `closeBundle` (it scans
  `design/dist/vite` by name) AFTER the bundle is written. Byte figures from such a build are valid;
  read the log before trusting the exit code or the numbers.
- **Anything the boot reads must exist before `start()`.** Moving a publication into `installHarness`,
  which runs after the engine starts, made `start()` throw and aborted the whole shell body — fifteen
  contract checks fell on `__go is not a function`. The first detailed line (`state is not defined`,
  from `screen_addresses.py`) was the cause; the rest were consequences.
- **The pre-push suite sees what the phase gate does not.** `tests/scripts/test_check_markup_contracts.py`'s
  imperative-emission non-vacuity named the engine path of the harness panel; a·1's gate was green
  and the push failed on it. Tests that name a MOVED file's path fall only in pytest — grep `tests/` for
  every path a phase moves.
- Guards a move must re-aim in the same commit: the tree arm's buckets, the size ledger (re-record
  DOWNWARD), `check-no-french.py`, `nofrench_states.py`, `check-state-ownership.py`
  (`ENGINE_SOURCES`), `harness/common.py` (`_NOT_THE_DESIGN`), `check-maquette-comments.py --record`.
  Comments under `design/src` may not name a lot, a phase or a date.
- `tsc` over the design (`cd frontend/maquette/design && npx tsc --noEmit`, own lock) catches what
  the build does not: an engine `let` imported into TypeScript is an implicit `any` (read the typed
  window publication instead), and the engine's literals type narrower than their use.

## a·2 prepared — measured on a·1's head, re-take before moving anything

The pass (DESIGN § 2.4), kept here because the scratch copy dies with the session. It prints, per
`window.__` name, its publishers, the product read lines (outside `engine/` and `harness/`, tests and
comments excluded), the engine reads, the harness module's reads and the rule files reading it:

```python
import re, pathlib, collections, sys
W = pathlib.Path("/Users/izno/dev/worktrees/wave-l13a")
SRC = W / "frontend/maquette/design/src"
def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return "\n".join(re.sub(r"(^|[^:\"'`])//.*$", r"\1", line) for line in text.split("\n"))
NAME = re.compile(r"window\.(__[A-Za-z0-9_]+)")
WRITE = re.compile(r"window\.(__[A-Za-z0-9_]+)\s*(=|\?\?=)(?!=)")
publishers = collections.defaultdict(set); product = collections.defaultdict(list)
engine = collections.Counter(); harness = collections.Counter()
for path in sorted(SRC.rglob("*")):
    if path.suffix not in (".ts", ".tsx", ".js") or ".test." in path.name:
        continue
    rel = path.relative_to(SRC).as_posix()
    for number, line in enumerate(strip_comments(path.read_text(encoding="utf-8")).split("\n"), 1):
        writes = {m.start() for m in WRITE.finditer(line)}
        for m in WRITE.finditer(line):
            publishers[m.group(1)].add(rel)
        for m in NAME.finditer(line):
            if m.start() in writes or re.match(r"\s*:", line[m.end():]):
                continue
            if rel.startswith("engine/"): engine[m.group(1)] += 1
            elif rel.startswith("harness/"): harness[m.group(1)] += 1
            else: product[m.group(1)].append(f"{rel}:{number}")
rules = collections.Counter()
for path in (W / "frontend/maquette/harness").glob("*.py"):
    for name in set(NAME.findall(path.read_text(encoding="utf-8"))):
        rules[name] += 1
for n in sorted(set(publishers) | set(product) | set(engine) | set(harness)):
    print(n, sorted(publishers.get(n, [])), len(product.get(n, [])), engine[n], harness[n], rules[n])
if "--readers" in sys.argv:
    for n in sorted(product):
        print(n, " ".join(product[n]))
```

What it read on a·1's head: **27 names, 211 product lines** — the shell's 19 (`__address`,
`__bridge`, `__dialog`, `__followActions`, `__gestures`, `__loadingDone`, `__panel`, `__queries`,
`__queueActions`, `__refillEngineData`, `__refillProducers`, `__refillSuggestions`, `__releases`,
`__screens`, `__searchResults`, `__settingLabels`, `__store` 42 lines, `__suggestions`, `__toast` 32
lines), the engine's six (`__referentiel` 44 lines, `__navigationState`, `__closeLayers`, `__derouler`,
`__announcePops`, `__startEngine`), `__mocks` (`app/outbox-wiring.ts:85`) and `__servedIdentity`
(`lib/served-identity.ts:92`).

- **The engine reads 21 product publications off `window`** (≈55 lines): `__address` 15,
  `__layers` 6, `__settingsVerbs` 5, `__dialog` 3, `__followVerbs` 3, `__queueActions` 3, `__entry`,
  `__navigation`, `__popover`, `__stackedSurfaces`, `__toast` 2 each, and one each of
  `__deleteLibraryItems`, `__episodeSaying`, `__followActions`, `__loadingDone`, `__mocks`,
  `__pendingDecisions`, `__queue`, `__searchResults`, `__sortWays`, `__suggestions`. They become
  imports through `engine/seams.ts` in a·2.
- **Publication sites** are of two shapes: module-level (`history-bridge.ts:129,191`,
  `panel-host.ts:297,352`, `labels.ts:113`, `popover-episode.ts:73`, `follow-verbs.ts:231`,
  `panel-setting.ts:346`, `sorting.ts:58`) and inside an `install*` that closes over the query client
  (`queries.ts:107,117,171`, `search-queries.ts:43`, `releases/queries.ts:50`,
  `library/queries.ts:180`, `arrivals/queries.ts:116`, `queue.ts:283,334`, `engine-data.ts:52`,
  `dialog-host.ts:66`, `toast-host.ts:205`, `entry.ts:306,381`, `layer-registry.ts:68`,
  `navigation-seam.ts:58`, `stacked-surface.ts:109`); `__gestures` has TWO publishers
  (`press-arbitration.ts:170`, `pull-gesture.ts:107`); `__store`, `__queries` and `__address` are
  assigned in `shell.tsx`'s body.
- **Rules read 98 window names.** Names no rule reads through `window.` — candidates for losing their
  publication once product and engine import them: `__address`, `__episodeSaying`, `__followVerbs`,
  `__navigation`, `__pendingDecisions`, `__popover`, `__refillEngineData`, `__refillProducers`,
  `__refillSuggestions`, `__settingsVerbs`, `__stackedSurfaces`, `__unknownDialog`. **Rules also read
  names bare**, inside evaluate strings: `__navEchec` 10, `__go` 16, `__screens` 5, `__words` 5,
  `__panel` 3, `__bridge` 2, `__referentiel` 2, `__startup` 2, `__clickProbe` 2, `__mocks` 1,
  `__deleteLibraryItems` 1, `__close` 1, `__addSearch` 1 (`grep -ohE "(^|[^A-Za-z0-9_.])__[A-Za-z][A-Za-z0-9_]+" frontend/maquette/harness/*.py`).
  The harness module itself reads `__navigation`, `__refillEngineData`, `__routeur`, `__relay`,
  `__queue`, `__libraryNextPage` — it imports what stops being published.
- **`__navEchec` writers** outside the engine: `app/entry.ts:144,165`, `app/panel-host.ts:170`,
  `app/dialog-host.ts:53`, `features/settings/topic-verb.ts:54`,
  `features/maintenance/topic-verb.ts:40` (declared in `app/history-bridge.ts:81`).
- **`__followActions` in the media screen** (`features/media/media-screen.tsx:74`, read inside the
  component); the route is `routes/media-sheet.tsx`, `component: MediaScreen` — composing the follow
  actions in means a wrapping component in the route, since `createRoute` passes no props.
- **`__servedIdentity`**: written by `frontend/maquette/host_identity.py:158`
  (`with_served_identity`, an inline `<script>window.__servedIdentity=…;</script>` with `<`, `>`, `&`
  escaped), read by `lib/served-identity.ts:92`, held by `harness/identity.py:122,142,153,168,362`
  (the marker in the served HTML, and the rule WRITES `window.__servedIdentity` to drive the published
  case — the re-aim keeps a way for the rule to drive both cases). `serve.py` is read at boot:
  `pm2 restart torrentmate-design` is the operator's host, not this wave's — `logout.py` and
  `startup.py` start their own `serve.py`.
