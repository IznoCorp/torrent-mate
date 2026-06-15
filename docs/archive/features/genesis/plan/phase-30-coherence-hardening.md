# Phase 30 — Coherence hardening (audit-driven, S-cost batch)

**Source of truth:** the full coherence-audit JSON (5 lenses + synthesis + 2 adversarial verdicts)
at `/private/tmp/claude-501/-Users-izno-dev-KanbanMate/55eac608-91ab-46b8-9c7a-ea73bfc8db9f/tasks/wpjhhjbe2.output`
— READ IT before implementing; every item below MUST apply the verdict corrections recorded there.
Operator approved: audit ranks #1-10 + #13 (recovery edges), grouped here. Ranks #11-12 (M) = phase 31.

## Items (one commit each unless trivially paired; gate each with `rm -rf .mypy_cache && make check`)

1. **Persistent-failure visibility** — `fetch_token_scopes` raises on 401/403 (doctor token check FAILs
   instead of PASSing); daemon heartbeat becomes JSON `{ts, last_tick_ok, consecutive_failures}` with
   BACKWARD-COMPAT parsing (plain-epoch fallback); doctor FAILs on consecutive_failures ≥ 3 and derives
   its TTL as `max(120, 2*idle_max)`; add a board-reachable (authenticated cheap_probe) doctor check;
   actionable 401/403 log line ("token invalid — check ~/.kanban/token") + DEGRADED surfaced.
2. **Transport + loop backoff** — `_transport`: treat 429/500/503/504 as transient, honor Retry-After
   with a small per-request budget (≤ ~15-20s, well under action_timeout); `run_loop`: after ~3
   consecutive tick failures escalate sleep geometrically (cap ~300s), SNAP BACK to the 10s cadence on
   first success (failure-mode-only backoff — the fixed cadence stays the normal regime).
3. **Dashboard true on-change** — bucket the rendered heartbeat age (minutes) so the body hash is
   stable; gate/TTL-cache the per-agent progress (`list_issue_comments`) reads instead of per-tick
   before the hash check; body-diff guard in `upsert_stage_comment` so identical ⏳ re-upserts skip the
   PATCH. (~1400 wasted API calls/h today.)
4. **LIVE status set** — `LIVE = {RUNNING, WAITING}` constant; use it in the drain's already-running
   guard (drain.py:98 is RUNNING-only — a re-dispatch KILLS a WAITING agent's session via the
   idempotent launch pre-kill), a NEW pre-launch already-live guard in the tick, and as a refactor in
   done_arrival/list_running (already correct). Wrap each tick transition iteration in try/except
   (log, errors+=1, advance baseline, continue) so a mid-loop raise never replays a launch.
5. **transitions.yml defaults authoritative** — `build_tick_config` prefers the TransitionConfig
   cap/rate when transitions_yaml is present; demote the columns.yml defaults block to an
   explicitly-commented fallback (or stop rendering it) so ONE surface is authoritative; align the
   loader default (2) with the template (3).
6. **Doc truths + gate process** — CLAUDE.md:84-86: `safe/trusted` → the 4 profiles, PAUSE floor =
   `docs`; DESIGN: fix the §9 vs teardown-on-Done contradiction + add the phase-29 "agent discipline"
   subsection (the deferred 29.5 doc: scope guard, identity-then-state, Blocked-not-Cancel, binding
   chain); add one line to the CLAUDE.md phase-gate checklist: "tracker row updated + DESIGN delta
   present". (The comprehensive DESIGN re-sync stays deferred per the operator's docs-pause.)
7. **Real never-hang watchdog** — executor shutdown(wait=False, cancel_futures=True) in try/finally
   with each abandoned worker LOGGED (daemonized thread factory); timeout= on every git invocation in
   the worktree adapter (the bare `git fetch origin <base>` has none); run the tick pre-create under
   the watchdog.
8. **Observable logs** — JSONLHandler: `exc` field when exc_info is set + rendered by `kanban logs`;
   ~10MB size rotation; route the fs_store stderr breadcrumb through a module logger.
9. **Done-arrival reclaims worktrees** — key the teardown on `deps.workspace.worktree_exists(issue)`
   (NOT persisted-state existence — the dominant orphan is a worktree with no state); add a cheap
   unpushed-commits check that downgrades to Blocked + sticky instead of silent destruction; loud log;
   update the DESIGN acceptance note (it currently blesses leaving worktrees).
10. **Prompt-delivery observability** — logger.warning with the captured pane tail on `_poll_pane`
    timeout; post-send verification as WARN-ONLY (+ sticky note), hard-fail ONLY on unambiguous
    evidence (prompt text visibly sitting untyped) — never kill a good launch on a heuristic.
11. **Corrupt-state quarantine** — on load() parse failure move the poison file to `state/corrupt/`
    (evidence preserved, no re-parse noise); add a doctor check "slot file without a matching state
    file" (NO auto-release).
12. **Recovery edges** — DEFAULT_TRANSITIONS: `Review→InProgress` (rework prompt mirroring the fix-CI
    pattern, profile dev, advance auto:PRCI, hardened-prompt constants applied), `Planned→Spec` (no-op),
    `Done→Backlog` (plain no-op whitelist edge — NOT a RESET; residual state is rare post-teardown-on-
    Done). Tests assert the three edges + that nothing else changed.

## Constraints

Hexagonal layering; urllib timeouts; no shell=True; Google docstrings; LOC hard ceiling 1000
(actions.py AT 1000, tick.py 991 — extract rather than grow; the audit's deferred module splits may be
pulled in IF a ceiling forces it); Conventional Commits, NO AI attribution; NEVER touch
helm prep (docs/superpowers/roadmap/), ROADMAP.md, IMPLEMENTATION.md, or plan files; stage by explicit
path only. Final: full `make check` green.
