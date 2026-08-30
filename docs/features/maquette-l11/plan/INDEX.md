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
| 4 | The outbox store | `phase-04-the-outbox-store.md` | behaviour |
| 5 | The outbox, and its replay | `phase-05-the-outbox.md` | behaviour |
| 6 | What is waiting is said | `phase-06-the-pending-count.md` | behaviour |
| 7 | The three entry points | `phase-07-the-entry-points.md` | behaviour |
| 8 | P27 — standalone hides the install offer | `phase-08-standalone.md` | rule |
| 9 | P30 — the back-forward cache ratchet | `phase-09-bfcache.md` | rule |
| 10 | The close | `phase-10-the-close.md` | prose |

---

## ACCEPTANCE

Every criterion is an executable command with a documented expected output (SH-16). A criterion
that cannot be run is not a criterion.

| # | Criterion | Command | Expected |
| --- | --- | --- | --- |
| ACC-01 | The served copy carries a build stamp | `cat /tmp/tm-refonte/build-stamp.json` | JSON with `commit`, `dirty`, `source_stamp`, `token` |
| ACC-02 | A stamp that moves mid-run is a named failure, not a silent pass | `frontend/maquette/harness/mutate-stamp.sh` (phase 1) | the rule FAILS naming « served copy replaced mid-run » |
| ACC-03 | Two suites cannot interleave | run `run.sh --oracle` twice at once | the second reports the lock's holder and exits, never measures |
| ACC-04 | The contract tier's announced figure matches what it runs | `make harness-contracts \| head -3` and `grep -c . <(grep -o "[a-z_0-9]*\.py" <<<"$(grep '^CONTRACTS=' frontend/maquette/harness/run.sh)")` | the same number, 12 |
| ACC-05 | **P7** — the shell opens offline | `python3 frontend/maquette/harness/pwa.py` | PASS « offline, a named state renders » |
| ACC-06 | `/api/*` is never cached | inspect the worker's route table (phase 2) | `/api/` and the stream are NetworkOnly |
| ACC-07 | `/build.json` answers without a session | `curl --connect-timeout 10 --max-time 30 -s https://tm-design.iznogoudatall.xyz/build.json` | JSON with `source_stamp`, HTTP 200, no redirect to the gate |
| ACC-08 | The poll sees a moved stamp and reloads exactly once | phase 3's rule | PASS, reload count 1 |
| ACC-09 | The freshness signal survives a dirty tree | edit a source, rebuild, re-read `/build.json` | `source_stamp` moved while `commit` did not |
| ACC-10 | The outbox store survives a restart | phase 4's rule | the envelope is present after a reload |
| ACC-11 | **P8** — a mutation issued offline departs on reconnection | phase 5's rule | PASS, the mock applied it once |
| ACC-12 | …and exactly once, proved on the mock's side | phase 5's rule | the idempotency key was seen twice, applied once |
| ACC-13 | An offline mutation does not roll back | phase 5's rule | the optimistic cache write survives |
| ACC-14 | What is waiting is visible | phase 6's rule | the connection mark carries the pending count |
| ACC-15 | **P9** — the manifest declares all three entry points | `curl --connect-timeout 10 --max-time 30 -s https://tm-design.iznogoudatall.xyz/manifest.webmanifest \| python3 -m json.tool` | `share_target`, `launch_handler`, `handle_links` all present |
| ACC-16 | The address `share_target` names actually pre-fills | phase 7's rule | `/add?q=Silo` opens the add screen with « Silo » in the field |
| ACC-17 | **P27** — standalone hides the install offer | phase 8's rule | PASS under emulated `display-mode: standalone` |
| ACC-18 | **P30** — the back-forward cache is not evicted | phase 9's rule | `pageshow.persisted` true after a walk out and back |
| ACC-19 | Push is declined in writing, not forgotten | `grep -n "L16" BUGS.md` | a register entry naming L16 as the consumer |
| ACC-20 | The wave's gate | `run.sh` · `run.sh --a11y` · `oracle.py --check` · `make check` | no violation · 0 violations · green or named · exit 0 |

---

## What no phase does

- **It does not touch `frontend/src`.** The shipped app's PWA already works and is archived at
  switchover; changing it here is work thrown away with the app that holds it.
- **It does not declare push notifications.** D-8, with its written reason and its consumer (L16).
- **It does not move a producer.** Those are L19's, and the inventory command still names them.
- **It does not add `100dvh`.** P11 is L12's, and the tree has no `dvh` today (§ 1 of the design).
- **It does not extend a grandfathered file.** `features/acquisition/page.tsx` and
  `features/library/page.tsx` are two of L14's four.
