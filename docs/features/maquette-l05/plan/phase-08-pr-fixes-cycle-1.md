# Phase 8 — PR fixes, review cycle 1

Four adversarial reviewers read PR #482; none had written the code. Everything
below was then **re-verified by the guarantor** against the running prototype or
by grep — a subagent's report is not evidence, and two of these were reported
with a predicted mechanism that only partly reproduced.

**The pull request must not merge until 8.1–8.4 are closed.**

## 8.1 — A cold SCREEN address puts the not-found page underneath it · CONFIRMED

`destinationOf` (`lib/addresses.ts:145`) resolves any path outside `PAGE_PATHS`
to `NOT_FOUND_PAGE`. The five screen routes are not in that table, so the boot
sets `state.page = "404"` for every one of them. The screen covers the frame, so
R75 stays green — and the defect appears the moment it closes.

Reproduced by the guarantor:

    cold /media/tvdb/403245 -> page='404' notFound='/media/tvdb/403245'
       after Retour         -> url=/ page=404 view='Adresse introuvable…'

**It lands on the wave's headline feature.** Someone opening the DOIT-11 stable
link to a media sheet and pressing Retour is told the address does not exist.
It is a REGRESSION against `main`, where `stateFromUrl()` read only the query so
`page` fell back to `acq`.

Fix: a screen address resolves to the page UNDERNEATH, the way `SIGN_IN_PATH`
already does (`addresses.ts:146`) — not to the not-found page.
Hold: R69 gains a cold entry per screen route asserting the page underneath.

## 8.2 — The not-found state composes the home page's address · CONFIRMED

`addressOf` (`addresses.ts:116`) falls back to `"/"` for a page the table does
not carry. `PAGE_PATHS["404"]` is undefined, so the 404 state composes `/` —
which parses back as the HOME page. A state composes to an address naming a
DIFFERENT state, and the operator's mistyped address is rewritten behind their
back, which is exactly what R69 hold 4 exists to forbid.

Reproduced by the guarantor:

    cold /nimportequoi   -> url=/nimportequoi
       after one back    -> url=/ page='404' notFound='/nimportequoi'

R69 hold 4 measures the COLD load only, so it cannot see the rewrite that
happens one Back later. The `?? "/"` fallback must be a refusal, not a default.

## 8.3 — The panel address is guessed at, fabricates media, and eats the guard

Three defects in one block (`legacy.js:34441`), each reported with browser
evidence:

- **A value with no colon is accepted.** `indexOf(":")` returns `-1`, so
  `slice(0, -1)` / `slice(0)` turn `follows` into kind `follow`, subject
  `follows`. This contradicts the comment three lines above it, which promises
  an unknown kind is IGNORED.
- **An unknown subject fabricates a panel.** `openFollowSheet` falls back to a
  synthesised `{ t: title, k: "show", st: "up_to_date" }` — a medium that does
  not exist, labelled « à jour », now reachable FROM A URL for the first time
  because of this wave. NE-DOIT-PAS-1 in its purest form.
- **A cold `?panel=` consumes the exit guard.** `openPanel` pushes its layer
  entry before the boot writes the guard, so the guard marker lands on the
  panel's entry; closing the panel then leaves `panel=` in the address
  permanently and the « Encore un retour pour quitter » warning never arms.

Fix: refuse a malformed value; verify the subject resolves BEFORE opening;
reopen after the guard is written; strip `panel=` when the reopen did not
happen. Holds: a bogus value, and Back on a COLD-reopened panel.

## 8.4 — The scratch port moved off one collision straight onto another · CONFIRMED

Phase 1 moved `server.py`'s `PROOF_PORT` from 8917 (which `screen_addresses.py`
declares) to **8918 — which `switchover.py:25` declares**. Confirmed by grep. A
collision fixed by creating a second one, and its failure mode is worse:
`switchover.py` swallows the bind error (`stderr=DEVNULL`), so R73 reports « the
session opens: 501 » — a port race presenting as a broken auth host.

