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
