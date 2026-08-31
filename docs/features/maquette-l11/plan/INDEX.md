# L11 — the plan

The design is `../DESIGN.md`, which owns the reasoning and the ten decisions. This file owns the
ORDER, the definition of done per phase, and the ACCEPTANCE criteria. `IMPLEMENTATION.md` owns the
status; it is not repeated here, because a status that exists twice goes stale in one of the two
copies (B-152).

---

## The order, and why it is this one

**Phase 1 is B-256, and it is first for a reason that is not politeness.** Every other phase in
this wave is proved by the harness, and B-256 is the finding that the harness can measure the wrong
prototype without saying so. Running nine phases of measurement on an instrument known to be
unsound, and repairing the instrument at the end, would mean every earlier reading was taken before
the thing that makes readings trustworthy existed. It goes first, and the wave's own gates are the
first thing it protects.

**Then the shell, then the freshness, then the queue.** The worker has to cache before an update
discipline has anything to update, and the queue has to exist before anything can publish what is
waiting in it. The entry points come after the shell because `share_target` names an address, and
an address that only works online is not an entry point.

**P27 and P30 come last, and they are cheap on purpose.** Both were pulled into this lot by the
operator on 2026-08-30 against `MODEL.md` § 3's assignment. Neither changes behaviour: P27 reads a
surface that already exists under a media query that is already read, and P30 records a property
the tree already has (`grep -rn "beforeunload" design/src` → 0). They are last because a rule that
records good news is worth having and is worth nobody's turn ahead of the work.

| # | Phase | File | What it commits |
| --- | --- | --- | --- |
| 1 | B-256 — the lock and the stamp | `phase-01-the-lock-and-the-stamp.md` | instrument |
| 2 | The worker precaches the shell | `phase-02-the-shell-is-cached.md` | behaviour |
| 3 | `/build.json` and the update discipline | `phase-03-freshness.md` | behaviour |
| 4–5 | The outbox, its store and its replay | `phase-04-and-05-the-outbox.md` | behaviour |
| 6 | What is waiting is said | *(with 4–5 above)* | behaviour |
| 7 | The three entry points | *(with 8–9 below)* | behaviour |
| 8–9 | P27 and P30 | `phase-08-and-09-standalone-and-bfcache.md` | rule |
| 10 | The close, and the review's repairs | `REPORT.md` | prose |

**The phases that share a file share it because they landed in one commit each and one
subject between them.** This row used to name six files that were never written, and no guard
could see it: `check-docs-cited-paths.py` reads six named directives and never `docs/features/**`.

---

## ACCEPTANCE

Every criterion is an executable command with a documented expected output (SH-16). A criterion
that cannot be run is not a criterion.

| # | Criterion | Command | Expected |
| --- | --- | --- | --- |
| ACC-01 | The served copy carries a build stamp | `python3 frontend/maquette/harness/served_copy.py --token` | a non-empty token |
| ACC-02 | The lock and the stamp behave | `python3 -m pytest tests/scripts/test_served_copy.py -q` | 13 passed |
| ACC-03 | …and the WIRING that calls them is in place | `python3 frontend/maquette/harness/served_copy.py` | 15 rules EXECUTED — no violation |
| ACC-04 | The contract tier announces no figure it cannot keep | `grep -c "rules)" Makefile` | `0` |
| ACC-05 | **P7** — the shell opens offline, and **P9**'s manifest half | `python3 frontend/maquette/harness/pwa.py` | 0 failures |
| ACC-06 | `/api/*` and the stream are never cached | `grep -n "const NEVER" frontend/maquette/design/sw.js` | `/api/` and `/ws` by prefix |
| ACC-07 | `/build.json` answers without a session | `python3 -c "import urllib.request as u,json; print(json.load(u.urlopen('https://tm-design.iznogoudatall.xyz/build.json', timeout=15)))"` | `{'build': '<12 hex>'}` |
| ACC-08 | The bundle, the worker and `/build.json` carry ONE identity | `cd frontend/maquette/design && grep -o 'const BUILD = "[a-f0-9]*"' dist/sw.js && cat dist/build.json` | the same value |
| ACC-09 | A touched source does NOT move the identity — it is a content hash, not a timestamp | `touch frontend/maquette/design/src/app/outbox.ts && cd frontend/maquette/design && npm run build && cat dist/build.json` | unchanged. *(The other half — a real edit DOES move it — is read by ACC-12, which makes the build move and holds the reload.)* |
| ACC-10 | **P8** — held, persisted, departed once, and said | `python3 frontend/maquette/harness/outbox.py` | 16 rules EXECUTED — no violation |
| ACC-11 | A refused replay leaves the queue rather than jamming it | the same rule | PASS on that hold |
| ACC-12 | The update discipline reloads once and never loops | `python3 frontend/maquette/harness/freshness.py` | 5 rules EXECUTED — no violation |
| ACC-13 | **P27** and **P30** | `python3 frontend/maquette/harness/installed.py` | 8 rules EXECUTED — no violation |
| ACC-14 | Signing out takes the cached shell, the worker and the queue with it | `python3 frontend/maquette/harness/pwa.py` | 0 failures, R111's holds among them — `logout.py` is R54, the cookie, and holds none of this |
| ACC-15 | **P9** — the three entry points are declared | `python3 -c "import urllib.request as u,json; m=json.load(u.urlopen('https://tm-design.iznogoudatall.xyz/manifest.webmanifest', timeout=15)); print(sorted(k for k in m if k in ('share_target','launch_handler','handle_links')))"` | all three listed |
| ACC-16 | …and the address one of them names really pre-fills | `python3 frontend/maquette/harness/pwa.py` | PASS on R108's pre-fill hold |
| ACC-17 | Push is declined in writing, with its consumer named | `grep -n "B-257" BUGS.md` | an entry naming L16 |
| ACC-18 | The queue's clock is the only one, and it is argued for | `python3 scripts/check-live-relay.py` | `0 poll(s), 1 exempt and named` |
| ACC-19 | No rule lost a hold | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` | no rule falls |
| ACC-20 | The wave's gate | `frontend/maquette/harness/run.sh` · `--a11y` · `oracle.py --check` · `make check` | no violation · 0 violations · no divergence · exit 0 |

---

## What no phase does

- **It does not touch `frontend/src`.** The shipped app's PWA already works and is archived at
  switchover; changing it here is work thrown away with the app that holds it.
- **It does not declare push notifications.** D-8, with its written reason and its consumer (L16).
- **It does not move a producer.** Those are L19's, and the inventory command still names them.
- **It does not add `100dvh`.** P11 is L12's, and the tree has no `dvh` today (§ 1 of the design).
- **It does not extend a grandfathered file.** `features/acquisition/page.tsx` and
  `features/library/page.tsx` are two of L14's four.