Fix: bind port 0 and read the port back. A scratch server has no reason to want
a fixed one, and no third list to drift.

## 8.5 — Two new catches break the file's own convention

`showSignIn` (`legacy.js:11161`) and `hideSignIn` (`:11173`) swallow the address
write bare. Every other navigation writer in the file follows B-026: log AND set
`window.__navEchec`. Measured: with the writer broken, the gate covers the
application while the address denies it — no log, no flag.

**And the flag is read by no rule at all** — `grep navEchec harness/*.py` is
empty, on this branch and on `main`. So the convention these catches break is
itself unenforced, which is why they passed every gate. The close is one hold.

## 8.6 — The addressing arm goes green over a corpus it cannot read

Two blind spots, both mutation-proved by a reviewer:

- An inline `validateSearch: (raw) => ({ page: … })` — no named type — escapes
  it entirely, so `?page=` can come back under a green gate.
- Deleting `lib/addresses.ts` reports `0 dial(s), 0 page(s)` and **clean**.

The same file's own `arm_cycles` docstring names this exact failure: « counting
it as no edge is how a reader stays green over a tree it cannot read ». Fix:
absence is a violation; add the inline shape; add
`tests/scripts/test_check_frontend_boundaries.py` carrying the four mutations.

## 8.7 — Smaller, confirmed

- `url_state.py:65` re-declares five dials; the model has **six** (`panel`).
  Already drifted, in the wave that wrote the comment forbidding it.
- `navigationState()` carries five dials and not `maintTopic`, so a Back onto a
  `/maintenance?topic=X` entry can leave address and interface disagreeing. The
  guarantor reproduced a disagreement in the opposite direction to the one
  predicted (interface keeps the topic, address drops it) — the mechanism is
  real, the walk that exposes it is not the one the report gave.
- `serve_forever` accepts any port with no validation: `--serve 8710` binds a
  reverse-proxy port CLAUDE.md forbids.
- Three of four `REOPEN` kinds are exercised by nothing; four of seven page
  addresses are asserted nowhere; nothing holds `PAGE_PATHS` against the
  engine's `PAGES_OF()`.
- The oracle reference was recorded at commit 8 of 13 — re-record at the tip.

---

## How this phase runs — read before any sub-phase

**Branch** `fix/maquette-l05` · **version** 0.98.26 → 0.98.27 · one sub-phase, one dispatch, one
commit minimum, in the order 8.1 → 8.7. The orchestrator is the guarantor of every dispatch.

**Every sub-phase follows the same four beats, and none is optional:**

1. **Reproduce first, against the tree as it stands.** Run the command the finding names (or
   the rule that is about to gain a hold) and paste its output into the commit body. A fix
   for a defect nobody saw is a fix for a defect nobody can prove gone.
2. **Fix the code.** Inside the files the sub-phase names — nothing else.
3. **Land the rule that bites**, in the harness file the sub-phase names. A hold is one
   `journal.check(...)` in an existing rule — never a new `*.py` in `harness/` (the suite
   counts files, and a new rule changes the count every document cites). Hold names are
   English, and they say what is wanted, not what exists.
4. **Mutation-test the rule**: re-introduce the defect on purpose (a one-line revert is
   enough), rebuild, re-run the rule, confirm it FALLS and that the failing hold's message
   names THIS defect; restore; re-run; green. Paste both runs into the commit body.

**Measuring anything goes through the served copy, and it is manual.** The harness reads
`http://127.0.0.1:8899/`, served from `/tmp/tm-refonte/`. After every change to
`design/src/**` or `design/*.html`:

```
cd frontend/maquette/design && npm run build >/dev/null \
  && cp dist/index.html /tmp/tm-refonte/wrapped.html && cp -R dist/vite /tmp/tm-refonte/vite
python3 frontend/maquette/harness/<rule>.py       # one rule, from the repository root
```

