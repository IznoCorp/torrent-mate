# Phase 37 — Trust-audit fixes (the 14 verified defects)

**Source of truth:** the trust-audit JSON at
`/private/tmp/claude-501/-Users-izno-dev-KanbanMate/55eac608-91ab-46b8-9c7a-ea73bfc8db9f/tasks/wkilrz8yk.output`
— every defect there is VERIFIED with file:line evidence + a fix + a live test. Implement ALL of
them (2 critical, 5 major, 6 medium, the 7-item minor cluster opportunistically), one commit per
defect (pair trivially-related ones). The operator's standing rule: "rien ne doit être laissé
derrière". Fix shapes (binding, from the audit):

1. (crit) Gate scripts: ship `check-pr-ready.sh`/`check-merge-ready.sh` as kanbanmate package data
   AND resolve relative `script:` entries against the package root (PoC `_SKILL_ROOT` parity);
   `kanban init` may additionally copy them into `<clone>/bin/` idempotently.
2. (crit) `GithubClient.move_card` resolves name-then-key (mirror `bin/kanban_move.py:225`); ALL
   baselines store display NAMES (script_route on_fail/advance targets, RollbackAction,
   transition_step baseline) so a rollback fires ONCE, never loops.
3. (maj) `{{code}}` fills `str(issue)` (bare int) in `_launch_context` AND all 5 helpers strip a
   leading `#` defensively.
4. (maj) Reaper relaunch: persist title+body on TicketState (the drain queue payload already
   proves the shape) so a relaunched agent doesn't DESYNC on an empty body.
5. (maj) A `reap` teardown flavour: kill session + purge state + move Blocked ONLY — no worktree
   removal, no branch delete, no PR close (PoC parity).
6. (maj) PAUSE: thread kill_switch into `_drain_queue` + `_try_relaunch` — no launches under PAUSE
   (queue markers + bookkeeping intact).
7. (maj) Anti-double-session guard: in the LAUNCH path, if store state is LIVE at a DIFFERENT
   stage AND `sessions.is_alive(ticket-<n>)` → bounce/refuse, never kill the live agent.
8. (med) Forward ✅ finalize: keep it working when session-end already purged state (PoC kept an
   idle record; either re-derive the left stage or finalize from the transition itself).
9. (med) `check-pr-ready.sh`: zero-CI-checks policy (treat as green with a recap note) + export
   the token from `~/.kanban/token` into the script env.
10. (med) `run_check_script` with a gone worktree → recreate or fail to on_fail (never strand).
11. (med) config.yml override path: thread `config_dir` (worktree skill provisioning).
12. (med) `kanban-update-main` reads the registry `dev_repo_path` (three docstrings already claim it).
13. (med) launch watchdog: don't release the slot while the abandoned launch thread may still
    create the session (align with the phase-34 timeout registry).
14. (min) The 7-item minor cluster from the audit — opportunistic.

Gate per commit: `rm -rf .mypy_cache && make check` fully green. Conventional Commits; explicit
paths; NEVER touch ROADMAP.md / docs/superpowers/roadmap/ / this plan (except the tracker row in
the final chore commit). After landing: orchestrator deploys + runs the audit's 14-step live test
plan with the operator.
