# Constitution v2 mission — session report (2026-07-15 → 16)

One-page synthesis so the context survives a clear (constitution §10 / §méthode).
Branch series: `fix/constitution-v2-*`. Base: `main`. Prod autodeploys on squash-merge.

## What shipped (merged + prod-verified via `/api/version` build_commit)

| PR   | Version | What                                                                                           | Proof                                                               |
| ---- | ------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| #288 | 0.49.1  | Constitution v2 (§6–§10 + DOIT/NE-DOIT-PAS) + qBittorrent bypass-localhost ban (CLAUDE.md/doc) | make check green                                                    |
| #289 | 0.49.2  | §6 visible queue everywhere: maintenance runner queues, `pipeline-queue` waiter, dup-only 409  | 202 (no 409) + persisted `queue` steps + 58–97 s waits + completion |
| #290 | 0.49.3  | Fix « En file » badge (bug found BY the live proof, not by tests)                              | badge « En file » + banner captured live on prod                    |
| #291 | 0.49.4  | E2a: errored/missing torrents visible in Downloads panel (qBit + Transmission), French reason  | red-on-old across both clients + read-model + front                 |
| #292 | 0.49.5  | E2b: ingest skip/defer reasons persisted + « Ce qui n'a pas avancé » in run detail             | red-on-old writer cap/omit + route round-trip + front               |
| #293 | 0.49.6  | E3a: provider-ID identity guard before REPLACE (§7)                                            | integration: different-ID target survives, item skipped             |
| #294 | 0.49.7  | E3b: append-only destructive-op journal (migration 015 + writer + wiring + endpoint)           | integration: overwrite journaled on the real dispatch path          |
| #295 | 0.49.8  | E4: ingest fail-safe copy (HnR) + remove torrent from client after move                        | red-on-old: pause+obligation⇒copy; move⇒client.delete               |
| #296 | 0.49.9  | E5: `grab --dry-run` applies the real quality profile (§9); reconcile/3D verified              | shared `resolve_effective_profile`; profile-fidelity tests          |
| #297 | 0.49.10 | E6: version-bump CI guard + PR template + CHANGELOG decision + this report                     | (in flight)                                                         |

Phase 0, E1, E2, E3, E4, E5 are **merged and live** on `tm.iznogoudatall.xyz`.

## My own mistakes, recorded honestly (§10-5)

1. **The badge test lied.** My first unit test « proved » the E1 « En file » badge but mocked the
   queue step present immediately — it did not cover the first-poll race. Only the real prod run
   caught the actual bug (badge stuck on « Exécution démarrée »). Fixed with a red-on-old test that
   reproduces the race; the badge is now sticky on the 202 hint. **Lesson: a green unit test is not
   a live proof.**
2. **`lint:tokens` was a fake guard on CI.** ripgrep was absent from the runner, so `|| true`
   swallowed the exit-127 and the token guard silently passed without ever grepping. Fixed the
   script to fail loudly without `rg` and installed ripgrep in CI.
3. **The ruff hook keeps stripping imports added before their use** — hit twice (`import sys` in the
   event_bus test, model imports in maintenance routes). Re-add after the usage exists.
4. **A branch-hygiene slip**: committed E2a onto the already-merged E1b branch, then cherry-picked
   onto a fresh branch from main. No harm, caught immediately.

## CI fragilities encountered (candidates for hardening)

- `test_hash_determinism` Hypothesis deadline flake (fixed: `deadline=None`).
- `lint:tokens` no-op (fixed).
- `test_emit_no_subscribers_zero_allocation` — deterministic non-zero under coverage's C tracer
  (fixed: skip the strict count when a line tracer is active). Blocked a purely-ingest PR.
- Adding migration 015 required updating **6 test files** hardcoding schema version 14→15.

## Open items surfaced for operator arbitrage (§méthode-4 — not dropped)

- **E3**: a dedicated UI panel for the destructive-op journal (the table + `GET
/api/maintenance/destructive-log` are in place and queryable; a panel is a follow-up).
- **E5-A**: dispatch-time movie auto-unfollow — `mark_done_by_hash` closes the wanted row but does
  not unfollow; the film stays followed until the next detect cron (< 24 h, ownership-based).
- **E5-B**: the movie card status still keys off the raw `grabbed` counter, not ownership (the
  series card already uses `truth.py`/ownership).
- Assumed-open (operator-owned, not to « fix » unprompted): Top Chef Le Concours Parallèle
  (empty provider catalog), Obsession index residue, decision id 57, 2160p-vs-1080p ranking.

## Remaining mission work

- **E7** — final DOIT/NE-DOIT-PAS screen×rule sweep, table recorded.
- **Runtime truths** — prove in prod: « Le Robot sauvage » physically in the library (grabbed→done),
  House of the Dragon root cause + real recovery, Silo « à jour » / American Dad cleaned, §2
  « Posters récupérés » live, sans-trailer filter clicked, resolve queue on a real unmatched item.
- **Final honest report** (this file is its seed).