A run without that rebuild measures the PREVIOUS build and says nothing about the change.
The host on 8899 is already up (`lsof -nP -iTCP:8899 -sTCP:LISTEN`); never start a second one,
never bind 8710/8711/8712/8899 from a rule, never run `run.sh` from a dispatch (it is the
orchestrator's gate, and it takes minutes).

**Language.** No French in code, identifiers, `data-*` names or console messages;
interface text only through `fr.json`; harness comments English and undated — no phase,
session or bug number in a comment (`B-043` may appear in a commit body, never in source).
`python3 scripts/check-no-french.py` must stay clean.

**Gates a dispatch runs before its commit:** `ruff check` + `ruff format --check` on touched
`.py`; `cd frontend/maquette/design && npx tsc -b && npx eslint src` when a `.ts(x)` moved;
`python3 scripts/check-frontend-boundaries.py`; `python3 scripts/check-markup-contracts.py`;
the rule(s) touched, green after the mutation was restored. `make lint` / `make test` /
`make check` / the full suite / the oracle are the orchestrator's, at the phase gate.

### Decisions taken for this phase (the orchestrator's; the operator reviews them in the PR)

- **D-8.1 — which page sits under a screen.** A screen address resolves to the page underneath
  the way `SIGN_IN_PATH` already does: `HOME_PAGE`. That is the tree before L05 (where
  `stateFromUrl()` read only the query and `page` fell back to `acq`), so it is the regression
  undone and nothing more; a per-screen mapping (the media sheet over the library, a
  resolution over the arrivals) is a UX proposal for the operator, not this phase's to decide.
  The screen paths are DECLARED in `lib/addresses.ts` as `SCREEN_PATHS` — the five `path:`
  literals of the screen routes, one list — and an offline check holds that list against the
  route files (the three ends of the contract: the table, the routes, the rule).
- **D-8.2 — what the not-found state composes.** `addressOf(NOT_FOUND_PAGE, values)` returns
  `values.notFound` — the address exactly as asked — and THROWS when that is missing, never
  `/`. A refusal, because a state that composes to another state's address is the rewrite hold
  4 forbids; and the `state.notFound` field is what the boot already writes, so nothing new is
  carried.
- **D-8.3 — the panel address.** A value with no `:` is refused (no reopen, `panel=` stripped).
  An unknown kind is refused (as the comment already promised). An unknown SUBJECT is refused
  BEFORE opening: each `REOPEN` producer answers whether the subject resolves, and
  `openFollowSheet` loses its synthesised fallback — a follow nobody holds has no panel, and
  the four producers are asked the same question through the same shape. The reopen happens
  AFTER the guard entry is written, so the guard marker never lands on the panel's entry; when
  nothing reopened, the arrival address is recorded WITHOUT `panel=`.
- **D-8.4 — the scratch port.** `start_server(0, root)` binds an ephemeral port and the context
  manager yields the port it got; `PROOF_PORT` and `screen_addresses.py`'s `PORT` go away.
  `switchover.py` keeps 8918 (it spawns `serve.py` as a process and needs a number) and stops
  swallowing stderr on a failed boot — a bind error is printed, not hidden.
- **D-8.5 — the navigation-failure flag.** `showSignIn`/`hideSignIn` log and raise
  `window.__navEchec` like every other writer. One hold in R69: with `__bridge.replace`
  made to throw from the page, raising the gate sets the flag — and the rule reads it.
- **D-8.6 — the addressing arm.** Absence of `lib/addresses.ts` is a violation; an inline
  `validateSearch: (raw) => ({ page: … })` is read; `tests/scripts/test_check_frontend_boundaries.py`
  carries the four mutations (the two above, plus the two the arm already refused).
- **D-8.7 — the smaller ones.** `url_state.py`'s dial list reads SIX (adds `panel`);
  `navigationState()` carries `maintTopic` and `onEngineBack` applies it; `serve_forever`
  refuses `RESERVED_PORTS` except 8899 (its own); R69 exercises every `REOPEN` kind cold and
  asserts every page address; one offline check holds `PAGE_PATHS` against the engine's
  `PAGES_OF()` ids. The oracle re-record is DONE (#483) and is not part of this phase.
