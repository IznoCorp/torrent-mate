# Phase 38 — Worktree helper PATH (pyenv-proof)

**Finding (live e2e):** orchestrated agents launch in a tmux session that inherits the shell
environment where `pyenv global` may be a DIFFERENT python than the one running the daemon. pyenv
shims dispatch per ACTIVE version, so a kanban-\* console script installed under the engine's
interpreter but ABSENT from the agent's pyenv-global install exits 127 ("command not found") — the
observed `kanban-update-body` case (entry point added in phase 29, missing from a stale 3.11.9
editable install). The other helpers worked only by luck of an older editable install whose entry
points predate phase 29.

**Fix (surgical — does NOT touch the target project's python):** provision a dedicated helper dir
into each worktree and prepend it to the agent's PATH.
(1) `adapters/perms.provision_worktree_bin(worktree)` creates `<worktree>/.claude/kanban-bin/`
holding SYMLINKS to the RESOLVED ABSOLUTE console scripts of THE ENGINE'S OWN interpreter (resolved
via the shared `_resolve_console_bin` — `shutil.which` then the `sys.executable` scripts dir, the
same order `_resolve_heartbeat_bin` uses). The seven agent helpers are linked (`kanban-move`,
`kanban-comment`, `kanban-progress`, `kanban-update-body`, `kanban-session-end`, `kanban-heartbeat`,
`kanban-update-main`); an unresolved helper is SKIPPED with a logged warning (fail-soft); each launch
REFRESHES the symlinks (idempotent). The dir holds ONLY kanban-\* symlinks → zero impact on the
project's own python/pip. (2) `app/actions.LaunchAction._agent_command` prefixes the composed command
with `export PATH=<quoted kanban-bin>:"$PATH"; ` so both `claude` AND the trailing
`; kanban-session-end <issue>` resolve from the engine's interpreter (`$PATH` stays unquoted so it
expands in the agent's shell; the dir is shlex-quoted). Core stays pure — the PATH prefix is composed
in the app layer beside the I/O. (3) `cli/doctor` gains an advisory `pyenv twin` check
(`_check_pyenv_global_twin`): when `~/.pyenv/version` (fail-soft read) differs in MAJOR.MINOR from the
engine interpreter, it emits a WARNING noting agents inherit that pyenv-global but helpers are
provisioned via the worktree kanban-bin — never blocking (always `ok=True`).

**Tests:** provisioning symlinks all helpers / skips an unresolved one with a warning (no raise) /
idempotently refreshes a stale target; the launched command starts with the PATH export naming the
worktree kanban-bin; the doctor pyenv-twin check warns on a minor mismatch, passes on a same-minor
patch drift, passes silently when pyenv is absent, and stays advisory inside `run_doctor`.

**Gate:** `rm -rf .mypy_cache && make check` green (1439 passed, 8 skipped; only soft-LOC warnings).
