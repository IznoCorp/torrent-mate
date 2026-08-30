# L11 — Offline and PWA: what landed, and what it cost

**Committed to the repository with `git add -f`.** The global `.gitignore` carries a `docs/` rule,
so a new file here is invisible to `git add -A`, to `git status` and to every gate — B-251, and
L15's own report existed on one disk while two documents cited it.

---

## The running count for B-085 — « a guard is green because of what it does not read »

**Six for this wave, four of them found by MUTATING the wave's own rules.** The full entry is in
`BUGS.md`; the two that generalise are these.

**R105 went green TWICE over a shell that was not there.** With the document deliberately dropped
from the precache, the page still opened offline — Chrome's own disk cache answered the reload
after the server was gone, and « the shell opened offline » was true of the wrong cache entirely.
Turning the browser's HTTP cache off through CDP, it passed **again**: on the harness host
`/offline.html` has no file behind it, so the fallback handler folds it onto the document and the
worker's *last-resort* entry is a full copy of the prototype. **The consequence held while the
mechanism was gone**, and that is the difference between a rule and a coincidence. The rule holds
the document under its own key now, and reads navigation timing's `workerStart` to say positively
that the worker is what answered.

**R107 was silent about the client's half of « at least once ».** With the network up, an envelope
forgotten *before* its request answered and one forgotten *after* are indistinguishable. The
property only exists at the moment a departure FAILS, and the rule never put it there — so a client
promising *at most* once, losing the operator's action to a dropped connection, passed eleven green
holds.

---

## What each phase committed

| # | Phase | Rule | Mutations seen red |
| --- | --- | --- | --- |
| 1 | B-256 — the lock and the stamp | **R104** (8 holds) + 12 unit tests | M1–M5, and M1b/M2b on the ORDER rather than on presence |
| 2 | The shell is cached (P7) | **R105** (via `pwa.py`) | M6 no cache · M7 no fallback · M8 no document |
| 3 | `/build.json` and the discipline | **R106** (5 holds) | M9 latch · M10 offline · M11 no comparison |
| 4–5 | The outbox and its replay (P8) | **R107** (11 holds at the phase gate) | M12 rollback · M13 memory-only · M14 no dedup · M15 forget-first |
| 6 | What is waiting is said | R107 → 14 holds | — |
| 7 | The three entry points (P9) | **R108** (via `pwa.py`) | — |
| 8–9 | P27 and P30 | **R109 / R110** (7 holds) | M16/M18 the standalone guard · M17 a `beforeunload` |

---

## Three defects the rules found in the code they were written for

**The update discipline reloaded in a LOOP — fifteen times.** `reloading` is module state and a
reload *replaces the document*, so the flag was false again on the way back in. A reload loop on a
design host is indistinguishable from a host that is down. The latch is `sessionStorage` now: one
reload per served build, and if the page comes back still not matching, convergence has failed and
that needs a person.

**`platform.py` shadowed the standard library** (B-260). A rule is run as
`python3 <harness>/<rule>.py`, which puts the harness directory at `sys.path[0]`. Four subprocess
smoke tests failed with `AttributeError: module 'platform' has no attribute
'python_implementation'`, raised inside `attr/_compat.py`, which none of them mentions. Invisible to
`ruff`, to the harness suite, to the boundaries guard and to the abbreviation guard; only the full
test suite saw it. **A directory that lands on `sys.path` may not hold a file named after anything
in the standard library, and the harness is 80 such files.**

**The design host answers 401 for `/` itself** (B-259). A browser reads the manifest of the page in
front of it, so the only document a phone can install from is the sign-in gate — where `/vite/*` is
401 because the bundles *are* the prototype, and `/` is 401 because the login page is served with
that status. `cache.addAll` and `Promise.all` both fail the install as a whole. The install
attempts everything and **requires nothing**; the running application completes the shell.

---

## Two rules the wave broke, each because a fact grew a third end

`server.py` held that every root-level resource the document names 404s rather than folding. The
served copy now really holds `/sw.js`, so the hold was asking a file that exists to answer 404. It
measures the absent ones, with a hold above it refusing an empty subject — and the file that exists
gets the promise that now matters: served as itself, never folded, because folded it answers
`text/html` and registration dies on the MIME type in silence.

`switchover.py` assembles a scratch design root from a named list. `sw.js` is a **build input**
now, so a tree without it fails the build outright and the rule reported four 503s about a host
that was fine.

---

## What this wave did NOT do, and said so

- **P30's runtime half is device-only.** Chrome refuses the back-forward cache whenever a DevTools
  client is attached, and Playwright is always one: `pageshow.persisted` came back `undefined` on a
  real walk out and back, with and without `--enable-features=BackForwardCache`. What runs in CI is
  the ratchet — `beforeunload` and `unload` are what evict, and the tree registers neither.
- **R109 proves the application's branch, not Chrome's.** `Emulation.setEmulatedMedia` does not
  carry `display-mode` in this Chrome (measured, all three payload shapes), so the query is answered
  in the page. Whether Chrome reports standalone correctly when really installed is Chrome's job,
  and only a home screen settles it.
- **Push notifications are declined in writing** (B-257), with their consumer named: §18's ratio
  alert, which is L16.
- **The share target's OS half is not proved.** No rule can make an operating system share into an
  application. What is proved is the pair: the manifest declares it, and `/add?q=` pre-fills.
- **`MODEL` Part 13 says a feature's `queries.ts` enqueues; `send()` does.** The intent — the queue
  learns no domain — is kept exactly; what changes is that there is **one** writer instead of six.

---

## The wave's gates, at the close

| Gate | Result |
| --- | --- |
| `harness/run.sh` (79 rules) + the 23 cheap guards | **no violation** |
| `harness/run.sh --a11y` | **87 states, 0 violations**; light-theme ratchet 166 against a ceiling of 166 |
| `oracle.py --check` | **no divergence**, 2 958 measurements over 87 states × 34 regions, reference at `212faf0a` |
| `make check` | **exit 0** — 10 956 passed, 4 skipped, 2 xfailed |
| `scripts/harness-hold-counts.py --compare` | `pwa.py` 28 → 47, `server.py` 12 → 14, four rules new; **no rule lost a hold** |

The oracle is green because nothing in this lot draws a pixel differently: the worker changes what
is fetched, not what is painted, and the pending count lands in a mark L10 already drew.
